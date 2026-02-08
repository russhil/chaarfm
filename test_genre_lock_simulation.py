#!/usr/bin/env python3
"""
Test Script: Genre Lock Simulation (Standalone)

This script creates FULLY SYNTHETIC track data and simulates user interactions
to test the genre locking behavior of the recommendation engine.

It does NOT require database access - all data is generated in-memory.

The test:
1. Creates 3 distinct genre clusters (Punjabi, Western R&B, Bollywood)
2. Simulates a user who ONLY likes Punjabi tracks
3. Verifies that after 5+ positive signals, 90%+ of recommendations are Punjabi
"""

import numpy as np
import sys
from typing import Dict, List, Tuple
from collections import defaultdict

# ==============================================================================
# COMPLETE MOCK SYSTEM - NO DATABASE REQUIRED
# ==============================================================================

class MockUserDB:
    """Mock user_db module to prevent all database access."""
    engine = None  # Prevent engine access
    
    @staticmethod
    def init_db(): pass
    @staticmethod
    def get_available_collections(): return ["test_collection"]
    @staticmethod
    def get_youtube_collections(): return []
    @staticmethod
    def log_interaction_db(*args, **kwargs): pass
    @staticmethod
    def update_cluster_affinity(*args, **kwargs): pass
    @staticmethod
    def update_cluster_centroid(*args, **kwargs): pass
    @staticmethod
    def add_cluster_negative(*args, **kwargs): pass
    @staticmethod
    def get_cluster_negatives(*args, **kwargs): return []
    @staticmethod
    def get_user_profile(user_id, collection=None): 
        return {"user_id": user_id, "is_guest": False, "clusters": {}}
    @staticmethod
    def get_user_interaction_history(user_id, collection_name=None, limit=100):
        return []

# Inject mock BEFORE importing any modules that use user_db
sys.modules['user_db'] = MockUserDB


# ==============================================================================
# SYNTHETIC DATA GENERATOR
# ==============================================================================

def create_synthetic_tracks(num_tracks_per_cluster: int = 100, 
                            vector_dim: int = 200) -> Dict[str, dict]:
    """
    Create synthetic track data with distinct genre clusters.
    
    Each cluster has a distinct centroid, and tracks are generated
    with Gaussian noise around the centroid.
    
    Returns:
        track_map: Dict mapping track_id -> track_info
    """
    np.random.seed(42)  # Reproducibility
    
    track_map = {}
    
    # Define 3 distinct genre centroids
    # These are orthogonal/far apart in vector space to simulate distinct genres
    
    # Cluster 0: "Punjabi" - dominant in dimensions 0-50
    punjabi_center = np.zeros(vector_dim)
    punjabi_center[0:50] = np.random.uniform(0.5, 1.0, 50)
    punjabi_center = punjabi_center / np.linalg.norm(punjabi_center)
    
    # Cluster 1: "Western R&B" - dominant in dimensions 50-100
    western_center = np.zeros(vector_dim)
    western_center[50:100] = np.random.uniform(0.5, 1.0, 50)
    western_center = western_center / np.linalg.norm(western_center)
    
    # Cluster 2: "Bollywood" - dominant in dimensions 100-150
    bollywood_center = np.zeros(vector_dim)
    bollywood_center[100:150] = np.random.uniform(0.5, 1.0, 50)
    bollywood_center = bollywood_center / np.linalg.norm(bollywood_center)
    
    centroids = {
        0: ("Punjabi", punjabi_center, [
            "Sukha", "Diljit Dosanjh", "Sidhu Moose Wala", "Shubh", "AP Dhillon",
            "Parmish Verma", "Jazzy B", "Karan Aujla", "Sharry Mann", "HARNOOR",
            "Guru Randhawa", "Garry Sandhu", "Amrit Maan"
        ]),
        1: ("Western", western_center, [
            "Drake", "Solange", "SZA", "Frank Ocean", "The Weeknd",
            "Brent Faiyaz", "Kanye West", "Travis Scott", "Tyler", "Doja Cat"
        ]),
        2: ("Bollywood", bollywood_center, [
            "Pritam", "Arijit Singh", "Amit Trivedi", "Sachin-Jigar", 
            "A.R. Rahman", "Vishal-Shekhar", "Shankar-Ehsaan-Loy"
        ])
    }
    
    # Generate tracks for each cluster
    for cluster_id, (genre_name, center, artist_names) in centroids.items():
        for i in range(num_tracks_per_cluster):
            # Add Gaussian noise to the centroid
            noise = np.random.normal(0, 0.1, vector_dim)
            track_vector = center + noise
            track_vector = track_vector / np.linalg.norm(track_vector)  # Normalize
            
            # Generate realistic filename
            artist = artist_names[i % len(artist_names)]
            track_name = f"Song_{i:03d}"
            filename = f"{artist} - {track_name}"
            
            track_id = f"{genre_name.lower()}_{i}"
            
            track_map[track_id] = {
                "id": track_id,
                "filename": filename,
                "duration": 180,  # 3 minutes
                "vector": track_vector.tolist(),
                "source_collection": "test_collection",
                "youtube_id": f"YT_{track_id}",  # Fake YouTube ID
                "_cluster_id": cluster_id,  # Hidden metadata for testing
                "_genre": genre_name
            }
    
    return track_map, centroids


# ==============================================================================
# STANDALONE RECOMMENDER (Simplified)
# ==============================================================================

class StandaloneRecommender:
    """
    A simplified recommender that uses the core logic from UserRecommender
    but operates entirely on synthetic in-memory data.
    """
    
    def __init__(self, track_map: Dict[str, dict], centroids: Dict):
        self.track_map = track_map
        self.centroids = {cid: c[1] for cid, c in centroids.items()}  # cluster_id -> vector
        self.genre_names = {cid: c[0] for cid, c in centroids.items()}  # cluster_id -> name
        
        # Session state - mimics UserRecommender
        self.session_likes = []  # List of liked vectors
        self.session_dislikes = []  # List of disliked vectors
        self.played_ids = set()
        self.global_dislikes = set()
        self.user_vector = None
        self.anchor_track = None
        self.last_strong_like = None
        self.last_strong_like_duration = None
        
        # Streak/Lock state
        self.streak = 0
        self.cluster_consecutive_success = 0
        self.cluster_fail_count = 0
        self.cluster_consecutive_fails = 0
        self.exploration_drift = 0.0
        self.current_cluster_id = None
        
        # Build cluster assignments
        self.track_clusters = {}  # track_id -> cluster_id
        for tid, t in self.track_map.items():
            self.track_clusters[tid] = t.get("_cluster_id")
        
        print(f"StandaloneRecommender initialized with {len(track_map)} tracks")
        print(f"Clusters: {list(self.genre_names.items())}")
    
    def _find_vector_cluster(self, vector) -> int:
        """Find which cluster a vector belongs to."""
        if vector is None:
            return None
        vec = np.array(vector)
        best_cluster = None
        max_sim = -1
        for cid, centroid in self.centroids.items():
            sim = np.dot(vec, centroid) / (np.linalg.norm(vec) * np.linalg.norm(centroid) + 1e-8)
            if sim > max_sim:
                max_sim = sim
                best_cluster = cid
        return best_cluster
    
    def _get_cluster_likes(self, cluster_id: int) -> List:
        """Get session likes that belong to a specific cluster."""
        cluster_likes = []
        for vec in self.session_likes:
            vec_cluster = self._find_vector_cluster(vec)
            if vec_cluster == cluster_id:
                cluster_likes.append(vec)
        return cluster_likes
    
    def send_feedback(self, track_id: str, duration: float):
        """
        Send feedback for a track. Positive if duration >= 20s.
        This is the key method for emulating user interactions.
        """
        track = self.track_map.get(track_id)
        if not track:
            return
        
        vector = track.get("vector")
        total_duration = track.get("duration", 180)
        pct_listened = duration / total_duration if total_duration > 0 else 0
        
        # Thresholds
        is_good = (duration >= 15 and pct_listened >= 0.05) or (pct_listened >= 0.15)
        liked = (duration >= 45) or (pct_listened >= 0.40)
        disliked = duration < 5.0
        
        track_cluster = self._find_vector_cluster(vector)
        
        if disliked or not is_good:
            # Skip/Dislike
            self.cluster_fail_count += 1
            self.cluster_consecutive_fails += 1
            self.session_dislikes.append(vector)
            self.global_dislikes.add(track_id)
            
            # Move user vector away
            if self.user_vector is not None:
                u_vec = np.array(self.user_vector)
                t_vec = np.array(vector)
                u_vec = u_vec - 0.2 * (t_vec - u_vec)
                if np.linalg.norm(u_vec) > 0:
                    u_vec = u_vec / np.linalg.norm(u_vec)
                self.user_vector = u_vec.tolist()
            
            if self.cluster_consecutive_fails >= 5:
                self.streak = 0
                self.cluster_consecutive_success = 0
                self.exploration_drift = 1.0
        else:
            # Positive signal
            self.streak += 1
            self.cluster_consecutive_success += 1
            self.cluster_fail_count = 0
            self.cluster_consecutive_fails = 0
            self.session_likes.append(vector)
            self.anchor_track = track
            self.current_cluster_id = track_cluster
            
            if liked and duration >= 60:
                self.last_strong_like = vector
                self.exploration_drift = 0.0
            else:
                self.exploration_drift = max(0.0, self.exploration_drift - 0.3)
            
            # Move user vector towards
            if self.user_vector is None:
                self.user_vector = vector
            else:
                u_vec = np.array(self.user_vector)
                t_vec = np.array(vector)
                u_vec = u_vec + 0.15 * (t_vec - u_vec)
                if np.linalg.norm(u_vec) > 0:
                    u_vec = u_vec / np.linalg.norm(u_vec)
                self.user_vector = u_vec.tolist()
        
        self.played_ids.add(track_id)
    
    def get_next_batch(self, size: int = 5, use_cluster_filter: bool = False) -> List[dict]:
        """
        Get next batch of recommendations.
        
        Args:
            size: Number of tracks
            use_cluster_filter: If True, filter session_likes to current cluster
                               (THIS IS THE FIX WE'RE TESTING)
        """
        batch = []
        
        for _ in range(size):
            track = self._get_next_recommendation(use_cluster_filter=use_cluster_filter)
            if track:
                batch.append(track)
        
        return batch
    
    def _get_next_recommendation(self, use_cluster_filter: bool = False) -> dict:
        """Get a single recommendation."""
        
        # Determine mode
        mode = "EXPLORE"
        if self.streak >= 1 or self.cluster_consecutive_success >= 1:
            mode = "EXPLOIT"
        if self.exploration_drift > 0.7 and self.streak == 0:
            mode = "EXPLORE"
        
        candidates = []
        
        if mode == "EXPLOIT" and self.session_likes:
            # THE KEY LOGIC: How we select the anchor
            
            if use_cluster_filter and self.current_cluster_id is not None:
                # FIX: Filter session_likes to current cluster
                cluster_likes = self._get_cluster_likes(self.current_cluster_id)
                if not cluster_likes:
                    cluster_likes = self.session_likes  # Fallback
            else:
                # CURRENT BEHAVIOR: Use all session_likes
                cluster_likes = self.session_likes
            
            # Select anchor from recent likes
            recent_likes = cluster_likes[-5:] if cluster_likes else []
            
            if recent_likes:
                # Random choice from recent likes (the "Multi-Modal Ratio Rule")
                anchor_vec = recent_likes[np.random.randint(0, len(recent_likes))]
            else:
                anchor_vec = self.user_vector
            
            # Find similar tracks
            candidates = self._find_similar_tracks(anchor_vec, limit=20)
        
        if not candidates:
            # EXPLORE: Random selection from valid tracks
            valid = [t for tid, t in self.track_map.items() 
                    if tid not in self.played_ids and tid not in self.global_dislikes]
            if valid:
                candidates = [valid[np.random.randint(0, len(valid))]]
        
        if candidates:
            selected = candidates[0]
            self.played_ids.add(selected['id'])
            return selected
        
        return None
    
    def _find_similar_tracks(self, anchor_vec, limit: int = 20) -> List[dict]:
        """Find tracks similar to anchor vector."""
        anchor = np.array(anchor_vec)
        scored = []
        
        for tid, track in self.track_map.items():
            if tid in self.played_ids or tid in self.global_dislikes:
                continue
            
            vec = np.array(track.get("vector", []))
            if len(vec) == 0:
                continue
            
            sim = np.dot(anchor, vec) / (np.linalg.norm(anchor) * np.linalg.norm(vec) + 1e-8)
            scored.append((track, sim))
        
        # Sort by similarity
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [t for t, s in scored[:limit]]


# ==============================================================================
# TEST RUNNER
# ==============================================================================

def run_genre_lock_test(use_fix: bool = False, 
                        num_seed_likes: int = 5,
                        num_test_batches: int = 3) -> Tuple[bool, float]:
    """
    Run the genre lock test.
    
    Args:
        use_fix: If True, use cluster-filtered anchor selection
        num_seed_likes: Number of Punjabi tracks to like first
        num_test_batches: Number of batches to generate after seeding
    
    Returns:
        (passed, target_percentage)
    """
    print("=" * 70)
    print(f"🎵 Genre Lock Test {'(WITH FIX)' if use_fix else '(CURRENT BEHAVIOR)'}")
    print("=" * 70)
    
    # Create synthetic tracks
    track_map, centroids = create_synthetic_tracks(num_tracks_per_cluster=100)
    
    # Create recommender
    recommender = StandaloneRecommender(track_map, centroids)
    
    # Step 1: Get initial batch (exploration)
    print("\n📦 Step 1: Initial exploration batch")
    initial_batch = recommender.get_next_batch(size=5, use_cluster_filter=use_fix)
    for t in initial_batch:
        print(f"   - [{t['_genre']}] {t['filename']}")
    
    # Step 2: Find Punjabi tracks and send positive feedback
    print(f"\n📤 Step 2: Sending {num_seed_likes} positive signals for PUNJABI tracks")
    punjabi_tracks = [t for t in track_map.values() if t["_genre"] == "Punjabi" 
                      and t["id"] not in recommender.played_ids]
    
    seed_count = 0
    for t in punjabi_tracks[:num_seed_likes + 5]:  # Extra in case some are played
        if t["id"] not in recommender.played_ids:
            recommender.send_feedback(t["id"], duration=60.0)  # Strong like
            print(f"   ✅ Liked: {t['filename']}")
            seed_count += 1
            if seed_count >= num_seed_likes:
                break
    
    print(f"\n   Current state:")
    print(f"   - Streak: {recommender.streak}")
    print(f"   - Current Cluster: {recommender.current_cluster_id} ({recommender.genre_names.get(recommender.current_cluster_id, 'Unknown')})")
    print(f"   - Session Likes: {len(recommender.session_likes)}")
    
    # Step 3: Generate test batches
    print(f"\n📦 Step 3: Generating {num_test_batches} test batches...")
    
    all_recommendations = []
    genre_counts = defaultdict(int)
    
    for batch_num in range(num_test_batches):
        batch = recommender.get_next_batch(size=5, use_cluster_filter=use_fix)
        print(f"\n   Batch {batch_num + 1}:")
        for t in batch:
            genre = t["_genre"]
            genre_counts[genre] += 1
            all_recommendations.append(t)
            symbol = "✅" if genre == "Punjabi" else "❌"
            print(f"   {symbol} [{genre}] {t['filename']}")
        
        # Simulate user continuing to like Punjabi, skip others
        for t in batch:
            if t["_genre"] == "Punjabi":
                recommender.send_feedback(t["id"], duration=45.0)
            else:
                recommender.send_feedback(t["id"], duration=2.0)  # Skip
    
    # Step 4: Calculate results
    print("\n" + "=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    
    total = len(all_recommendations)
    punjabi_count = genre_counts.get("Punjabi", 0)
    punjabi_pct = (punjabi_count / total * 100) if total > 0 else 0
    
    print(f"Total recommendations: {total}")
    print(f"Genre distribution:")
    for genre, count in sorted(genre_counts.items()):
        pct = count / total * 100 if total > 0 else 0
        print(f"   {genre}: {count} ({pct:.1f}%)")
    
    passed = punjabi_pct >= 90.0
    
    print()
    if passed:
        print(f"✅ TEST PASSED: {punjabi_pct:.1f}% Punjabi (>= 90%)")
    else:
        print(f"❌ TEST FAILED: {punjabi_pct:.1f}% Punjabi (< 90%)")
    
    return passed, punjabi_pct


def main():
    """Main test entry point."""
    print("\n" + "=" * 70)
    print("GENRE LOCK FIX VERIFICATION")
    print("=" * 70)
    print()
    print("This test compares CURRENT behavior vs FIXED behavior")
    print("The fix filters session_likes to current cluster before anchor selection")
    print()
    
    # Test 1: Current behavior (should fail)
    print("\n\n")
    passed_current, pct_current = run_genre_lock_test(use_fix=False, 
                                                       num_seed_likes=5, 
                                                       num_test_batches=3)
    
    # Test 2: With fix (should pass)
    print("\n\n")
    passed_fixed, pct_fixed = run_genre_lock_test(use_fix=True, 
                                                   num_seed_likes=5, 
                                                   num_test_batches=3)
    
    # Summary
    print("\n\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"Current behavior:  {pct_current:.1f}% Punjabi -> {'PASS' if passed_current else 'FAIL'}")
    print(f"With cluster fix:  {pct_fixed:.1f}% Punjabi -> {'PASS' if passed_fixed else 'FAIL'}")
    
    if not passed_current and passed_fixed:
        print()
        print("✅ FIX VERIFIED: Cluster-filtering session_likes improves genre lock!")
        print()
        print("RECOMMENDED FIX in user_recommender.py:")
        print("   1. Track cluster_id with each session_like: (vector, cluster_id)")
        print("   2. Filter session_likes to current_cluster_id in Vibe Lock mode")
        print("   3. Only use anchors from the locked cluster")
    elif passed_current:
        print()
        print("ℹ️ Current behavior already passes. Issue may be elsewhere.")
    else:
        print()
        print("⚠️ Neither version passed. More investigation needed.")
    
    print("=" * 70)
    
    return 0 if (passed_current or passed_fixed) else 1


if __name__ == "__main__":
    exit(main())
