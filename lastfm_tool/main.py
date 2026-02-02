import pylast
import json
import os
import time

def get_credentials():
    print("Please enter your Last.fm API Key.")
    api_key = input("API Key: ").strip()
    
    print("Please enter your Last.fm API Secret (leave empty if you don't have one, though pylast might require it).")
    api_secret = input("API Secret: ").strip()
    
    print("Please enter the Last.fm Username you want to fetch data for.")
    username = input("Username: ").strip()
    
    return api_key, api_secret, username

def main():
    print("--- Last.fm Data Extractor ---")
    
    api_key, api_secret, username = get_credentials()
    
    if not api_key or not username:
        print("API Key and Username are required.")
        return

    # If secret is missing, try to init with just key or empty secret
    if not api_secret:
        api_secret = "dummy_secret" # pylast might need a string, but for read-only calls it might not check it on server side if using just API key auth?
        # Actually pylast uses md5(secret) for signing, which is needed for write ops or auth. 
        # For get_user, maybe it's not needed.
    
    try:
        network = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret)
        
        user = network.get_user(username)
        print(f"Fetching data for user: {user.get_name()}")
        
        # 1. Top Tracks
        print("\nFetching Top Tracks (Overall)...")
        # pylast returns TopItem objects
        top_tracks_objs = user.get_top_tracks(period=pylast.PERIOD_OVERALL, limit=50)
        
        top_tracks = []
        for item in top_tracks_objs:
            track = item.item
            top_tracks.append({
                "rank": item.weight, # In get_top_tracks, weight is usually rank or playcount? It's weight.
                "artist": track.artist.name,
                "title": track.title,
                "playcount": item.weight # weight matches playcount for top tracks
            })
            
        print(f"  Got {len(top_tracks)} top tracks.")
        
        # 2. Recent Tracks
        print("\nFetching Recent Tracks...")
        recent_tracks_objs = user.get_recent_tracks(limit=50)
        
        recent_tracks = []
        for item in recent_tracks_objs:
            track = item.track
            recent_tracks.append({
                "artist": track.artist.name,
                "title": track.title,
                "album": item.album,
                "timestamp": item.timestamp,
                "date": item.playback_date
            })
            
        print(f"  Got {len(recent_tracks)} recent tracks.")
        
        # Save to file
        output = {
            "username": username,
            "top_tracks": top_tracks,
            "recent_tracks": recent_tracks
        }
        
        with open("lastfm_data.json", "w") as f:
            json.dump(output, f, indent=2, default=str)
            
        print("\nDone! Data saved to lastfm_data.json")
        
    except pylast.WSError as e:
        print(f"Last.fm API Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
