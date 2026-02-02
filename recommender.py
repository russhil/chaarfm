import numpy as np
from vector_db import get_client, get_random_tracks, recommend_tracks, get_track_by_id
from clustering import ClusterManager

# Constants
ENGAGEMENT_THRESHOLD_SEC = 20
SETTLE_STREAK = 3
DUPLICATE_THRESHOLD = 0.95
BANDIT_ALPHA_PRIOR = 1.0
BANDIT_BETA_PRIOR = 1.0

# Micro-interaction thresholds
INSTANT_SKIP_SEC = 2.0
QUICK_SKIP_SEC = 5.0
PARTIAL_LISTEN_SEC = 15.0
GOOD_ENGAGE_SEC = 30.0
STRONG_ENGAGE_SEC = 60.0

# Drift parameters
DRIFT_INCREMENT = 0.05
DRIFT_DECREMENT = 0.1

class RecommenderSession:
    def __init__(self):
        self.client = get_client()
        self.streak = 0
        self.liked_vectors = []
        self.disliked_vectors = []
        self.played_ids = set()
        self.played_filenames = set()  # Strict uniqueness by filename too
        self.last_track = None
        self.history = [] 
        
        # Clustering & Bandit
        self.cluster_manager = ClusterManager(n_clusters=20)
        self.cluster_manager.fit()
        self.cluster_scores = {} # cid -> {alpha, beta}
        self.current_cluster_id = None
        
        # Gradual drift (0=locked, 1=exploring)
        self.exploration_drift = 0.0
        self.session_centroid = None
        
        # Outlier detection
        self._compute_outliers()
        
        self.init_bandit()

        self.user_vector = None # The evolving user taste vector
        self.init_bandit()
    
    def _compute_outliers(self):
        """Identify outlier tracks that shouldn't be used for probing."""
        self.outlier_tracks = set()
        self.cluster_densities = {}
        
        if not self.cluster_manager.initialized:
            return
        
        for cid, track_ids in self.cluster_manager.clusters.items():
            if len(track_ids) < 3:
                continue
            
            centroid = self.cluster_manager.centroids[cid]
            distances = []
            for tid in track_ids:
                if tid in self.cluster_manager.track_map:
                    vec = np.array(self.cluster_manager.track_map[tid]['vector'])
                    dist = np.linalg.norm(vec - centroid)
                    distances.append((tid, dist))
            
            if distances:
                mean_dist = np.mean([d for _, d in distances])
                std_dist = np.std([d for _, d in distances])
                threshold = mean_dist + 2 * std_dist
                
                for tid, dist in distances:
                    if dist > threshold:
                        self.outlier_tracks.add(tid)
                
                self.cluster_densities[cid] = 1.0 / (mean_dist + 0.01)
        
        print(f"Identified {len(self.outlier_tracks)} outlier tracks")

    def init_bandit(self):
        # Initialize scores for all clusters
        for cid in self.cluster_manager.clusters.keys():
            self.cluster_scores[cid] = {'alpha': BANDIT_ALPHA_PRIOR, 'beta': BANDIT_BETA_PRIOR}

    def reset_session(self):
        self.streak = 0
        self.liked_vectors = []
        self.disliked_vectors = [] 
        self.played_ids = set()
        self.played_filenames = set()
        self.history = []
        self.last_track = None
        self.user_vector = None
        self.exploration_drift = 0.0
        self.session_centroid = None
        self.init_bandit()

    def update_user_vector(self, track_vector, direction):
        """
        Reinforcement Learning Update:
        Moves the user_vector towards or away from the track_vector.
        direction: +1 for Like/Finish (towards), -1 for Dislike/Skip (away)
        """
        LEARNING_RATE_POS = 0.1
        LEARNING_RATE_NEG = 0.05
        
        if self.user_vector is None:
            if direction > 0:
                self.user_vector = np.array(track_vector)
                print("Initialized User Vector with first like.")
            return

        u_vec = np.array(self.user_vector)
        t_vec = np.array(track_vector)
        
        if direction > 0:
            # Move towards: New = Old + LR * (Target - Old)
            delta = t_vec - u_vec
            u_vec = u_vec + LEARNING_RATE_POS * delta
            print(f"RL Update: Moved User Vector TOWARDS track.")
        else:
            # Move away: New = Old - LR * (Target - Old)
            # Or simply move in opposite direction of track relative to current
            # A simple implementation is to subtract a fraction of the track vector
            # But better to move away from the track vector direction
             delta = t_vec - u_vec
             u_vec = u_vec - LEARNING_RATE_NEG * delta
             print(f"RL Update: Moved User Vector AWAY from track.")
             
        # Normalize to keep it on the hypersphere (if using cosine sim)
        norm = np.linalg.norm(u_vec)
        if norm > 0:
            u_vec = u_vec / norm
            
        self.user_vector = u_vec.tolist()

    def set_seed(self, track_id):
        """Sets the user vector explicitly (Search Start)."""
        track_info = None
        if self.cluster_manager.initialized and track_id in self.cluster_manager.track_map:
             track_info = self.cluster_manager.track_map[track_id]
        else:
            track_info = get_track_by_id(self.client, track_id)
            
        if track_info:
            self.user_vector = track_info['vector']
            self.last_track = track_info
            self.played_ids.add(track_id)
            print(f"Seeded User Vector with: {track_info['filename']}")
            return track_info
        return None

    def is_duplicate(self, candidate_vector):
        if not self.history: return False
        
        recent_vectors = []
        for h in self.history[-50:]:
            if 'vector' in h: recent_vectors.append(h['vector'])
        
        if not recent_vectors: return False

        candidate_arr = np.array(candidate_vector)
        cand_norm = np.linalg.norm(candidate_arr)
        if cand_norm == 0: return False
        
        for v in recent_vectors:
            v_arr = np.array(v)
            v_norm = np.linalg.norm(v_arr)
            if v_norm == 0: continue
            
            sim = np.dot(candidate_arr, v_arr) / (cand_norm * v_norm)
            if sim > DUPLICATE_THRESHOLD:
                print(f"Duplicate detected! Similarity: {sim}")
                return True
        return False

    def select_cluster(self):
        """Thompson Sampling to select a cluster."""
        best_cluster = None
        max_theta = -1
        
        print("Bandit Scores:")
        for cid, stats in self.cluster_scores.items():
            # Sample from Beta distribution
            theta = np.random.beta(stats['alpha'], stats['beta'])
            
            if theta > max_theta:
                max_theta = theta
                best_cluster = cid
                
        print(f"Selected Cluster: {best_cluster} (theta={max_theta:.2f})")
        return best_cluster

    def _is_unique(self, track):
        """Check if track is unique (not played in this session)."""
        if track['id'] in self.played_ids:
            return False
        if track.get('filename') in self.played_filenames:
            return False
        return True
    
    def _find_nearest_cluster(self, reference_centroid, skip_clusters):
        """Find nearest cluster to reference, excluding skip_clusters."""
        best_cluster = None
        best_dist = float('inf')
        
        for cid in self.cluster_scores.keys():
            if cid in skip_clusters:
                continue
            cluster_tracks = self.cluster_manager.get_cluster_tracks(cid)
            valid_tracks = [t for t in cluster_tracks 
                          if t not in self.played_ids 
                          and t not in self.outlier_tracks
                          and self.cluster_manager.track_map.get(t, {}).get('filename') not in self.played_filenames]
            if not valid_tracks:
                continue
            
            dist = np.linalg.norm(self.cluster_manager.centroids[cid] - reference_centroid)
            if dist < best_dist:
                best_dist = dist
                best_cluster = cid
        
        return best_cluster
    
    def get_next_track(self):
        candidates = []
        FETCH_LIMIT = 20  # Increased to have more options for filtering
        
        mode = "EXPLORE"
        exploit_prob = 0.7
        
        if self.streak > 1:
            exploit_prob = 0.95
            print(f"High Streak ({self.streak}) -> Boosting Exploit Mode to 95%")
        
        if self.user_vector is not None:
            if np.random.random() < exploit_prob:
                mode = "EXPLOIT"
        
        print(f"Recommendation Mode: {mode} | Drift: {self.exploration_drift:.2f}")

        if mode == "EXPLOIT" and self.user_vector is not None:
            print("EXPLOIT: Probing near User Preference Vector...")
            candidates = recommend_tracks(
                self.client,
                positive_vectors=[self.user_vector],
                negative_vectors=self.disliked_vectors,
                avoid_ids=self.played_ids,
                limit=FETCH_LIMIT
            )
            
            # GRADUAL DRIFT: If drift is high, add some tracks from nearby clusters
            if self.exploration_drift >= 0.3 and self.current_cluster_id is not None:
                nearby_cluster = self._find_nearest_cluster(
                    self.cluster_manager.centroids[self.current_cluster_id],
                    {self.current_cluster_id}
                )
                if nearby_cluster is not None:
                    print(f"  🌊 Drift active - adding tracks from nearby cluster {nearby_cluster}")
                    nearby_tracks = self.cluster_manager.get_cluster_tracks(nearby_cluster)
                    for tid in nearby_tracks[:5]:
                        if tid not in self.outlier_tracks:
                            tinfo = self.cluster_manager.track_map.get(tid)
                            if tinfo and self._is_unique(tinfo):
                                candidates.append(tinfo)
        else:
            print("EXPLORE: Using Cluster Bandit...")
            
            cluster_id = self.select_cluster()
            self.current_cluster_id = cluster_id
            
            # Get representatives, excluding outliers
            reps = self.cluster_manager.get_representatives(cluster_id, limit=10)
            valid_reps = [rid for rid in reps 
                         if rid not in self.played_ids 
                         and rid not in self.outlier_tracks
                         and self.cluster_manager.track_map.get(rid, {}).get('filename') not in self.played_filenames]
            
            valid_track_id = None
            if valid_reps:
                print("Picking Cluster Representative (non-outlier)")
                valid_track_id = valid_reps[0]
            else:
                print("Picking from Cluster (non-outlier)")
                cluster_tracks = self.cluster_manager.get_cluster_tracks(cluster_id)
                valid_cluster_tracks = [t for t in cluster_tracks 
                                       if t not in self.played_ids 
                                       and t not in self.outlier_tracks
                                       and self.cluster_manager.track_map.get(t, {}).get('filename') not in self.played_filenames]
                
                if valid_cluster_tracks:
                    # Pick closest to centroid instead of random
                    centroid = self.cluster_manager.centroids[cluster_id]
                    valid_cluster_tracks.sort(
                        key=lambda tid: np.linalg.norm(
                            np.array(self.cluster_manager.track_map[tid]['vector']) - centroid
                        )
                    )
                    valid_track_id = valid_cluster_tracks[0]
            
            if valid_track_id:
                tinfo = self.cluster_manager.track_map.get(valid_track_id)
                if tinfo:
                    candidates = [{
                        "id": tinfo['id'],
                        "filename": tinfo['filename'],
                        "s3_url": tinfo.get('s3_url'), # PASS S3 URL
                        "vector": tinfo['vector'],
                        "score": 0 
                    }]
            else:
                 print("Cluster exhausted - finding NEAREST cluster")
                 # Find nearest cluster instead of random
                 nearest = self._find_nearest_cluster(
                     self.cluster_manager.centroids[cluster_id],
                     {cluster_id}
                 )
                 if nearest is not None:
                     print(f"  Falling back to nearest cluster {nearest}")
                     self.current_cluster_id = nearest
                     cluster_tracks = self.cluster_manager.get_cluster_tracks(nearest)
                     valid = [t for t in cluster_tracks 
                             if t not in self.played_ids 
                             and t not in self.outlier_tracks
                             and self.cluster_manager.track_map.get(t, {}).get('filename') not in self.played_filenames]
                     if valid:
                         tinfo = self.cluster_manager.track_map.get(valid[0])
                         if tinfo:
                             candidates = [tinfo]
                 
                 if not candidates and self.user_vector is not None:
                      candidates = recommend_tracks(self.client, positive_vectors=[self.user_vector], limit=FETCH_LIMIT, avoid_ids=self.played_ids)
                 
                 if not candidates:
                      print("Fallback to library search")
                      candidates = get_random_tracks(self.client, limit=FETCH_LIMIT, avoid_ids=self.played_ids)

        if not candidates:
            candidates = get_random_tracks(self.client, limit=FETCH_LIMIT, avoid_ids=self.played_ids)
        
        # STRICT UNIQUENESS FILTER
        selected_track = None
        
        for track in candidates:
            if not self._is_unique(track):
                continue
            if self.is_duplicate(track['vector']):
                continue
            selected_track = track
            break
        
        if not selected_track and candidates:
             print("All candidates filtered. Finding NEAREST available cluster.")
             # Find nearest cluster with available tracks
             ref_centroid = self.cluster_manager.centroids.get(self.current_cluster_id)
             if ref_centroid is None and self.user_vector is not None:
                 ref_centroid = np.array(self.user_vector)
             
             if ref_centroid is not None:
                 nearest = self._find_nearest_cluster(ref_centroid, {self.current_cluster_id} if self.current_cluster_id else set())
                 if nearest is not None:
                     cluster_tracks = self.cluster_manager.get_cluster_tracks(nearest)
                     for tid in cluster_tracks:
                         if tid in self.outlier_tracks:
                             continue
                         tinfo = self.cluster_manager.track_map.get(tid)
                         if tinfo and self._is_unique(tinfo):
                             selected_track = tinfo
                             break
        
        if selected_track:
            self.played_ids.add(selected_track['id'])
            self.played_filenames.add(selected_track['filename'])
            self.last_track = selected_track
            return {
                "id": selected_track['id'],
                "filename": selected_track['filename'],
                "s3_url": selected_track.get('s3_url') # Ensure this is passed
            }
        return None

    def feedback(self, track_id, duration, liked=False, disliked=False, finished=False):
        track_info = None
        
        if self.cluster_manager.initialized and track_id in self.cluster_manager.track_map:
             track_info = self.cluster_manager.track_map[track_id]
        elif self.last_track and self.last_track['id'] == track_id:
            track_info = self.last_track
        else:
            track_info = get_track_by_id(self.client, track_id)
        
        if not track_info:
            print("Error: Track not found for feedback.")
            return

        vector = track_info.get('vector')

        # MICRO-INTERACTION INTERPRETATION
        alpha_boost = 0
        beta_boost = 0
        tier = "Unknown"
        rl_direction = 0
        drift_delta = 0
        
        if disliked:
            print("Feedback: Explicit Dislike")
            self.disliked_vectors.append(vector)
            beta_boost = 2.0
            self.streak = 0
            tier = "Explicit Dislike"
            rl_direction = -1
            drift_delta = 0.1
        elif liked:
            print("Feedback: Explicit Like")
            self.liked_vectors.append(vector)
            alpha_boost = 2.0
            self.streak += 1
            tier = "Explicit Like"
            rl_direction = 1
            drift_delta = -DRIFT_DECREMENT * 2
        elif finished:
            print("Feedback: Finished Song")
            alpha_boost = 2.0
            self.streak += 1
            tier = "Finished"
            rl_direction = 1
            drift_delta = -DRIFT_DECREMENT * 3
        else:
            # MICRO-INTERACTION: Duration-based signals
            if duration < INSTANT_SKIP_SEC:
                print(f"Feedback: INSTANT SKIP ({duration}s) - Strong negative")
                beta_boost = 2.5
                self.streak = 0 
                tier = "Instant Skip"
                rl_direction = -1
                drift_delta = 0.1  # Big drift increase
            elif duration < QUICK_SKIP_SEC:
                print(f"Feedback: Quick Skip ({duration}s) - Moderate negative")
                beta_boost = 1.5
                self.streak = 0
                tier = "Quick Skip"
                rl_direction = -0.5
                drift_delta = DRIFT_INCREMENT
            elif duration < PARTIAL_LISTEN_SEC:
                print(f"Feedback: Partial Listen ({duration}s) - Slight positive")
                alpha_boost = 0.3
                tier = "Partial Listen"
                rl_direction = 0.2
                drift_delta = -0.02
            elif duration < GOOD_ENGAGE_SEC:
                print(f"Feedback: Good Engagement ({duration}s)")
                alpha_boost = 0.8
                self.streak += 1
                tier = "Good Engagement"
                rl_direction = 0.6
                drift_delta = -DRIFT_DECREMENT
            elif duration < STRONG_ENGAGE_SEC:
                print(f"Feedback: Strong Engagement ({duration}s)")
                alpha_boost = 1.5
                self.streak += 1
                tier = "Strong Engagement"
                rl_direction = 0.8
                drift_delta = -DRIFT_DECREMENT * 2
            else:
                print(f"Feedback: Full Listen ({duration}s)")
                alpha_boost = 2.0
                self.streak += 1
                tier = "Full Listen"
                rl_direction = 1.0
                drift_delta = -DRIFT_DECREMENT * 3
        
        # Update exploration drift (clamp 0-1)
        self.exploration_drift = max(0.0, min(1.0, self.exploration_drift + drift_delta))
        print(f"  Drift: {self.exploration_drift:.2f}")
        
        # Update session centroid with positive signals
        if rl_direction > 0.2 and vector is not None:
            track_vec = np.array(vector)
            if self.session_centroid is None:
                self.session_centroid = track_vec.copy()
            else:
                alpha = min(0.3, rl_direction * 0.3)
                self.session_centroid = (1 - alpha) * self.session_centroid + alpha * track_vec
        
        # GRADUAL DRIFT HANDLING instead of abrupt cluster switch
        if rl_direction < 0:
             self.negative_streak = getattr(self, 'negative_streak', 0) + 1
             print(f"Negative Streak: {self.negative_streak}")
             
             if self.negative_streak >= 3:
                 if self.exploration_drift >= 0.5:
                     print("!!! HIGH DRIFT: Gradually shifting to nearby cluster !!!")
                     # Find nearest cluster and boost it
                     if self.current_cluster_id is not None:
                         nearest = self._find_nearest_cluster(
                             self.cluster_manager.centroids[self.current_cluster_id],
                             {self.current_cluster_id}
                         )
                         if nearest is not None:
                             self.cluster_scores[nearest]['alpha'] += 3.0
                             print(f"  Boosted nearest cluster {nearest}")
                 else:
                     print("!!! DETECTED BAD FLOW: Increasing drift !!!")
                     self.exploration_drift = min(1.0, self.exploration_drift + 0.2)
                 
                 beta_boost += 3.0
                 self.negative_streak = 0
        else:
            self.negative_streak = 0
        
        # Update User Vector (Reinforcement Learning)
        if rl_direction != 0:
            self.update_user_vector(vector, rl_direction)

        # Update Bandit
        if self.current_cluster_id is not None:
             self.cluster_scores[self.current_cluster_id]['alpha'] += alpha_boost
             self.cluster_scores[self.current_cluster_id]['beta'] += beta_boost
             
             print(f"Updated Cluster {self.current_cluster_id}: {self.cluster_scores[self.current_cluster_id]} (Alpha+{alpha_boost}, Beta+{beta_boost})")

        # Log User Behaviour
        import csv
        import datetime
        
        log_file = "user_behavior_log.csv"
        file_exists = False
        try:
            with open(log_file, 'r') as f: file_exists = True
        except FileNotFoundError: pass
        
        with open(log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "track_id", "filename", "duration", "liked", "disliked", "finished", "tier", "cluster_id", "alpha_boost", "beta_boost"])
                
            writer.writerow([
                datetime.datetime.now().isoformat(),
                track_id,
                track_info['filename'],
                duration,
                liked,
                disliked,
                finished,
                tier,
                self.current_cluster_id,
                alpha_boost,
                beta_boost
            ])

        # Add to history
        self.history.append({
            "id": track_id,
            "filename": track_info['filename'],
            "duration": duration,
            "liked": liked,
            "disliked": disliked,
            "finished": finished,
            "vector": vector 
        })
