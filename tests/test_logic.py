
import sys
import os
import numpy as np

# Mocking user_db and other dependencies
class MockUserDB:
    engine = None
    def update_cluster_affinity(self, *args, **kwargs): pass
    def update_cluster_centroid(self, *args, **kwargs): pass

sys.modules['user_db'] = MockUserDB()

# Import the recommender
from user_recommender import UserRecommender, QUICK_SKIP_SEC

def test_recommender_logic():
    print("Testing Recommender Logic...")
    
    rec = UserRecommender()
    
    # Mock data
    rec.track_map = {
        "t1": {"id": "t1", "filename": "Track 1", "vector": [1.0, 0.0, 0.0]},
        "t2": {"id": "t2", "filename": "Track 2", "vector": [0.9, 0.1, 0.0]},
        "t3": {"id": "t3", "filename": "Track 3", "vector": [0.8, 0.2, 0.0]},
        "t4": {"id": "t4", "filename": "Track 4", "vector": [0.0, 1.0, 0.0]},
        "t5": {"id": "t5", "filename": "Track 5", "vector": [0.0, 0.9, 0.1]},
    }
    rec.cluster_manager.track_map = rec.track_map
    rec.cluster_manager.n_clusters = 2
    rec.cluster_manager.fit()
    rec.init_bandit() # Re-init bandit scores

    
    # 1. Cold Start
    print("\n--- Cold Start ---")
    t, reason = rec.get_next_track()
    print(f"Track: {t['filename']}, Reason: {reason}")
    assert "Exploiting" not in reason, "Should not exploit on cold start"
    
    # 2. User Likes Track (> 5s)
    print("\n--- User Listens > 5s (Green Signal) ---")
    rec.record_feedback("t1", 6.0) # > QUICK_SKIP_SEC (5.0)
    print(f"Streak: {rec.streak}, User Vector: {rec.user_vector}")
    assert rec.streak >= 1, "Streak should increment on >5s play"
    assert rec.user_vector is not None, "User vector should be initialized"
    
    # 3. Verify Lock-in (100% Exploit)
    print("\n--- Verifying Lock-in ---")
    t, reason = rec.get_next_track()
    print(f"Track: {t['filename']}, Reason: {reason}")
    assert "Locked in" in reason or "Exploiting" in reason, "Should be locked in"
    
    # 4. Verify No Random Exploration in Batch
    print("\n--- Verifying Batch Consistency ---")
    batch = rec.get_next_batch()
    for item in batch:
        print(f"Batch Item: {item['filename']}, Reason: {item['justification']}")
        assert "Exploiting" in item['justification'] or "Locked in" in item['justification'], "Batch item should be exploit"
        assert "Drift injection" not in item['justification'], "No drift injection allowed when locked in"

    # 5. Verify Boredom Trigger (Skip < 5s)
    print("\n--- Triggering Boredom (Skip < 5s) ---")
    rec.record_feedback("t2", 2.0) # Skip
    print(f"Streak: {rec.streak}, Drift: {rec.exploration_drift}")
    assert rec.streak == 0, "Streak should reset on skip"
    
    # Force high drift to test exploration trigger
    rec.exploration_drift = 0.8
    t, reason = rec.get_next_track()
    print(f"Track: {t['filename']}, Reason: {reason}")
    # Might be exploit (0.4 prob) or explore (0.6 prob), but justification should reflect state
    if "Boredom" in reason:
        print("Boredom logic triggered correctly")
    else:
        print(f"Resulted in: {reason}")

    print("\nTest Complete.")

if __name__ == "__main__":
    test_recommender_logic()
