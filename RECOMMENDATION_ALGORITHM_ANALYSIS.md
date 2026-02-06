# ChaarFM Recommendation Algorithm Analysis

## Executive Summary

The ChaarFM recommendation system implements a sophisticated cluster-based recommendation engine that uses multi-armed bandit algorithms, reinforcement learning, and real-time user interaction analysis to deliver personalized music recommendations. The system is designed to handle cluster-based probing where user engagement with distinct music clusters (like Bollywood, Punjabi, etc.) directly influences the recommendation ratios in real time.

## Core Architecture Overview

### 1. Dual Recommendation Systems

The codebase contains two primary recommendation systems:

#### A. **UserRecommender** (Primary - user_recommender.py)
- **Purpose**: Production-grade user-aware recommendations with persistent profiles
- **Features**: Session-based learning, cluster affinity tracking, multi-modal support
- **Database Integration**: Full PostgreSQL integration with user profiles, cluster affinity, and interaction logging

#### B. **BatchRecommender** (Secondary - batch_recommender.py) 
- **Purpose**: Batch-oriented recommendations with detailed mathematical logging
- **Features**: Transparent decision-making, nuanced track selection with positive/negative centroids
- **Use Case**: Primarily for analysis and debugging

### 2. Clustering Architecture

Both systems use **KMeans clustering** to segment the music library:

```python
# UserRecommender: 10-20 clusters (optimized for speed)
self.cluster_manager = ClusterManager(self.track_map, n_clusters=10)

# BatchRecommender: 50 clusters (detailed analysis)
N_CLUSTERS = 50
```

**Key Features:**
- **Dynamic Cluster Assignment**: Each track belongs to exactly one cluster
- **Centroid Calculation**: Mathematical center point for each cluster
- **Representative Selection**: Tracks closest to cluster centroid for exploration
- **Outlier Detection**: Identification and exclusion of tracks that don't fit well in any cluster

## User Interaction Processing & Cluster-Based Probing

### 1. Engagement Tracking System

The system tracks multiple levels of user engagement:

```python
# Dynamic Thresholds (user_recommender.py)
def update_feedback(self, track_id, duration):
    total_duration = t.get('duration', 0) if t else 0
    if total_duration == 0: total_duration = 200
    
    pct_listened = duration / total_duration
    
    # Good engagement: >20s OR >15% of song
    is_good = (duration >= 20) or (pct_listened >= 0.15)
    
    # Strong engagement (Like): >45s OR >40% of song
    liked = (duration >= 45) or (pct_listened >= 0.40)
    
    # Dislike/Skip: <5s 
    disliked = duration < 5.0 
    
    # Finished: >90% OR >120s
    finished = (pct_listened >= 0.90) or (duration >= 120)
```

### 2. Real-Time Ratio Calculation

**For cluster-based probing (Bollywood vs Punjabi example):**

#### A. Session Likes Tracking
```python
# Each positive interaction adds to session_likes
if liked or is_green_signal:
    self.session_likes.append(vector) # Add track's vector to session history
    self.streak += 1
    self.cluster_consecutive_success += 1
```

#### B. Multi-Modal Ratio Enforcement
```python
# MULTI-MODAL SAMPLING (The Ratio Rule)
# "Respect the Ratio of your Reality"
if recent_likes:
    # 4 Punjabi + 1 Rap = 80% chance Punjabi, 20% chance Rap
    selected_anchor = random.choice(recent_likes)
    target_vectors = [selected_anchor]
```

**Real-time example:**
- User likes 2 Bollywood tracks → `session_likes` contains 2 Bollywood vectors
- User likes 2 Punjabi tracks → `session_likes` contains 2 Bollywood + 2 Punjabi vectors
- **Next recommendation**: `random.choice(session_likes)` gives 50% Bollywood, 50% Punjabi probability
- **System automatically maintains the exact ratio based on user's demonstrated preferences**

### 3. Skip Processing & Immediate Updates

When a user skips a recommendation:

```python
def feedback_internal(self, track_id, duration, liked, disliked, finished, total_duration=0):
    if not is_green_signal: # Skip detected
        self.cluster_fail_count += 1
        
        if self.cluster_fail_count > 5:
            # Cluster exhausted - break out and explore
            self.streak = 0
            self.exploration_drift = 1.0 # Force exploration
        else:
            # Refine current cluster
            drift_delta = 0.15  # Accumulate drift for gradual transition
            rl_dir = -1.0       # Move user vector away from skipped track
            
        # Immediate negative reinforcement
        self.session_dislikes.append(vector)
        self.global_dislikes.add(str(track_id))  # Permanent avoidance
        self.disliked_vectors.append(vector)
```

**Immediate Impact:**
1. **User Vector Update**: Reinforcement learning immediately moves the user preference vector away from skipped content
2. **Cluster Penalty**: The current cluster receives negative feedback
3. **Global Blacklist**: Skipped track is permanently excluded from future recommendations
4. **Ratio Rebalancing**: If the skip breaks a successful streak, the system increases exploration to find the preferred cluster

## Recommendation Generation Logic

### 1. Mode Selection Algorithm

```python
def get_next_track(self):
    exploit_prob = 0.8 # Default exploitation probability
    
    # Lock-in on success: "as soon as a green signal comes it is time to exploit"
    if self.streak >= 1 or self.cluster_consecutive_success >= 1:
        exploit_prob = 1.0
        mode = "EXPLOIT"
    
    # Exploration trigger: high drift + no streak + multiple failures
    if self.exploration_drift > 0.7 and self.streak == 0 and self.cluster_fail_count > 1:
        exploit_prob = 0.4
        mode = "EXPLORE"
```

### 2. Exploit Mode: Ratio-Based Recommendations

**When the system has identified user preferences:**

```python
if mode == "EXPLOIT" and self.user_vector is not None:
    # CLUSTER LOCKING & RATIO ENFORCEMENT
    if self.streak >= 1 and self.current_cluster_id is not None:
        # Use recent session likes for ratio calculation
        recent_likes = self.session_likes[-5:] if self.session_likes else []
        
        if recent_likes:
            # MULTI-MODAL SAMPLING: Respect demonstrated preferences
            selected_anchor = random.choice(recent_likes)
            target_vectors = [selected_anchor]
            force_target_flag = True # Tight similarity matching
```

**Mathematical Similarity Calculation:**
```python
def _recommend_similar(self, target_vecs, avoid_ids, limit=20, negative_vecs=None):
    # 1. Calculate session centroid and variance
    if self.session_likes and not force_target:
        likes_matrix = np.array(self.session_likes)
        mean_target = np.mean(likes_matrix, axis=0)  # Center of user's taste
        
        # Variance controls recommendation tightness
        dists = np.linalg.norm(likes_matrix - mean_target, axis=1)
        variance_target = np.mean(dists**2)
        
        # Feature weighting: emphasize consistent dimensions
        std_per_dim = np.std(likes_matrix, axis=0)
        feature_weights = 1.0 / (std_per_dim + 1e-6)
        feature_weights = feature_weights / np.mean(feature_weights)
    
    # 2. Score candidates using Gaussian similarity
    for tid in search_space:
        v = np.array(t['vector'])
        
        if feature_weights is not None:
            v_weighted = v * np.sqrt(feature_weights)
            mean_target_weighted = mean_target * np.sqrt(feature_weights)
            dist_sq = np.sum((mean_target_weighted - v_weighted)**2)
        else:
            dist_sq = np.sum((mean_target - v)**2)
        
        # Gaussian scoring: tighter variance = more selective recommendations
        sigma = max(0.05, np.sqrt(variance_target))
        sim_score = np.exp( - (cosine_dist**2) / (2 * (sigma**2)) )
        
        # Negative filtering: avoid previously disliked content
        penalty = 0.0
        for d_vec in all_negatives:
            d_sim = np.dot(d_vec, v) / (np.linalg.norm(d_vec)*np.linalg.norm(v) + 1e-8)
            if d_sim > 0.65:
                penalty += np.exp( - ((1.0-d_sim)**2) / (2 * (0.08**2)) ) * 3.0
        
        final_score = sim_score - penalty
```

### 3. Explore Mode: Smart Cluster Probing

**When the system needs to discover new preferences:**

```python
if mode == "EXPLORE":
    # Historical cluster prioritization
    if self.best_historical_cluster is not None:
        # Top 3 historical clusters with weighted selection
        sorted_clusters = sorted(self.cluster_scores.items(), 
                               key=lambda x: x[1]['alpha'], reverse=True)[:3]
        cids = [x[0] for x in sorted_clusters]
        weights = [x[1]['alpha'] for x in sorted_clusters]
        
        # Probabilistic selection prevents repetitive probing
        selected_cid = np.random.choice(cids, p=normalized_weights)
    
    # Radial probing from anchor
    candidates = self._get_anchor_candidates(anchor_vec, variance=probe_variance, limit=FETCH_LIMIT)
```

## Cluster Affinity & Persistent Learning

### 1. Database Schema for Cluster Tracking

```sql
-- Tracks user engagement with each cluster
CREATE TABLE cluster_affinity (
    user_id TEXT,
    cluster_id INTEGER,
    collection_name TEXT,
    positive_signals INTEGER DEFAULT 0,      -- Count of good interactions
    total_listen_seconds REAL DEFAULT 0,     -- Total time spent
    track_count INTEGER DEFAULT 0,          -- Number of tracks tried
    session_rejections INTEGER DEFAULT 0,    -- Number of skips
    last_positive_date TEXT,                -- Most recent positive interaction
    PRIMARY KEY (user_id, cluster_id, collection_name)
);

-- Stores refined cluster centroids based on user taste
CREATE TABLE cluster_centroids (
    user_id TEXT,
    cluster_id INTEGER,  
    collection_name TEXT,
    centroid TEXT,              -- JSON array of the personalized centroid
    sample_count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, cluster_id, collection_name)
);

-- Records specific tracks the user disliked within clusters
CREATE TABLE cluster_negatives (
    user_id TEXT,
    cluster_id INTEGER,
    collection_name TEXT,
    vector TEXT,               -- Vector of disliked track
    track_id TEXT,
    created_at TEXT
);
```

### 2. Real-Time Affinity Updates

```python
def record_feedback(self, track_id, duration):
    # 1. Update internal session state
    self.update_feedback(track_id, duration)
    
    # 2. Update persistent cluster affinity
    is_positive = duration >= GOOD_ENGAGE_SEC
    if self.current_cluster_id is not None:
        user_db.update_cluster_affinity(
            user_id=self.user_id,
            cluster_id=self.current_cluster_id,
            listen_seconds=duration,
            is_positive=is_positive,
            collection_name=self.collection_name
        )
```

### 3. Smart Session Initialization

```python
def _load_user_history(self):
    # Load historical top clusters and boost their bandit scores
    query = text("""
        SELECT cluster_id, total_listen_seconds as score 
        FROM cluster_affinity 
        WHERE user_id = :uid AND collection_name = :coll
        ORDER BY total_listen_seconds DESC LIMIT 5
    """)
    
    for row in result:
        cid = int(row.cluster_id)
        score = float(row.score)
        if cid in self.cluster_scores:
            # Historical boost prevents cold start
            boost = min(score * 5.0, 25.0)
            self.cluster_scores[cid]['alpha'] += boost
            
            if score > best_score:
                self.best_historical_cluster = cid
```

## Multi-Armed Bandit Implementation

### 1. Thompson Sampling for Cluster Selection

```python
def select_cluster(self):
    """Thompson Sampling: probabilistic cluster selection based on performance"""
    best_cluster = None
    max_theta = -1
    
    for cid, stats in self.cluster_scores.items():
        # Sample from Beta distribution: Beta(alpha, beta)
        # Higher alpha = more positive signals
        # Higher beta = more negative signals
        theta = np.random.beta(stats['alpha'], stats['beta'])
        
        if theta > max_theta:
            max_theta = theta
            best_cluster = cid
    
    return best_cluster

def init_bandit(self):
    # Initialize with weak prior: slightly optimistic
    for cid in self.cluster_manager.clusters.keys():
        self.cluster_scores[cid] = {
            'alpha': BANDIT_ALPHA_PRIOR,  # 1.0 - weak positive prior
            'beta': BANDIT_BETA_PRIOR     # 1.0 - weak negative prior
        }
```

### 2. Bandit Score Updates

```python
def feedback_internal(self, track_id, duration, liked, disliked, finished, total_duration=0):
    alpha_boost, beta_boost = 0, 0
    
    if disliked or not is_green_signal:
        if self.cluster_fail_count > 5:
            beta_boost = 3.0  # Strong negative signal for exhausted cluster
        else:
            beta_boost = 1.0  # Moderate negative for refinement
    
    elif liked or is_green_signal:
        alpha_boost = 1.0 # Positive reinforcement
        
    # Update bandit scores
    if self.current_cluster_id is not None:
        self.cluster_scores[self.current_cluster_id]['alpha'] += alpha_boost
        self.cluster_scores[self.current_cluster_id]['beta'] += beta_boost
```

## Reinforcement Learning Integration

### 1. User Vector Evolution

```python
def update_user_vector(self, track_vector, direction):
    """
    Moves user preference vector towards/away from tracks based on feedback
    direction: +1 for like (move towards), -1 for dislike (move away)
    """
    LEARNING_RATE_POS = 0.2 if is_early else 0.1  # Faster initial learning
    LEARNING_RATE_NEG = 0.25 if is_early else 0.2 # Strong negative learning
    
    if self.user_vector is None:
        if direction > 0:
            self.user_vector = np.array(track_vector) # Initialize with first like
        return

    u_vec = np.array(self.user_vector)
    t_vec = np.array(track_vector)
    scale = abs(direction)
    
    if direction > 0:
        # Move towards liked content
        delta = t_vec - u_vec
        u_vec = u_vec + (LEARNING_RATE_POS * scale) * delta
    else:
        # Move away from disliked content
        delta = t_vec - u_vec  
        u_vec = u_vec - (LEARNING_RATE_NEG * scale) * delta
    
    # Normalize to unit sphere
    if np.linalg.norm(u_vec) > 0: 
        u_vec /= np.linalg.norm(u_vec)
        
    self.user_vector = u_vec.tolist()
```

### 2. Exploration vs Exploitation Balance

```python
def get_next_track(self):
    # Gradual drift mechanism
    drift_delta = 0.15  # Accumulate on negative feedback
    self.exploration_drift = max(0.0, min(1.0, self.exploration_drift + drift_delta))
    
    # Mode selection
    if self.streak >= 1:
        mode = "EXPLOIT"  # Lock onto successful pattern
    elif self.exploration_drift > 0.7 and self.cluster_fail_count > 1:
        mode = "EXPLORE"  # Break out when stuck
    else:
        mode = "EXPLOIT"  # Default to exploitation
```

## Real-Time Cluster Ratio Implementation

### Current Implementation Analysis

**✅ Strengths:**
1. **Session Tracking**: `session_likes` accurately tracks user interactions within each session
2. **Probabilistic Selection**: `random.choice(session_likes)` naturally maintains ratios
3. **Immediate Updates**: Each like/skip immediately updates the probability distribution
4. **Cluster Identification**: System correctly identifies which cluster each interaction belongs to

**⚠️ Enhancement Opportunities:**
1. **Explicit Ratio Tracking**: No direct calculation of cluster percentages for user feedback
2. **Real-Time Display**: Current system doesn't expose the calculated ratios to the user interface
3. **Ratio Persistence**: Ratios reset each session rather than building long-term cluster preferences

### Recommended Enhancements

#### 1. **Explicit Cluster Ratio Calculation**

```python
def get_current_cluster_ratios(self):
    """Calculate current session cluster engagement ratios"""
    if not self.session_likes:
        return {}
    
    cluster_counts = {}
    total_interactions = len(self.session_likes)
    
    for liked_vector in self.session_likes:
        # Find which cluster this vector belongs to
        closest_cluster = self._find_vector_cluster(liked_vector)
        cluster_counts[closest_cluster] = cluster_counts.get(closest_cluster, 0) + 1
    
    # Convert to percentages
    cluster_ratios = {}
    for cluster_id, count in cluster_counts.items():
        cluster_ratios[cluster_id] = (count / total_interactions) * 100
    
    return cluster_ratios

def _find_vector_cluster(self, vector):
    """Find which cluster a given vector belongs to"""
    min_distance = float('inf')
    closest_cluster = None
    
    for cluster_id, centroid in self.cluster_manager.centroids.items():
        distance = np.linalg.norm(np.array(vector) - centroid)
        if distance < min_distance:
            min_distance = distance
            closest_cluster = cluster_id
    
    return closest_cluster
```

#### 2. **Real-Time Ratio Updates on Skip**

```python
def feedback_internal(self, track_id, duration, liked, disliked, finished, total_duration=0):
    # ... existing logic ...
    
    if not is_green_signal:  # Skip detected
        # Remove the influence of the skipped cluster
        current_cluster = self.cluster_manager.get_track_cluster(track_id)
        
        # Find most recent like from a different cluster
        for i in range(len(self.session_likes) - 1, -1, -1):
            like_vector = self.session_likes[i]
            like_cluster = self._find_vector_cluster(like_vector)
            
            if like_cluster != current_cluster:
                # Boost the alternative cluster by adding its vector again
                self.session_likes.append(like_vector)
                print(f"Skip detected: Boosting cluster {like_cluster} ratio")
                break
    
    # Real-time ratio calculation
    current_ratios = self.get_current_cluster_ratios()
    print(f"Current cluster ratios: {current_ratios}")
```

#### 3. **API Endpoint for Ratio Monitoring**

```python
# In server_user.py
@app.get("/api/cluster-ratios")
async def get_cluster_ratios(session_id: str = Query(...)):
    """Get current session cluster engagement ratios"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    ratios = session["recommender"].get_current_cluster_ratios()
    
    # Add cluster names/descriptions if available
    cluster_info = {}
    for cluster_id, percentage in ratios.items():
        # Get sample tracks from cluster for description
        sample_tracks = session["recommender"].cluster_manager.get_representatives(cluster_id, limit=3)
        cluster_info[cluster_id] = {
            "percentage": percentage,
            "sample_tracks": [session["recommender"].track_map[tid]["filename"] for tid in sample_tracks]
        }
    
    return cluster_info
```

## Operational Verification

### 1. **Bollywood vs Punjabi Test Case**

**Scenario**: User likes 2 Bollywood tracks, then 2 Punjabi tracks

**Expected System Behavior**:
```
Initial State: session_likes = []

After Bollywood Track 1: session_likes = [bollywood_vector_1]
- Next recommendation probability: 100% Bollywood-like

After Bollywood Track 2: session_likes = [bollywood_vector_1, bollywood_vector_2]  
- Next recommendation probability: 100% Bollywood-like

After Punjabi Track 1: session_likes = [bollywood_vector_1, bollywood_vector_2, punjabi_vector_1]
- Next recommendation probability: 67% Bollywood, 33% Punjabi

After Punjabi Track 2: session_likes = [bollywood_vector_1, bollywood_vector_2, punjabi_vector_1, punjabi_vector_2]
- Next recommendation probability: 50% Bollywood, 50% Punjabi
```

**System Implementation**:
```python
# This happens in get_next_track() -> EXPLOIT mode
selected_anchor = random.choice(recent_likes)  # 50/50 selection
target_vectors = [selected_anchor]            # Use selected anchor for similarity
```

### 2. **Skip Response Verification**

**Scenario**: User in 50/50 Bollywood/Punjabi state, skips a Bollywood recommendation

**Expected System Behavior**:
1. **Immediate Vector Update**: User vector moves away from skipped Bollywood track
2. **Cluster Penalty**: Bollywood cluster receives negative feedback  
3. **Drift Accumulation**: `exploration_drift += 0.15` (gradual departure from locked state)
4. **Next Recommendation**: Higher probability of Punjabi due to RL vector shift

**Verification Points**:
```python
def verify_skip_response(self, track_id, duration):
    pre_skip_ratios = self.get_current_cluster_ratios()
    pre_skip_user_vector = np.array(self.user_vector) if self.user_vector else None
    
    self.feedback_internal(track_id, duration, False, True, False)
    
    post_skip_ratios = self.get_current_cluster_ratios()
    post_skip_user_vector = np.array(self.user_vector) if self.user_vector else None
    
    # Verify vector moved away from skipped track
    if pre_skip_user_vector is not None and post_skip_user_vector is not None:
        skipped_track = self.track_map[track_id]
        skipped_vector = np.array(skipped_track['vector'])
        
        pre_similarity = np.dot(pre_skip_user_vector, skipped_vector)
        post_similarity = np.dot(post_skip_user_vector, skipped_vector)
        
        assert post_similarity < pre_similarity, "User vector should move away from skipped track"
    
    print(f"Pre-skip ratios: {pre_skip_ratios}")
    print(f"Post-skip ratios: {post_skip_ratios}")
```

## Conclusion

The ChaarFM recommendation algorithm successfully implements sophisticated cluster-based probing with real-time ratio adjustment. The system:

1. **✅ Tracks user engagement** with distinct music clusters through session-based interaction logging
2. **✅ Calculates engagement ratios** implicitly through probabilistic sampling of `session_likes`
3. **✅ Adjusts recommendation bubble** in real-time via reinforcement learning and bandit algorithms
4. **✅ Responds immediately to skips** by updating user vectors and cluster penalties
5. **✅ Converges on optimal alignment** through gradual drift mechanisms and exploration/exploitation balance

The architecture ensures that user interactions directly influence the recommendation ratios, with a 2 Bollywood + 2 Punjabi interaction history resulting in exactly 50% Bollywood / 50% Punjabi recommendation probability through the `random.choice(session_likes)` mechanism.

**Key Operational Principles:**
- **Mathematical Precision**: Every recommendation decision is based on calculated similarities and learned preferences
- **Real-Time Adaptation**: User interactions immediately influence subsequent recommendations
- **Cluster Respect**: The system maintains distinct cluster identities while allowing natural transitions
- **Persistent Learning**: User preferences are stored and influence future sessions
- **Transparent Logic**: The system provides detailed justifications for each recommendation decision