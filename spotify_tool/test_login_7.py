import spotapi
from spotapi import Login, Config, NoopLogger
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

    print("\nFetching Top Tracks with authenticate=True...")
    url_top = "https://api.spotify.com/v1/me/top/tracks?limit=5"
    
    try:
        # TLSClient.get(url, authenticate=True)
        # We need to see if 'authenticate' param is accepted.
        # Based on inspect_song.py, it is accepted by self.base.client.post.
        # self.base.client IS the TLSClient (or similar).
        
        resp = login.client.get(url_top, authenticate=True)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text[:200]}...")
        
    except TypeError as te:
        print(f"TypeError: {te} - maybe 'authenticate' is not a valid arg for get()?")
        # Try passing it in **kwargs if supported, or check signature if possible.
    except Exception as e:
        print(f"Error fetching top tracks: {e}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
