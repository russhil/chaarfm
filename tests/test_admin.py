import requests
import json

BASE_URL = "http://localhost:5002"

def test_flow():
    # 1. Login
    print("Logging in...")
    resp = requests.post(f"{BASE_URL}/api/login", json={"username": "russhil", "password": "123", "vectormap": "music_averaged"})
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        # Try creating the user if password fails (it shouldn't if DB is init, but maybe password is wrong?)
        # DB init uses hash of '10811' for russhil.
        resp = requests.post(f"{BASE_URL}/api/login", json={"username": "russhil", "password": "10811", "vectormap": "music_averaged"})
        
    if resp.status_code != 200:
        print(f"Login failed again: {resp.text}")
        return

    data = resp.json()
    session_id = data["session_id"]
    print(f"Session ID: {session_id}")
    
    # 2. Access Admin
    print("Accessing Admin...")
    resp = requests.get(f"{BASE_URL}/admin?session_id={session_id}")
    if resp.status_code == 200:
        print("Admin page accessed successfully!")
    else:
        print(f"Admin access failed: {resp.status_code} {resp.text}")

    # 3. Access Admin Stats
    print("Accessing Stats...")
    resp = requests.get(f"{BASE_URL}/api/admin/stats?session_id={session_id}")
    if resp.status_code == 200:
        print("Stats accessed successfully!")
        print(json.dumps(resp.json(), indent=2)[:200]) # Print snippet
    else:
        print(f"Stats access failed: {resp.status_code} {resp.text}")
        
    # 4. Chat (Simulate)
    # This requires an API key, so we'll just check if the endpoint exists and validates input
    print("Testing Chat Endpoint...")
    resp = requests.post(f"{BASE_URL}/api/admin/chat", json={
        "user_id": "russhil",
        "message": "Hello",
        "api_key": "dummy_key"
    })
    # Expecting error from Google API, but 200 from our server wrapping the error
    if resp.status_code == 200:
        print("Chat endpoint reachable!")
        print(resp.json())
    else:
        print(f"Chat endpoint failed: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    test_flow()
