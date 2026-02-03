from fastapi import FastAPI, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import os
import random
import asyncio
import json
import logging
import sys
import uuid
from typing import List, Dict, Any

# Import existing pipeline modules
try:
    from .universe import extract_universe
    from .downloader import download_song
    from .tagger import tag_mp3
    from .vectorizer import vectorize_audio
    from .storage import upload_to_r2, store_vector_db
except ImportError:
    pass

app = FastAPI(title="Last.fm Music Vectorizer")

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "../static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../templates"))

# --- Coordinator System ---
class Coordinator:
    def __init__(self):
        # Sessions map: code -> { 'ui': ws, 'worker': ws, 'queue': [], 'username': str }
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
    def create_session(self, code: str):
        if code not in self.sessions:
            self.sessions[code] = {
                'ui': None,
                'worker': None,
                'queue': [],
                'username': None,
                'active_job': None
            }
            
    async def connect_ui(self, code: str, ws: WebSocket):
        await ws.accept()
        self.create_session(code)
        self.sessions[code]['ui'] = ws
        await self.send_ui(code, "Waiting for Worker connection...", "info")
        
    async def connect_worker(self, code: str, ws: WebSocket):
        await ws.accept()
        self.create_session(code)
        self.sessions[code]['worker'] = ws
        await self.send_ui(code, "Worker Connected!", "success")
        
        # Check if queue has items and start processing
        if self.sessions[code]['queue']:
             await self.dispatch_next_job(code)
        
    def disconnect(self, code: str, client_type: str):
        if code in self.sessions:
            self.sessions[code][client_type] = None
            if self.sessions[code]['ui'] is None and self.sessions[code]['worker'] is None:
                del self.sessions[code]
            elif client_type == 'worker':
                 asyncio.create_task(self.send_ui(code, "Worker Disconnected", "error"))

    async def send_ui(self, code: str, msg: str, level: str = "normal"):
        session = self.sessions.get(code)
        if session and session['ui']:
            try:
                await session['ui'].send_json({
                    "type": "log",
                    "message": msg,
                    "level": level
                })
            except:
                self.sessions[code]['ui'] = None

    async def start_job(self, code: str, username: str):
        session = self.sessions.get(code)
        if not session: return
        
        session['username'] = username
        await self.send_ui(code, f"Fetching Last.fm data for {username}...", "info")
        
        # Run fetch in thread
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from populate_youtube_universe import ensure_schema, fetch_universe, get_existing_tracks
        
        try:
            # 1. Schema
            table_name = await asyncio.to_thread(ensure_schema, username)
            session['table_name'] = table_name
            
            # 2. Fetch
            universe_tracks = await asyncio.to_thread(fetch_universe, username)
            existing_tracks = await asyncio.to_thread(get_existing_tracks, table_name)
            
            targets = [t for t in universe_tracks if t not in existing_tracks]
            await self.send_ui(code, f"Found {len(targets)} new tracks to process.", "info")
            
            session['queue'] = targets
            
            if not session['worker']:
                await self.send_ui(code, "Waiting for worker to start processing...", "warning")
            else:
                await self.dispatch_next_job(code)
                
        except Exception as e:
            await self.send_ui(code, f"Error: {str(e)}", "error")

    async def dispatch_next_job(self, code: str):
        session = self.sessions.get(code)
        if not session or not session['worker'] or not session['queue']:
            if session and not session['queue']:
                 await self.send_ui(code, "All tracks processed!", "success")
            return

        artist, title = session['queue'].pop(0)
        job_id = str(uuid.uuid4())
        
        session['active_job'] = {
            'id': job_id,
            'artist': artist,
            'title': title
        }
        
        await self.send_ui(code, f"Dispatching: {artist} - {title}", "normal")
        
        try:
            await session['worker'].send_json({
                "type": "job",
                "job_id": job_id,
                "payload": {
                    "artist": artist,
                    "title": title
                }
            })
        except:
            # Worker died, put back in queue?
            session['queue'].insert(0, (artist, title))
            await self.send_ui(code, "Worker connection lost during dispatch", "error")

    async def handle_worker_result(self, code: str, data: dict):
        session = self.sessions.get(code)
        if not session: return
        
        status = data.get('status')
        if status == 'success':
            result = data.get('data', {})
            artist = result.get('artist')
            title = result.get('title')
            youtube_id = result.get('youtube_id')
            vector = result.get('vector')
            
            # Store to DB
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from populate_youtube_universe import store_entry
            
            saved = await asyncio.to_thread(
                store_entry, 
                session.get('table_name'), 
                artist, 
                title, 
                youtube_id, 
                vector
            )
            
            if saved:
                await self.send_ui(code, f"Saved: {artist} - {title}", "success")
            else:
                await self.send_ui(code, f"DB Error: {artist} - {title}", "error")
        else:
            await self.send_ui(code, f"Worker Failed: {data.get('error')}", "error")
            
        # Next
        await self.dispatch_next_job(code)

coordinator = Coordinator()

# --- Routes ---

@app.get("/ingest", response_class=HTMLResponse)
async def ingest_page(request: Request):
    return templates.TemplateResponse("youtube_ingest.html", {"request": request})

@app.websocket("/ws/remote/{code}/{client_type}")
async def remote_endpoint(websocket: WebSocket, code: str, client_type: str):
    if client_type == 'ui':
        await coordinator.connect_ui(code, websocket)
    elif client_type == 'worker':
        await coordinator.connect_worker(code, websocket)
    
    try:
        while True:
            data_str = await websocket.receive_text()
            data = json.loads(data_str)
            
            if client_type == 'ui':
                if data.get('type') == 'start':
                    await coordinator.start_job(code, data.get('username'))
            
            elif client_type == 'worker':
                if data.get('type') == 'result':
                    await coordinator.handle_worker_result(code, data)
                    
    except WebSocketDisconnect:
        coordinator.disconnect(code, client_type)

# Legacy Endpoint for single ingest
@app.post("/api/ingest/single")
async def ingest_single(data: dict): 
    # Placeholder to keep code valid if imported
    pass

if __name__ == "__main__":
    uvicorn.run("music_pipeline.web_app:app", host="0.0.0.0", port=8001, reload=True)
