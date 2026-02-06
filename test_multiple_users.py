#!/usr/bin/env python3
"""
Test Multiple User Sessions - Verify that concurrent users work correctly
"""

import asyncio
import aiohttp
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://localhost:5001"

async def create_session(session_http, user_id, collection="music_averaged", mode="classic"):
    """Create a session for a user"""
    print(f"🆕 Creating session for {user_id}...")
    
    # Login first
    login_data = {"username": user_id, "password": ""}
    async with session_http.post(f"{BASE_URL}/api/login", json=login_data) as resp:
        if resp.status != 200:
            print(f"❌ Login failed for {user_id}: {resp.status}")
            return None
        login_result = await resp.json()
        print(f"✅ {user_id} logged in: {login_result}")
    
    # Start session
    session_data = {"mode": mode, "collection": collection}
    async with session_http.post(f"{BASE_URL}/api/session/start", json=session_data) as resp:
        if resp.status != 200:
            print(f"❌ Session creation failed for {user_id}: {resp.status}")
            return None
        result = await resp.json()
        session_id = result.get("session_id")
        print(f"✅ Session created for {user_id}: {session_id[:8]}...")
        return session_id

async def test_user_session(user_id, session_id, num_tracks=5):
    """Test a user session with multiple track requests"""
    print(f"🎵 Testing {num_tracks} tracks for {user_id}...")
    
    async with aiohttp.ClientSession() as session_http:
        track_results = []
        
        for i in range(num_tracks):
            try:
                # Get next track
                async with session_http.get(f"{BASE_URL}/api/next?session_id={session_id}") as resp:
                    if resp.status != 200:
                        print(f"❌ Track request failed for {user_id}: {resp.status}")
                        break
                    
                    track = await resp.json()
                    track_id = track.get("id")
                    title = track.get("title", "Unknown")
                    justification = track.get("justification", "")
                    
                    print(f"  🎶 {user_id}: Track {i+1} - {title} ({justification})")
                    track_results.append({
                        "user": user_id,
                        "track_num": i+1,
                        "track_id": track_id,
                        "title": title,
                        "justification": justification
                    })
                    
                    # Simulate listening for random duration
                    listen_duration = 15 + (i * 10)  # Increasing engagement
                    
                    # Send feedback
                    feedback_data = {"id": track_id, "duration": listen_duration}
                    async with session_http.post(f"{BASE_URL}/api/feedback?session_id={session_id}", json=feedback_data) as feedback_resp:
                        if feedback_resp.status == 200:
                            print(f"    ✅ Feedback sent: {listen_duration}s")
                        else:
                            print(f"    ❌ Feedback failed: {feedback_resp.status}")
                    
                    # Small delay between tracks
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                print(f"❌ Error for {user_id} on track {i+1}: {e}")
                break
        
        return track_results

async def get_session_stats():
    """Get current session statistics from server"""
    async with aiohttp.ClientSession() as session_http:
        try:
            async with session_http.get(f"{BASE_URL}/api/session-stats") as resp:
                if resp.status == 200:
                    stats = await resp.json()
                    return stats
                else:
                    print(f"❌ Failed to get session stats: {resp.status}")
                    return None
        except Exception as e:
            print(f"❌ Error getting session stats: {e}")
            return None

async def main():
    """Test multiple users concurrently"""
    print("🚀 Testing Multiple User Sessions")
    print("=" * 50)
    
    # Test configuration
    users = ["alice", "bob", "charlie", "diana"]
    collections = ["music_averaged", "music_averaged", "music_averaged", "music_averaged"]
    
    # Create sessions for all users
    sessions = {}
    async with aiohttp.ClientSession() as session_http:
        for user, collection in zip(users, collections):
            session_id = await create_session(session_http, user, collection)
            if session_id:
                sessions[user] = session_id
            
            # Small delay between session creation
            await asyncio.sleep(0.2)
    
    print(f"\n📊 Created {len(sessions)} sessions")
    
    # Check session stats
    stats = await get_session_stats()
    if stats:
        print(f"📈 Session Stats: {stats['total_sessions']} total, {stats['unique_users']} users")
        print(f"    Users: {stats['users']}")
    
    # Test concurrent usage
    print("\n🎶 Testing concurrent music playback...")
    
    tasks = []
    for user, session_id in sessions.items():
        task = asyncio.create_task(test_user_session(user, session_id, num_tracks=3))
        tasks.append(task)
    
    # Run all user sessions concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\n📊 Results Summary:")
    print("=" * 50)
    
    for i, result in enumerate(results):
        user = list(sessions.keys())[i]
        if isinstance(result, Exception):
            print(f"❌ {user}: Error - {result}")
        else:
            print(f"✅ {user}: Completed {len(result)} tracks")
            for track_result in result:
                print(f"    • {track_result['title']}")
    
    # Final session stats
    print("\n📈 Final Session Stats:")
    final_stats = await get_session_stats()
    if final_stats:
        print(f"    Total Sessions: {final_stats['total_sessions']}")
        print(f"    Unique Users: {final_stats['unique_users']}")
        print(f"    User Breakdown: {final_stats['users']}")
    
    # Cleanup - logout all sessions
    print("\n🧹 Cleaning up sessions...")
    async with aiohttp.ClientSession() as session_http:
        for user, session_id in sessions.items():
            try:
                async with session_http.post(f"{BASE_URL}/api/logout?session_id={session_id}") as resp:
                    if resp.status == 200:
                        print(f"    ✅ {user} logged out")
                    else:
                        print(f"    ⚠️ {user} logout status: {resp.status}")
            except Exception as e:
                print(f"    ❌ {user} logout error: {e}")

if __name__ == "__main__":
    print("🎵 ChaarFM Multiple User Test")
    print("Make sure the server is running on localhost:5001")
    print()
    
    try:
        asyncio.run(main())
        print("\n✅ Test completed successfully!")
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()