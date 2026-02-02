import pylast
import json
import time
from .config import LASTFM_API_KEY, LASTFM_API_SECRET
import os
import certifi
import httpx

# SSL Fix
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Patch httpx
original_client = httpx.Client
class InsecureClient(original_client):
    def __init__(self, *args, **kwargs):
        kwargs['verify'] = False
        super().__init__(*args, **kwargs)
httpx.Client = InsecureClient

def get_network():
    return pylast.LastFMNetwork(api_key=LASTFM_API_KEY, api_secret=LASTFM_API_SECRET)

def extract_universe(username, limit_per_artist=5):
    """
    Extracts a music universe for the user.
    Returns a list of track metadata dictionaries.
    """
    network = get_network()
    user = network.get_user(username)
    print(f"Extracting universe for: {user.get_name()}")
    
    universe_tracks = {} # Key: "Artist - Title"
    
    # 1. Top Tracks (Overall) - Get more here
    print("  Fetching Top Tracks (Overall)...")
    try:
        top_tracks = user.get_top_tracks(period=pylast.PERIOD_OVERALL, limit=50)
        for item in top_tracks:
            track = item.item
            key = f"{track.artist.name} - {track.title}"
            universe_tracks[key] = {
                "artist": track.artist.name,
                "title": track.title,
                "source": "user_top_tracks"
            }
    except Exception as e:
        print(f"    Error: {e}")

    # 2. Top Artists -> Top Tracks
    print("  Fetching Top Artists and their top tracks...")
    try:
        top_artists = user.get_top_artists(period=pylast.PERIOD_OVERALL, limit=30) # Top 30 artists
        
        for i, item in enumerate(top_artists, 1):
            artist = item.item
            print(f"    [{i}/30] {artist.name}")
            try:
                tracks = artist.get_top_tracks(limit=limit_per_artist)
                for t in tracks:
                    track = t.item
                    key = f"{track.artist.name} - {track.title}"
                    if key not in universe_tracks:
                        universe_tracks[key] = {
                            "artist": track.artist.name,
                            "title": track.title,
                            "source": "artist_top_tracks"
                        }
                time.sleep(0.2)
            except Exception as e:
                print(f"      Error fetching tracks for {artist.name}: {e}")
                
    except Exception as e:
        print(f"    Error fetching artists: {e}")

    # 3. Recommendations (Similar to Top 5 Artists)
    print("  Fetching Recommendations...")
    try:
        top_5 = user.get_top_artists(period=pylast.PERIOD_OVERALL, limit=5)
        for item in top_5:
            artist = item.item
            print(f"    Similar to {artist.name}...")
            try:
                similar = artist.get_similar(limit=5)
                for sim_item in similar:
                    sim_artist = sim_item.item
                    try:
                        tracks = sim_artist.get_top_tracks(limit=3)
                        for t in tracks:
                            track = t.item
                            key = f"{track.artist.name} - {track.title}"
                            if key not in universe_tracks:
                                universe_tracks[key] = {
                                    "artist": track.artist.name,
                                    "title": track.title,
                                    "source": "recommendation"
                                }
                        time.sleep(0.2)
                    except:
                        pass
            except Exception as e:
                print(f"      Error: {e}")
                
    except Exception as e:
        print(f"    Error fetching recommendations: {e}")
        
    print(f"Total unique tracks found: {len(universe_tracks)}")
    return list(universe_tracks.values())
