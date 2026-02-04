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
        # Sessions map: code -> { 'ui': ws, 'workers': [ws1, ws2, ...], 'queue': [], 'username': str }
        # 'active_jobs': {worker_id: job_context} - tracks which worker is handling which job
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
    def create_session(self, code: str):
        if code not in self.sessions:
            self.sessions[code] = {
                'ui': None,
                'workers': [],  # List of worker WebSocket connections
                'worker_ids': {},  # Map ws_id -> worker_id for tracking
                'worker_ws_map': {},  # Map worker_id -> ws for reverse lookup
                'queue': [],
                'username': None,
                'active_jobs': {},  # Map worker_id -> job_context
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
                # Include worker count in state message for UI detection
                worker_count = len(session.get('workers', []))
                state_message = message or ""
                if worker_count > 0 and "worker" not in (state_message or "").lower():
                    state_message = f"{worker_count} worker(s) connected. {state_message}".strip()
                
                await session['ui'].send_json({
                    "type": "state",
                    "status": status,
                    "message": state_message,
                    "level": level,
                    "worker_count": worker_count  # Add explicit worker count
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
        session['active_jobs'] = {}
        session['assigned'] = set()
        session['paused'] = False
        session['stop_requested'] = False
            
    async def connect_ui(self, code: str, ws: WebSocket):
        await ws.accept()
        self.create_session(code)
        self.sessions[code]['ui'] = ws
        worker_count = len(self.sessions[code].get('workers', []))
        if worker_count == 0:
            await self.send_ui(code, "Waiting for Worker connection...", "info")
            await self.send_state(code, "idle", "Waiting for Worker connection...", "info")
        else:
            await self.send_ui(code, f"{worker_count} worker(s) connected. Ready to process.", "success")
            await self.send_state(code, "idle", f"{worker_count} worker(s) connected", "success")
        
    async def connect_worker(self, code: str, ws: WebSocket):
        await ws.accept()
        self.create_session(code)
        session = self.sessions[code]
        
        # Generate unique worker ID and store WebSocket reference
        worker_id = str(uuid.uuid4())
        session['workers'].append(ws)
        session['worker_ids'][id(ws)] = worker_id
        # Store reverse mapping for cleanup
        if 'worker_ws_map' not in session:
            session['worker_ws_map'] = {}
        session['worker_ws_map'][worker_id] = ws
        
        worker_count = len(session['workers'])
        await self.send_ui(code, f"Worker #{worker_count} Connected! ({worker_count} total)", "success")
        await self.send_state(code, "idle", f"{worker_count} worker(s) connected. Start ingestion when ready.", "success")
        
        # Check if queue has items and start processing
        if session['queue']:
             await self.dispatch_next_job(code)
        
    def disconnect(self, code: str, client_type: str, ws: WebSocket = None):
        if code not in self.sessions:
            return
            
        session = self.sessions[code]
        
        if client_type == 'ui':
            session['ui'] = None
        elif client_type == 'worker' and ws is not None:
            # Find the worker by WebSocket ID
            ws_id = id(ws)
            worker_id = session.get('worker_ids', {}).get(ws_id)
            
            if worker_id:
                # Clean up active job if this worker had one
                if worker_id in session.get('active_jobs', {}):
                    job_context = session['active_jobs'][worker_id]
                    # Re-queue the job if it was in progress
                    if job_context:
                        key = job_context.get('key')
                        session['assigned'].discard(key)
                        # Re-add to front of queue
                        session['queue'].insert(0, job_context.get('payload'))
                    session['active_jobs'].pop(worker_id, None)
                
                # Remove from mappings
                session['worker_ids'].pop(ws_id, None)
                session.get('worker_ws_map', {}).pop(worker_id, None)
            
            # Remove from workers list
            worker_count_before = len(session['workers'])
            session['workers'] = [w for w in session['workers'] if w != ws]
            worker_count_after = len(session['workers'])
            
            if worker_count_after < worker_count_before:
                remaining = worker_count_after
                asyncio.create_task(self.send_ui(code, f"Worker Disconnected ({remaining} remaining)", "warning"))
                if remaining == 0:
                    asyncio.create_task(self.send_state(code, "stopped", "All workers disconnected", "error"))
                else:
                    asyncio.create_task(self.send_state(code, "running", f"{remaining} worker(s) active", "info"))
                    # Try to dispatch jobs to remaining workers
                    if session.get('queue'):
                        asyncio.create_task(self.dispatch_next_job(code))
        
        # Clean up session if no connections remain
        if session['ui'] is None and len(session.get('workers', [])) == 0:
            del self.sessions[code]

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
        genre = (payload.get('genre') or '').strip()
        requested_count = payload.get('requestedCount')
        use_max = bool(payload.get('useMax'))

        try:
            requested_count = int(requested_count) if requested_count not in (None, "", "null") else None
        except (TypeError, ValueError):
            requested_count = None

        if requested_count is not None and requested_count < 1:
            requested_count = 1

        if session.get('active_jobs'):
            active_count = len(session['active_jobs'])
            await self.send_ui(code, f"Active ingestion in progress ({active_count} job(s) running). Stop or wait before starting another run.", "warning")
            await self.send_state(code, "paused", f"Active ingestion in progress ({active_count} jobs)", "warning")
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
            ensure_test_collection,
            normalize_track_key
        )
        from genre_universe import (
            fetch_genre_universe,
            ensure_genre_schema,
            get_existing_for_genre,
            genre_to_slug
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

                existing_tracks_set, existing_youtube_ids = await asyncio.to_thread(get_existing_tracks, table_name)
                # Use normalized comparison
                from populate_youtube_universe import normalize_track_key
                available_tracks = [
                    t for t in universe_tracks 
                    if normalize_track_key(t[0], t[1]) not in existing_tracks_set
                ]
                await self.send_ui(code, f"Found {len(existing_tracks_set)} existing tracks. {len(available_tracks)} tracks are new.", "info")

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

            elif mode == 'genre':
                if not genre:
                    await self.send_ui(code, "Genre name required.", "error")
                    await self.send_state(code, "stopped", "Missing genre name", "error")
                    return

                await self.send_ui(code, f"Fetching tracks for genre: {genre}...", "info")

                # Compute slug and ensure schema
                genre_slug = genre_to_slug(genre)
                table_name = await asyncio.to_thread(ensure_genre_schema, genre_slug)
                session['table_name'] = table_name

                # Fetch universe with quality filtering
                universe_tracks = await asyncio.to_thread(
                    fetch_genre_universe,
                    genre,
                    requested_count if not use_max else None,
                    None  # Use default quality_config
                )
                await self.send_ui(code, f"Found {len(universe_tracks)} tracks after quality filtering.", "info")

                if not universe_tracks:
                    await self.send_state(code, "complete", "No tracks found for this genre.", "warning")
                    return

                # Filter out already-ingested tracks
                existing = await asyncio.to_thread(get_existing_for_genre, table_name)
                available_tracks = []
                for track in universe_tracks:
                    youtube_url = track.get('youtube_url')
                    if youtube_url:
                        youtube_id = youtube_url.split('watch?v=')[-1].split('&')[0]
                        if (youtube_id, None) not in existing:
                            available_tracks.append(track)
                    elif track.get('artist') and track.get('title'):
                        if (None, (track['artist'], track['title'])) not in existing:
                            available_tracks.append(track)

                await self.send_ui(code, f"{len(available_tracks)} tracks are new.", "info")

                if not available_tracks:
                    await self.send_state(code, "complete", "No new tracks to process.", "warning")
                    return

                # If use_max, use all available; otherwise limit to requested_count
                if not use_max and requested_count:
                    available_tracks = available_tracks[:requested_count]

                session['queue'] = [
                    {
                        "artist": track.get('artist'),
                        "title": track.get('title'),
                        "table_name": table_name,
                        "youtube_url": track.get('youtube_url')
                    }
                    for track in available_tracks
                ]

                await self.send_ui(code, f"Queued {len(session['queue'])} tracks for genre '{genre}'.", "success")
                await self.send_state(code, "running", f"Queued {len(session['queue'])} tracks", "info")

            else:
                await self.send_ui(code, f"Unknown ingest mode: {mode}", "error")
                await self.send_state(code, "stopped", "Unknown ingest mode", "error")
                return

            worker_count = len(session.get('workers', []))
            if worker_count == 0:
                await self.send_ui(code, "Waiting for worker(s) to start processing...", "warning")
            else:
                # Dispatch jobs to all available workers
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

        workers = [w for w in session.get('workers', []) if w is not None]
        if not workers:
            await self.send_ui(code, "Waiting for worker connection...", "warning")
            return

        # Find available workers (not currently processing a job)
        available_workers = []
        for ws in workers:
            worker_id = session['worker_ids'].get(id(ws))
            if worker_id and worker_id not in session.get('active_jobs', {}):
                available_workers.append((ws, worker_id))

        # If no workers are available, wait for one to finish
        if not available_workers:
            return

        # Dispatch jobs to all available workers until queue is empty or all workers are busy
        while session['queue'] and available_workers:
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
            
            # Get next available worker
            ws, worker_id = available_workers.pop(0)
            
            job_context = {
                'id': job_id,
                'key': key,
                'table_name': job.get('table_name') or session.get('table_name'),
                'payload': job,
                'worker_id': worker_id
            }
            session['active_jobs'][worker_id] = job_context

            label = job.get('youtube_url') or f"{job.get('artist', 'Unknown')} - {job.get('title', 'Untitled')}"
            await self.send_ui(code, f"Dispatching to Worker #{len(session['workers']) - len(available_workers)}: {label}", "normal")
            
            active_count = len(session['active_jobs'])
            queue_remaining = len(session['queue'])
            await self.send_state(code, "running", f"{active_count} active, {queue_remaining} queued", "info")

            try:
                await ws.send_json({
                    "type": "job",
                    "job_id": job_id,
                    "payload": job
                })
            except Exception as e:
                # Worker disconnected, clean up
                session['queue'].insert(0, job)
                session['assigned'].discard(key)
                session['active_jobs'].pop(worker_id, None)
                # Remove worker from list
                session['workers'] = [w for w in session['workers'] if w != ws]
                session['worker_ids'].pop(id(ws), None)
                await self.send_ui(code, f"Worker connection lost during dispatch: {e}", "error")
                # Continue with next worker if available
                continue

        # If queue is empty and no active jobs, we're done
        if not session['queue'] and not session.get('active_jobs'):
            if not session.get('stop_requested'):
                await self.send_ui(code, "All tracks processed!", "success")
                await self.send_state(code, "complete", "All tracks processed!", "success")

    async def handle_worker_result(self, code: str, data: dict):
        session = self.sessions.get(code)
        if not session:
            return

        job_id = data.get('job_id')
        if not job_id:
            await self.send_ui(code, "Result received without job_id", "error")
            return

        # Find the job context by job_id
        job_context = None
        worker_id = None
        for wid, ctx in session.get('active_jobs', {}).items():
            if ctx.get('id') == job_id:
                job_context = ctx
                worker_id = wid
                break

        if job_context:
            session['assigned'].discard(job_context.get('key'))
            # Remove from active jobs
            session['active_jobs'].pop(worker_id, None)
        else:
            await self.send_ui(code, f"Received result for unknown job_id: {job_id}", "warning")

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

                table_name = (job_context or {}).get('table_name') if job_context else session.get('table_name')
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
                    active_count = len(session.get('active_jobs', {}))
                    queue_remaining = len(session.get('queue', []))
                    await self.send_state(code, "running", f"{active_count} active, {queue_remaining} queued", "success")
                else:
                    await self.send_ui(code, f"DB Error: {artist} - {title}", "error")
        else:
            await self.send_ui(code, f"Worker Failed: {data.get('error')}", "error")

        # Dispatch next job(s) to available workers
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
        coordinator.disconnect(code, client_type, websocket)

# Legacy Endpoint for single ingest
@app.post("/api/ingest/single")
async def ingest_single(data: dict): 
    # Placeholder to keep code valid if imported
    pass

if __name__ == "__main__":
    uvicorn.run("music_pipeline.web_app:app", host="0.0.0.0", port=8001, reload=True)
