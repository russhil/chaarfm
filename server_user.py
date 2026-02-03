"""
User-Aware Server - FastAPI with authentication and persistent profiles.

Philosophy: Every decision must be data-justified. No random unless zero data.
"""

from fastapi import FastAPI, Request, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import urllib.parse
import os
import uuid
import csv
import datetime
import requests
import json

from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth

# Initialize database
import user_db
user_db.init_db()

from user_recommender import UserRecommender

# Import Ingestion Coordinator
from music_pipeline.web_app import coordinator

INTERACTION_LOG_FILE = "user_interactions.csv"

def log_interaction(session_id, user_id, track_id, filename, action, duration=0, justification=None, details=None):
    """Log user interaction to Supabase (and CSV backup)."""
    # Primary: Supabase
    user_db.log_interaction_db(session_id, user_id, track_id, filename, action, duration, justification, details)
    
    # Secondary: CSV Backup (kept for safety)
    try:
        file_exists = os.path.exists(INTERACTION_LOG_FILE)
        
        with open(INTERACTION_LOG_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "session_id", "user_id", "track_id", "filename", "action", "duration", "justification", "details"])
            
            writer.writerow([
                datetime.datetime.now().isoformat(),
                session_id or "unknown",
                user_id,
                track_id,
                filename,
                action,
                duration,
                justification or "",
                details or ""
            ])
    except Exception as e:
        print(f"CSV Logging error: {e}")

app = FastAPI(title="chaar.fm")

# Session Middleware for Auth
# In production, set a strong SECRET_KEY in env
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "dev_secret_key"))

# OAuth Config
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

@app.on_event("startup")
async def startup_event():
    print("🚀 Application starting up...")
    try:
        user_db.init_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        # We might want to exit here if DB is critical, but logging it explicitly helps debugging.
        # In production, this will still likely cause the app to be unhealthy, which is correct.

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# MUSIC_ROOT for streaming - default
# Cloud: Set MUSIC_ROOT to /app/music_data or rely on R2_PUBLIC_URL
MUSIC_ROOT = os.environ.get("MUSIC_ROOT", "/Users/russhil/Desktop/aand pav/songs-downloaded")

# Collection-specific music roots
# In cloud, we assume all collections might be in subfolders or same folder
COLLECTION_MUSIC_ROOTS = {
    "music_averaged": MUSIC_ROOT,
    "merged": MUSIC_ROOT, # All collections aggregated
    # Add other collections relative to root if needed
    # "music_russhil": os.path.join(MUSIC_ROOT, "russhil"),
}

# R2 Cloud Storage Prefixes
# Maps collection name (table name) to R2 folder prefix
# If not listed, assumes root of bucket
COLLECTION_R2_PREFIXES = {
    "vectors_russhil": "russhil",
    "music_russhil": "russhil",
}

# Session management (in-memory for simplicity)
# In production, use Redis or JWT
sessions = {}  # session_id -> {"user_id": str, "recommender": UserRecommender, "queue": [], "music_root": str, "youtube_mode": bool}

def get_session(session_id: str) -> dict:
    """Get or create session."""
    if session_id and session_id in sessions:
        return sessions[session_id]
    return None

def create_session(user_id: str, collection_name: str = "music_averaged", youtube_mode: bool = False) -> str:
    """Create new session for user."""
    session_id = str(uuid.uuid4())
    recommender = UserRecommender(user_id, collection_name=collection_name, youtube_mode=youtube_mode)
    
    # Get music root for this collection
    music_root = COLLECTION_MUSIC_ROOTS.get(collection_name, MUSIC_ROOT)
    
    sessions[session_id] = {
        "user_id": user_id,
        "recommender": recommender,
        "collection": collection_name,
        "music_root": music_root,
        "queue": [],
        "youtube_mode": youtube_mode
    }
    
    # Pre-load first batch
    batch = recommender.get_next_batch()
    sessions[session_id]["queue"] = batch.copy()
    
    mode_label = "YOUTUBE" if youtube_mode else "CLASSIC"
    print(f"Created session {session_id[:8]}... for user {user_id} (collection: {collection_name}, mode: {mode_label})")
    return session_id

def ensure_queue(session):
    """Ensure the session queue has enough tracks."""
    QUEUE_SIZE = 5
    if len(session["queue"]) < 1: # Refill only when empty to ensure batch processing
        print(f"Refilling queue for user {session['user_id']}")
        batch = session["recommender"].get_next_batch()
        session["queue"].extend(batch)
        print(f"Added {len(batch)} tracks to queue")

# Cache for file paths to avoid repeated os.walk
file_path_cache = {}

def get_file_path(filename: str, music_root: str = None) -> str:
    """Get real file path with caching and robust search."""
    if music_root is None:
        music_root = MUSIC_ROOT
    
    # Use composite cache key for different roots
    cache_key = f"{music_root}:{filename}"
    if cache_key in file_path_cache:
        if os.path.exists(file_path_cache[cache_key]):
            return file_path_cache[cache_key]
    
    # Check direct path
    full = os.path.join(music_root, filename)
    if os.path.exists(full):
        file_path_cache[cache_key] = full
        return full
    
    # Recursive search
    print(f"Searching for file: {filename} in {music_root}...")
    for root, dirs, files in os.walk(music_root):
        # Check for exact match
        if filename in files:
            found_path = os.path.join(root, filename)
            file_path_cache[cache_key] = found_path
            return found_path
            
        # Check for NFC/NFD normalization issues (common on Mac)
        import unicodedata
        normalized_filename = unicodedata.normalize('NFC', filename)
        
        for f in files:
            if unicodedata.normalize('NFC', f) == normalized_filename:
                found_path = os.path.join(root, f)
                file_path_cache[cache_key] = found_path
                return found_path

    print(f"File NOT FOUND: {filename}")
    return None

# Request Models
class LoginRequest(BaseModel):
    username: str
    password: str = ""
    vectormap: str = "music_averaged"

class FeedbackRequest(BaseModel):
    id: str
    duration: float

class SelectRequest(BaseModel):
    id: str

class WaitlistRequest(BaseModel):
    email: str

# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve landing page (V3 Overhaul)."""
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/ingest", response_class=HTMLResponse)
async def ingest_page(request: Request):
    """Serve ingestion control page."""
    return templates.TemplateResponse("youtube_ingest.html", {"request": request})

@app.websocket("/ws/remote/{code}/{client_type}")
async def remote_endpoint(websocket: WebSocket, code: str, client_type: str):
    """Websocket for distributed ingestion."""
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
                    await coordinator.start_job(code, data)
                elif data.get('type') == 'pause':
                    await coordinator.set_pause(code, True)
                elif data.get('type') == 'resume':
                    await coordinator.set_pause(code, False)
                elif data.get('type') == 'stop':
                    await coordinator.stop_session(code)
            
            elif client_type == 'worker':
                if data.get('type') == 'result':
                    await coordinator.handle_worker_result(code, data)
                    
    except WebSocketDisconnect:
        coordinator.disconnect(code, client_type)

@app.get("/v2", response_class=HTMLResponse)
async def landing_v2(request: Request):
    """Serve alternate landing page (V2)."""
    return templates.TemplateResponse("landing_v2.html", {"request": request})

@app.get("/v3", response_class=HTMLResponse)
async def landing_v3(request: Request):
    """Serve alternate landing page (V3)."""
    return templates.TemplateResponse("landing_v3.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve login page."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/youtube-mode", response_class=HTMLResponse)
async def youtube_mode_page(request: Request):
    """YouTube mode: pick collection with ingested YouTube/Last.fm tracks, then launch player."""
    return templates.TemplateResponse("youtube_mode_landing.html", {"request": request})

@app.get("/player", response_class=HTMLResponse)
async def player(request: Request):
    """Serve player page (requires valid session)."""
    return templates.TemplateResponse("player.html", {"request": request})

class YouTubeModeStartRequest(BaseModel):
    collection: str

@app.post("/api/youtube-mode/start")
async def youtube_mode_start(data: YouTubeModeStartRequest):
    """Create a guest session for YouTube mode with the selected collection."""
    db_cols = set(user_db.get_available_collections())
    db_cols.add("merged")
    db_cols.add("music_averaged")
    collection = data.collection if data.collection in db_cols else "music_averaged"
    session_id = create_session("guest", collection_name=collection, youtube_mode=True)
    return {"status": "ok", "session_id": session_id, "collection": collection}

@app.get("/api/collections")
async def get_collections():
    """Get list of available collections."""
    cols = user_db.get_available_collections()
    # Ensure music_averaged and merged are present
    if "music_averaged" not in cols: cols.append("music_averaged")
    
    # Sort for UI consistency
    cols.sort()
    
    # Add "merged" option if not present in DB (it's a virtual collection)
    return {"collections": cols, "has_merged": True}

@app.get("/api/auth/google")
async def login_google(request: Request):
    """Redirect to Google for Auth."""
    # Determine redirect URI based on current request host
    # This handles both local and production URLs automatically
    redirect_uri = request.url_for('auth_google_callback')
    
    # If behind a proxy (like Render), ensure https scheme
    if "onrender.com" in str(redirect_uri) and str(redirect_uri).startswith("http://"):
        redirect_uri = str(redirect_uri).replace("http://", "https://")
        
    # FORCE PROMPT to ensure we get a fresh token if needed
    return await oauth.google.authorize_redirect(request, redirect_uri, prompt="select_account")

@app.get("/api/auth/google/callback")
async def auth_google_callback(request: Request):
    """Handle Google Auth Callback."""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        
        if not user_info:
            # Sometimes userinfo is inside the id_token claim
            # But authlib usually handles this. Let's try to fetch if missing.
            # user_info = await oauth.google.userinfo(token=token)
            pass
            
        # Get or Create User in DB
        db_user = user_db.get_or_create_google_user(user_info)
        
        # Create Session
        # We can map query param ?vectormap=... if we passed it state, but for now default.
        # Ideally, we should check if user has a preferred collection in profile.
        collection = "music_averaged" 
        
        session_id = create_session(db_user['id'], collection_name=collection)
        
        # Optimize: Pre-generate queue in background or async if possible?
        # create_session already calls get_next_batch which is slow.
        # We could offload the batch generation to a background task and return immediately?
        # But player page needs the queue to start playing.
        # The slowness is likely in UserRecommender.__init__ loading history/clusters.
        # We can optimize UserRecommender.__init__ to be lazier.
        
        # Return HTML that closes popup or redirects
        # Since we likely redirect the main window, we can just redirect to player
        # But we need to pass session_id to frontend.
        # Option 1: Set cookie (secure)
        # Option 2: Redirect with query param (simple)
        
        # Extract first name
        first_name = db_user.get('name', '').split(' ')[0] if db_user.get('name') else 'User'
        encoded_name = urllib.parse.quote(first_name)
        
        response = RedirectResponse(url=f"/player?session_id={session_id}&name={encoded_name}")
        return response
        
    except Exception as e:
        print(f"OAuth Error: {e}")
        return RedirectResponse(url="/login?error=oauth_failed")

@app.post("/api/login")
async def login(data: LoginRequest, response: Response):
    """Authenticate user and create session."""
    username = data.username.lower().strip()
    
    # Dynamic validation
    db_cols = set(user_db.get_available_collections())
    db_cols.add("merged")
    db_cols.add("music_averaged")
    
    collection = data.vectormap if data.vectormap in db_cols else "music_averaged"
    
    if username == "guest":
        session_id = create_session("guest", collection_name=collection)
        return {"status": "ok", "session_id": session_id, "user": "guest", "is_guest": True, "vectormap": collection}
    
    user = user_db.verify_user(username, data.password)
    if user:
        session_id = create_session(username, collection_name=collection)
        return {"status": "ok", "session_id": session_id, "user": username, "is_guest": False, "vectormap": collection}
    
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/next")
async def next_track(session_id: str = Query(...)):
    """Get next track from queue."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Ensure queue has items
    if not session["queue"]:
         ensure_queue(session)
    
    if not session["queue"]:
        raise HTTPException(status_code=500, detail="Queue empty and refill failed")
    
    track = session["queue"].pop(0)
    
    queue_remaining = len(session["queue"])
    response = {
        "id": track['id'],
        "title": track['filename'],
        "justification": track.get('justification', "Algorithm selection"),
        "queue_remaining": queue_remaining
    }
    
    if session.get("youtube_mode") and track.get("youtube_id"):
        response["youtube_id"] = track["youtube_id"]
        response["url"] = None
    else:
        encoded_name = urllib.parse.quote(track['filename'])
        response["url"] = f"/stream/{encoded_name}?track_id={track['id']}"
        response["youtube_id"] = None
    
    return response

@app.post("/api/feedback")
async def feedback(data: FeedbackRequest, session_id: str = Query(...)):
    """Record feedback."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    session["recommender"].record_feedback(
        track_id=data.id,
        duration=data.duration
    )
    
    # LOGGING
    track = session["recommender"].track_map.get(data.id)
    fname = track['filename'] if track else "Unknown"
    log_interaction(session_id, session["user_id"], data.id, fname, "feedback", duration=data.duration)
    
    # If queue empty, finalize and load next
    if len(session["queue"]) == 0:
        print("Queue empty - finalizing batch and loading next")
        session["recommender"].finalize_batch()
        # Do NOT refill here automatically.
        # Let next_track trigger the refill to ensure the feedback is fully processed 
        # before the new batch is generated.
        # But wait, next_track is called by the frontend.
        # If the frontend asks for next track, it hits next_track.
        # If the queue is empty, next_track calls ensure_queue.
        # ensure_queue generates the new batch.
        # So we are good. We just need to ensure finalize_batch is called.
        pass
    
    return {"status": "ok"}

@app.post("/api/reset")
async def reset_session(session_id: str = Query(...)):
    """Reset session to fresh state."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    user_id = session["user_id"]
    
    print(f"\n🔄 SESSION RESET for user {user_id}")
    
    # Create fresh recommender
    session["recommender"] = UserRecommender(user_id)
    session["queue"] = []
    ensure_queue(session)
    
    return {"status": "reset", "message": "Session reset to PROBE phase"}

@app.get("/api/search")
async def search(q: str = Query(..., min_length=1), session_id: str = Query(...)):
    """Search for tracks."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    results = session["recommender"].search(q)
    return [{"id": r["id"], "title": r["filename"]} for r in results]

@app.post("/api/select")
async def select_track(data: SelectRequest, session_id: str = Query(...)):
    """Select a specific track as seed."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    track = session["recommender"].set_seed(data.id)
    if track:
        session["queue"] = []
        session["recommender"].finalize_batch()
        ensure_queue(session)
        
        resp = {"id": track['id'], "title": track['filename'], "justification": "User selected manually"}
        if session.get("youtube_mode") and track.get("youtube_id"):
            resp["youtube_id"] = track["youtube_id"]
            resp["url"] = None
        else:
            encoded_name = urllib.parse.quote(track['filename'])
            resp["url"] = f"/stream/{encoded_name}?track_id={track['id']}"
            resp["youtube_id"] = None
        return resp
    raise HTTPException(status_code=404, detail="Track not found")

@app.get("/api/profile")
async def get_profile(session_id: str = Query(...)):
    """Get user's taste profile."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    user_id = session["user_id"]
    if user_id == "guest":
        return {"user": "guest", "message": "Guest mode has no persistent profile"}
    
    ranked = user_db.get_ranked_clusters(user_id)
    return {
        "user": user_id,
        "top_clusters": ranked[:10]
    }

@app.get("/stream/{filename}")
async def stream(filename: str, session_id: str = Query(None), track_id: str = Query(None)):
    """Stream an audio file. Supports R2 redirect or local file."""
    decoded_name = urllib.parse.unquote(filename)
    
    # Cloud Optimization: R2/S3 Redirect
    # If R2_PUBLIC_URL is set, redirect to cloud storage instead of serving local file.
    # This is critical for cloud hosting to avoid large volume mounts.
    r2_url = os.environ.get("R2_PUBLIC_URL")
    if r2_url:
        # Force root path as per user request
        clean_name = urllib.parse.quote(decoded_name)
        base_url = r2_url.rstrip("/")
        final_url = f"{base_url}/{clean_name}"
            
        print(f"Redirecting to R2: {final_url}")
        
        # Return 302 Found redirect
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=final_url)
    
    # Fallback to Local File Serving
    # Get session-specific music root if session exists
    music_root = None
    if session_id:
        session = get_session(session_id)
        if session and "music_root" in session:
            music_root = session["music_root"]
    
    real_path = get_file_path(decoded_name, music_root)
    
    if real_path and os.path.exists(real_path):
        return FileResponse(real_path, media_type="audio/mpeg", filename=decoded_name)
    
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/history-stats")
async def history_stats(session_id: str = Query(...)):
    """Get user's history statistics."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    return user_db.get_history_stats(session["user_id"])

class ClearHistoryRequest(BaseModel):
    mode: str  # "session", "1h", "4h", "24h", "48h", "72h", "all"

@app.post("/api/clear-history")
async def clear_history(data: ClearHistoryRequest, session_id: str = Query(...)):
    """Clear user history with time-based options."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    user_id = session["user_id"]
    
    if data.mode == "session":
        # Only reset current session, don't touch persistent history
        print(f"\n🔄 SESSION ONLY RESET for {user_id}")
        session["recommender"] = UserRecommender(user_id)
        session["queue"] = []
        ensure_queue(session)
        return {"status": "session_reset", "message": "Current session reset, history preserved"}
    
    elif data.mode == "all":
        result = user_db.clear_user_history(user_id, hours=None)
    
    elif data.mode in ["1h", "4h", "24h", "48h", "72h"]:
        hours = int(data.mode.replace("h", ""))
        result = user_db.clear_user_history(user_id, hours=hours)
    
    else:
        raise HTTPException(status_code=400, detail="Invalid mode")
    
    # Reinitialize recommender with new profile
    session["recommender"] = UserRecommender(user_id)
    session["queue"] = []
    ensure_queue(session)
    
    return result

@app.post("/api/logout")
async def logout(session_id: str = Query(...)):
    """End session."""
    if session_id in sessions:
        del sessions[session_id]
        print(f"Session {session_id[:8]}... ended")
    return {"status": "ok"}

@app.post("/api/waitlist")
async def waitlist(data: WaitlistRequest):
    """Add email to waitlist."""
    try:
        user_db.add_waitlist_email(data.email)
        return {"status": "ok", "message": "Added to waitlist"}
    except Exception as e:
        print(f"Waitlist error: {e}")
        # Return ok even if duplicate/error to not leak info
        return {"status": "ok", "message": "Added to waitlist"}

# --- Admin Routes ---

class AdminChatRequest(BaseModel):
    user_id: str
    message: str
    api_key: str
    context: str = "user" # "global" or "user"

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, session_id: str = Query(None)):
    """Serve admin dashboard."""
    # Simple auth check: must have valid session and be 'russhil'
    session = get_session(session_id)
    if not session or session["user_id"] != "russhil":
         # In a real app, redirect to login, but for now just 403 or login
         if not session:
             return templates.TemplateResponse("login.html", {"request": request})
         raise HTTPException(status_code=403, detail="Admin access only")
    
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/api/admin/stats")
async def admin_stats(session_id: str = Query(...)):
    """Get global and per-user stats."""
    session = get_session(session_id)
    if not session or session["user_id"] != "russhil":
        raise HTTPException(status_code=403, detail="Admin access only")
    
    return user_db.get_admin_stats()

@app.get("/api/admin/logs")
async def admin_logs(session_id: str = Query(...), limit: int = 100):
    """Get recent logs for real-time view from Render."""
    session = get_session(session_id)
    if not session or session["user_id"] != "russhil":
        raise HTTPException(status_code=403, detail="Admin access only")
    
    logs = user_db.get_logs(limit=limit)
    return logs # Already sorted DESC

@app.post("/api/admin/chat")
async def admin_chat(data: AdminChatRequest):
    """Chat with Gemma about a user's logs."""
    # 1. Gather Context
    logs = []
    
    # Fetch from Render based on context
    target_user = data.user_id if data.context == "user" else None
    db_logs = user_db.get_logs(limit=100, user_id=target_user)
    
    # Format for Prompt
    for row in db_logs:
        ts = row.get('timestamp', '')
        user = row.get('user_id', '')
        action = row.get('action', '')
        fname = row.get('filename', '')
        dur = row.get('duration', '')
        just = row.get('justification', '')
        
        logs.append(f"[{ts}] {user} | {action}: {fname} ({dur}s) | Reason: {just}")
            
    # Reverse to chronological for LLM
    recent_logs = logs[::-1] 
    log_text = "\n".join(recent_logs)
    
    # Get profile stats (only if user context)
    stats_text = "Global Context"
    if data.context == "user":
        profile = user_db.get_user_profile(data.user_id)
        stats_text = f"Clusters Explored: {len(profile.get('clusters', {}))}"
    
    # 2. Build Prompt
    godprompt = ""
    if os.path.exists("admin_godprompt.txt"):
        with open("admin_godprompt.txt", "r") as f:
            godprompt = f.read()
            
    prompt = f"""
{godprompt}

CONTEXT: {data.context.upper()}
TARGET: {data.user_id if data.context == "user" else "ALL USERS"}
STATS: {stats_text}

RECENT INTERACTION LOGS:
{log_text}

USER QUESTION: {data.message}
"""

    # 3. Call Gemma
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={data.api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            return {"reply": f"Error from AI: {response.text}"}
            
        result = response.json()
        reply = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No response generated.")
        return {"reply": reply}
        
    except Exception as e:
        return {"reply": f"System Error: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5001))
    print(f"🚀 Starting User Server on port {port}...")
    uvicorn.run("server_user:app", host="0.0.0.0", port=port, reload=True)
