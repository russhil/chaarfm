import spotapi
from spotapi import Login, Config, NoopLogger, User
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
    print("Login object created.")
    
    print("Dir of login:")
    print(dir(login))
    
    # Check if there is a 'token' or 'access_token' in login attributes
    # or inside 'client' cookies?
    
    print("\nLogin Cookies:")
    print(login.client.cookies)
    
    # Try to create a User instance
    print("\nCreating User instance...")
    user = User(login)
    print("User instance created.")
    print("Dir of user:")
    print(dir(user))
    
    # Check if User has access_token
    # Or if we can get it from somewhere.
    
    # If we can't find access_token, maybe we can use the cookies directly for requests?
    # But standard Web API needs Bearer token.
    # The private API might use cookies.
    # But my script uses standard Web API.
    
    # Maybe we need to fetch the token using the cookies.
    # 'spotapi' might have a method for that.
    
    # Check 'login.get_access_token' or similar?
    # In dir(login) from previous step, we saw:
    # ['... '_get_add_cookie', '_get_session', '_password_payload', '_set_non_otc', '_submit_password', 'client', 'csrf_token', 'flow_id', 'from_cookies', 'from_saver', 'handle_login_error', 'identifier_credentials', 'logged_in', 'logger', 'login', 'password', 'save', 'solver']
    
    # None of them look like 'get_access_token'.
    
    # However, 'spotapi' claims to be a wrapper for private API.
    # Maybe I should use 'spotapi' methods instead of 'requests.get'?
    # But I wanted to use standard Web API endpoints for top tracks.
    
    # If I can't get the access token easily, I might have to use 'spotapi' features.
    # Does 'spotapi' support top tracks?
    # 'Song' module? 'User' module?
    
    # Let's check 'User' module attributes more closely.
    # 'get_user_info'?
    
    # Let's try to get the token by making a request to 'https://open.spotify.com/get_access_token' using the cookies.
    # This is a common way to get it.
    
    print("\nAttempting to fetch token manually via open.spotify.com/get_access_token...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Cookie": f"sp_dc={sp_dc}"
    }
    import requests
    resp = requests.get("https://open.spotify.com/get_access_token?reason=transport&productType=web_player", headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"Token from web: {data.get('accessToken')}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
