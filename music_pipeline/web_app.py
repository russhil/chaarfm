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
                'active_job': None,
                'table_name': None,
                'mode': 'lastfm',
                'paused': False,
                'assigned': set(),
                'stop_requested': False
            }
            
    async def send_state(self, code: str, status: str, message: str = None, level: str = "info"):
        session = self.sessions.get(code)
        if session and session['ui']:
            try:
                await session['ui'].send_json({
                    "type": "state",
                    "status": status,
                    "message": message,
                    "level": level
                })
            except:
                session['ui'] = None

    def _job_key(self, job: Dict[str, Any]) -> str:
        youtube_url = job.get('youtube_url')
        if youtube_url:
            return youtube_url
        artist = (job.get('artist') or '').strip().lower()
        title = (job.get('title') or '').strip().lower()
        return f"{artist}::{title}"

    def _reset_session_state(self, session: Dict[str, Any]):
        session['queue'] = []
        session['active_job'] = None
        session['assigned'] = set()
        session['paused'] = False
        session['stop_requested'] = False
            
    async def connect_ui(self, code: str, ws: WebSocket):
        await ws.accept()
        self.create_session(code)
        self.sessions[code]['ui'] = ws
        await self.send_ui(code, "Waiting for Worker connection...", "info")
        await self.send_state(code, "idle", "Waiting for Worker connection...", "info")
        
    async def connect_worker(self, code: str, ws: WebSocket):
        await ws.accept()
        self.create_session(code)
        self.sessions[code]['worker'] = ws
        await self.send_ui(code, "Worker Connected!", "success")
        await self.send_state(code, "running", "Worker connected", "success")
        
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
                 asyncio.create_task(self.send_state(code, "stopped", "Worker disconnected", "error"))

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

    async def start_job(self, code: str, payload: dict):
        session = self.sessions.get(code)
        if not session:
            return

        mode = (payload.get('mode') or 'lastfm').lower()
        username = (payload.get('username') or '').strip()
        youtube_url = (payload.get('youtubeUrl') or payload.get('youtube_url') or '').strip()
        requested_count = payload.get('requestedCount')
        use_max = bool(payload.get('useMax'))

        try:
            requested_count = int(requested_count) if requested_count not in (None, "", "null") else None
        except (TypeError, ValueError):
            requested_count = None

        if requested_count is not None and requested_count < 1:
            requested_count = 1

        if session.get('active_job'):
            await self.send_ui(code, "Active ingestion in progress. Stop or wait before starting another run.", "warning")
            await self.send_state(code, "paused", "Active ingestion in progress", "warning")
            return

        self._reset_session_state(session)
        session['mode'] = mode
        session['username'] = username

        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from populate_youtube_universe import (
            ensure_schema,
            fetch_universe,
            get_existing_tracks,
            prepare_random_track_batch,
            ensure_test_collection
        )

        try:
            if mode == 'lastfm':
                if not username:
                    await self.send_ui(code, "Last.fm username required.", "error")
                    await self.send_state(code, "stopped", "Missing Last.fm username", "error")
                    return

                await self.send_ui(code, f"Fetching Last.fm data for {username}...", "info")

                table_name = await asyncio.to_thread(ensure_schema, username)
                session['table_name'] = table_name

                universe_tracks = await asyncio.to_thread(fetch_universe, username)
                await self.send_ui(code, f"Universe contains {len(universe_tracks)} tracks.", "info")

                existing_tracks = await asyncio.to_thread(get_existing_tracks, table_name)
                available_tracks = [t for t in universe_tracks if t not in existing_tracks]
                await self.send_ui(code, f"{len(available_tracks)} tracks are new.", "info")

                if not available_tracks:
                    await self.send_state(code, "complete", "No new tracks to process.", "warning")
                    return

                selected_tracks = prepare_random_track_batch(available_tracks, requested_count, use_max)
                session['queue'] = [
                    {
                        "artist": artist,
                        "title": title,
                        "table_name": table_name,
                        "youtube_url": None
                    }
                    for artist, title in selected_tracks
                ]

                await self.send_ui(code, f"Queued {len(session['queue'])} random tracks.", "success")
                await self.send_state(code, "running", f"Queued {len(session['queue'])} tracks", "info")

            elif mode == 'single':
                if not youtube_url:
                    await self.send_ui(code, "YouTube URL required for single ingest.", "error")
                    await self.send_state(code, "stopped", "Missing YouTube URL", "error")
                    return

                table_name = await asyncio.to_thread(ensure_test_collection)
                session['table_name'] = table_name
                session['queue'] = [{
                    "artist": None,
                    "title": None,
                    "table_name": table_name,
                    "youtube_url": youtube_url.strip()
                }]

                await self.send_ui(code, "Queued single YouTube test ingest.", "info")
                await self.send_state(code, "running", "Queued 1 test track", "info")
            else:
                await self.send_ui(code, f"Unknown ingest mode: {mode}", "error")
                await self.send_state(code, "stopped", "Unknown ingest mode", "error")
                return

            if not session['worker']:
                await self.send_ui(code, "Waiting for worker to start processing...", "warning")
            else:
                await self.dispatch_next_job(code)

        except Exception as e:
            await self.send_ui(code, f"Error: {str(e)}", "error")
            await self.send_state(code, "stopped", "Failed to start job", "error")

    async def dispatch_next_job(self, code: str):
        session = self.sessions.get(code)
        if not session:
            return

        if session.get('paused') or session.get('stop_requested'):
            return

        if not session.get('worker'):
            await self.send_ui(code, "Waiting for worker connection...", "warning")
            return

        while session['queue']:
            job = session['queue'].pop(0)
            if isinstance(job, tuple):
                job = {
                    "artist": job[0],
                    "title": job[1],
                    "table_name": session.get('table_name'),
                    "youtube_url": None
                }
            key = self._job_key(job)
            if key in session['assigned']:
                continue

            session['assigned'].add(key)
            job_id = str(uuid.uuid4())
            session['active_job'] = {
                'id': job_id,
                'key': key,
                'table_name': job.get('table_name') or session.get('table_name'),
                'payload': job
            }

            label = job.get('youtube_url') or f"{job.get('artist', 'Unknown')} - {job.get('title', 'Untitled')}"
            await self.send_ui(code, f"Dispatching: {label}", "normal")
            await self.send_state(code, "running", f"Dispatching {label}", "info")

            try:
                await session['worker'].send_json({
                    "type": "job",
                    "job_id": job_id,
                    "payload": job
                })
            except:
                session['queue'].insert(0, job)
                session['assigned'].discard(key)
                session['active_job'] = None
                await self.send_ui(code, "Worker connection lost during dispatch", "error")
                await self.send_state(code, "stopped", "Worker disconnected", "error")
                return
            else:
                return

        session['active_job'] = None
        if not session.get('stop_requested'):
            await self.send_ui(code, "All tracks processed!", "success")
            await self.send_state(code, "complete", "All tracks processed!", "success")

    async def handle_worker_result(self, code: str, data: dict):
        session = self.sessions.get(code)
        if not session:
            return

        job_context = session.get('active_job')
        if job_context:
            session['assigned'].discard(job_context.get('key'))

        status = data.get('status')
        if status == 'success':
            result = data.get('data', {})
            artist = result.get('artist')
            title = result.get('title')
            youtube_id = result.get('youtube_id')
            vector = result.get('vector')

            if not vector:
                await self.send_ui(code, f"Vector missing for {artist} - {title}", "error")
            else:
                import sys
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from populate_youtube_universe import store_entry

                table_name = (job_context or {}).get('table_name') or session.get('table_name')
                saved = await asyncio.to_thread(
                    store_entry,
                    table_name,
                    artist,
                    title,
                    youtube_id,
                    vector
                )

                if saved:
                    await self.send_ui(code, f"Saved: {artist} - {title}", "success")
                    await self.send_state(code, "running", f"Saved {artist} - {title}", "success")
                else:
                    await self.send_ui(code, f"DB Error: {artist} - {title}", "error")
        else:
            await self.send_ui(code, f"Worker Failed: {data.get('error')}", "error")

        session['active_job'] = None
        await self.dispatch_next_job(code)

    async def set_pause(self, code: str, paused: bool):
        session = self.sessions.get(code)
        if not session:
            return
        if session.get('paused') == paused:
            return

        session['paused'] = paused
        if paused:
            await self.send_ui(code, "Processing paused.", "warning")
            await self.send_state(code, "paused", "Processing paused", "warning")
        else:
            await self.send_ui(code, "Processing resumed.", "info")
            await self.send_state(code, "running", "Processing resumed", "info")
            await self.dispatch_next_job(code)

    async def stop_session(self, code: str):
        session = self.sessions.get(code)
        if not session:
            return
        session['queue'] = []
        session['paused'] = False
        session['stop_requested'] = True
        await self.send_ui(code, "Stop requested. Current job will finish, new jobs halted.", "warning")
        await self.send_state(code, "stopped", "Stop requested", "warning")

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
                msg_type = data.get('type')
                if msg_type == 'start':
                    await coordinator.start_job(code, data)
                elif msg_type == 'pause':
                    await coordinator.set_pause(code, True)
                elif msg_type == 'resume':
                    await coordinator.set_pause(code, False)
                elif msg_type == 'stop':
                    await coordinator.stop_session(code)
            
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
