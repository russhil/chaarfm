"""
Vectorization Pipeline Web UI (Supabase Edition)
================================================

A web interface to monitor and control the MP3 vectorization pipeline.

Usage:
    python pipeline_server.py
    
Then open: http://localhost:5005
"""

import os
import sys
import json
import time
import asyncio
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

import config_manager
config_manager.load_env_vars()

# ============================================================================
# CONFIGURATION
# ============================================================================

_config = config_manager.load_config()
FOLDERS = _config.get("folders", {})
COLLECTIONS = _config.get("collections", {})

SUPPORTED_EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
VECTOR_SIZE = 200

# ============================================================================
# GLOBAL STATE
# ============================================================================

pipeline_state = {
    "status": "idle",
    "current_folder": None,
    "current_file": None,
    "total_files": 0,
    "processed_files": 0,
    "failed_files": 0,
    "start_time": None,
    "eta_seconds": None,
    "logs": [],
    "folder_progress": {},
    "error": None
}

pipeline_thread: Optional[threading.Thread] = None
stop_flag = threading.Event()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    pipeline_state["logs"].append(entry)
    if len(pipeline_state["logs"]) > 100:
        pipeline_state["logs"] = pipeline_state["logs"][-100:]
    print(entry)

def scan_folder(folder_path: str) -> list:
    files = []
    folder = Path(folder_path)
    if not folder.exists(): return files
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(str(path))
    return sorted(files)

def run_pipeline():
    global pipeline_state
    
    try:
        import numpy as np
        import vecs
        from audio_processor import MusicNNExtractor
        import hashlib
        
        pipeline_state["status"] = "running"
        pipeline_state["start_time"] = time.time()
        pipeline_state["error"] = None
        
        log("🚀 Pipeline started (Supabase Mode)")
        
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL env var not set! Configure it first.")
            
        # Scan folders
        log("📁 Scanning folders...")
        all_files = {}
        total = 0
        
        for source, folder in FOLDERS.items():
            files = scan_folder(folder)
            all_files[source] = files
            pipeline_state["folder_progress"][source] = {
                "total": len(files), "processed": 0, "failed": 0
            }
            log(f"  {source}: {len(files)} files")
            total += len(files)
        
        pipeline_state["total_files"] = total
        
        if total == 0:
            log("❌ No files found!")
            pipeline_state["status"] = "error"
            return
        
        # Initialize Supabase
        log("☁️ Connecting to Supabase...")
        vx = vecs.create_client(db_url)
        log("  ✅ Connected to Postgres/Pgvector")
        
        # Pre-create collections
        for name, collection in COLLECTIONS.items():
            try:
                vx.get_or_create_collection(name=collection, dimension=VECTOR_SIZE)
                log(f"  Collection ready: {collection}")
            except Exception as e:
                log(f"  ⚠️ Error creating collection {collection}: {e}")

        # Initialize extractor
        log("🧠 Loading MusiCNN model...")
        extractor = MusicNNExtractor()
        
        # Process files
        log("🎵 Processing files...")
        batch_points = {} # name -> list
        batch_size = 50
        
        processed_set = set() 
        # Ideally we check DB for existing files to skip?
        # Simulating "Resume" is expensive without querying.
        # We'll skip implemented for now or assume overwrite is okay. 
        # User asked for "dump".
        
        for source, files in all_files.items():
            pipeline_state["current_folder"] = source
            col_name = COLLECTIONS.get(source, f"music_{source}")
            
            log(f"\n📂 Processing [{source}] -> {col_name}...")
            
            for i, file_path in enumerate(files):
                if stop_flag.is_set():
                    log("⏹️ Pipeline stopped by user")
                    pipeline_state["status"] = "idle"
                    return
                
                filename = os.path.basename(file_path)
                pipeline_state["current_file"] = filename
                
                try:
                    result = extractor.extract(file_path)
                    vector = result["average_vector"].tolist()
                    
                    point_id = hashlib.md5(f"{source}:{filename}".encode()).hexdigest()
                    combined_id = hashlib.md5(f"combined_{source}:{filename}".encode()).hexdigest()
                    
                    meta = {"filename": filename, "source": source, "path": file_path}
                    
                    # Buffer
                    if col_name not in batch_points: batch_points[col_name] = []
                    batch_points[col_name].append((point_id, vector, meta))
                    
                    if "music_combined" not in batch_points: batch_points["music_combined"] = []
                    batch_points["music_combined"].append((combined_id, vector, meta))
                    
                    pipeline_state["processed_files"] += 1
                    pipeline_state["folder_progress"][source]["processed"] += 1
                    
                except Exception as e:
                    pipeline_state["failed_files"] += 1
                    pipeline_state["folder_progress"][source]["failed"] += 1
                    log(f"  ❌ Failed: {filename[:20]}... {e}")
                
                # ETA
                elapsed = time.time() - pipeline_state["start_time"]
                if pipeline_state["processed_files"] > 0:
                    rate = elapsed / pipeline_state["processed_files"]
                    remaining = pipeline_state["total_files"] - pipeline_state["processed_files"]
                    pipeline_state["eta_seconds"] = remaining * rate
                
                # Upload batches
                for cname in batch_points:
                    if len(batch_points[cname]) >= batch_size:
                        try:
                            col = vx.get_or_create_collection(name=cname, dimension=VECTOR_SIZE)
                            col.upsert(records=batch_points[cname])
                            batch_points[cname] = []
                            # log(f"  Synced batch to {cname}")
                        except Exception as e:
                            log(f"  ❌ Upload failed: {e}")
                
                if (i + 1) % 50 == 0:
                    log(f"  {source}: {i+1}/{len(files)}")
        
        # Remaining
        log("\n📤 Uploading remaining...")
        for cname, records in batch_points.items():
            if records:
                col = vx.get_or_create_collection(cname, dimension=VECTOR_SIZE)
                col.upsert(records)
        
        elapsed = time.time() - pipeline_state["start_time"]
        log(f"\n✅ Complete! Time: {elapsed/60:.1f} mins")
        pipeline_state["status"] = "completed"
        
    except Exception as e:
        log(f"❌ Error: {e}")
        pipeline_state["status"] = "error"
        pipeline_state["error"] = str(e)
        import traceback
        traceback.print_exc()

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(title="Vectorization Pipeline")

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vectorization Pipeline (Supabase)</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;500;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Outfit', sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh;
            color: white;
            padding: 40px;
        }
        .container { max-width: 900px; margin: 0 auto; }
        h1 {
            font-size: 2.5rem;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .status-badge {
            display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 0.9rem;
        }
        .status-idle { background: rgba(255,255,255,0.1); }
        .status-running { background: rgba(76, 175, 80, 0.3); color: #81c784; }
        .status-completed { background: rgba(33, 150, 243, 0.3); color: #64b5f6; }
        .status-error { background: rgba(244, 67, 54, 0.3); color: #e57373; }
        
        .progress-bar { height: 12px; background: rgba(255,255,255,0.1); border-radius: 6px; overflow: hidden; margin: 10px 0; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #f093fb, #f5576c); border-radius: 6px; transition: width 0.3s; }
        .stats { display: flex; gap: 30px; margin: 20px 0; flex-wrap: wrap; }
        .stat { text-align: center; }
        .stat-value { font-size: 2rem; font-weight: 700; color: #f093fb; }
        .stat-label { font-size: 0.85rem; color: rgba(255,255,255,0.5); }
        
        .btn { padding: 12px 30px; border: none; border-radius: 10px; font-size: 1rem; font-weight: 600; cursor: pointer; margin-right: 10px; transition: all 0.3s; }
        .btn-primary { background: linear-gradient(135deg, #f093fb, #f5576c); color: white; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(240,147,251,0.3); }
        .btn-danger { background: rgba(244, 67, 54, 0.3); color: #e57373; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .logs { background: rgba(0,0,0,0.3); border-radius: 10px; padding: 15px; height: 250px; overflow-y: auto; font-family: monospace; font-size: 0.85rem; line-height: 1.6; }
        .log-entry { color: rgba(255,255,255,0.8); }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Vectorization Pipeline (Supabase)</h1>
        
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <span class="status-badge" id="status">Idle</span>
                <div>
                    <button class="btn btn-primary" id="startBtn" onclick="startPipeline()">▶️ Start</button>
                    <button class="btn btn-danger" id="stopBtn" onclick="stopPipeline()" disabled>⏹️ Stop</button>
                </div>
            </div>
            
            <div class="stats">
                <div class="stat"><div class="stat-value" id="processed">0</div><div class="stat-label">Processed</div></div>
                <div class="stat"><div class="stat-value" id="total">0</div><div class="stat-label">Total</div></div>
                <div class="stat"><div class="stat-value" id="failed">0</div><div class="stat-label">Failed</div></div>
            </div>
            
            <div class="progress-bar"><div class="progress-fill" id="progressBar" style="width: 0%"></div></div>
            <div id="eta" style="color: rgba(255,255,255,0.6); margin-top: 5px;"></div>
            
            <div id="currentFile" style="margin-top: 10px; font-size: 0.9rem; color: #f093fb;"></div>
        </div>
        
        <div class="card">
            <h3>📂 Folder Progress</h3>
            <div id="folderProgress"></div>
        </div>
        
        <div class="card">
            <h3>📋 Logs</h3>
            <div class="logs" id="logs"></div>
        </div>
    </div>
    
    <script>
        let eventSource;
        function connectSSE() {
            eventSource = new EventSource('/api/progress');
            eventSource.onmessage = (e) => { updateUI(JSON.parse(e.data)); };
            eventSource.onerror = () => { setTimeout(connectSSE, 2000); };
        }
        
        function updateUI(data) {
            const statusEl = document.getElementById('status');
            statusEl.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);
            statusEl.className = 'status-badge status-' + data.status;
            
            document.getElementById('startBtn').disabled = data.status === 'running';
            document.getElementById('stopBtn').disabled = data.status !== 'running';
            
            document.getElementById('processed').textContent = data.processed_files;
            document.getElementById('total').textContent = data.total_files;
            document.getElementById('failed').textContent = data.failed_files;
            
            const pct = data.total_files > 0 ? (data.processed_files / data.total_files * 100) : 0;
            document.getElementById('progressBar').style.width = pct + '%';
            
            if (data.eta_seconds) {
                const mins = Math.floor(data.eta_seconds / 60);
                const secs = Math.floor(data.eta_seconds % 60);
                document.getElementById('eta').textContent = `ETA: ${mins}m ${secs}s remaining`;
            } else {
                document.getElementById('eta').textContent = '';
            }
            
            document.getElementById('currentFile').textContent = data.current_file ? 'Processing: ' + data.current_file : '';
            
            let folderHTML = '';
            for (const [name, prog] of Object.entries(data.folder_progress || {})) {
                 const fpct = prog.total > 0 ? (prog.processed / prog.total * 100) : 0;
                 folderHTML += `<div style="margin:10px 0;"><strong>${name}</strong>: ${prog.processed}/${prog.total}<div class="progress-bar"><div class="progress-fill" style="width: ${fpct}%"></div></div></div>`;
            }
            document.getElementById('folderProgress').innerHTML = folderHTML;
            
            const logsEl = document.getElementById('logs');
            logsEl.innerHTML = (data.logs || []).map(l => `<div class="log-entry">${l}</div>`).join('');
            logsEl.scrollTop = logsEl.scrollHeight;
        }
        
        async function startPipeline() { await fetch('/api/start', { method: 'POST' }); }
        async function stopPipeline() { await fetch('/api/stop', { method: 'POST' }); }
        
        connectSSE();
    </script>
</body>
</html>
"""

@app.get("/api/progress")
async def progress_stream():
    async def event_generator():
        while True:
            data = {
                "status": pipeline_state["status"],
                "current_folder": pipeline_state["current_folder"],
                "current_file": pipeline_state["current_file"],
                "total_files": pipeline_state["total_files"],
                "processed_files": pipeline_state["processed_files"],
                "failed_files": pipeline_state["failed_files"],
                "start_time": pipeline_state["start_time"],
                "eta_seconds": pipeline_state["eta_seconds"],
                "logs": pipeline_state["logs"][-20:],
                "folder_progress": pipeline_state["folder_progress"],
                "error": pipeline_state["error"]
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.post("/api/start")
async def start_pipeline():
    global pipeline_thread, stop_flag
    if pipeline_state["status"] == "running": return {"error": "Already running"}
    
    pipeline_state.update({
        "status": "idle", "current_folder": None, "current_file": None,
        "total_files": 0, "processed_files": 0, "failed_files": 0,
        "start_time": None, "eta_seconds": None, "logs": [],
        "folder_progress": {}, "error": None
    })
    
    stop_flag.clear()
    pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
    pipeline_thread.start()
    return {"status": "started"}

@app.post("/api/stop")
async def stop_pipeline():
    stop_flag.set()
    return {"status": "stopping"}

if __name__ == "__main__":
    print("Open: http://localhost:5005")
    uvicorn.run(app, host="0.0.0.0", port=5005)
