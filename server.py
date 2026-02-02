from flask import Flask, render_template, jsonify, request, send_file
import os
import urllib.parse
from recommender import RecommenderSession
from main import scan_directory, DEFAULT_MUSIC_DIR

app = Flask(__name__)
session = RecommenderSession()

# File mapping (Basename -> Full Path)
# This is needed because the DB only stores basenames (from previous implementation)
print("Building file map...")
FILE_MAP = {}

def refresh_file_map():
    """Scans the music directory and updates the file map."""
    global FILE_MAP
    print("Refreshing file map...")
    files = scan_directory(DEFAULT_MUSIC_DIR)
    count = 0
    for f in files:
        key = os.path.basename(f)
        if key not in FILE_MAP:
             FILE_MAP[key] = f
             count += 1
    print(f"Refreshed map. Added {count} new files. Total: {len(FILE_MAP)}")

# Initial scan
files = scan_directory(DEFAULT_MUSIC_DIR)
for f in files:
    key = os.path.basename(f)
    FILE_MAP[key] = f
print(f"Mapped {len(FILE_MAP)} files.")

def get_file_path(filename):
    """
    Returns the full path for a filename. 
    If not in map, tries to refresh map once.
    """
    if filename in FILE_MAP:
        path = FILE_MAP[filename]
        if os.path.exists(path):
            return path
        else:
            # File moved or deleted?
            print(f"File {filename} in map but not found on disk at {path}")
            del FILE_MAP[filename]
    
    # Try refresh
    refresh_file_map()
    
    if filename in FILE_MAP:
        return FILE_MAP[filename]
    
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/next')
def next_track():
    track = session.get_next_track()
    if track:
        # Check if we have the file
        file_path = get_file_path(track['filename'])
        
        if not file_path:
             print(f"Warning: File {track['filename']} not found in map even after refresh.")
             # We could try to get another track, but for now let's send it
             # and let the frontend/stream handle the error (or we could loop here)
        
        return jsonify({
            "id": track['id'],
            "title": track['filename'],
            "url": f"/stream/{urllib.parse.quote(track['filename'])}"
        })
    return jsonify({"error": "No tracks found"}), 404

@app.route('/api/feedback', methods=['POST'])
def feedback():
    data = request.json
    session.feedback(
        track_id=data.get('id'),
        duration=data.get('duration', 0),
        liked=data.get('liked', False),
        disliked=data.get('disliked', False),
        finished=data.get('finished', False)
    )
    return jsonify({"status": "ok", "streak": session.streak})

@app.route('/stream/<path:filename>')
def stream(filename):
    # filename is URL encoded in the request, flask might decode it?
    # Actually 'path' converter might keep slashes, but we are just sending basename.
    
    # If using quote in url, here we get it decoded usually.
    # Safe check
    
    real_path = get_file_path(filename)
    if real_path and os.path.exists(real_path):
        return send_file(real_path)
    return "File not found", 404

@app.route('/api/search')
def search():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])
    
    # Simple substring search in FILE_MAP
    # Ideally use Qdrant for semantic search? But user probably wants exact name first.
    # We can iterate clustering track_map if available for IDs, otherwise we might not have IDs easily mapped in FILE_MAP
    # Wait, FILE_MAP is just name->path.
    # But we need IDs for set_seed.
    # recommender.cluster_manager.track_map has id -> {filename, ...}
    # Let's use that if available
    
    results = []
    if session.cluster_manager.initialized:
        for tid, info in session.cluster_manager.track_map.items():
            if query in info['filename'].lower():
                results.append({
                    "id": tid,
                    "title": info['filename']
                })
                if len(results) > 20: break
    else:
        # Fallback if clustering not ready (unlikely)
        pass
        
    return jsonify(results)

@app.route('/api/select', methods=['POST'])
def select_track():
    data = request.json
    track_id = data.get('id')
    
    track_info = session.set_seed(track_id)
    if track_info:
        return jsonify({
            "id": track_info['id'],
            "title": track_info['filename'],
            "url": f"/stream/{urllib.parse.quote(track_info['filename'])}"
        })
    return jsonify({"error": "Track not found"}), 404

@app.route('/api/library')
def library():
    """Returns a list of all tracks in the library."""
    # Ensure map is up to date
    refresh_file_map()
    
    library_list = []
    # querying Qdrant for everything is slow/expensive if we just need list.
    # But we have FILE_MAP which is basename -> path.
    # ideally we want IDs too. 
    # Let's use what we have. If we need IDs, we might have to scroll Qdrant or cache it.
    
    # For sync, filename is the key for now since stream url uses it.
    # But player uses ID. 
    # Let's get all from Qdrant to be safe, or just iterate file map and assume IDs will be fetched later?
    # The Sync needs to download files. filename is enough.
    
    # Wait, simple list of filenames:
    for filename, path in FILE_MAP.items():
        try:
            size = os.path.getsize(path)
            library_list.append({
                "filename": filename,
                "size": size
            })
        except OSError:
            pass
            
    return jsonify(library_list)

if __name__ == '__main__':
    session.reset_session()
    app.run(host='0.0.0.0', port=5010, debug=True)
