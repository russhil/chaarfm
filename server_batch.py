"""
Server with Batch Preloading - Uses Original UI

This server:
1. Uses averaged vectors (1 per song)
2. Preloads 5 songs internally
3. Serves them one at a time via /api/next
4. Uses the ORIGINAL frontend UI
"""

import os
import urllib.parse
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List

from batch_recommender import BatchRecommender

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
recommender = BatchRecommender()
preloaded_queue = []  # Internal queue of preloaded tracks

# Helper
def get_file_path(filename):
    """Securely resolves file path."""
    name = os.path.basename(filename)
    path = os.path.join(DEFAULT_MUSIC_DIR, name)
    if os.path.exists(path):
        return path
    
    local_path = os.path.join(os.getcwd(), name)
    if os.path.exists(local_path):
        return local_path
    
    return None

def ensure_queue():
    """Ensure we have tracks in the queue."""
    global preloaded_queue
    
    if len(preloaded_queue) == 0:
        # Get next batch
        batch = recommender.get_next_batch()
        preloaded_queue = batch.copy()
        print(f"Preloaded {len(preloaded_queue)} tracks into queue")

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
    # Use ORIGINAL frontend
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/next")
async def next_track():
    """Get next track from preloaded queue."""
    global preloaded_queue
    
    ensure_queue()
    
    if preloaded_queue:
        track = preloaded_queue.pop(0)
        encoded_name = urllib.parse.quote(track['filename'])
        
        remaining = len(preloaded_queue)
        print(f"Serving: {track['filename']} (Queue remaining: {remaining})")
        
        return {
            "id": track['id'],
            "title": track['filename'],
            "url": f"/stream/{encoded_name}",
            "filename": track['filename'],
            "queue_remaining": remaining,
            "batch_size": 5
        }
    
    return JSONResponse(content={"error": "No tracks available"}, status_code=404)

@app.post("/api/feedback")
async def feedback(data: FeedbackRequest):
    """Record feedback based on duration only."""
    global preloaded_queue
    
    # Just pass duration - the recommender handles signal calculation
    recommender.record_feedback(
        track_id=data.id,
        duration=data.duration
    )
    
    # If queue is empty after this, finalize batch and load next
    if len(preloaded_queue) == 0:
        print("Queue empty - finalizing batch and loading next")
        recommender.finalize_batch()
        ensure_queue()
    
    return {"status": "ok"}

@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    """Search for tracks by name."""
    results = recommender.search(q)
    return [{"id": r["id"], "title": r["filename"]} for r in results]

@app.post("/api/select")
async def select_track(data: SelectRequest):
    """Select a specific track as seed."""
    global preloaded_queue
    
    track = recommender.set_seed(data.id)
    if track:
        # Clear queue and reload based on new seed
        preloaded_queue = []
        recommender.finalize_batch()
        ensure_queue()
        
        encoded_name = urllib.parse.quote(track['filename'])
        return {
            "id": track['id'],
            "title": track['filename'],
            "url": f"/stream/{encoded_name}"
        }
    raise HTTPException(status_code=404, detail="Track not found")

@app.get("/api/library")
async def library():
    """Get all tracks in library."""
    tracks = []
    for tid, info in recommender.track_map.items():
        encoded_name = urllib.parse.quote(info['filename'])
        tracks.append({
            "id": tid,
            "title": info['filename'],
            "url": f"/stream/{encoded_name}"
        })
    return tracks

@app.post("/api/reset")
async def reset_session():
    """Reset all session memory and start fresh."""
    global preloaded_queue, recommender
    
    print("\n" + "🔄" * 30)
    print("SESSION RESET - Starting fresh!")
    print("🔄" * 30 + "\n")
    
    # Reinitialize recommender
    from batch_recommender import BatchRecommender
    recommender = BatchRecommender()
    preloaded_queue = []
    
    # Load first batch
    ensure_queue()
    
    return {"status": "reset", "message": "Session reset to PROBE phase"}

@app.get("/stream/{filename}")
async def stream(filename: str):
    """Stream an audio file."""
    decoded_name = urllib.parse.unquote(filename)
    real_path = get_file_path(decoded_name)
    
    if real_path and os.path.exists(real_path):
        return FileResponse(real_path, media_type="audio/mpeg", filename=decoded_name)
    
    raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
