"""
Migration Script: Segmented -> Averaged Vectors

This script:
1. Reads all segmented vectors from music_collection
2. Groups them by filename (song)
3. Computes average vector per song
4. Stores in new collection: music_averaged
"""

import numpy as np
from collections import defaultdict
from qdrant_client import QdrantClient
from qdrant_client.http import models
import uuid

# Config
SOURCE_COLLECTION = "music_collection"
TARGET_COLLECTION = "music_averaged"
VECTOR_SIZE = 200

def get_client():
    try:
        return QdrantClient(host="localhost", port=6333)
    except:
        return QdrantClient(path="./qdrant_data")

def fetch_all_points(client, collection_name):
    """Fetch all points from a collection using scroll."""
    all_points = []
    offset = None
    
    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            scroll_filter=None,
            limit=100,
            with_vectors=True,
            with_payload=True,
            offset=offset
        )
        all_points.extend(points)
        print(f"Fetched {len(all_points)} points...")
        if offset is None:
            break
    
    return all_points

def group_by_filename(points):
    """Group points by their filename (song)."""
    groups = defaultdict(list)
    
    for p in points:
        filename = p.payload.get("filename", "unknown")
        vector = p.vector
        groups[filename].append(vector)
    
    return groups

def compute_average_vectors(groups):
    """Compute average vector for each song."""
    averaged = {}
    
    for filename, vectors in groups.items():
        if len(vectors) == 0:
            continue
        
        # Stack and average
        arr = np.array(vectors)
        avg = np.mean(arr, axis=0)
        
        # Normalize (for cosine similarity)
        norm = np.linalg.norm(avg)
        if norm > 0:
            avg = avg / norm
        
        averaged[filename] = avg.tolist()
    
    return averaged

def create_averaged_collection(client):
    """Create the averaged collection if it doesn't exist."""
    collections = client.get_collections()
    exists = any(c.name == TARGET_COLLECTION for c in collections.collections)
    
    if exists:
        print(f"Collection {TARGET_COLLECTION} already exists. Deleting and recreating...")
        client.delete_collection(TARGET_COLLECTION)
    
    client.create_collection(
        collection_name=TARGET_COLLECTION,
        vectors_config=models.VectorParams(
            size=VECTOR_SIZE,
            distance=models.Distance.COSINE
        )
    )
    print(f"Created collection: {TARGET_COLLECTION}")

def upload_averaged_vectors(client, averaged):
    """Upload averaged vectors to the new collection."""
    points = []
    
    for filename, vector in averaged.items():
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, filename))
        points.append(models.PointStruct(
            id=point_id,
            vector=vector,
            payload={"filename": filename, "type": "averaged"}
        ))
    
    # Upload in batches
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i+batch_size]
        client.upsert(collection_name=TARGET_COLLECTION, points=batch)
        print(f"Uploaded {i + len(batch)}/{len(points)} averaged vectors...")
    
    print(f"Done! Uploaded {len(points)} averaged song vectors.")

def main():
    print("=" * 60)
    print("MIGRATION: Segmented -> Averaged Vectors")
    print("=" * 60)
    
    client = get_client()
    
    # Step 1: Fetch all segmented points
    print("\n[1/4] Fetching all segmented vectors...")
    points = fetch_all_points(client, SOURCE_COLLECTION)
    print(f"Total segmented vectors: {len(points)}")
    
    # Step 2: Group by filename
    print("\n[2/4] Grouping by song filename...")
    groups = group_by_filename(points)
    print(f"Unique songs: {len(groups)}")
    
    # Show some stats
    segment_counts = [len(v) for v in groups.values()]
    print(f"Segments per song: min={min(segment_counts)}, max={max(segment_counts)}, avg={np.mean(segment_counts):.1f}")
    
    # Step 3: Compute averages
    print("\n[3/4] Computing average vectors...")
    averaged = compute_average_vectors(groups)
    print(f"Averaged vectors: {len(averaged)}")
    
    # Step 4: Create new collection and upload
    print("\n[4/4] Creating new collection and uploading...")
    create_averaged_collection(client)
    upload_averaged_vectors(client, averaged)
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE!")
    print(f"  Source: {SOURCE_COLLECTION} ({len(points)} segments)")
    print(f"  Target: {TARGET_COLLECTION} ({len(averaged)} songs)")
    print("=" * 60)

if __name__ == "__main__":
    main()
