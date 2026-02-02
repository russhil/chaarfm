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

    # 1. Try to get access token using login.client
    print("\nFetching access token using login.client...")
    url_token = "https://open.spotify.com/get_access_token?reason=transport&productType=web_player"
    try:
        # Note: TLSClient.get returns a response object
        resp = login.client.get(url_token)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text[:200]}...") # Print first 200 chars
        
        token = None
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("accessToken")
            print(f"Got Token: {token[:10]}...")
            
            # If we got a token, try to use it for Top Tracks
            if token:
                print("\nFetching Top Tracks with Token...")
                headers = {"Authorization": f"Bearer {token}"}
                url_top = "https://api.spotify.com/v1/me/top/tracks?limit=5"
                # Use login.client or requests? Use login.client to be safe with TLS, but headers are custom
                # TLSClient.get(url, headers=...)
                resp_top = login.client.get(url_top, headers=headers)
                print(f"Status: {resp_top.status_code}")
                print(f"Response: {resp_top.text[:200]}...")
        else:
            print("Failed to get token.")
            
    except Exception as e:
        print(f"Error fetching token: {e}")

    # 2. Try to get Top Tracks WITHOUT token (just cookies)
    print("\nFetching Top Tracks with just cookies...")
    url_top = "https://api.spotify.com/v1/me/top/tracks?limit=5"
    try:
        resp_top_cookie = login.client.get(url_top)
        print(f"Status: {resp_top_cookie.status_code}")
        print(f"Response: {resp_top_cookie.text[:200]}...")
    except Exception as e:
        print(f"Error fetching top tracks (cookies): {e}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
