
import unittest
import numpy as np
from user_recommender import UserRecommender, ClusterManager

class MockClusterManager:
    def __init__(self):
        self.centroids = {
            0: np.array([0.9, 0.1]), # Cluster 0: High X, Low Y
            1: np.array([0.1, 0.9])  # Cluster 1: Low X, High Y
        }
        self.clusters = {0: ['t1', 't2'], 1: ['t3', 't4']}
        self.cluster_densities = {0: 1.0, 1: 1.0}

class TestProbing(unittest.TestCase):
    def setUp(self):
        # Mock Data
        self.rec = UserRecommender(user_id="test_user")
        
        # Override track map with distinct directional vectors
        self.rec.track_map = {
            't1': {'id': 't1', 'filename': 'Song A', 'vector': [0.95, 0.1]}, # Close to Cluster 0
            't2': {'id': 't2', 'filename': 'Song B', 'vector': [0.9, 0.15]}, # Close to Cluster 0
            't3': {'id': 't3', 'filename': 'Song C', 'vector': [0.1, 0.95]}, # Close to Cluster 1
            't4': {'id': 't4', 'filename': 'Song D', 'vector': [0.15, 0.9]}, # Close to Cluster 1
            't5': {'id': 't5', 'filename': 'Song E', 'vector': [0.5, 0.5]},  # Middle
        }
        
        # Mock Cluster Manager
        self.rec.cluster_manager = MockClusterManager()
        self.rec.cluster_densities = {0: 1.0, 1: 1.0}
        
        # Clear state
        self.rec.played_ids = set()
        self.rec.global_dislikes = set()
        self.rec.session_likes = []
        self.rec.best_historical_cluster = None
        
    def test_smart_start(self):
        print("\n--- Test Smart Start ---")
        # Simulate historical preference for Cluster 0
        self.rec.best_historical_cluster = 0
        
        # Should pick t1 or t2 (Cluster 0)
        track, just = self.rec.get_next_track()
        print(f"Selected: {track['filename']} ({just})")
        
        self.assertTrue(track['id'] in ['t1', 't2'])
        self.assertIn("Smart Start", just)

    def test_flow_probing(self):
        print("\n--- Test Flow Probing ---")
        # Simulate session likes in middle
        self.rec.session_likes = [np.array([0.5, 0.5])]
        self.rec.streak = 0 # Force explore
        self.rec.exploration_drift = 1.0
        
        # Should pick t5 (Middle)
        track, just = self.rec.get_next_track()
        print(f"Selected: {track['filename']} ({just})")
        
        self.assertEqual(track['id'], 't5')
        self.assertIn("Flowing outwards", just)

    def test_dislike_avoidance(self):
        print("\n--- Test Dislike Avoidance ---")
        self.rec.global_dislikes.add('t1')
        self.rec.best_historical_cluster = 0
        
        # Should NOT pick t1, should pick t2
        track, just = self.rec.get_next_track()
        print(f"Selected: {track['filename']} ({just})")
        
        self.assertEqual(track['id'], 't2')

if __name__ == '__main__':
    unittest.main()
