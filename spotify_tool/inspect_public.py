import spotapi
from spotapi import Public
import inspect

try:
    print("Dir of Public:")
    print(dir(Public))
    
    # Try to see how it gets token
    print("\nSource of Public.__init__:")
    # print(inspect.getsource(Public.__init__))
    
    # Instantiate Public
    p = Public()
    print("\nPublic instance created.")
    print("Dir of p:")
    print(dir(p))
    print(f"p.client type: {type(p.client)}")
    
    # Check if p.client has access_token
    # Public likely uses Client Credentials or anonymous token?
    # But for "Top Tracks", we need User context.
    
except Exception as e:
    print(f"Error: {e}")
