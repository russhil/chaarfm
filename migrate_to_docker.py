"""
Migrate Local Qdrant Data to Docker
====================================

This script migrates all collections from local storage (./qdrant_data)
to a running Docker Qdrant server (localhost:6333).

It will:
1. Connect to local storage
2. Connect to Docker server
3. DELETE all existing collections on Docker (clean slate)
4. Copy all data from local to Docker

Usage:
    python migrate_to_docker.py
"""

import sys
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

VECTOR_SIZE = 200

def main():
    print("=" * 60)
    print("MIGRATE LOCAL QDRANT TO DOCKER")
    print("=" * 60)
    
    # 1. Connect to local storage
    print("\n📁 Connecting to local storage (./qdrant_data)...")
    try:
        local_client = QdrantClient(path="./qdrant_data")
        local_collections = [c.name for c in local_client.get_collections().collections]
        print(f"  Found {len(local_collections)} collections: {local_collections}")
    except Exception as e:
        print(f"  ❌ Failed to connect to local storage: {e}")
        print("  Make sure ./qdrant_data exists and has data")
        sys.exit(1)
    
    if not local_collections:
        print("  ❌ No collections found in local storage!")
        sys.exit(1)
    
    # 2. Connect to Docker server
    print("\n🐳 Connecting to Docker Qdrant (localhost:6333)...")
    try:
        docker_client = QdrantClient(host="localhost", port=6333)
        docker_client.get_collections()  # Test connection
        print("  ✅ Connected to Docker server")
    except Exception as e:
        print(f"  ❌ Failed to connect to Docker: {e}")
        print("  Make sure Docker is running: docker run -p 6333:6333 qdrant/qdrant")
        sys.exit(1)
    
    # 3. Delete existing collections on Docker (clean slate)
    print("\n🧹 Cleaning Docker collections (removing residue)...")
    docker_collections = [c.name for c in docker_client.get_collections().collections]
    for coll_name in docker_collections:
        print(f"  Deleting: {coll_name}")
        docker_client.delete_collection(coll_name)
    print("  ✅ Docker cleaned")
    
    # 4. Migrate each collection
    print("\n📤 Migrating collections...")
    
    for coll_name in local_collections:
        print(f"\n  [{coll_name}]")
        
        # Get collection info from local
        try:
            local_info = local_client.get_collection(coll_name)
            point_count = local_info.points_count
            print(f"    Points to migrate: {point_count}")
        except:
            print(f"    ⚠️ Could not get info, skipping")
            continue
        
        if point_count == 0:
            print(f"    ⚠️ Empty collection, skipping")
            continue
        
        # Create collection on Docker
        docker_client.create_collection(
            collection_name=coll_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        )
        print(f"    Created collection on Docker")
        
        # Scroll through all points and upload in batches
        offset = None
        uploaded = 0
        batch_size = 100
        
        while True:
            result = local_client.scroll(
                collection_name=coll_name,
                limit=batch_size,
                offset=offset,
                with_vectors=True,
                with_payload=True
            )
            points, offset = result
            
            if not points:
                break
            
            # Convert to PointStruct
            points_to_upload = [
                PointStruct(
                    id=p.id,
                    vector=p.vector,
                    payload=p.payload
                ) for p in points
            ]
            
            docker_client.upsert(collection_name=coll_name, points=points_to_upload)
            uploaded += len(points_to_upload)
            print(f"    Uploaded: {uploaded}/{point_count}", end="\r")
            
            if offset is None:
                break
        
        print(f"    ✅ Uploaded {uploaded} points")
    
    # 5. Verify
    print("\n\n✅ MIGRATION COMPLETE")
    print("=" * 60)
    print("Docker collections:")
    for coll in docker_client.get_collections().collections:
        info = docker_client.get_collection(coll.name)
        print(f"  {coll.name}: {info.points_count} points")

if __name__ == "__main__":
    main()
