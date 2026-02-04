"""
User Recommender - Bandit/Session Logic (Restored Backup)
Adapted for Supabase (In-Memory Vector Operations)
"""

import numpy as np
import json
import random
import datetime
import csv
from sklearn.cluster import KMeans
from sqlalchemy import text
import user_db

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

class ClusterManager:
    def __init__(self, track_map, n_clusters=20):
        self.track_map = track_map
        self.n_clusters = n_clusters
        self.clusters = {} # cid -> [tids]
        self.centroids = {} # cid -> vec
        self.initialized = False
        
    def fit(self):
        if not self.track_map: return
        ids = list(self.track_map.keys())
        vecs = [self.track_map[i]['vector'] for i in ids]
        
        n = min(self.n_clusters, len(vecs))
        if n < 1: n = 1
        
        km = KMeans(n_clusters=n, random_state=42, n_init=10)
        labels = km.fit_predict(vecs)
        self.centroids = {i: km.cluster_centers_[i] for i in range(n)}
        
        self.clusters = {i: [] for i in range(n)}
        for idx, lbl in enumerate(labels):
            self.clusters[lbl].append(ids[idx])
            
        self.initialized = True
        
    def get_cluster_tracks(self, cid):
        return self.clusters.get(cid, [])
        
    def get_representatives(self, cid, limit=10):
        tids = self.clusters.get(cid, [])
        if not tids: return []
        # Sort by dist to centroid
        cent = self.centroids[cid]
        sorted_tids = sorted(tids, key=lambda t: np.linalg.norm(np.array(self.track_map[t]['vector']) - cent))
        return sorted_tids[:limit]

class UserRecommender:
    def __init__(self, user_id="guest", collection_name=None, youtube_mode=False):
        self.user_id = user_id
        self.collection_name = collection_name or "music_averaged"
        self.youtube_mode = youtube_mode
        
        # Data Loading
        self.track_map = {}
        self._load_vector_data()
        
        # Session State
        self.streak = 0
        self.liked_vectors = []
        self.disliked_vectors = []
        self.session_likes = [] # Store all liked vectors in session
        self.session_dislikes = [] # Store all disliked vectors in session
        self.played_ids = set()
        self.played_filenames = set()
        self.last_track = None
        self.anchor_track = None # Track that started the current vibe/streak
        self.history = []
        
        # Clustering & Bandit
        # Optimization: Don't fit KMeans on every session start.
        # Cache the centroids/clusters globally or in DB.
        # For now, reduce n_clusters or n_init to speed up startup.
        # Or even better, just load centroids from DB if available.
        
        self.cluster_manager = ClusterManager(self.track_map, n_clusters=20) # Reduced from 50 to 20 for speed
        self.cluster_manager.fit() # This is the slow part (KMeans on 2500 vectors)
        self.cluster_scores = {}
        self.current_cluster_id = None
        
        # Gradual drift
        self.exploration_drift = 0.0
        self.session_centroid = None
        self.negative_streak = 0
        
        # Persistent Cluster Negatives Cache
        self.active_cluster_negatives = []
        self.loaded_cluster_id = None
        self.cluster_consecutive_success = 0  # Track consecutive >60s plays in same cluster
        self.cluster_fail_count = 0 # Track consecutive skips in cluster to detect exhaustion
        
        # Outlier detection
        self.outlier_tracks = set()
        self.cluster_densities = {}
        self._compute_outliers()
        self.init_bandit()
        
        self.user_vector = None
        
        # Load User History for Smart Start
        self.best_historical_cluster = None
        self.global_dislikes = set()
        self._load_user_history()
        self._load_user_dislikes()
        
        print(f"UserRecommender Initialized for {user_id} ({len(self.track_map)} tracks)")

    def _load_user_dislikes(self):
        """Load historically disliked/skipped tracks to prevent repeats at startup."""
        try:
            print(f"Loading dislikes for {self.user_id}...")
            # Fetch skips and dislikes
            query = text(f"""
                SELECT track_id FROM user_logs 
                WHERE user_id = :uid 
                AND (action = 'skip' OR action = 'dislike')
                GROUP BY track_id 
                HAVING COUNT(*) >= 1
            """)
            # Note: Strictness can be adjusted. If skipped once, maybe give another chance?
            # User said: "same 10 songs they skip everytime". So filtering all is safer for now.
            
            with user_db.engine.connect() as conn:
                result = conn.execute(query, {"uid": self.user_id}).fetchall()
            
            count = 0
            for row in result:
                if row.track_id is not None and str(row.track_id):
                    self.global_dislikes.add(str(row.track_id))
                    count += 1
            print(f"Loaded {count} historically disliked/skipped tracks.")
        except Exception as e:
            print(f"Could not load dislikes: {e}")

    def _load_user_history(self):
        """
        Load historical cluster affinities to prime the bandit.
        """
        try:
            print(f"Loading user history for {self.user_id}...")
            query = text(f"""
                SELECT cluster_id, total_listen_seconds as score 
                FROM cluster_affinity 
                WHERE user_id = :uid AND collection_name = :coll
                ORDER BY total_listen_seconds DESC LIMIT 5
            """)
            
            with user_db.engine.connect() as conn:
                result = conn.execute(query, {"uid": self.user_id, "coll": self.collection_name}).fetchall()
            
            if result:
                print(f"Found {len(result)} historical top clusters.")
                best_score = -1
                for row in result:
                    cid = int(row.cluster_id)
                    score = float(row.score)
                    if cid in self.cluster_scores:
                        # Boost alpha based on history (cap to avoid overwhelming session)
                        boost = min(score * 5.0, 25.0)
                        self.cluster_scores[cid]['alpha'] += boost
                        print(f"Boosted Cluster {cid} alpha to {self.cluster_scores[cid]['alpha']}")
                        
                        if score > best_score:
                            best_score = score
                            self.best_historical_cluster = cid
            
            if self.best_historical_cluster is not None:
                print(f"Best Historical Cluster Identified: {self.best_historical_cluster}")
                
        except Exception as e:
            print(f"Could not load user history (First run?): {e}")

    def _load_vector_data(self):
        print(f"Loading tracks from {self.collection_name} (Render)...")
        
        collections_to_load = []
        merge_youtube_only = False  # When True, only add tracks that have youtube_id (for youtube_all)
        if self.collection_name == "merged":
            collections_to_load = user_db.get_available_collections()
            print(f"Merged Mode: Loading from {len(collections_to_load)} collections: {collections_to_load}")
        elif self.collection_name == "youtube_all":
            collections_to_load = user_db.get_youtube_collections()
            merge_youtube_only = True
            print(f"YouTube (all): Loading from {len(collections_to_load)} YouTube-only collections: {collections_to_load}")
        else:
            collections_to_load = [self.collection_name]
            
        try:
            total_loaded = 0
            for col_name in collections_to_load:
                # Sanitize table name to prevent injection (though get_available_collections returns trusted names)
                # But we should still be careful.
                # Since we trust get_available_collections(), we just proceed.
                
                # Try 'vecs' schema first, then 'public'
                standard_schema = True
                try:
                    query = text(f'SELECT id, vec, metadata FROM vecs."{col_name}"')
                    with user_db.engine.connect() as conn:
                        result = conn.execute(query).fetchall()
                except Exception as e_vecs:
                    # print(f"Not in vecs schema: {e_vecs}, trying public...")
                    try:
                        query = text(f'SELECT id, vec, metadata FROM public."{col_name}"')
                        with user_db.engine.connect() as conn:
                            result = conn.execute(query).fetchall()
                    except Exception as e_public:
                        # Try alternative schema (embedding, artist, title, s3_url, youtube_id)
                        has_youtube_col = False
                        try:
                            query = text(f'SELECT id, embedding, artist, title, s3_url, youtube_id FROM public."{col_name}"')
                            with user_db.engine.connect() as conn:
                                result = conn.execute(query).fetchall()
                            standard_schema = False
                            has_youtube_col = True
                        except Exception as e_alt:
                            try:
                                query = text(f'SELECT id, embedding, artist, title, s3_url FROM public."{col_name}"')
                                with user_db.engine.connect() as conn:
                                    result = conn.execute(query).fetchall()
                                standard_schema = False
                            except Exception as e_alt2:
                                print(f"Failed to load {col_name} from both vecs and public (std & alt): {e_alt2}")
                                continue
                    
                for row in result:
                    if standard_schema:
                        vec = row.vec
                        meta = row.metadata
                        if isinstance(meta, str):
                             try: meta = json.loads(meta)
                             except: meta = {}
                        if not isinstance(meta, dict): meta = {}
                        
                        filename = meta.get("filename", "Unknown")
                        duration = meta.get("duration", 0)
                    else:
                        # Alternative Schema
                        vec = row.embedding
                        if row.artist and row.title:
                            filename = f"{row.artist} - {row.title}"
                        elif row.title:
                            filename = row.title
                        else:
                            filename = f"Track {row.id}"
                        duration = 0
                        youtube_id = (row.youtube_id or None) if has_youtube_col else None
                        
                    # Vector parsing (common)
                    if isinstance(vec, str):
                        try: vec = json.loads(vec)
                        except: pass
                    elif isinstance(vec, np.ndarray): vec = vec.tolist()
                    
                    entry = {
                        "id": str(row.id),
                        "filename": filename,
                        "duration": duration,
                        "vector": vec,
                        "source_collection": col_name
                    }
                    entry["youtube_id"] = youtube_id if not standard_schema else (meta.get("youtube_id") if isinstance(meta, dict) else None)
                    # When merging YouTube (all), exclude non-YouTube tracks so classic vectors are not mixed in
                    if merge_youtube_only and not entry.get("youtube_id"):
                        continue
                    self.track_map[str(row.id)] = entry
                    total_loaded += 1
            
            print(f"Total tracks loaded: {total_loaded}")
            
        except Exception as e:
            print(f"Error loading Render data: {e}")

    def _compute_outliers(self):
        """Identify outlier tracks that shouldn't be used for probing."""
        self.outlier_tracks = set()
        self.cluster_densities = {}
        
        if not self.cluster_manager.initialized: return
        
        for cid, tids in self.cluster_manager.clusters.items():
            if len(tids) < 3: continue
            cent = self.cluster_manager.centroids[cid]
            dists = []
            for tid in tids:
                if tid in self.track_map:
                    v = np.array(self.track_map[tid]['vector'])
                    d = np.linalg.norm(v - cent)
                    dists.append((tid, d))
            
            if dists:
                mean = np.mean([d for _,d in dists])
                std = np.std([d for _,d in dists])
                thresh = mean + 2*std
                for tid, d in dists:
                    if d > thresh: self.outlier_tracks.add(tid)
                
                self.cluster_densities[cid] = 1.0 / (mean + 0.01)
                
        print(f"Identified {len(self.outlier_tracks)} outliers")

    def init_bandit(self):
        if not self.cluster_manager.initialized or not self.cluster_manager.clusters:
            return
        for cid in self.cluster_manager.clusters.keys():
            self.cluster_scores[cid] = {'alpha': BANDIT_ALPHA_PRIOR, 'beta': BANDIT_BETA_PRIOR}

    # Similarity Helper (Replaces recommend_tracks)
    def _recommend_similar(self, target_vecs, avoid_ids, limit=20, negative_vecs=None, whitelist_ids=None, force_target=False):
        if not target_vecs: return []
        
        # User Strategy: "look at every song ive liked before in that session and move to their averages"
        # We use session_likes if available, otherwise target_vecs (which is just user_vector)
        # But wait, target_vecs passed in is [self.user_vector].
        
        # 1. Calculate Positive Center & Variance (Gaussian Scoring)
        # User Strategy: "user interactions to scale the vectors... mathematical patterns"
        # We calculate the Mean (Centroid) and Variance (Spread) of the session likes.
        
        mean_target = None
        variance_target = 1.0 # Default wide variance
        
        if self.session_likes and not force_target:
            # Stack vectors to (N, D) array
            likes_matrix = np.array(self.session_likes)
            
            # Mean Vector (Center of the "Subcluster")
            mean_target = np.mean(likes_matrix, axis=0)
            
            # Variance (Spread of the "Subcluster")
            # We calculate average squared distance from mean to get a scalar variance proxy
            # (Simplification of Covariance Matrix for performance)
            
            feature_weights = None
            
            if len(self.session_likes) > 1:
                # 1. Scalar Variance
                dists = np.linalg.norm(likes_matrix - mean_target, axis=1)
                variance_target = np.mean(dists**2)
                # Clamp variance to avoid over-fitting (div by zero)
                variance_target = max(0.01, variance_target) 
                
                # 2. Feature Weighting (New Logic)
                # "prioritise that similar dimension and demote other meaningless dimensions"
                std_per_dim = np.std(likes_matrix, axis=0)
                # Inverse variance weighting: High variance -> Low weight
                raw_weights = 1.0 / (std_per_dim + 1e-6)
                # Normalize so mean weight is 1.0 (Preserve overall magnitude)
                feature_weights = raw_weights / np.mean(raw_weights)
                
                # Log central features
                top_dims = np.argsort(feature_weights)[-3:][::-1]
                print(f"[ALGO] Feature Weighting Active. Top Dims: {top_dims} (Weights: {feature_weights[top_dims].round(2)})")
                
                # Apply weights to mean target immediately for efficiency
                # We will also apply to candidates in the loop
                # mean_target is already set, but we need a weighted version for distance calc
                
                # User Instruction: "scale the vectors"
                # If variance is low, we punish distant tracks MORE (Zoom In).
                # If variance is high, we punish distant tracks LESS (Wide Net).
            else:
                variance_target = 0.15 # TIGHT default for single track (Strong Lock-in)
            
            # Blend with RL vector if available (Long-term drift)
            if self.user_vector is not None:
                mean_target = 0.8 * mean_target + 0.2 * np.array(self.user_vector)
        else:
            mean_target = np.mean(target_vecs, axis=0)
            if force_target:
                 # When forcing target (Vibe Lock), use very tight variance
                 # UNLESS the user is skipping (Fail Count > 0).
                 # If skipping, we RELAX the lock to allow "Free Flowing" adjustment.
                 if self.cluster_fail_count > 0:
                     variance_target = 0.2
                     print(f"[ALGO] Vibe Lock Relaxed (Fail {self.cluster_fail_count}) -> Variance set to {variance_target} (Flowing)")
                 else:
                     variance_target = 0.05 
                     print(f"[ALGO] Forcing Target: Variance set to {variance_target} (Tight Lock)")
            else:
                 variance_target = 1.0 # Default
            feature_weights = None # No weighting if only 1 target or default
            
        # Panic Tightening: If user is skipping a lot in this cluster, narrow the focus drastically
        # REMOVED per user request: "drill in without actually locking me in"
        # We don't want to narrow focus on failures, we want to allow DRIFT (handled by relaxed variance above).
        # if self.cluster_fail_count > 2:
        #    variance_target *= 0.5
        #    print(f"[ALGO] Panic Tightening (Fail {self.cluster_fail_count}) -> Reducing Variance to {variance_target:.4f}")
            
        print(f"[ALGO] Sub-cluster Stats: MeanNorm={np.linalg.norm(mean_target):.2f}, Var={variance_target:.4f}")
        
        candidates = []
        
        # Optimization: Iterate only whitelist if provided and smaller than track_map
        search_space = self.track_map.keys()
        if whitelist_ids is not None:
            search_space = [tid for tid in whitelist_ids if tid in self.track_map]
            print(f"[ALGO] Cluster Locking Active: Restricted to {len(search_space)} tracks")
            
        # Pre-calculate weighted mean if needed
        mean_target_weighted = mean_target
        if feature_weights is not None:
             mean_target_weighted = mean_target * np.sqrt(feature_weights)
            
        # Prepare Negative Vectors (Session + Persistent Cluster)
        all_negatives = []
        if negative_vecs:
            all_negatives.extend(negative_vecs)
            
        # Load persistent cluster negatives if we are in a cluster
        if self.current_cluster_id is not None:
            # Check if we need to load (cache miss or cluster change)
            if self.current_cluster_id != self.loaded_cluster_id:
                self.active_cluster_negatives = user_db.get_cluster_negatives(self.user_id, self.current_cluster_id, self.collection_name)
                self.loaded_cluster_id = self.current_cluster_id
                print(f"[ALGO] Loaded {len(self.active_cluster_negatives)} persistent negatives for Cluster {self.current_cluster_id}")
            
            # Add to effective list
            if self.active_cluster_negatives:
                all_negatives.extend(self.active_cluster_negatives)

        for tid in search_space:
            t = self.track_map[tid]
            if tid in avoid_ids: continue
            if not self._track_valid_for_mode(t): continue
            v = np.array(t['vector'])
            
            # Gaussian Similarity: exp(-distance^2 / (2 * variance))
            # This creates a "soft boundary" based on user behavior.
            
            # Weighted Distance Calculation
            if feature_weights is not None:
                v_weighted = v * np.sqrt(feature_weights)
                # Weighted Euclidean Distance Squared
                dist_sq = np.sum((mean_target_weighted - v_weighted)**2)
                
                # Weighted Cosine Similarity
                # Note: We use the weighted vectors for dot product and norms
                cosine_sim = np.dot(mean_target_weighted, v_weighted) / (np.linalg.norm(mean_target_weighted)*np.linalg.norm(v_weighted) + 1e-8)
            else:
                # Standard Euclidean/Cosine
                dist_sq = np.sum((mean_target - v)**2)
                cosine_sim = np.dot(mean_target, v) / (np.linalg.norm(mean_target)*np.linalg.norm(v) + 1e-8)
            
            cosine_dist = 1.0 - cosine_sim
            
            # Apply Variance Scaling (The "Mathematical Pattern")
            # Score = exp( - (Distance) / (Sensitivity * Variance) )
            # We map 1.0 (perfect) to 1.0, and decay based on variance.
            # Low variance -> Fast decay (Only very close songs get high score)
            # High variance -> Slow decay (Distant songs get decent score)
            
            # Sensitivity constant to tune the curve
            sigma = max(0.05, np.sqrt(variance_target)) # Std Dev
            
            # Gaussian Score
            sim_score = np.exp( - (cosine_dist**2) / (2 * (sigma**2)) )
            
            # 2. Negative Filtering (Active Avoidance)
            penalty = 0.0
            penalty_breakdown = []
            if all_negatives:
                for d_vec in all_negatives:
                    d_vec = np.array(d_vec)
                    # For dislikes, we also want a "Zone of Avoidance"
                    # We can use a fixed tight variance for dislikes (Specific rejection)
                    d_sim = np.dot(d_vec, v) / (np.linalg.norm(d_vec)*np.linalg.norm(v) + 1e-8)
                    
                    # Widen the dislike influence zone (0.7 -> 0.6)
                    if d_sim > 0.65:
                        # ZONE REFINEMENT (Hole Punching)
                        # User Request: "marks that specific 'Sad Song' spot as a Negative Zone"
                        # We use a TIGHT sigma to punch a sharp hole without killing the genre.
                        d_dist = 1.0 - d_sim
                        # Sigma 0.08 = Very sharp hole. 
                        # Penalty 3.0 = Absolute rejection at center.
                        d_penalty_score = np.exp( - (d_dist**2) / (2 * (0.08**2)) ) 
                        p_val = d_penalty_score * 3.0
                        penalty += p_val
                        # penalty_breakdown.append(f"{p_val:.2f}") # Too verbose for inner loop
            
            final_score = sim_score - penalty
            
            # MULTI-TARGET OVERLAP BOOST (New Logic)
            # "if a song is close to 4 out of 5 songs that ive liked then play it"
            # If we have multiple target vectors (overlap mode), boost score if close to MANY of them
            if len(target_vecs) > 1 and not force_target:
                close_count = 0
                for t_vec in target_vecs:
                    # Check individual closeness to each liked song
                    sub_sim = np.dot(t_vec, v) / (np.linalg.norm(t_vec)*np.linalg.norm(v) + 1e-8)
                    if sub_sim > 0.85: # Threshold for "close"
                        close_count += 1
                
                # Boost based on coverage ratio
                coverage_ratio = close_count / len(target_vecs)
                if coverage_ratio > 0.5:
                     boost = coverage_ratio * 0.2 # Up to 20% boost for perfect overlap
                     final_score += boost
                     # print(f"  -> Boosted {t['filename']} by {boost:.2f} (Overlap {close_count}/{len(target_vecs)})")

            candidates.append((t, final_score, sim_score, penalty))

            
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Debug Top 5
        print(f"[ALGO] Top 5 Candidates for Similarity Recommendation:")
        for i, c in enumerate(candidates[:5]):
            t, fs, ss, pen = c
            print(f"  {i+1}. {t['filename']} | Score: {fs:.4f} (Sim: {ss:.4f} - Pen: {pen:.4f})")

        return [c[0] for c in candidates[:limit]]

    def _get_anchor_candidates(self, anchor_vector, variance=1.0, limit=20):
        """
        Radial Probing: Find tracks around a central anchor with a specific variance.
        Used for Smart Exploration and Session Flow.
        """
        if anchor_vector is None: return []
        
        candidates = []
        anchor = np.array(anchor_vector)
        sigma = max(0.05, np.sqrt(variance))
        
        print(f"[ALGO] Radial Probing: Sigma={sigma:.2f}, Variance={variance:.2f}")
        
        # Combined Avoidance Set
        avoid_ids = self.played_ids.union(self.global_dislikes).union(self.outlier_tracks)
        
        for tid, t in self.track_map.items():
            if tid in avoid_ids: continue
            if not self._track_valid_for_mode(t): continue
            
            v = np.array(t['vector'])
            
            # Distance to Anchor
            cosine_sim = np.dot(anchor, v) / (np.linalg.norm(anchor)*np.linalg.norm(v) + 1e-8)
            cosine_dist = 1.0 - cosine_sim
            
            # Gaussian Score
            # We want high score for things close to anchor
            score = np.exp( - (cosine_dist**2) / (2 * (sigma**2)) )
            
            candidates.append((t, score))
            
        # Sort by score
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        print(f"[ALGO] Top 5 Anchor Candidates:")
        for i, c in enumerate(candidates[:5]):
            print(f"  {i+1}. {c[0]['filename']} | Score: {c[1]:.4f}")
            
        return [c[0] for c in candidates[:limit]]

    def update_user_vector(self, track_vector, direction):
        """
        Reinforcement Learning Update:
        Moves the user_vector towards or away from the track_vector.
        direction: +1 for Like/Finish (towards), -1 for Dislike/Skip (away)
        """
        # Boost initial learning rates for first few interactions to lock in faster
        is_early = (len(self.session_likes) + len(self.session_dislikes)) < 5
        
        LEARNING_RATE_POS = 0.2 if is_early else 0.1
        LEARNING_RATE_NEG = 0.25 if is_early else 0.2 # Significantly increased per user request
        
        if self.user_vector is None:
            if direction > 0:
                self.user_vector = np.array(track_vector)
                print("Initialized User Vector with first like.")
            return

        u_vec = np.array(self.user_vector)
        t_vec = np.array(track_vector)
        
        # Use magnitude of direction to scale the update
        scale = abs(direction)
        
        if direction > 0:
            # Move towards: New = Old + LR * (Target - Old)
            delta = t_vec - u_vec
            u_vec = u_vec + (LEARNING_RATE_POS * scale) * delta
            print(f"RL Update: Moved User Vector TOWARDS track (Scale {scale:.2f})")
        else:
            # Move away: New = Old - LR * (Target - Old)
            delta = t_vec - u_vec
            u_vec = u_vec - (LEARNING_RATE_NEG * scale) * delta
            print(f"RL Update: Moved User Vector AWAY from track (Scale {scale:.2f})")
            
        if np.linalg.norm(u_vec) > 0: u_vec /= np.linalg.norm(u_vec)
        self.user_vector = u_vec.tolist()

    def set_seed(self, track_id):
        t = self.track_map.get(track_id)
        if t:
            print(f"[ALGO] Manual Selection: {t['filename']} - OVERRIDING SESSION STATE")
            
            # 1. Hard Reset of User Vector
            self.user_vector = t['vector']
            
            # 2. Set Anchors
            self.last_track = t
            self.anchor_track = t
            self.played_ids.add(track_id)
            
            # 3. Force Deep Lock (Highest Order Input)
            self.streak = 5 # Instant max streak
            self.cluster_consecutive_success = 5 # Instant deep lock
            self.cluster_fail_count = 0
            self.exploration_drift = 0.0 # Zero drift
            
            # 4. Overwrite Session Context (The "Highest Order" decision)
            # We flood the session history with this track to force the Ratio Rule 
            # to see ONLY this vibe.
            self.session_likes = [t['vector']] * 5 
            
            # 5. Snap to Cluster
            best_cid = self._find_nearest_cluster(np.array(t['vector']), set())
            self.current_cluster_id = best_cid
            self.cluster_scores[best_cid]['alpha'] += 5.0 # Boost bandit score
            
            print(f"[ALGO] Seed Set. Switched to Cluster {best_cid}. Session Context Reset to target.")
            return t
        return None

    def is_duplicate(self, candidate_vector):
        if not self.history: return False
        recent = [h['vector'] for h in self.history[-50:] if 'vector' in h]
        if not recent: return False
        c = np.array(candidate_vector)
        if np.linalg.norm(c) == 0: return False
        
        for r in recent:
            rv = np.array(r)
            if np.linalg.norm(rv) == 0: continue
            sim = np.dot(c, rv)/(np.linalg.norm(c)*np.linalg.norm(rv))
            if sim > DUPLICATE_THRESHOLD: return True
        return False

    def select_cluster(self):
        best = None
        max_theta = -1
        print("Bandit Sampling...")
        for cid, s in self.cluster_scores.items():
            theta = np.random.beta(s['alpha'], s['beta'])
            if theta > max_theta:
                max_theta = theta
                best = cid
        print(f"Selected Cluster {best} (theta={max_theta:.2f})")
        return best

    def _is_unique(self, track):
        tid = str(track.get('id', ''))
        return (tid not in self.played_ids and track.get('filename') not in self.played_filenames)

    def _track_valid_for_mode(self, track):
        """Filter tracks by mode: youtube_mode requires youtube_id."""
        if not track: return False
        if self.youtube_mode and not track.get('youtube_id'):
            return False
        return True

    def _find_nearest_cluster(self, ref_centroid, skip_clusters):
        best = None
        min_d = float('inf')
        for cid, cent in self.cluster_manager.centroids.items():
            if cid in skip_clusters: continue
            d = np.linalg.norm(cent - ref_centroid)
            if d < min_d:
                min_d = d
                best = cid
        return best

    def get_next_track(self):
        candidates = []
        FETCH_LIMIT = 20
        mode = "EXPLORE"
        justification = "Random fallback"
        
        # Determine mode
        exploit_prob = 0.8 # Default to high exploitation
        
        # User Instruction: "as soon as a green signal comes it is time to exploit"
        # "green signal" defined as > 5s play.
        if self.streak >= 1 or self.cluster_consecutive_success >= 1:
            exploit_prob = 1.0
            justification = "Locked in (User liked previous tracks) - "
        
        # Only explore if drift is high (boredom detected via skips) AND we lost our streak
        # AND we have enough failures to justify a pivot.
        # User Complaint: "why did it say boredom detected after giving me 3 punjabi pop songs that i listened fully"
        # The drift check > 0.6 is too sensitive or accumulation is wrong.
        # If I listen fully, drift should decrease (reset).
        # Let's check update_state logic.
        
        if self.exploration_drift > 0.7 and self.streak == 0 and self.cluster_fail_count > 1:
             exploit_prob = 0.4 # Start exploring
             justification = "Boredom detected (Drift high) - "
        
        if self.user_vector is not None and np.random.random() < exploit_prob:
            mode = "EXPLOIT"
            if self.cluster_consecutive_success >= 3:
                justification += "Exploiting user taste vector (Deep Lock)"
            else:
                justification += f"Exploiting user taste vector (Streak: {self.streak})"
            
        print(f"[ALGO] Mode: {mode} | Drift: {self.exploration_drift:.2f} | Streak: {self.streak} | Fail: {self.cluster_fail_count}")
        
        if mode == "EXPLOIT" and self.user_vector is not None:
            whitelist = None
            target_vectors = [self.user_vector]
            force_target_flag = False
            
            # CLUSTER LOCKING:
            # If we are strictly locked in (Streak >= 1) and have a valid cluster context
            if self.streak >= 1 and self.current_cluster_id is not None:
                # ANCHOR LOCKING: Use ALL session likes (limited to recent) to find the overlap zone
                # "find the common parts between those two songs"
                
                # Filter session_likes to ensure we are using relevant context
                # Use the last 5 likes to define the current "vibe"
                recent_likes = self.session_likes[-5:] if self.session_likes else []
                
                # REMOVED "Black Sheep" Filtering:
                # To support Multi-Modal Vibe (e.g. 4 Punjabi + 1 Rap), we MUST include the outlier.
                # If the user liked it, it is NOT a mistake. It is a signal.
                # The random.choice() below handles the ratio naturally.

                if recent_likes:
                    # MULTI-MODAL SAMPLING (The Ratio Rule)
                    # "Respect the Ratio of your Reality"
                    # We DO NOT filter "Black Sheep" (outliers). If the user liked it, it's part of the vibe.
                    # 4 Punjabi + 1 Rap = 80% chance Punjabi, 20% chance Rap.
                    
                    selected_anchor = random.choice(recent_likes)
                    target_vectors = [selected_anchor]
                    
                    justification = f"Vibe Lock: Anchoring to specific recent like (Multi-Modal Ratio)"
                    print(f"[ALGO] Vibe Lock Active: Anchoring to single exemplar (from {len(recent_likes)} recent likes)")
                    
                    # Force target to ensure we lock tight to this specific exemplar
                    # This finds songs very similar to the exemplar (Punjabi -> Punjabi, Rap -> Rap)
                    force_target_flag = True 
                elif self.anchor_track:
                     # Fallback to single anchor if session_likes is empty (shouldn't happen if streak >= 1)
                     target_vectors = [self.anchor_track['vector']]
                     justification = f"Vibe Lock: Anchoring to '{self.anchor_track['filename']}'"
                     force_target_flag = True

                if self.current_cluster_id in self.cluster_manager.clusters:
                    cluster_tracks = self.cluster_manager.clusters[self.current_cluster_id]
                    # REMOVED CLUSTER WHITELISTING per user feedback
                    # "vibe lock all play horrible songs" -> forcing selection from bad clusters
                    # "radial probe... plays correct songs" -> radial probe has no whitelist
                    # We will now search the entire space but rely on the strong Anchor/Variance logic to keep it tight.
                    
                    # if len(cluster_tracks) > 5 and self.cluster_fail_count < 3:
                    #      whitelist = cluster_tracks
                    #      justification += f" (Restricted to Cluster {self.current_cluster_id})"
                    if self.cluster_fail_count >= 3:
                        print(f"[ALGO] Cluster {self.current_cluster_id} Failing ({self.cluster_fail_count} skips) -> Lifting Lock")

            # Strict uniqueness in candidates
            candidates_centroid = self._recommend_similar(target_vectors, self.played_ids, limit=FETCH_LIMIT, negative_vecs=self.disliked_vectors, whitelist_ids=whitelist, force_target=force_target_flag)
            
            # RADIAL PROBE INJECTION (User Request)
            # "slips in a track that is... slightly outside the usual safe zone"
            # We use a slightly WIDER variance (0.25) to find "Neighbors" not just clones.
            candidates_radial = []
            if self.session_likes:
                last_like = self.session_likes[-1]
                # Variance 0.25 = "Slightly Outside" (Neighboring sub-genre)
                candidates_radial = self._get_anchor_candidates(last_like, variance=0.25, limit=10)
                print(f"[ALGO] Radial Probe Injection: Found {len(candidates_radial)} neighbor candidates (Var 0.25).")

            # Merge Strategy: 
            # User says: "slips in a track" -> We don't want ONLY probes.
            # We want mostly "Ratio Rule" candidates (Vibe Lock), with 1-2 Probes mixed in.
            
            combined = []
            seen_ids = set()
            
            # 1. Add ONE high-quality Probe first (to ensure exploration)
            probes_added = 0
            for c in candidates_radial:
                if c['id'] not in seen_ids and c['id'] not in self.played_ids and c['id'] not in self.global_dislikes:
                    combined.append(c)
                    seen_ids.add(c['id'])
                    probes_added += 1
                    if probes_added >= 2: break # Limit to 2 probes at top
            
            # 2. Add Centroid/Ratio Candidates (The Core Vibe)
            for c in candidates_centroid:
                if c['id'] not in seen_ids:
                    combined.append(c)
                    seen_ids.add(c['id'])
            
            # 3. Add remaining Probes (if needed, at the bottom)
            # ... actually, we don't need more probes at the bottom. The core vibe is better.
            
            candidates = combined
            
            # Filter: played, outliers, dislikes, duplicates
            candidates = [
                c for c in candidates
                if c['filename'] not in self.played_filenames
                and c['id'] not in self.outlier_tracks
                and str(c['id']) not in {str(x) for x in self.global_dislikes}
                and not self.is_duplicate(c['vector'])
            ]
            
            if not candidates:
                print("Cluster Exhausted (No Candidates Left) - Switching to EXPLORE")
                mode = "EXPLORE" # Fallback to explore logic below
                self.streak = 0
                self.cluster_fail_count = 0
                self.exploration_drift = 1.0

        if mode == "EXPLORE": # Changed from 'else' to allow fallback from EXPLOIT
            # EXPLORE MODE - Refined Radial Probing
            # "start probing outwards from that... stop randomly giving users"
            
            anchor_vec = None
            probe_variance = 1.0
            
            if self.session_likes:
                # 1. Flow Outwards: Use session mean as anchor
                # "I might listen to some chil bollywood alongside chill hip hop and slowly flow outwards"
                anchor_vec = np.mean(self.session_likes, axis=0)
                probe_variance = 1.5 # Wide net for flow
                justification = "Flowing outwards from session taste (Radial Probe)"
                
            elif self.best_historical_cluster is not None and self.cluster_scores:
                # 2. Smart Start: Randomized Probing of High-Affinity Clusters
                # "everytime i open the app it probes me with the same tracks... has to be a better solution"
                # Solution: Sample from Top N clusters instead of always taking the absolute best.
                # AND: Anchor to a random REAL TRACK in that cluster, not the abstract centroid.
                
                # Get top 3 clusters by alpha (history score)
                sorted_clusters = sorted(self.cluster_scores.items(), key=lambda x: x[1]['alpha'], reverse=True)[:3]
                
                # Weighted selection
                cids = [x[0] for x in sorted_clusters]
                weights = [x[1]['alpha'] for x in sorted_clusters]
                total_w = sum(weights)
                probs = [w/total_w for w in weights]
                
                selected_cid = np.random.choice(cids, p=probs)
                
                # Get tracks in this cluster
                cluster_tracks = self.cluster_manager.get_cluster_tracks(selected_cid)
                
                # Filter out played/disliked to find a valid start seed
                valid_seeds = [tid for tid in cluster_tracks if tid not in self.global_dislikes and tid not in self.outlier_tracks and self._track_valid_for_mode(self.track_map.get(tid))]
                
                if valid_seeds:
                    # Pick a random track as the anchor (Real Track Anchoring)
                    seed_id = random.choice(valid_seeds)
                    seed_track = self.track_map.get(seed_id)
                    if seed_track:
                        anchor_vec = seed_track['vector']
                        probe_variance = 0.8 # Slightly tighter since we are on a real track
                        justification = f"Smart Start: Probing Cluster {selected_cid} (Anchor: {seed_track['filename']})"
                        self.current_cluster_id = selected_cid
                
                if anchor_vec is None: # Fallback if no valid seeds
                    anchor_vec = self.cluster_manager.centroids[selected_cid]
                    probe_variance = 1.0
                    justification = f"Smart Start: Probing Cluster {selected_cid} (Centroid)"
                
            else:
                # 3. Cold Start: Pick a random HIGH DENSITY cluster (Safe bet)
                # Avoid outliers/sparse clusters
                dense_clusters = [cid for cid, dens in self.cluster_densities.items() if dens > 0.5]
                if not dense_clusters: dense_clusters = list(self.cluster_manager.centroids.keys())
                
                if dense_clusters:
                    cid = random.choice(dense_clusters)
                    # Pick random track instead of centroid for variety
                    cluster_tracks = self.cluster_manager.get_cluster_tracks(cid)
                    valid_seeds = [tid for tid in cluster_tracks if tid not in self.global_dislikes and self._track_valid_for_mode(self.track_map.get(tid))]
                    
                    if valid_seeds:
                        seed_id = random.choice(valid_seeds)
                        seed_track = self.track_map.get(seed_id)
                        anchor_vec = seed_track['vector']
                        probe_variance = 1.0
                        justification = f"Cold Start: Probing Cluster {cid} (Random Track)"
                    else:
                        anchor_vec = self.cluster_manager.centroids[cid]
                        justification = f"Cold Start: Probing Cluster {cid} (Centroid)"
                        
                    self.current_cluster_id = cid
            
            # Get Candidates
            candidates = self._get_anchor_candidates(anchor_vec, variance=probe_variance, limit=FETCH_LIMIT)
            
            if not candidates:
                 # Absolute fallback if everything is filtered
                 print("Warning: Radial probe empty, falling back to random safe track.")
                 all_safe = [t for t in self.track_map.values() if t['id'] not in self.outlier_tracks and t['id'] not in self.global_dislikes and self._track_valid_for_mode(t)]
                 if all_safe:
                     candidates = [random.choice(all_safe)]
                     justification = "Emergency Random Fallback"

        # Final filtering: exclude duplicates and ensure uniqueness
        filtered = []
        for c in candidates:
            if c['id'] in self.played_ids or c['filename'] in self.played_filenames:
                continue
            if str(c['id']) in {str(x) for x in self.global_dislikes}:
                continue
            if self.is_duplicate(c.get('vector', [])):
                continue
            filtered.append(c)
        candidates = filtered
        
        if not candidates:
            return None, "No tracks available"
            
        # Select best candidate (Top 1)
        selected_track = candidates[0]
        
        # Update state
        self.last_track = selected_track
        self.played_ids.add(str(selected_track['id']))
        self.played_filenames.add(selected_track['filename'])
        
        # Find which cluster this track belongs to for logging
        # (Approximate by distance to centroids)
        best_cid = self._find_nearest_cluster(np.array(selected_track['vector']), set())
        self.current_cluster_id = best_cid
        
        return selected_track, justification

    def get_next_batch(self):
        # Wrapper for server_user
        size = 5
        batch = []
        for _ in range(size):
            t, reason = self.get_next_track()
            if t: 
                item = {"id": t['id'], "filename": t['filename'], "justification": reason}
                if self.youtube_mode and t.get('youtube_id'):
                    item["youtube_id"] = t['youtube_id']
                batch.append(item)
        return batch

    def finalize_batch(self):
        """
        Called when a batch of tracks is exhausted.
        Can be used to trigger batch-level updates or logging.
        """
        print(f"Batch finalized. Streak: {self.streak}, Drift: {self.exploration_drift:.2f}")

    def record_feedback(self, track_id, duration):
        """
        Record feedback and update persistent storage.
        Alias for update_feedback but adds DB persistence.
        """
        # 1. Update internal state
        self.update_feedback(track_id, duration)
        
        # 2. Update persistent DB
        is_positive = duration >= GOOD_ENGAGE_SEC
        if self.current_cluster_id is not None:
             user_db.update_cluster_affinity(
                 user_id=self.user_id,
                 cluster_id=self.current_cluster_id,
                 listen_seconds=duration,
                 is_positive=is_positive,
                 collection_name=self.collection_name
             )
             
             # Update centroid if we have a user vector
             if self.user_vector is not None:
                 user_db.update_cluster_centroid(
                     user_id=self.user_id,
                     cluster_id=self.current_cluster_id,
                     new_vector=np.array(self.user_vector),
                     weight=0.1,
                     collection_name=self.collection_name
                 )

    def update_feedback(self, track_id, duration):
        # Renamed from feedback to update_feedback
        # Dynamic Thresholds based on user instruction:
        # "baseline being at atleast 15-20 seconds or 10-20% of the song"
        
        t = self.track_map.get(track_id)
        total_duration = t.get('duration', 0) if t else 0
        if total_duration == 0: total_duration = 200 # Default assumption if missing
        
        pct_listened = duration / total_duration if total_duration > 0 else 0
        
        # Good engagement: >20s OR >15% of song
        is_good = (duration >= 20) or (pct_listened >= 0.15)
        
        # Strong engagement (Like): >45s OR >40% of song
        liked = (duration >= 45) or (pct_listened >= 0.40)
        
        # Dislike/Skip: Not good engagement
        # But we distinguish "Instant Skip" (<5s) for stronger penalties if needed
        disliked = duration < 5.0 
        
        finished = (pct_listened >= 0.90) or (duration >= 120)

        # Pass "is_good" as a signal to feedback_internal to avoid "Quick Skip" logic
        # We reuse 'liked' for strong positive, but we need to handle "not skipped but not strong like"
        # Logic in feedback_internal handles "else: if duration < QUICK_SKIP..."
        # We will override the logic inside feedback_internal slightly or just pass the right signals.
        
        # To make it clean, let's just use the duration passed to feedback_internal
        # and update feedback_internal to check these dynamic thresholds.
        # However, feedback_internal uses hardcoded QUICK_SKIP_SEC. 
        # So we should probably modify feedback_internal. 
        # For now, let's just pass raw duration and handle dynamic check there.
        
        self.feedback_internal(track_id, duration, liked, disliked, finished, total_duration)
        
    def feedback_internal(self, track_id, duration, liked, disliked, finished, total_duration=0):
        t = self.track_map.get(track_id)
        if not t: return
        vector = t.get('vector')
        
        # Dynamic skip check
        if total_duration == 0: total_duration = 200
        pct_listened = duration / total_duration
        
        # User defined "Green Signal": At least 15-20s OR 10-20%
        is_green_signal = (duration >= 15) or (pct_listened >= 0.10)
        
        print(f"[ALGO] Feedback: Dur={duration}s ({pct_listened*100:.1f}%) | GreenSignal={is_green_signal} | Liked={liked} | Disliked={disliked}")

        alpha_boost, beta_boost = 0, 0
        rl_dir = 0
        drift_delta = 0
        
        # Logic from paste
        if disliked: # Explicit dislike or < 5s (passed from update_feedback)
            # Don't punish cluster too hard, just move user vector away
            # User Instruction: "doesnt mean my like was wrong, it means my dislike is a signal to zoom in more"
            
            # If we are in exploit mode (streak > 0), a dislike shouldn't trigger full panic.
            # User said: "reset only when the behaviour is unpredictable"
            
            self.cluster_fail_count += 1
            print(f"Cluster Fail Count: {self.cluster_fail_count}/5")
            
            if self.cluster_fail_count > 5:
                # Unpredictable behavior / Exhaustion
                self.streak = 0
                self.cluster_consecutive_success = 0
                self.cluster_fail_count = 0
                rl_dir = -1.0
                drift_delta = 1.0 # FORCE EXPLORATION
                print("Cluster Exhausted/Unpredictable - Breaking Out!")
            else:
                # Just refining
                # drift_delta = 0.0 # Stay in cluster - NO! 
                # User complaint: "boredom detected" after 3 likes and 1 skip.
                # If I skip after 3 likes, my drift should NOT go up significantly if I was locked in.
                # In fact, we should actively DECREASE drift or keep it low to stay in EXPLOIT mode.
                drift_delta = -0.1 # Keep drift low, reinforce lock-in
                rl_dir = -1.0 # Strong move away to refine cluster
                print("Refining Cluster Focus (Staying in Cluster - Drift Suppressed)")
            
            self.disliked_vectors.append(vector)
            self.session_dislikes.append(vector) # Add to session history
            self.global_dislikes.add(str(track_id))  # Immediate avoidance
            if len(self.disliked_vectors) > 50: self.disliked_vectors.pop(0)
            
        elif liked:
            alpha_boost = 1.0
            self.streak += 1
            self.cluster_consecutive_success += 1
            self.anchor_track = t # Update anchor to the successful track
            self.cluster_fail_count = 0 # Reset fail count
            rl_dir = 1.0
            drift_delta = -0.5 # STRONG DECREASE to fix "Boredom" bug
            self.session_likes.append(vector) # Add to session history
            
        else: # Time based / Green Signal check
            if not is_green_signal: # Replaces duration < QUICK_SKIP_SEC
                # Treat as true skip/boredom/drifting factor
                # User Request: "instant skips should be treated as drifting factors"
                # "incorporate this free flowing behaviour where my interaction keeps shaping the flow"
                
                self.cluster_fail_count += 1
                print(f"Cluster Fail Count (Skip): {self.cluster_fail_count}/5")
                
                if self.cluster_fail_count > 5:
                    self.streak = 0
                    self.cluster_consecutive_success = 0
                    self.cluster_fail_count = 0
                    rl_dir = -0.8
                    drift_delta = 1.0 # FORCE EXPLORATION
                    print("Cluster Exhausted (Skips) - Breaking Out!")
                else:
                    # Refine but Allow Drift
                    # Previous: drift_delta = -0.05 (Suppress) -> WRONG. 
                    # New: drift_delta = +0.15 (Accumulate Drift). 
                    # This allows the user to "flow" out of a vibe if they start skipping,
                    # without an abrupt "Break Out" unless they really persist.
                    drift_delta = 0.15 
                    rl_dir = -1.0 # Strong push away from this specific track
                    print("Refining Cluster Focus (Skip - Drifting +0.15 - Moving Away)")
                    
                self.session_dislikes.append(vector)
                self.global_dislikes.add(str(track_id))
                self.disliked_vectors.append(vector)
                
            else: # is_green_signal (>=15s or >=10%)
                # Treat as positive engagement, sufficient to trigger lock-in
                alpha_boost = 0.2
                self.streak += 1 
                self.anchor_track = t # Update anchor to the successful track
                self.cluster_fail_count = 0 # Reset fail count
                rl_dir = 0.3
                drift_delta = -0.05
                self.session_likes.append(vector) # Add to session history

        # Apply drift change
        # User Instruction: "why did it say boredom detected after giving me 3 punjabi pop songs that i listened fully"
        # If we had 3 successes, drift should be 0.
        # If we then have 1 skip (disliked=True), drift_delta was +0.0 or +0.2
        # If exploration_drift was 0, it becomes 0.2.
        # Threshold is > 0.6 (or 0.7 now).
        # So it shouldn't have triggered boredom unless drift wasn't reset properly.
        # Check update_state drift reset logic.
        # It resets drift on LIKE. 
        # But wait, feedback_internal is called AFTER update_state in record_feedback?
        # Let's check record_feedback.
        
        self.exploration_drift = max(0.0, min(1.0, self.exploration_drift + drift_delta))
        print(f"Feedback {duration}s -> Drift {self.exploration_drift:.2f}, RL {rl_dir}")
        
        # Session Centroid
        if rl_dir > 0.2:
            v = np.array(vector)
            if self.session_centroid is None: self.session_centroid = v
            else: self.session_centroid = 0.7 * self.session_centroid + 0.3 * v
            
        # RL
        if rl_dir != 0: self.update_user_vector(vector, rl_dir)
        
        # Bandit - Minimal Cluster Penalization
        # We only boost alpha (positive), we don't heavily boost beta (negative) 
        # to avoid killing the cluster. We rely on RL to move away from bad songs.
        if self.current_cluster_id is not None:
             self.cluster_scores[self.current_cluster_id]['alpha'] += alpha_boost
             self.cluster_scores[self.current_cluster_id]['beta'] += beta_boost

        self.history.append({'id': track_id, 'vector': vector, 'duration': duration})
        
        # Persistent Cluster Negative
        # User Instruction: "if i enter the punjabi zone... save that... insert me in the exact moment"
        # We save skips/dislikes that happen while LOCKED IN (streak > 0) to refine the cluster definition.
        is_negative = disliked or (not liked and not is_green_signal)
        if is_negative and self.current_cluster_id is not None and self.streak > 0:
             print(f"[ALGO] Persisting Cluster Negative for Cluster {self.current_cluster_id} (Refining Vibe)")
             user_db.add_cluster_negative(self.user_id, self.current_cluster_id, vector, track_id, self.collection_name)
             # Also add to active cache immediately so it affects next track in same session
             self.active_cluster_negatives.append(vector)

    def search(self, query):
        q = query.lower()
        res = []
        for t in self.track_map.values():
            if not self._track_valid_for_mode(t): continue
            if q in t['filename'].lower():
                res.append(t)
                if len(res) >= 20: break
        return res
