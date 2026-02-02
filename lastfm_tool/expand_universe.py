import pylast
import json
import os
import certifi
import httpx
import time
import random

# --- SSL Fix ---
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

original_client = httpx.Client

class InsecureClient(original_client):
    def __init__(self, *args, **kwargs):
        kwargs['verify'] = False
        super().__init__(*args, **kwargs)

httpx.Client = InsecureClient
# ----------------

# Credentials
API_KEY = "f3d0dfdb4bb8c0fbe7e41400c6ff979e"
API_SECRET = "072547e52c6e1f3b890b9af5a10103e8"

def main():
    print("--- Expanding Music Universe to ~2000 Songs ---")
    
    # Load existing universe
    try:
        with open("lastfm_tool/music_universe.json", "r") as f:
            universe_data = json.load(f)
    except FileNotFoundError:
        # Try checking current directory if running from lastfm_tool
        try:
             with open("music_universe.json", "r") as f:
                universe_data = json.load(f)
        except FileNotFoundError:
            print("Error: 'music_universe.json' not found. Please run generate_universe.py first.")
            return

    network = pylast.LastFMNetwork(api_key=API_KEY, api_secret=API_SECRET)
    
    familiar_artists = list(universe_data["music_universe"]["artists"].keys())
    extended_artists = [a["name"] for a in universe_data["extended_pool"]["artists"]]
    
    all_target_artists = list(set(familiar_artists + extended_artists))
    print(f"Found {len(all_target_artists)} total artists to mine.")
    
    # We want ~1800 songs from artists (leaving room for the existing 100 top tracks)
    # Target: ~15-20 songs per artist
    tracks_per_artist = 20
    
    collected_tracks = {} # Key: "Artist - Title", Value: Metadata
    
    # Add existing top tracks first
    print("Adding existing top tracks...")
    for key, data in universe_data["music_universe"]["tracks"].items():
        collected_tracks[key] = data
        
    print(f"Starting with {len(collected_tracks)} tracks.")
    
    # Shuffle artists to get a random mix if we stop early, though we probably won't need to
    # random.shuffle(all_target_artists)
    
    for i, artist_name in enumerate(all_target_artists, 1):
        try:
            print(f"[{i}/{len(all_target_artists)}] Fetching top tracks for: {artist_name}")
            artist = pylast.Artist(artist_name, network)
            top_tracks = artist.get_top_tracks(limit=tracks_per_artist)
            
            for item in top_tracks:
                track = item.item
                track_key = f"{track.artist.name} - {track.title}"
                
                if track_key not in collected_tracks:
                    collected_tracks[track_key] = {
                        "artist": track.artist.name,
                        "title": track.title,
                        "listeners": item.weight, # For artist top tracks, weight is listeners/playcount
                        "source": "artist_top_tracks"
                    }
            
            # Rate limiting sleep
            time.sleep(0.2)
            
        except Exception as e:
            print(f"  Error fetching tracks for {artist_name}: {e}")
            
    print(f"\nExtraction Complete!")
    print(f"Total Unique Songs Collected: {len(collected_tracks)}")
    
    # Convert to list
    final_list = list(collected_tracks.values())
    
    # Save
    output_file = "lastfm_tool/expanded_universe_tracks.json"
    with open(output_file, "w") as f:
        json.dump(final_list, f, indent=2)
        
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    main()
