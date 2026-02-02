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
    
    print("\nClient Headers:")
    print(login.client.headers)
    
    print("\nCalling _get_session()...")
    try:
        session = login._get_session()
        print(f"Session type: {type(session)}")
        print(f"Session: {session}")
    except Exception as e:
        print(f"Error calling _get_session: {e}")

    # Check if we can extract token from headers
    if "authorization" in login.client.headers:
        print(f"Authorization header found: {login.client.headers['authorization']}")
    elif "Authorization" in login.client.headers:
        print(f"Authorization header found: {login.client.headers['Authorization']}")
        
    # Try calling get_user_info
    print("\nCalling User.get_user_info()...")
    user = User(login)
    try:
        info = user.get_user_info()
        print("User info retrieved.")
        print(info.keys())
    except Exception as e:
        print(f"Error calling get_user_info: {e}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
