"""
Post-vectorization quality analyzer for genre collections.

Identifies outlier tracks (poorly produced songs) using embedding space analysis
and provides cleanup tools to remove them from collections.
"""

import os
import sys
import logging
import psycopg2
import numpy as np
from typing import List, Dict, Optional, Set
from collections import defaultdict

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from music_pipeline.config import DATABASE_URL as CFG_DB_URL
    DATABASE_URL = CFG_DB_URL
except ImportError:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")

logger = logging.getLogger(__name__)


def analyze_collection_outliers(table_name: str, method: str = "cluster_based") -> List[Dict]:
    """
    Analyze a genre collection to identify outlier tracks (poorly produced songs).
    
    Args:
        table_name: Name of the collection table (e.g., 'vectors_genre_lofi')
        method: Detection method - 'cluster_based' (default), 'isolation', or 'lof'
    
    Returns:
        List of dicts with track info and outlier scores:
        [{"track_id": id, "artist": ..., "title": ..., "youtube_id": ..., 
          "outlier_score": float, "method": str, "reason": str}, ...]
    """
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set")
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # Load all tracks with embeddings
        cur.execute(f"""
            SELECT id, artist, title, youtube_id, embedding
            FROM {table_name}
            WHERE embedding IS NOT NULL
        """)
        rows = cur.fetchall()
        
        if len(rows) < 10:
            logger.warning(f"Collection {table_name} has too few tracks ({len(rows)}) for outlier detection")
            return []
        
        tracks = []
        vectors = []
        for row in rows:
            track_id, artist, title, youtube_id, embedding = row
            tracks.append({
                'track_id': track_id,
                'artist': artist,
                'title': title,
                'youtube_id': youtube_id
            })
            # Parse embedding (could be list, array, or string)
            if isinstance(embedding, str):
                import json
                embedding = json.loads(embedding)
            elif hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
            vectors.append(np.array(embedding))
        
        vectors = np.array(vectors)
        
        outliers = []
        
        if method == "cluster_based":
            outliers = _cluster_based_outliers(tracks, vectors)
        elif method == "isolation":
            outliers = _isolation_forest_outliers(tracks, vectors)
        elif method == "lof":
            outliers = _lof_outliers(tracks, vectors)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        return outliers
        
    except Exception as e:
        logger.error(f"Failed to analyze outliers: {e}")
        raise e
    finally:
        cur.close()
        conn.close()


def _cluster_based_outliers(tracks: List[Dict], vectors: np.ndarray) -> List[Dict]:
    """Cluster-based outlier detection (mean + 2*std threshold)."""
    from sklearn.cluster import KMeans
    
    n_clusters = min(20, len(tracks) // 5)  # Adaptive cluster count
    if n_clusters < 2:
        n_clusters = 2
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(vectors)
    centroids = kmeans.cluster_centers_
    
    outliers = []
    
    for cid in range(n_clusters):
        cluster_indices = [i for i, l in enumerate(labels) if l == cid]
        if len(cluster_indices) < 3:
            # Small clusters are suspicious - mark all as outliers
            for idx in cluster_indices:
                outliers.append({
                    **tracks[idx],
                    'outlier_score': 1.0,
                    'method': 'cluster_based',
                    'reason': f'Sparse cluster (size {len(cluster_indices)})'
                })
            continue
        
        # Compute distances from centroid
        cluster_centroid = centroids[cid]
        distances = []
        for idx in cluster_indices:
            dist = np.linalg.norm(vectors[idx] - cluster_centroid)
            distances.append((idx, dist))
        
        mean_dist = np.mean([d for _, d in distances])
        std_dist = np.std([d for _, d in distances])
        threshold = mean_dist + 2 * std_dist
        
        for idx, dist in distances:
            if dist > threshold:
                outliers.append({
                    **tracks[idx],
                    'outlier_score': dist / threshold,  # Normalized score
                    'method': 'cluster_based',
                    'reason': f'Distance {dist:.2f} > threshold {threshold:.2f} (cluster {cid})'
                })
    
    return outliers


def _isolation_forest_outliers(tracks: List[Dict], vectors: np.ndarray) -> List[Dict]:
    """Isolation Forest for global outlier detection."""
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        logger.warning("sklearn not available, falling back to cluster-based")
        return _cluster_based_outliers(tracks, vectors)
    
    iso_forest = IsolationForest(contamination=0.1, random_state=42)
    predictions = iso_forest.fit_predict(vectors)
    scores = iso_forest.score_samples(vectors)
    
    outliers = []
    for i, (pred, score) in enumerate(zip(predictions, scores)):
        if pred == -1:  # Outlier
            outliers.append({
                **tracks[i],
                'outlier_score': -score,  # Lower score = more outlier
                'method': 'isolation',
                'reason': f'Isolation Forest score: {score:.4f}'
            })
    
    return outliers


def _lof_outliers(tracks: List[Dict], vectors: np.ndarray) -> List[Dict]:
    """Local Outlier Factor for density-based outlier detection."""
    try:
        from sklearn.neighbors import LocalOutlierFactor
    except ImportError:
        logger.warning("sklearn not available, falling back to cluster-based")
        return _cluster_based_outliers(tracks, vectors)
    
    n_neighbors = min(20, len(tracks) // 2)
    if n_neighbors < 5:
        n_neighbors = 5
    
    lof = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=0.1)
    predictions = lof.fit_predict(vectors)
    scores = lof.negative_outlier_factor_
    
    outliers = []
    for i, (pred, score) in enumerate(zip(predictions, scores)):
        if pred == -1:  # Outlier
            outliers.append({
                **tracks[i],
                'outlier_score': -score,  # Lower score = more outlier
                'method': 'lof',
                'reason': f'LOF score: {score:.4f}'
            })
    
    return outliers


def remove_outliers_from_collection(table_name: str, outlier_ids: List[str], dry_run: bool = True) -> Dict:
    """
    Remove outlier tracks from a collection.
    
    Args:
        table_name: Name of the collection table
        outlier_ids: List of track IDs to remove
        dry_run: If True, only report what would be removed (default: True)
    
    Returns:
        Dict with removal stats: {"removed": count, "dry_run": bool}
    """
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set")
    
    if dry_run:
        logger.info(f"DRY RUN: Would remove {len(outlier_ids)} tracks from {table_name}")
        return {"removed": len(outlier_ids), "dry_run": True}
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # Build query with placeholders
        placeholders = ','.join(['%s'] * len(outlier_ids))
        query = f"DELETE FROM {table_name} WHERE id IN ({placeholders})"
        cur.execute(query, outlier_ids)
        conn.commit()
        
        removed_count = cur.rowcount
        logger.info(f"Removed {removed_count} outlier tracks from {table_name}")
        
        return {"removed": removed_count, "dry_run": False}
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to remove outliers: {e}")
        raise e
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    # CLI for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze and clean genre collection outliers")
    parser.add_argument("table_name", help="Collection table name (e.g., vectors_genre_lofi)")
    parser.add_argument("--method", choices=["cluster_based", "isolation", "lof"], 
                       default="cluster_based", help="Outlier detection method")
    parser.add_argument("--remove", action="store_true", help="Actually remove outliers (default: dry run)")
    parser.add_argument("--min-score", type=float, default=1.0, 
                       help="Minimum outlier score to remove (default: 1.0)")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    print(f"Analyzing outliers in {args.table_name}...")
    outliers = analyze_collection_outliers(args.table_name, method=args.method)
    
    print(f"\nFound {len(outliers)} outliers:")
    for outlier in sorted(outliers, key=lambda x: x['outlier_score'], reverse=True)[:20]:
        print(f"  {outlier['artist']} - {outlier['title']}: score={outlier['outlier_score']:.2f} ({outlier['reason']})")
    
    if args.remove:
        outlier_ids = [str(o['track_id']) for o in outliers if o['outlier_score'] >= args.min_score]
        result = remove_outliers_from_collection(args.table_name, outlier_ids, dry_run=False)
        print(f"\nRemoved {result['removed']} tracks.")
    else:
        print(f"\nDRY RUN: Use --remove to actually delete outliers")
