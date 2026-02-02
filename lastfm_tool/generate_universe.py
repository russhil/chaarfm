import pylast
import json
import os
import certifi
import httpx
import time
from collections import defaultdict

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
USERNAME = "russhil"

def get_familiar_music(user):
    print("Building Music Universe (Familiar Music)...")
    
    universe = {
        "artists": {},
        "tracks": {},
        "genres": defaultdict(int)
    }
    
    periods = [
        (pylast.PERIOD_7DAYS, "7day"),
        (pylast.PERIOD_1MONTH, "1month"),
        (pylast.PERIOD_3MONTHS, "3month"),
        (pylast.PERIOD_6MONTHS, "6month"),
        (pylast.PERIOD_12MONTHS, "12month"),
        (pylast.PERIOD_OVERALL, "overall")
    ]
    
    # 1. Top Artists (across all periods to capture phases)
    for period_val, period_name in periods:
        print(f"  Fetching Top Artists ({period_name})...")
        try:
            top_artists = user.get_top_artists(period=period_val, limit=50)
            for item in top_artists:
                artist_name = item.item.name
                playcount = int(item.weight)
                
                if artist_name not in universe["artists"]:
                    universe["artists"][artist_name] = {
                        "playcount": 0,
                        "periods": []
                    }
                
                # We store the max playcount seen (usually 'overall' has max, but good to be safe)
                universe["artists"][artist_name]["playcount"] = max(universe["artists"][artist_name]["playcount"], playcount)
                universe["artists"][artist_name]["periods"].append(period_name)
                
                # Get tags for genre analysis (only for top 20 overall to save requests)
                if period_name == "overall" and len(universe["artists"]) <= 20:
                    try:
                        tags = item.item.get_top_tags(limit=3)
                        for tag in tags:
                            universe["genres"][tag.item.name] += 1
                    except:
                        pass
        except Exception as e:
            print(f"    Error fetching {period_name} artists: {e}")

    # 2. Top Tracks
    print("  Fetching Top Tracks (Overall)...")
    try:
        top_tracks = user.get_top_tracks(period=pylast.PERIOD_OVERALL, limit=100)
        for item in top_tracks:
            track = item.item
            track_key = f"{track.artist.name} - {track.title}"
            universe["tracks"][track_key] = {
                "artist": track.artist.name,
                "title": track.title,
                "playcount": item.weight
            }
    except Exception as e:
        print(f"    Error fetching top tracks: {e}")

    # 3. Loved Tracks
    print("  Fetching Loved Tracks...")
    try:
        loved_tracks = user.get_loved_tracks(limit=100)
        for item in loved_tracks:
            track = item.track
            track_key = f"{track.artist.name} - {track.title}"
            if track_key not in universe["tracks"]:
                universe["tracks"][track_key] = {
                    "artist": track.artist.name,
                    "title": track.title,
                    "playcount": 0 # Unknown if not in top tracks
                }
            universe["tracks"][track_key]["loved"] = True
    except Exception as e:
        print(f"    Error fetching loved tracks: {e}")
        
    return universe

def get_extended_pool(user, familiar_artists):
    print("\nGenerating Extended Pool (Recommendations)...")
    
    recommendations = {
        "artists": [],
        "source": "algorithm"
    }
    
    # Method 1: Get Similar Artists for Top 5 Overall Artists
    # Since get_recommended_artists might require authentication that pylast handles differently or is deprecated,
    # we use 'similar artists' as a robust fallback.
    
    print("  Fetching Similar Artists based on your Top 5...")
    top_5_artists = sorted(familiar_artists.items(), key=lambda x: x[1]['playcount'], reverse=True)[:5]
    
    seen_artists = set(familiar_artists.keys())
    
    for artist_name, data in top_5_artists:
        print(f"    Finding artists similar to {artist_name}...")
        try:
            # We need an Artist object
            artist = pylast.Artist(artist_name, user.network)
            similar = artist.get_similar(limit=10)
            
            for item in similar:
                sim_artist_name = item.item.name
                match_score = item.match
                
                if sim_artist_name not in seen_artists:
                    recommendations["artists"].append({
                        "name": sim_artist_name,
                        "similar_to": artist_name,
                        "match_score": match_score
                    })
                    seen_artists.add(sim_artist_name) # Avoid duplicates in list
        except Exception as e:
            print(f"    Error getting similar artists for {artist_name}: {e}")
            
    return recommendations

def main():
    try:
        network = pylast.LastFMNetwork(api_key=API_KEY, api_secret=API_SECRET)
        user = network.get_user(USERNAME)
        print(f"Connected as {user.get_name()}")
        
        # 1. Build Universe
        universe = get_familiar_music(user)
        
        # 2. Build Extended Pool
        extended_pool = get_extended_pool(user, universe["artists"])
        
        # 3. Compile Report
        final_data = {
            "user": USERNAME,
            "stats": {
                "familiar_artists_count": len(universe["artists"]),
                "familiar_tracks_count": len(universe["tracks"]),
                "top_genres": sorted(universe["genres"].items(), key=lambda x: x[1], reverse=True)[:10]
            },
            "music_universe": universe,
            "extended_pool": extended_pool
        }
        
        with open("music_universe.json", "w") as f:
            json.dump(final_data, f, indent=2, default=str)
            
        print("\nExtraction Complete!")
        print(f"Saved {len(universe['artists'])} artists and {len(universe['tracks'])} tracks to your universe.")
        print(f"Found {len(extended_pool['artists'])} recommended artists for your extended pool.")
        print("Data saved to 'music_universe.json'.")
        
    except Exception as e:
        print(f"Fatal Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
