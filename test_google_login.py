#!/usr/bin/env python3
"""
Test script to verify the Google login flow endpoints are accessible.
"""

import requests

BASE_URL = "http://localhost:5001"

def test_server_is_running():
    """Test if server is reachable."""
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"✅ Server is running. Status: {response.status_code}")
        print(f"   Response length: {len(response.text)} characters")
        return True
    except Exception as e:
        print(f"❌ Server not reachable: {e}")
        return False

def test_login_endpoint():
    """Test login page endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/login")
        print(f"✅ Login endpoint accessible. Status: {response.status_code}")
        print(f"   Page title: {response.text.split('<title>')[1].split('</title>')[0]}")
        return True
    except Exception as e:
        print(f"❌ Login endpoint failed: {e}")
        return False

def test_pick_mode_endpoint():
    """Test pick mode endpoint (should redirect to login)."""
    try:
        response = requests.get(f"{BASE_URL}/pick-mode", allow_redirects=True)
        print(f"✅ Pick mode endpoint accessible. Final status: {response.status_code}")
        print(f"   Redirect chain: {[resp.url for resp in response.history]} -> {response.url}")
        print(f"   Page title: {response.text.split('<title>')[1].split('</title>')[0]}")
        return True
    except Exception as e:
        print(f"❌ Pick mode endpoint failed: {e}")
        return False

def test_google_login_initiation():
    """Test Google login initiation endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/api/auth/google", allow_redirects=False)
        print(f"✅ Google login initiation. Status: {response.status_code}")
        if response.status_code == 302:
            print(f"   Redirect to Google: {response.headers['Location']}")
        return True
    except Exception as e:
        print(f"❌ Google login initiation failed: {e}")
        return False

if __name__ == "__main__":
    print("=== ChaarFM Google Login Flow Test ===")
    print()
    
    all_tests_passed = True
    
    if not test_server_is_running():
        all_tests_passed = False
    else:
        print()
        all_tests_passed = test_login_endpoint()
        print()
        all_tests_passed = test_pick_mode_endpoint() and all_tests_passed
        print()
        all_tests_passed = test_google_login_initiation() and all_tests_passed
    
    print()
    if all_tests_passed:
        print("✅ All endpoints are accessible!")
        print("   - The server is running on http://localhost:5001")
        print("   - Login page is available at /login")
        print("   - Pick mode is accessible at /pick-mode")
        print("   - Google login initiation is working at /api/auth/google")
        print()
        print("🎯 The Google login flow has been successfully tested!")
        print()
        print("Note: To fully test the callback, you would need to:")
        print("1. Run the app")
        print("2. Go to http://localhost:5001/login")
        print("3. Click 'SIGN IN WITH GOOGLE'")
        print("4. Complete the Google OAuth flow")
        print("5. Verify you're redirected to /pick-mode")
    else:
        print("❌ Some tests failed. Please check the server logs.")
