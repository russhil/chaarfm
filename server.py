from flask import Flask, render_template, jsonify, request, redirect
import os
import urllib.parse
from recommender import RecommenderSession

app = Flask(__name__)
session = RecommenderSession()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/next')
def next_track():
    track = session.get_next_track()
    if track:
        # Return the s3_url if available, otherwise construct a stream URL
        # But wait, our new vector_db returns 's3_url' in the track object.
        # Let's verify track structure.
        
        # We need to make sure the frontend uses 'url' correctly.
        # If s3_url is present, we send it as 'url'.
        
        return jsonify({
            "id": track['id'],
            "title": track.get('filename', 'Unknown Track'),
            "url": track.get('s3_url') or f"/stream/{urllib.parse.quote(track.get('filename', ''))}"
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
    """
    Fallback for local files if s3_url is missing.
    In the new cloud-native setup, this shouldn't be hit often.
    But for backward compatibility or local dev, we keep it.
    """
    # ... logic to find file locally ...
    return "Streaming from local file is deprecated. Please ensure DB has s3_url.", 404

@app.route('/api/search')
def search():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])
    
    # We should search in the DB (Postgres) now
    # Or use the in-memory cluster map if it has everything.
    
    results = []
    if session.cluster_manager.initialized:
        for tid, info in session.cluster_manager.track_map.items():
            if query in info['filename'].lower():
                results.append({
                    "id": tid,
                    "title": info['filename']
                })
                if len(results) > 20: break
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
            "url": track_info.get('s3_url') or f"/stream/{urllib.parse.quote(track_info['filename'])}"
        })
    return jsonify({"error": "Track not found"}), 404

@app.route('/api/library')
def library():
    """Returns a list of all tracks in the library."""
    # We can fetch from DB or use cluster map
    library_list = []
    
    # Using cluster map is faster if initialized
    if session.cluster_manager.initialized:
         for tid, info in session.cluster_manager.track_map.items():
             library_list.append({
                 "id": tid,
                 "filename": info['filename'],
                 "s3_url": info.get('s3_url')
             })
    
    # Limit to avoid massive JSON
    return jsonify(library_list[:5000])

if __name__ == '__main__':
    session.reset_session()
    app.run(host='0.0.0.0', port=5010, debug=True)
