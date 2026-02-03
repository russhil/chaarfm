import os
import urllib.parse
from fastapi import FastAPI, HTTPException, Request, Body, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List
import json

from recommender import RecommenderSession
from music_pipeline.web_app import coordinator

# Configuration
DEFAULT_MUSIC_DIR = "/Users/russhil/Desktop/aand pav/songs-downloaded"

app = FastAPI(title="chaar.fm", description="Personalized Music Stream")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global Session
session = RecommenderSession()

# Helper
def get_file_path(filename):
    """Securely resolves file path."""
    # Basic check against directory traversal
    name = os.path.basename(filename)
    path = os.path.join(DEFAULT_MUSIC_DIR, name)
    if os.path.exists(path):
        return path
    
    # Check current directory for fallback
    local_path = os.path.join(os.getcwd(), name)
    if os.path.exists(local_path):
        return local_path
        
    return None

# Models
class FeedbackRequest(BaseModel):
    id: str
    duration: float
    liked: bool = False
    disliked: bool = False
    finished: bool = False

class SelectRequest(BaseModel):
    id: str

# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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

@app.get("/youtube-mode", response_class=HTMLResponse)
async def youtube_mode_page(request: Request):
    return templates.TemplateResponse("youtube_mode.html", {"request": request})

@app.get("/api/next")
async def next_track(mode: Optional[str] = "mp3"):
    youtube_mode = (mode == "youtube")
    track = session.get_next_track(youtube_mode=youtube_mode)
    
    if track:
        # URL Encode filename for the stream URL
        encoded_name = urllib.parse.quote(track['filename'])
        return {
            "id": track['id'],
            "title": track['filename'],
            "url": f"/stream/{encoded_name}" if track.get('s3_url') else None,
            "filename": track['filename'],
            "youtube_id": track.get('youtube_id')
        }
    return JSONResponse(content={"error": "No recommendations available"}, status_code=404)

@app.post("/api/feedback")
async def feedback(data: FeedbackRequest):
    session.feedback(
        track_id=data.id, 
        duration=data.duration, 
        liked=data.liked, 
        disliked=data.disliked,
        finished=data.finished
    )
    return {"status": "ok"}

@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    query = q.lower()
    results = []
    
    # Use cluster manager map if available
    if session.cluster_manager.initialized:
        seen_filenames = set()
        for tid, info in session.cluster_manager.track_map.items():
            fname_lower = info['filename'].lower()
            if query in fname_lower:
                if fname_lower in seen_filenames: continue
                seen_filenames.add(fname_lower)
                
                results.append({
                    "id": tid,
                    "title": info['filename']
                })
                if len(results) > 20: break
    
    return results

@app.post("/api/select")
async def select_track(data: SelectRequest):
    track_info = session.set_seed(data.id)
    if track_info:
        encoded_name = urllib.parse.quote(track_info['filename'])
        return {
            "id": track_info['id'],
            "title": track_info['filename'],
            "url": f"/stream/{encoded_name}",
            "youtube_id": track_info.get('youtube_id')
        }
    raise HTTPException(status_code=404, detail="Track not found")

@app.get("/api/library")
async def library():
    if session.cluster_manager.initialized:
        tracks = []
        for tid, info in session.cluster_manager.track_map.items():
             encoded_name = urllib.parse.quote(info['filename'])
             tracks.append({
                 "id": tid,
                 "title": info['filename'],
                 "url": f"/stream/{encoded_name}",
                 "youtube_id": info.get("youtube_id")
             })
        return tracks
    return []

@app.get("/stream/{filename}")
async def stream(filename: str):
    # Decode? FastAPI might pass raw, but usually decoded. 
    # urllib.parse.unquote is safe to double-call usually if no %
    decoded_name = urllib.parse.unquote(filename)
    real_path = get_file_path(decoded_name)
    
    if real_path and os.path.exists(real_path):
        return FileResponse(real_path, media_type="audio/mpeg", filename=decoded_name)
    
    raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    # Use 0.0.0.0 for mobile access
    uvicorn.run(app, host="0.0.0.0", port=5001)
