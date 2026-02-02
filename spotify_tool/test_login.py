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
    print("Login object created.")
    print(f"Type of login: {type(login)}")
    print(f"Type of login.client: {type(login.client)}")
    print("Dir of login.client:")
    print(dir(login.client))
    
    # Try to find access token
    if hasattr(login.client, "access_token"):
        print(f"access_token: {login.client.access_token}")
    else:
        print("access_token attribute NOT found on login.client")
        
    # Check if we can get it via get_client_token if it exists
    if hasattr(login.client, "get_client_token"):
         print("Calling get_client_token()...")
         try:
             res = login.client.get_client_token()
             print(f"Result: {res}")
         except Exception as e:
             print(f"Error calling get_client_token: {e}")

    # Check BaseClient
    print(f"\nIs instance of BaseClient? {isinstance(login.client, spotapi.BaseClient)}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
