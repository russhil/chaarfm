"""
MP3 to Vector Pipeline (Supabase/Vecs Edition)
==============================================

High-performance parallel music vectorization pushing to Supabase (pgvector).
Features:
- Multiprocess extraction
- Supabase/pgvector ingestion via 'vecs' list
- Robust state management
"""

import os
import sys
import time
import json
import hashlib
import sqlite3
import argparse
import multiprocessing
import signal
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from queue import Queue, Empty
from threading import Thread

# Supabase / Vecs
import vecs

import config_manager
config_manager.load_env_vars()
from config_manager import configure_interactive

# ============================================================================
# CONFIGURATION
# ============================================================================

_config = config_manager.load_config()
FOLDERS = _config.get("folders", {})
COLLECTIONS = _config.get("collections", {})

if not FOLDERS:
    # Check Env for SOURCES logic if locally empty
    env_sources = os.environ.get("SOURCES", "").split(",")
    if any(env_sources):
        # We are in cloud mode, but pipeline runs locally usually.
        # If running pipeline in cloud, well, we assume folders exist.
        pass
    else:
        # Only run interactive config if NOT running in GUI mode
        if "--gui" not in sys.argv:
            print("⚠️ No music folders configured! Launching configuration tool...")
            configure_interactive()
            _config = config_manager.load_config()
            FOLDERS = _config.get("folders", {})
            COLLECTIONS = _config.get("collections", {})

VECTOR_SIZE = 200
SUPPORTED_EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
DB_STATE_FILE = "vectorize_state.db"

# Global worker state
_extractor = None

# ============================================================================
# GUI HELPERS
# ============================================================================

def run_gui_input():
    """Launch GUI to get folder and database details."""
    root = tk.Tk()
    root.withdraw()  # Hide main window

    # 1. Select Folder
    messagebox.showinfo("Select Music Folder", "Please select the folder containing your MP3 files.")
    folder_path = filedialog.askdirectory(title="Select Music Folder")
    
    if not folder_path:
        messagebox.showerror("Error", "No folder selected. Exiting.")
        sys.exit(1)

    # 2. Get Supabase Connection String
    # Try to pre-fill from env
    default_db = os.environ.get("DATABASE_URL", "")
    
    db_url = simpledialog.askstring(
        "Supabase Connection", 
        "Enter your Supabase PostgreSQL Connection String:\n(e.g., postgresql://postgres.xxxx:password@aws-1-us-east-1.pooler.supabase.com:6543/postgres)",
        initialvalue=default_db
    )

    if not db_url:
        messagebox.showerror("Error", "No database URL provided. Exiting.")
        sys.exit(1)

    root.destroy()
    return folder_path, db_url

# ============================================================================
# WORKER PROCESS
# ============================================================================

def init_worker():
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["TF_NUM_INTRAOP_THREADS"] = "1"
    os.environ["TF_NUM_INTEROP_THREADS"] = "1"
    global _extractor
    try:
        from audio_processor import MusicNNExtractor
        _extractor = MusicNNExtractor()
    except Exception as e:
        print(f"Worker init failed: {e}", file=sys.stderr)
        raise

def process_file_task(args: Tuple[str, str, str]) -> Dict:
    file_path, source, collection_name = args
    filename = os.path.basename(file_path)
    try:
        if _extractor is None: raise RuntimeError("Extractor not initialized")
        result = _extractor.extract(file_path)
        vector = result["average_vector"].tolist()
        
        unique_str = f"{source}:{file_path}"
        point_id = hashlib.md5(unique_str.encode()).hexdigest()
        combined_id = hashlib.md5(f"combined:{source}:{file_path}".encode()).hexdigest()
        
        return {
            "status": "success",
            "file_path": file_path,
            "filename": filename,
            "source": source,
            "vector": vector,
            "point_id": point_id,
            "combined_point_id": combined_id,
            "mtime": os.path.getmtime(file_path)
        }
    except Exception as e:
        return {"status": "error", "file_path": file_path, "error": str(e)}

# ============================================================================
# STATE DB
# ============================================================================

class StateManager:
    def __init__(self, db_path=DB_STATE_FILE):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()
        
    def _init_db(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS processed_files (path TEXT PRIMARY KEY, mtime REAL, point_id TEXT, processed_at TEXT)''')
        self.conn.commit()
    
    def is_processed(self, file_path: str) -> bool:
        try:
            current = os.path.getmtime(file_path)
            self.cursor.execute('SELECT mtime FROM processed_files WHERE path = ?', (file_path,))
            row = self.cursor.fetchone()
            return row and abs(current - row[0]) < 1.0
        except: return False
            
    def mark_batch(self, items: List[Dict]):
        data = [(i['file_path'], i['mtime'], i['point_id'], datetime.now().isoformat()) for i in items]
        self.cursor.executemany('INSERT OR REPLACE INTO processed_files (path, mtime, point_id, processed_at) VALUES (?, ?, ?, ?)', data)
        self.conn.commit()

    def clear(self):
        self.cursor.execute('DELETE FROM processed_files')
        self.conn.commit()

# ============================================================================
# SUPABASE UPLOADER
# ============================================================================

class AsyncSupabaseUploader(Thread):
    def __init__(self, db_url: str, store_path: bool, db_manager: StateManager, batch_size: int = 300):
        super().__init__()
        self.client = vecs.create_client(db_url)
        self.store_path = store_path
        self.db = db_manager
        self.batch_size = batch_size
        self.queue = Queue()
        self.running = True
        self.daemon = True
        self.processed_count = 0
        self.failure_count = 0
        
        # Cache collection objects
        self.cols = {}
        
    def get_col(self, name):
        if name not in self.cols:
            self.cols[name] = self.client.get_or_create_collection(name=name, dimension=VECTOR_SIZE)
        return self.cols[name]
        
    def run(self):
        pending = []
        while self.running or not self.queue.empty():
            try:
                try:
                    item = self.queue.get(timeout=0.5)
                    if item["status"] == "success": pending.append(item)
                except Empty:
                    pass
                
                if len(pending) >= self.batch_size or (not self.running and pending):
                     self.upload_batch(pending)
                     pending = []
                     
            except Exception as e:
                print(f"Uploader Loop Error: {e}")
                
    def upload_batch(self, batch):
        if not batch: return
        try:
            col_map = {}
            for item in batch:
                src = item['source']
                name = f"music_{src}"
                if name not in col_map: col_map[name] = []
                
                meta = {"filename": item["filename"], "source": src}
                if self.store_path: meta["path"] = item["file_path"]
                
                # vecs record: (id, vector, metadata)
                col_map[name].append((item["point_id"], item["vector"], meta))
                
                # Combined
                if "music_combined" not in col_map: col_map["music_combined"] = []
                col_map["music_combined"].append((item["combined_point_id"], item["vector"], meta))
            
            for name, records in col_map.items():
                col = self.get_col(name)
                # vecs upsert
                col.upsert(records=records)
                
            self.db.mark_batch(batch)
            self.processed_count += len(batch)
            print(f"☁️  Synced {len(batch)} tracks to Supabase.")
            
        except Exception as e:
            print(f"❌ Batch Upload Failed: {e}")
            self.failure_count += len(batch)

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Supabase Music Vectorizer")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=300)
    parser.add_argument("--store-path", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=4)
    parser.add_argument("--gui", action="store_true", help="Launch GUI for selection")
    args = parser.parse_args()
    
    print("🚀 MUSIC PIPELINE -> SUPABASE")
    
    # GUI Mode Logic
    selected_folder = None
    if args.gui:
        selected_folder, gui_db_url = run_gui_input()
        os.environ["DATABASE_URL"] = gui_db_url # Override for this session
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Fallback to GUI if not found and not explicitly suppressed (simple check)
        print("⚠️ DATABASE_URL not found. Launching GUI...")
        selected_folder, gui_db_url = run_gui_input()
        os.environ["DATABASE_URL"] = gui_db_url
        db_url = gui_db_url

    if not db_url:
        print("❌ DATABASE_URL env var missing! Set it to your Supabase connection string.")
        sys.exit(1)
        
    # State DB
    state_db = StateManager()
    if args.recreate:
        state_db.clear()
        # Note: vecs delete collection? 
        # For safety, we won't auto-delete cloud collections unless explicit.
        # But user asked to "push entire vector db".
        pass

    # Start Uploader
    uploader = AsyncSupabaseUploader(db_url, args.store_path, state_db, args.batch_size)
    uploader.start()
    
    # Scan Files
    tasks = []
    skipped = 0
    
    # If GUI selected a folder, use ONLY that folder (Treat as 'gui_selection' source)
    if selected_folder:
        print(f"📂 Scanning GUI selected folder: {selected_folder}")
        scan_folders = {"gui_selection": selected_folder}
    else:
        scan_folders = FOLDERS

    for source, folder in scan_folders.items():
        if not os.path.exists(folder): continue
        for root, _, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS:
                    full_path = os.path.join(root, f)
                    if not args.recreate and state_db.is_processed(full_path):
                        skipped += 1
                        continue
                    tasks.append((full_path, source, f"music_{source}"))
                    
    print(f"Found {len(tasks)} new files ({skipped} skipped).")
    
    if args.dry_run: return

    # Processing Loop
    workers = args.workers or max(1, multiprocessing.cpu_count() - 2)
    pool = multiprocessing.Pool(processes=workers, initializer=init_worker)
    
    try:
        for result in pool.imap_unordered(process_file_task, tasks, chunksize=args.chunk_size):
            uploader.queue.put(result)
            
    except KeyboardInterrupt:
        print("Stopping...")
        pool.terminate()
        
    pool.close()
    pool.join()
    
    uploader.running = False
    uploader.join()
    print("Done.")

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    main()
