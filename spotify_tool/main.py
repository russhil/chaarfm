import json
import os
import requests
from spotapi import Login, Config, NoopLogger

def get_credentials():
    """
    Prompt user for sp_dc cookie and identifier.
    """
    print("Please enter your Spotify 'sp_dc' cookie.")
    print("To find this: Open Spotify in your browser, open Developer Tools (F12), go to Application/Storage -> Cookies, and copy the value of 'sp_dc'.")
    sp_dc = input("sp_dc: ").strip()
    
    print("\nPlease enter your Spotify username or email (identifier).")
    identifier = input("Identifier: ").strip()
    
    return sp_dc, identifier

def main():
    print("--- Spotify Data Extractor ---")
    
    sp_dc, identifier = get_credentials()
    
    print("\nLogging in...")
    cfg = Config(logger=NoopLogger())
    
    # Construct the dump object as expected by Login.from_cookies
    dump = {
        "identifier": identifier,
        "cookies": {
            "sp_dc": sp_dc
        }
    }
    
    try:
        # Create Login instance from cookies
        login = Login.from_cookies(dump, cfg)
        
        # Access the client and token
        token = login.client.access_token
        
        if not token:
            print("Access token not found immediately. Attempting to refresh session...")
            # Some implementations might need a refresh or a request to populate token
            # But usually from_cookies sets it up.
            pass
            
        if not token:
             # Try to get it from client if it's a property that computes it
             login.client.get_client_token()
             # Or check if login.client.access_token is populated now
             token = login.client.access_token

        if not token:
             print("Could not retrieve access token. The cookie might be invalid or expired.")
             return

        print(f"Got access token: {token[:10]}...")
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        # 1. Get Top Tracks
        print("\nFetching Top Tracks...")
        top_tracks = {}
        for term in ["short_term", "medium_term", "long_term"]:
            print(f"  Fetching {term}...")
            url = f"https://api.spotify.com/v1/me/top/tracks?limit=50&time_range={term}"
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get("items", [])
                top_tracks[term] = data
                print(f"    Got {len(data)} tracks.")
            else:
                print(f"    Failed to fetch {term}: {resp.status_code} {resp.text}")
        
        # 2. Get Recently Played
        print("\nFetching Recently Played...")
        url = "https://api.spotify.com/v1/me/player/recently-played?limit=50"
        resp = requests.get(url, headers=headers)
        recently_played = []
        if resp.status_code == 200:
            recently_played = resp.json().get("items", [])
            print(f"  Got {len(recently_played)} tracks.")
        else:
            print(f"  Failed to fetch recently played: {resp.status_code} {resp.text}")
            
        # Save to file
        output = {
            "user_identifier": identifier,
            "top_tracks": top_tracks,
            "recently_played": recently_played
        }
        
        output_file = "spotify_data.json"
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)
            
        print(f"\nDone! Data saved to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
