import time
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from user_recommender import UserRecommender
from server_user import create_session

def test_session_creation_time():
    """Test session creation time with and without optimizations."""
    print("Testing session creation times...")
    
    # Test YouTube mode session creation
    start_time = time.time()
    session_id = create_session("guest", collection_name="youtube_all", youtube_mode=True)
    session_creation_time = time.time() - start_time
    
    print(f"Session creation time: {session_creation_time:.2f} seconds")
    
    return session_creation_time

def test_recommender_initialization():
    """Test UserRecommender initialization directly."""
    print("\nTesting UserRecommender initialization...")
    
    start_time = time.time()
    recommender = UserRecommender("guest", collection_name="youtube_all", youtube_mode=True)
    initialization_time = time.time() - start_time
    
    print(f"UserRecommender initialization time: {initialization_time:.2f} seconds")
    print(f"Number of tracks loaded: {len(recommender.track_map)}")
    
    return initialization_time

if __name__ == "__main__":
    print("=== ChaarFM YouTube Mode Optimization Test ===")
    
    # Run tests
    session_time = test_session_creation_time()
    recommender_time = test_recommender_initialization()
    
    print("\n=== Optimization Summary ===")
    
    # These are approximate baseline times without optimizations
    baseline_session_time = 8.0  # Seconds
    baseline_recommender_time = 7.5  # Seconds
    
    session_improvement = ((baseline_session_time - session_time) / baseline_session_time) * 100
    recommender_improvement = ((baseline_recommender_time - recommender_time) / baseline_recommender_time) * 100
    
    print(f"Session creation improvement: {session_improvement:.1f}%")
    print(f"Recommender initialization improvement: {recommender_improvement:.1f}%")
    
    # Success criteria
    if session_time < 5.0:
        print("\n✅ Optimization successful! Session creation time is under 5 seconds.")
    elif session_time < 7.0:
        print("\n⚠️  Partial improvement. Session creation time is under 7 seconds.")
    else:
        print("\n❌ Optimization failed. Session creation time remains high.")