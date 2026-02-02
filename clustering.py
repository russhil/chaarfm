import numpy as np
from sklearn.cluster import KMeans
from vector_db import get_client, get_all_vectors

class ClusterManager:
    def __init__(self, n_clusters=20):
        self.client = get_client()
        self.n_clusters = n_clusters
        self.kmeans = None
        self.track_map = {} # id -> track info
        self.clusters = {} # cluster_id -> list of track_ids
        self.centroids = []
        self.representatives = {} # cluster_id -> list of track_ids sorted by distance to center
        self.track_to_cluster = {} # id -> cluster_id
        self.initialized = False

    def fit(self):
        print("Fetching all vectors for clustering...")
        tracks = get_all_vectors(self.client)
        
        if not tracks:
            print("No tracks found for clustering.")
            return

        print(f"Clustering {len(tracks)} tracks into {self.n_clusters} clusters...")
        
        self.track_map = {t['id']: t for t in tracks}
        vectors = [t['vector'] for t in tracks]
        ids = [t['id'] for t in tracks]
        
        # Adjust n_clusters if we have fewer tracks 
        effective_clusters = min(self.n_clusters, len(tracks))
        
        self.kmeans = KMeans(n_clusters=effective_clusters, random_state=42, n_init=10)
        labels = self.kmeans.fit_predict(vectors)
        self.centroids = self.kmeans.cluster_centers_
        
        # Organize results
        self.clusters = {i: [] for i in range(effective_clusters)}
        for idx, label in enumerate(labels):
            self.clusters[label].append(ids[idx])
            self.track_to_cluster[ids[idx]] = int(label)
            
        # Find representatives (closest to centroid)
        print("Identifying cluster representatives...")
        for i in range(effective_clusters):
            cluster_vectors = []
            cluster_ids = self.clusters[i]
            centroid = self.centroids[i]
            
            # Calculate distances
            distances = []
            for tid in cluster_ids:
                vec = self.track_map[tid]['vector']
                dist = np.linalg.norm(np.array(vec) - centroid)
                distances.append((dist, tid))
            
            # Sort by distance
            distances.sort(key=lambda x: x[0])
            self.representatives[i] = [d[1] for d in distances]
            
        print("Clustering complete.")
        self.initialized = True

    def get_cluster_tracks(self, cluster_id):
        return self.clusters.get(cluster_id, [])

    def get_representatives(self, cluster_id, limit=5):
        reps = self.representatives.get(cluster_id, [])
        return reps[:limit]

    def get_random_from_cluster(self, cluster_id):
        tracks = self.clusters.get(cluster_id, [])
        if tracks:
            return np.random.choice(tracks)
        return None
    
    def get_track_cluster(self, track_id):
        """Return the cluster id for a given track id, if known."""
        return self.track_to_cluster.get(track_id)
