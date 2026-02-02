import spotapi
from spotapi import Login, Config, NoopLogger
import inspect

sp_dc = "AQDGwVh2qOgNjz3Wg0pOUex9BQoaffQLNmOpRF-MsQRBW8eM1P82nkgg2e_3noaLXDswAFa6m0ta5hNzqpm6HrCoMsH5mGkSgLufx9cOvPS_WVDHmFGe-zvZ4GdvrkUVGPbh_TbNwErSz882MCBuPaHb8_tdqhATX1tqIBCfo3hZXSbq1HSHhiu3vqmhaNmi7sl8NsXWiPijgQqDdQ"
identifier = "hello@russhil.com"

cfg = Config(logger=NoopLogger())
dump = {
    "identifier": identifier,
    "cookies": {
        "sp_dc": sp_dc
    }
}

try:
    login = Login.from_cookies(dump, cfg)
    print("Inspecting login.client.authenticate:")
    try:
        print(inspect.getsource(login.client.authenticate))
    except Exception as e:
        print(f"Could not get source: {e}")
        # Try signature
        print(f"Signature: {inspect.signature(login.client.authenticate)}")

    # Check if there is an 'access_token' attribute on login.client that is hidden?
    # No, dir() showed everything.
    
    # Check if 'login.client' has a 'session' or 'base' attribute?
    # No 'base'.
    
    # Maybe check spotapi.client.BaseClient again?
    # Does TLSClient inherit from it?
    # In test_login.py: Is instance of BaseClient? False.
    
    # So TLSClient is standalone.
    
except Exception as e:
    print(f"Error: {e}")
