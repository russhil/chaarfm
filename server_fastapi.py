import os
import urllib.parse
from fastapi import FastAPI, HTTPException, Request, Body, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List

from recommender import RecommenderSession

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

@app.get("/api/next")
async def next_track():
    track = session.get_next_track()
    if track:
        # URL Encode filename for the stream URL
        encoded_name = urllib.parse.quote(track['filename'])
        return {
            "id": track['id'],
            "title": track['filename'],
            "url": f"/stream/{encoded_name}",
            "filename": track['filename']
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
            "url": f"/stream/{encoded_name}"
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
                 "url": f"/stream/{encoded_name}"
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
