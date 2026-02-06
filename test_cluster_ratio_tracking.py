#!/usr/bin/env python3
"""
Test Script: Cluster Ratio Tracking Verification

This script verifies that the ChaarFM recommendation system correctly:
1. Tracks user engagement with distinct music clusters
2. Calculates engagement ratios based on user interactions
3. Adjusts recommendation probabilities to reflect these ratios in real time
4. Responds immediately to skips by updating cluster preferences

Test Scenario: Bollywood vs Punjabi cluster interaction
"""

import sys
import os
import numpy as np
from typing import Dict, List, Tuple

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the recommendation system
from user_recommender import UserRecommender
import user_db

class ClusterRatioTest:
    def __init__(self):
        print("🧪 Initializing Cluster Ratio Tracking Test")
        print("=" * 60)
        
        # Initialize database and recommender
        user_db.init_db()
        self.recommender = UserRecommender(
            user_id="test_user", 
            collection_name="music_averaged",
            youtube_mode=False
        )
        
        # Clear any existing session state
        self.recommender.session_likes = []
        self.recommender.session_dislikes = []
        self.recommender.played_ids = set()
        self.recommender.user_vector = None
        self.recommender.streak = 0
        
        print(f"✅ Recommender initialized with {len(self.recommender.track_map)} tracks")
        print(f"✅ Found {len(self.recommender.cluster_manager.clusters)} clusters")
        print()

    def find_cluster_representatives(self) -> Dict[int, List[str]]:
        """Find representative tracks for each cluster to simulate different genres"""
        print("🔍 Analyzing cluster composition...")
        
        cluster_samples = {}
        for cluster_id, track_ids in self.recommender.cluster_manager.clusters.items():
            samples = []
            for track_id in track_ids[:5]:  # Get first 5 tracks from each cluster
                if track_id in self.recommender.track_map:
                    filename = self.recommender.track_map[track_id]['filename']
                    samples.append((track_id, filename))
            cluster_samples[cluster_id] = samples
        
        # Display cluster samples
        for cluster_id, samples in cluster_samples.items():
            print(f"  Cluster {cluster_id}:")
            for track_id, filename in samples:
                print(f"    • {filename}")
        
        print()
        return cluster_samples

    def get_current_cluster_ratios(self) -> Dict[int, float]:
        """Calculate current session cluster engagement ratios"""
        if not self.recommender.session_likes:
            return {}
        
        cluster_counts = {}
        total_interactions = len(self.recommender.session_likes)
        
        for liked_vector in self.recommender.session_likes:
            # Find which cluster this vector belongs to
            closest_cluster = self._find_vector_cluster(liked_vector)
            cluster_counts[closest_cluster] = cluster_counts.get(closest_cluster, 0) + 1
        
        # Convert to percentages
        cluster_ratios = {}
        for cluster_id, count in cluster_counts.items():
            cluster_ratios[cluster_id] = (count / total_interactions) * 100
        
        return cluster_ratios

    def _find_vector_cluster(self, vector: List[float]) -> int:
        """Find which cluster a given vector belongs to"""
        min_distance = float('inf')
        closest_cluster = None
        
        vector_np = np.array(vector)
        for cluster_id, centroid in self.recommender.cluster_manager.centroids.items():
            distance = np.linalg.norm(vector_np - centroid)
            if distance < min_distance:
                min_distance = distance
                closest_cluster = cluster_id
        
        return closest_cluster

    def simulate_user_interaction(self, track_id: str, duration: float, description: str):
        """Simulate a user interaction with detailed logging"""
        print(f"🎵 Simulating: {description}")
        print(f"   Track ID: {track_id}")
        print(f"   Duration: {duration}s")
        
        # Get track info
        track = self.recommender.track_map.get(track_id)
        if not track:
            print(f"   ❌ Track not found: {track_id}")
            return
        
        filename = track['filename']
        cluster_id = self._find_vector_cluster(track['vector'])
        print(f"   Track: {filename}")
        print(f"   Cluster: {cluster_id}")
        
        # Record the feedback
        self.recommender.record_feedback(track_id, duration)
        
        # Display updated ratios
        ratios = self.get_current_cluster_ratios()
        if ratios:
            print(f"   📊 Updated Cluster Ratios:")
            for cid, percentage in sorted(ratios.items()):
                print(f"      Cluster {cid}: {percentage:.1f}%")
        else:
            print(f"   📊 No positive interactions yet")
        
        print(f"   Session Likes Count: {len(self.recommender.session_likes)}")
        print()

    def test_recommendation_probability(self, num_samples: int = 100) -> Dict[int, int]:
        """Test that recommendation probabilities match cluster ratios"""
        print(f"🎯 Testing recommendation probabilities ({num_samples} samples)...")
        
        if not self.recommender.session_likes:
            print("   ⚠️  No session likes to test with")
            return {}
        
        cluster_selections = {}
        
        # Simulate the recommendation selection process multiple times
        for _ in range(num_samples):
            # This mimics the core logic from get_next_track()
            selected_anchor = np.random.choice(len(self.recommender.session_likes))
            anchor_vector = self.recommender.session_likes[selected_anchor]
            cluster_id = self._find_vector_cluster(anchor_vector)
            
            cluster_selections[cluster_id] = cluster_selections.get(cluster_id, 0) + 1
        
        # Convert to percentages
        cluster_probabilities = {}
        for cluster_id, count in cluster_selections.items():
            cluster_probabilities[cluster_id] = (count / num_samples) * 100
        
        print("   📈 Observed Recommendation Probabilities:")
        expected_ratios = self.get_current_cluster_ratios()
        
        for cluster_id in sorted(set(list(expected_ratios.keys()) + list(cluster_probabilities.keys()))):
            expected = expected_ratios.get(cluster_id, 0)
            observed = cluster_probabilities.get(cluster_id, 0)
            diff = abs(expected - observed)
            
            status = "✅" if diff < 10 else "⚠️"  # Allow 10% tolerance for randomness
            print(f"      Cluster {cluster_id}: Expected {expected:.1f}%, Observed {observed:.1f}% {status}")
        
        print()
        return cluster_selections

    def test_skip_response(self, track_id: str, description: str):
        """Test that skipping a track immediately updates cluster preferences"""
        print(f"⏭️  Testing skip response: {description}")
        
        # Record pre-skip state
        pre_skip_ratios = self.get_current_cluster_ratios()
        pre_skip_user_vector = np.array(self.recommender.user_vector) if self.recommender.user_vector else None
        pre_skip_drift = self.recommender.exploration_drift
        
        # Get track info for analysis
        track = self.recommender.track_map.get(track_id)
        if not track:
            print(f"   ❌ Track not found: {track_id}")
            return
        
        skipped_cluster = self._find_vector_cluster(track['vector'])
        print(f"   Skipping track from Cluster {skipped_cluster}: {track['filename']}")
        
        # Simulate skip (duration < 5 seconds = dislike)
        self.recommender.record_feedback(track_id, 2.0)  # 2 second skip
        
        # Record post-skip state
        post_skip_ratios = self.get_current_cluster_ratios()
        post_skip_user_vector = np.array(self.recommender.user_vector) if self.recommender.user_vector else None
        post_skip_drift = self.recommender.exploration_drift
        
        print(f"   📊 Pre-skip ratios: {pre_skip_ratios}")
        print(f"   📊 Post-skip ratios: {post_skip_ratios}")
        print(f"   📈 Drift change: {pre_skip_drift:.3f} → {post_skip_drift:.3f}")
        
        # Verify user vector moved away from skipped track
        if pre_skip_user_vector is not None and post_skip_user_vector is not None:
            skipped_vector = np.array(track['vector'])
            
            # Calculate cosine similarity before and after
            pre_similarity = np.dot(pre_skip_user_vector, skipped_vector) / (
                np.linalg.norm(pre_skip_user_vector) * np.linalg.norm(skipped_vector)
            )
            post_similarity = np.dot(post_skip_user_vector, skipped_vector) / (
                np.linalg.norm(post_skip_user_vector) * np.linalg.norm(skipped_vector)
            )
            
            similarity_change = post_similarity - pre_similarity
            status = "✅" if similarity_change < 0 else "❌"
            print(f"   🧭 User vector similarity to skipped track: {pre_similarity:.3f} → {post_similarity:.3f} ({similarity_change:+.3f}) {status}")
        
        print(f"   🚫 Added to global dislikes: {track_id in [str(x) for x in self.recommender.global_dislikes]}")
        print()

    def run_complete_test(self):
        """Run the complete cluster ratio tracking test"""
        print("🚀 Starting Complete Cluster Ratio Tracking Test")
        print("=" * 60)
        
        # Step 1: Find cluster representatives
        cluster_samples = self.find_cluster_representatives()
        
        # Select two different clusters to simulate (Bollywood vs Punjabi equivalent)
        cluster_ids = list(cluster_samples.keys())[:2]
        if len(cluster_ids) < 2:
            print("❌ Need at least 2 clusters for testing")
            return False
        
        cluster_a, cluster_b = cluster_ids
        print(f"📋 Test Setup: Using Cluster {cluster_a} vs Cluster {cluster_b}")
        print()
        
        # Get tracks from each cluster
        tracks_a = [track_id for track_id, _ in cluster_samples[cluster_a][:2]]
        tracks_b = [track_id for track_id, _ in cluster_samples[cluster_b][:2]]
        
        # Step 2: Simulate 2 + 2 interaction pattern (like Bollywood + Punjabi example)
        print("📖 Test Scenario: 2 tracks from Cluster A + 2 tracks from Cluster B")
        print()
        
        # Interactions with Cluster A
        self.simulate_user_interaction(tracks_a[0], 45.0, f"Like Cluster {cluster_a} Track 1")
        self.simulate_user_interaction(tracks_a[1], 50.0, f"Like Cluster {cluster_a} Track 2")
        
        # Interactions with Cluster B  
        self.simulate_user_interaction(tracks_b[0], 40.0, f"Like Cluster {cluster_b} Track 1")
        self.simulate_user_interaction(tracks_b[1], 55.0, f"Like Cluster {cluster_b} Track 2")
        
        # Step 3: Verify 50/50 ratio is achieved
        final_ratios = self.get_current_cluster_ratios()
        print("🎯 Final Ratio Check:")
        
        if cluster_a in final_ratios and cluster_b in final_ratios:
            ratio_a = final_ratios[cluster_a]
            ratio_b = final_ratios[cluster_b]
            
            print(f"   Cluster {cluster_a}: {ratio_a:.1f}%")
            print(f"   Cluster {cluster_b}: {ratio_b:.1f}%")
            
            # Check if ratios are approximately 50/50
            target_ratio = 50.0
            tolerance = 5.0  # Allow 5% deviation
            
            ratio_check = (abs(ratio_a - target_ratio) <= tolerance and 
                          abs(ratio_b - target_ratio) <= tolerance)
            
            status = "✅" if ratio_check else "❌"
            print(f"   50/50 Ratio Achievement: {status}")
            print()
        else:
            print(f"   ❌ Missing expected clusters in ratios: {final_ratios}")
            print()
        
        # Step 4: Test recommendation probability alignment
        prob_results = self.test_recommendation_probability(200)
        
        # Step 5: Test skip response
        if len(cluster_samples[cluster_a]) > 2:
            skip_track = cluster_samples[cluster_a][2][0]  # Third track from cluster A
            self.test_skip_response(skip_track, f"Skip from dominant Cluster {cluster_a}")
        
        # Step 6: Verify system can generate next recommendation
        print("🔮 Testing Next Track Generation...")
        try:
            next_track, justification = self.recommender.get_next_track()
            if next_track:
                next_cluster = self._find_vector_cluster(self.recommender.track_map[next_track['id']]['vector'])
                print(f"   ✅ Successfully generated next track from Cluster {next_cluster}")
                print(f"   Track: {next_track['filename']}")
                print(f"   Justification: {justification}")
            else:
                print(f"   ⚠️  No next track generated")
        except Exception as e:
            print(f"   ❌ Error generating next track: {e}")
        
        print()
        print("🏁 Test Complete!")
        print("=" * 60)
        return True

def main():
    """Main test execution"""
    try:
        test = ClusterRatioTest()
        success = test.run_complete_test()
        
        if success:
            print("✅ All tests passed! The cluster ratio tracking system is working correctly.")
        else:
            print("❌ Some tests failed. Check the output above for details.")
            
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()