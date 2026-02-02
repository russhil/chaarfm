import spotapi
from spotapi import Login, Config, NoopLogger, Player, PrivatePlaylist
import json

sp_dc = "AQDGwVh2qOgNjz3Wg0pOUex9BQoaffQLNmOpRF-MsQRBW8eM1P82nkgg2e_3noaLXDswAFa6m0ta5hNzqpm6HrCoMsH5mGkSgLufx9cOvPS_WVDHmFGe-zvZ4GdvrkUVGPbh_TbNwErSz882MCBuPaHb8_tdqhATX1tqIBCfo3hZXSbq1HSHhiu3vqmhaNmi7sl8NsXWiPijgQqDdQ"
identifier = "hello@russhil.com"

cfg = Config(logger=NoopLogger())
dump = {
    "identifier": identifier,
    "cookies": {
        "sp_dc": sp_dc
    }
}

print("Attempting login...")
try:
    login = Login.from_cookies(dump, cfg)
    print("Login successful.")

    # 1. Recently Played (History)
    print("\nFetching Recently Played (Player.last_songs_played)...")
    player = Player(login)
    try:
        # Check if last_songs_played is a method or property
        # dir(Player) showed it.
        # Based on explore_spotapi_2.py, it's in the list.
        # Let's assume it's a property or method.
        # If it's a property, just accessing it might trigger fetch or return cached.
        # But 'Player' likely needs to initialize state.
        
        # Player usually controls the active player.
        # 'last_songs_played' might be the history.
        
        history = player.last_songs_played
        print(f"History Type: {type(history)}")
        print(f"History: {history}")
        
    except Exception as e:
        print(f"Error fetching history: {e}")

    # 2. Liked Songs (Library)
    print("\nFetching Liked Songs (PrivatePlaylist.get_library)...")
    pp = PrivatePlaylist(login)
    try:
        # get_library might return liked songs
        library = pp.get_library()
        print(f"Library Type: {type(library)}")
        # print(f"Library: {library}") # Might be large
        
        if isinstance(library, dict) and 'items' in library:
            print(f"Got {len(library['items'])} items.")
        elif isinstance(library, list):
             print(f"Got {len(library)} items.")
        else:
             print("Library structure unknown.")
             
    except Exception as e:
        print(f"Error fetching library: {e}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
