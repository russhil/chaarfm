"""
Apply Power 0.3 Transformation to Vector Collections
=====================================================

Takes existing Qdrant collections and creates Power 0.3 transformed versions
for better cluster separation.

Usage:
    python pipeline_transform.py [collection_name]
    
    If no collection specified, transforms all 3:
    - music_russhil -> music_russhil_p03
    - music_sahil -> music_sahil_p03
    - music_combined -> music_combined_p03
"""

import sys
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

# Collections to transform
SOURCE_COLLECTIONS = [
    "music_russhil",
    "music_sahil",
    "music_combined"
]

VECTOR_SIZE = 200

def get_client():
    try:
        return QdrantClient(host="localhost", port=6333)
    except:
        return QdrantClient(path="./qdrant_data")

def power_transform(vectors: np.ndarray, power: float = 0.3) -> np.ndarray:
    """Apply power transformation and L2 normalize."""
    transformed = np.sign(vectors) * np.abs(vectors) ** power
    norms = np.linalg.norm(transformed, axis=1, keepdims=True) + 1e-8
    return transformed / norms

def transform_collection(client, source_name: str, target_name: str):
    """Transform a collection using Power 0.3."""
    
    print(f"\n{'='*60}")
    print(f"Transforming: {source_name} -> {target_name}")
    print(f"{'='*60}")
    
    # Check if source exists
    collections = [c.name for c in client.get_collections().collections]
    if source_name not in collections:
        print(f"  ERROR: Source collection '{source_name}' does not exist")
        return False
    
    # Load all points from source
    print(f"  Loading points from {source_name}...")
    all_points = []
    offset = None
    
    while True:
        result = client.scroll(
            collection_name=source_name,
            limit=1000,
            offset=offset,
            with_vectors=True,
            with_payload=True
        )
        points, offset = result
        if not points:
            break
        all_points.extend(points)
        if offset is None:
            break
    
    print(f"  Loaded {len(all_points)} points")
    
    if not all_points:
        print("  WARNING: No points to transform")
        return False
    
    # Extract vectors and transform
    print(f"  Applying Power 0.3 transformation...")
    vectors = np.array([p.vector for p in all_points])
    transformed = power_transform(vectors, power=0.3)
    
    # Create target collection
    if target_name in collections:
        print(f"  Deleting existing target: {target_name}")
        client.delete_collection(target_name)
    
    client.create_collection(
        collection_name=target_name,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
    )
    print(f"  Created collection: {target_name}")
    
    # Upload transformed points
    print(f"  Uploading transformed points...")
    points_to_upload = []
    
    for i, p in enumerate(all_points):
        points_to_upload.append(PointStruct(
            id=p.id,
            vector=transformed[i].tolist(),
            payload=p.payload
        ))
    
    # Batch upload
    batch_size = 100
    for i in range(0, len(points_to_upload), batch_size):
        batch = points_to_upload[i:i+batch_size]
        client.upsert(collection_name=target_name, points=batch)
    
    print(f"  ✅ Uploaded {len(points_to_upload)} points to {target_name}")
    return True

def main():
    client = get_client()
    
    # Determine which collections to transform
    if len(sys.argv) > 1 and sys.argv[1] not in ["--help", "-h"]:
        # Specific collection
        source = sys.argv[1]
        target = source + "_p03"
        transform_collection(client, source, target)
    else:
        # All collections
        print("Transforming all collections with Power 0.3...")
        for source in SOURCE_COLLECTIONS:
            target = source + "_p03"
            transform_collection(client, source, target)
    
    # Summary
    print(f"\n{'='*60}")
    print("TRANSFORMATION COMPLETE")
    print(f"{'='*60}")
    print("\nAll collections:")
    for c in client.get_collections().collections:
        info = client.get_collection(c.name)
        print(f"  {c.name}: {info.points_count} points")

if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
    else:
        main()
