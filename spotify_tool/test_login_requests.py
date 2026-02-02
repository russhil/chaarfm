import requests
import json

sp_dc = "AQDGwVh2qOgNjz3Wg0pOUex9BQoaffQLNmOpRF-MsQRBW8eM1P82nkgg2e_3noaLXDswAFa6m0ta5hNzqpm6HrCoMsH5mGkSgLufx9cOvPS_WVDHmFGe-zvZ4GdvrkUVGPbh_TbNwErSz882MCBuPaHb8_tdqhATX1tqIBCfo3hZXSbq1HSHhiu3vqmhaNmi7sl8NsXWiPijgQqDdQ"

print("Fetching access token using requests...")
url_token = "https://open.spotify.com/get_access_token?reason=transport&productType=web_player"

headers = {
    "Referer": "https://open.spotify.com/",
    "Origin": "https://open.spotify.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": f"sp_dc={sp_dc}",
    "App-Platform": "WebPlayer"
}

try:
    resp = requests.get(url_token, headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:200]}...") 
    
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("accessToken")
        print(f"Got Token: {token[:10]}...")
        
        if token:
            print("\nFetching Top Tracks with Token...")
            headers_api = {
                "Authorization": f"Bearer {token}",
                "User-Agent": headers["User-Agent"]
            }
            url_top = "https://api.spotify.com/v1/me/top/tracks?limit=5"
            resp_top = requests.get(url_top, headers=headers_api)
            print(f"Status: {resp_top.status_code}")
            print(f"Response: {resp_top.text[:200]}...")
    else:
        print("Failed to get token.")
        
except Exception as e:
    print(f"Error fetching token: {e}")
