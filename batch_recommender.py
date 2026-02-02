"""
Batch Recommender v5 - Detailed Mathematical Logging

Full transparency on WHY each decision is made.
"""

import numpy as np
from qdrant_client import QdrantClient
from sklearn.cluster import KMeans

# Config
COLLECTION_NAME = "music_averaged"
BATCH_SIZE = 5
N_CLUSTERS = 50  # Increased from 20 for more specific groupings
SKIP_THRESHOLD = 5.0

class BatchRecommender:
    def __init__(self):
        self.client = self._get_client()
        
        # Session State
        self.played_ids = set()
        self.played_filenames = set()
        
        # Session Stats
        self.session_max_duration = 0.0
        self.session_durations = []
        
        # Session History
        self.session_history = []
        
        # Phase tracking
        self.phase = "PROBE"
        self.batch_count = 0
        self.locked_batch_count = 0
        self.EXPLORE_EVERY_N_BATCHES = 4
        
        # Current Batch
        self.current_batch = []
        self.batch_feedback = {}
        
        # Cluster State
        self.cluster_labels = {}
        self.cluster_stickiness = {}
        self.cluster_visit_count = {}
        self.cluster_best_signal = {}
        
        # Sticky Path
        self.sticky_cluster = None
        self.sticky_strength = 0.0
        
        # Boredom Detection
        self.consecutive_skips_on_sticky = 0
        self.BOREDOM_THRESHOLD = 5  # If 5 consecutive skips on sticky cluster, go back to PROBE
        
        # Track map
        self.track_map = {}
        
        self._load_all_tracks()
        self._cluster_tracks()
    
    def _get_client(self):
        try:
            return QdrantClient(host="localhost", port=6333)
        except:
            return QdrantClient(path="./qdrant_data")
    
    def _load_all_tracks(self):
        print("Loading all tracks from averaged collection...")
        offset = None
        
        while True:
            points, offset = self.client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                with_vectors=True,
                with_payload=True,
                offset=offset
            )
            
            for p in points:
                self.track_map[p.id] = {
                    "id": p.id,
                    "filename": p.payload["filename"],
                    "vector": p.vector
                }
            
            if offset is None:
                break
        
        print(f"Loaded {len(self.track_map)} tracks.")
    
    def _cluster_tracks(self):
        print(f"Clustering {len(self.track_map)} tracks into {N_CLUSTERS} clusters...")
        
        ids = list(self.track_map.keys())
        vectors = [self.track_map[tid]["vector"] for tid in ids]
        
        kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
        labels = kmeans.fit_predict(vectors)
        
        self.cluster_centroids = kmeans.cluster_centers_
        
        for i, tid in enumerate(ids):
            self.cluster_labels[tid] = int(labels[i])
        
        for cid in range(N_CLUSTERS):
            self.cluster_stickiness[cid] = 0.0
            self.cluster_visit_count[cid] = 0
            self.cluster_best_signal[cid] = 0.0
        
        # Log cluster composition
        cluster_samples = {i: [] for i in range(N_CLUSTERS)}
        for tid, cid in self.cluster_labels.items():
            cluster_samples[cid].append(self.track_map[tid]["filename"][:40])
        
        print("\n📊 CLUSTER COMPOSITION (first 3 songs each):")
        for cid in range(N_CLUSTERS):
            samples = cluster_samples[cid][:3]
            print(f"  Cluster {cid} ({len(cluster_samples[cid])} songs): {samples}")
        
        print("\nClustering complete.")
    
    def _compute_relative_signal(self, duration):
        """Compute relative signal with full formula logging."""
        if duration < SKIP_THRESHOLD:
            signal = -(SKIP_THRESHOLD - duration) / SKIP_THRESHOLD
            return signal, f"SKIP: -({SKIP_THRESHOLD:.1f} - {duration:.1f}) / {SKIP_THRESHOLD:.1f} = {signal:.3f}"
        
        if self.session_max_duration <= SKIP_THRESHOLD:
            signal = min(1.0, (duration - SKIP_THRESHOLD) / 60.0)
            return signal, f"EARLY: ({duration:.1f} - {SKIP_THRESHOLD:.1f}) / 60 = {signal:.3f} (no session max yet)"
        
        numerator = duration - SKIP_THRESHOLD
        denominator = self.session_max_duration - SKIP_THRESHOLD + 0.1
        signal = min(1.0, max(0.0, numerator / denominator))
        return signal, f"RELATIVE: ({duration:.1f} - {SKIP_THRESHOLD:.1f}) / ({self.session_max_duration:.1f} - {SKIP_THRESHOLD:.1f}) = {signal:.3f}"
    
    def _get_tracks_from_cluster(self, cluster_id, limit=5):
        candidates = []
        for tid, cid in self.cluster_labels.items():
            if cid != cluster_id:
                continue
            if tid in self.played_ids:
                continue
            if self.track_map[tid]["filename"] in self.played_filenames:
                continue
            candidates.append(self.track_map[tid])
        
        np.random.shuffle(candidates)
        return candidates[:limit]
    
    def _get_nuanced_tracks(self, cluster_id, limit=5):
        """Get tracks with positive attraction and negative repulsion."""
        candidates = []
        for tid, cid in self.cluster_labels.items():
            if cid != cluster_id:
                continue
            if tid in self.played_ids:
                continue
            if self.track_map[tid]["filename"] in self.played_filenames:
                continue
            candidates.append(self.track_map[tid])
        
        if not candidates:
            return []
        
        # Find positive and NEGATIVE tracks in this cluster
        cluster_positives = [h for h in self.session_history 
                           if h['cluster_id'] == cluster_id and h['relative_signal'] > 0]
        cluster_negatives = [h for h in self.session_history 
                           if h['cluster_id'] == cluster_id and h['relative_signal'] < -0.3]  # Strong skips only
        
        print(f"\n  📐 NUANCED SELECTION MATH (with negative repulsion):")
        
        if cluster_positives:
            print(f"     ✅ Positive history ({len(cluster_positives)} tracks):")
            for h in cluster_positives[:5]:  # Show first 5
                track = self.track_map.get(h['track_id'])
                if track:
                    print(f"       • {track['filename'][:35]}... (+{h['relative_signal']:.2f})")
            
            positive_vectors = []
            for h in cluster_positives:
                track = self.track_map.get(h['track_id'])
                if track:
                    weight = h['relative_signal']
                    positive_vectors.append((np.array(track['vector']), weight))
            
            if positive_vectors:
                total_pos_weight = sum(w for _, w in positive_vectors)
                positive_centroid = sum(v * w for v, w in positive_vectors) / total_pos_weight
            else:
                positive_centroid = None
        else:
            positive_centroid = None
            print(f"     ⚠️ No positive history in cluster")
        
        # Compute NEGATIVE centroid
        if cluster_negatives:
            print(f"     ❌ Negative history ({len(cluster_negatives)} tracks):")
            for h in cluster_negatives[:5]:
                track = self.track_map.get(h['track_id'])
                if track:
                    print(f"       • {track['filename'][:35]}... ({h['relative_signal']:.2f})")
            
            negative_vectors = []
            for h in cluster_negatives:
                track = self.track_map.get(h['track_id'])
                if track:
                    weight = abs(h['relative_signal'])
                    negative_vectors.append((np.array(track['vector']), weight))
            
            if negative_vectors:
                total_neg_weight = sum(w for _, w in negative_vectors)
                negative_centroid = sum(v * w for v, w in negative_vectors) / total_neg_weight
            else:
                negative_centroid = None
        else:
            negative_centroid = None
        
        # Score candidates: attract to positive, REPEL from negative
        scored = []
        for c in candidates:
            v = np.array(c['vector'])
            
            # Positive attraction
            if positive_centroid is not None:
                pos_sim = np.dot(positive_centroid, v) / (np.linalg.norm(positive_centroid) * np.linalg.norm(v) + 1e-8)
            else:
                pos_sim = 0.5  # Neutral
            
            # Negative repulsion (penalize similarity to skipped tracks)
            if negative_centroid is not None:
                neg_sim = np.dot(negative_centroid, v) / (np.linalg.norm(negative_centroid) * np.linalg.norm(v) + 1e-8)
                # Penalty: higher similarity to negative = lower score
                neg_penalty = neg_sim * 0.5  # 50% weight for negative
            else:
                neg_penalty = 0
            
            noise = np.random.random() * 0.1
            final_score = pos_sim - neg_penalty + noise
            scored.append((c, final_score, pos_sim, neg_penalty, noise))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        print(f"\n     📊 Scoring: final = pos_sim - neg_penalty + noise")
        print(f"     Top candidates:")
        for i, (c, final, pos_sim, neg_pen, noise) in enumerate(scored[:limit]):
            print(f"       {i+1}. {pos_sim:.3f} - {neg_pen:.3f} + {noise:.3f} = {final:.3f} | {c['filename'][:35]}...")
        
        return [c for c, _, _, _, _ in scored[:limit]]
    
    def _select_best_cluster(self):
        """Select cluster with detailed reasoning."""
        print(f"\n  🎯 CLUSTER SELECTION REASONING:")
        
        if self.sticky_cluster is not None:
            print(f"     STICKY CLUSTER ACTIVE: {self.sticky_cluster} (strength: {self.sticky_strength:.2f})")
            print(f"     → Returning sticky cluster {self.sticky_cluster}")
            return self.sticky_cluster
        
        print(f"     No sticky cluster - evaluating all:")
        
        best_cluster = None
        best_score = -float('inf')
        
        for cid in range(N_CLUSTERS):
            visits = self.cluster_visit_count[cid]
            best_sig = self.cluster_best_signal[cid]
            noise = np.random.random() * 0.05
            
            if visits == 0:
                score = 0.5 + np.random.random() * 0.3
                reason = f"unvisited, neutral + exploration"
            else:
                score = best_sig + noise
                reason = f"best_signal={best_sig:.2f} + noise={noise:.2f}"
            
            if score > best_score:
                best_score = score
                best_cluster = cid
            
            if best_sig > 0 or visits > 0:
                print(f"       C{cid}: score={score:.3f} ({reason})")
        
        print(f"     → Selected Cluster {best_cluster} (score: {best_score:.3f})")
        return best_cluster
    
    def get_next_batch(self):
        self.batch_count += 1
        
        print("\n" + "=" * 70)
        print(f"BATCH #{self.batch_count} | Phase: {self.phase}")
        print(f"Session: {len(self.session_history)} tracks | Max listen: {self.session_max_duration:.1f}s")
        if self.sticky_cluster is not None:
            print(f"Sticky: Cluster {self.sticky_cluster} (strength: {self.sticky_strength:.2f})")
        print("=" * 70)
        
        batch = []
        
        if self.phase == "PROBE":
            print("PROBING: 1 song from 5 different clusters...")
            available_clusters = list(range(N_CLUSTERS))
            np.random.shuffle(available_clusters)
            
            for cid in available_clusters[:BATCH_SIZE]:
                tracks = self._get_tracks_from_cluster(cid, limit=1)
                if tracks:
                    batch.append(tracks[0])
                    print(f"  Cluster {cid}: {tracks[0]['filename'][:50]}...")
            
            self.phase = "FOLLOWING"
        
        elif self.phase == "FOLLOWING":
            target_cluster = self._select_best_cluster()
            
            if self.sticky_cluster is not None:
                print(f"\nFOLLOWING: Sticky Cluster {target_cluster}")
            else:
                print(f"\nSEARCHING: Best Cluster {target_cluster}")
            
            batch = self._get_nuanced_tracks(target_cluster, limit=BATCH_SIZE)
            
            # Exploration check
            self.locked_batch_count += 1
            should_explore = (self.locked_batch_count % self.EXPLORE_EVERY_N_BATCHES == 0)
            
            if should_explore and self.sticky_cluster is not None:
                print(f"\n  🔍 EXPLORATION SLOT (every {self.EXPLORE_EVERY_N_BATCHES} batches)")
                other_clusters = [c for c in range(N_CLUSTERS) if c != target_cluster]
                if other_clusters and len(batch) >= BATCH_SIZE:
                    explore_cluster = np.random.choice(other_clusters)
                    explore_tracks = self._get_tracks_from_cluster(explore_cluster, limit=1)
                    if explore_tracks:
                        print(f"     Replacing slot 5 with Cluster {explore_cluster}: {explore_tracks[0]['filename'][:40]}...")
                        batch[-1] = explore_tracks[0]
        
        # Fallback
        if len(batch) < BATCH_SIZE:
            print(f"\n⚠️ Only {len(batch)} tracks available, filling with random...")
            for tid, info in self.track_map.items():
                if len(batch) >= BATCH_SIZE:
                    break
                if tid not in self.played_ids:
                    batch.append(info)
        
        self.current_batch = batch
        self.batch_feedback = {}
        
        for track in batch:
            self.played_ids.add(track["id"])
            self.played_filenames.add(track["filename"])
        
        print(f"\n📋 FINAL BATCH ({len(batch)} tracks):")
        for i, t in enumerate(batch):
            cid = self.cluster_labels.get(t["id"], "?")
            print(f"  {i+1}. [C{cid}] {t['filename'][:55]}...")
        
        return [{"id": t["id"], "filename": t["filename"]} for t in batch]
    
    def record_feedback(self, track_id, duration):
        """Record feedback with full mathematical breakdown."""
        track = self.track_map.get(track_id)
        if not track:
            return
        
        cluster_id = self.cluster_labels.get(track_id)
        
        # Update session max
        max_updated = False
        if duration > self.session_max_duration:
            old_max = self.session_max_duration
            self.session_max_duration = duration
            max_updated = True
        
        self.session_durations.append(duration)
        
        # Compute signal with formula
        relative_signal, formula = self._compute_relative_signal(duration)
        
        # Store
        self.batch_feedback[track_id] = {
            "duration": duration,
            "relative_signal": relative_signal
        }
        
        self.session_history = [h for h in self.session_history if h['track_id'] != track_id]
        self.session_history.append({
            "track_id": track_id,
            "cluster_id": cluster_id,
            "duration": duration,
            "relative_signal": relative_signal
        })
        
        # Detailed log
        print(f"\n{'─'*60}")
        print(f"FEEDBACK: {track['filename'][:50]}...")
        print(f"  Duration: {duration:.1f}s | Cluster: {cluster_id}")
        if max_updated:
            print(f"  📈 NEW SESSION MAX: {old_max:.1f}s → {self.session_max_duration:.1f}s")
        print(f"  📊 Signal Formula: {formula}")
        
        # Signal interpretation
        if relative_signal < 0:
            print(f"  ❌ NEGATIVE SIGNAL: {relative_signal:.3f}")
        elif relative_signal >= 0.8:
            print(f"  🔥 MAGNUM OPUS: {relative_signal:.3f}")
        elif relative_signal >= 0.5:
            print(f"  ✨ STRONG POSITIVE: {relative_signal:.3f}")
        else:
            print(f"  ✓ POSITIVE: {relative_signal:.3f}")
        
        # Sticky Logic
        if relative_signal > 0:
            # Update cluster best
            old_best = self.cluster_best_signal.get(cluster_id, 0)
            if relative_signal > old_best:
                self.cluster_best_signal[cluster_id] = relative_signal
                print(f"  📈 Cluster {cluster_id} best signal: {old_best:.2f} → {relative_signal:.2f}")
            
            # Sticky path decision
            if self.sticky_cluster is None:
                self.sticky_cluster = cluster_id
                self.sticky_strength = relative_signal
                print(f"  🔒 LOCKED to Cluster {cluster_id} (first positive signal)")
            
            elif cluster_id != self.sticky_cluster:
                required_strength = self.sticky_strength * 1.2
                print(f"\n  🤔 PATH CHANGE EVALUATION:")
                print(f"     Current sticky: Cluster {self.sticky_cluster} (strength: {self.sticky_strength:.2f})")
                print(f"     New signal: Cluster {cluster_id} (strength: {relative_signal:.2f})")
                print(f"     Required to switch: {required_strength:.2f} (current × 1.2)")
                
                if relative_signal > required_strength:
                    old = self.sticky_cluster
                    self.sticky_cluster = cluster_id
                    self.sticky_strength = relative_signal
                    improvement = (relative_signal / self.sticky_strength - 1) * 100
                    print(f"     ✅ SWITCHING: {old} → {cluster_id} (+{improvement:.0f}% stronger)")
                else:
                    deficit = required_strength - relative_signal
                    print(f"     ❌ NOT SWITCHING: need {deficit:.2f} more to overcome threshold")
            
            else:
                if relative_signal > self.sticky_strength:
                    print(f"  📍 REINFORCING Cluster {cluster_id}: {self.sticky_strength:.2f} → {relative_signal:.2f}")
                    self.sticky_strength = relative_signal
                else:
                    print(f"  📍 STAYING on Cluster {cluster_id} (signal not stronger)")
            
            # Reset boredom counter on positive signal
            self.consecutive_skips_on_sticky = 0
        
        else:
            # NEGATIVE signal - check for boredom
            if self.sticky_cluster is not None and cluster_id == self.sticky_cluster:
                self.consecutive_skips_on_sticky += 1
                print(f"  😴 Boredom counter: {self.consecutive_skips_on_sticky}/{self.BOREDOM_THRESHOLD}")
                
                if self.consecutive_skips_on_sticky >= self.BOREDOM_THRESHOLD:
                    print(f"\n  🔄 BOREDOM DETECTED! Resetting to PROBE phase...")
                    self.phase = "PROBE"
                    self.sticky_cluster = None
                    self.sticky_strength = 0.0
                    self.consecutive_skips_on_sticky = 0
                    self.locked_batch_count = 0
                    # Don't clear history - we still remember what didn't work
                    print(f"  🔄 Session memory preserved, but exploring new clusters")
        
        print(f"{'─'*60}")
    
    def finalize_batch(self):
        print("\n" + "=" * 70)
        print("BATCH FINALIZATION")
        print("=" * 70)
        
        if not self.batch_feedback:
            print("No feedback recorded.")
            return
        
        print("\n📊 SESSION SUMMARY:")
        print(f"  Total tracks played: {len(self.session_history)}")
        print(f"  Session max listen: {self.session_max_duration:.1f}s")
        
        if self.sticky_cluster is not None:
            print(f"  Sticky cluster: {self.sticky_cluster} (strength: {self.sticky_strength:.2f})")
        
        # Show positive history by cluster
        print(f"\n📈 POSITIVE SIGNALS BY CLUSTER:")
        cluster_positives = {}
        for h in self.session_history:
            if h['relative_signal'] > 0:
                cid = h['cluster_id']
                if cid not in cluster_positives:
                    cluster_positives[cid] = []
                track = self.track_map.get(h['track_id'])
                cluster_positives[cid].append({
                    'name': track['filename'][:35] if track else 'Unknown',
                    'signal': h['relative_signal']
                })
        
        for cid, tracks in sorted(cluster_positives.items(), key=lambda x: -sum(t['signal'] for t in x[1])):
            total = sum(t['signal'] for t in tracks)
            print(f"  Cluster {cid} (total: {total:.2f}):")
            for t in tracks:
                print(f"    • {t['name']}... ({t['signal']:.2f})")
        
        print("=" * 70)
    
    def search(self, query):
        query = query.lower()
        results = []
        for tid, info in self.track_map.items():
            if query in info["filename"].lower():
                results.append({"id": tid, "filename": info["filename"]})
                if len(results) >= 20:
                    break
        return results
    
    def set_seed(self, track_id):
        track = self.track_map.get(track_id)
        if track:
            self.played_ids.add(track_id)
            self.played_filenames.add(track["filename"])
            self.phase = "FOLLOWING"
            
            cluster_id = self.cluster_labels.get(track_id)
            self.sticky_cluster = cluster_id
            self.sticky_strength = 1.0
            self.cluster_best_signal[cluster_id] = 1.0
            
            print(f"Seeded with: {track['filename']} (Cluster {cluster_id})")
            return track
        return None
