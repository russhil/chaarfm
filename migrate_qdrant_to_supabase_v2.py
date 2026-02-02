import sys
import os
import json
import time

try:
    from qdrant_client import QdrantClient
    import vecs
except ImportError:
    print("⚠️  Dependencies missing.")
    sys.exit(1)

import config_manager
config_manager.load_env_vars()

DB_URL = os.environ.get("DATABASE_URL")

def migrate():
    print("🚀 MIGRATION: Qdrant -> Supabase (Retry)")
    
    if not DB_URL:
        print("❌ ERROR: DATABASE_URL not found in .env.")
        sys.exit(1)
    
    # 1. Connect to Qdrant (Prioritize Docker)
    client = None
    source = "unknown"
    
    print("🔍 Checking Qdrant sources...")
    try:
        # Try Docker
        client = QdrantClient(host="localhost", port=6333, timeout=2)
        # Test connection
        cols = client.get_collections().collections
        print("  ✅ Connected to Docker Qdrant (localhost:6333)")
        source = "docker"
    except Exception as e:
        print(f"  ⚠️ Docker Qdrant not available: {e}")
        # Try Local
        if os.path.exists("./qdrant_data"):
            print("  📂 Found local ./qdrant_data")
            client = QdrantClient(path="./qdrant_data")
            source = "local"
        else:
            print("❌ No Qdrant source found (neither Docker nor ./qdrant_data).")
            return

    # 2. Get Collections
    try:
        collections = client.get_collections().collections
        print(f"found {len(collections)} collections in {source}.")
    except Exception as e:
        print(f"❌ Failed to list collections: {e}")
        return
        
    collections_to_migrate = ["music_averaged"]
    print(f"Targeting only: {collections_to_migrate}")
    
    # 3. Connect to Supabase
    print(f"☁️ Connecting to Supabase...")
    try:
        vx = vecs.create_client(DB_URL)
        print("  ✅ Connected to Postgres/Pgvector")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return
    
    # 4. Migrate
    for name in collections_to_migrate:
        print(f"\nMigrating '{name}'...")
        
        # Get count/dim
        try:
            info = client.get_collection(name)
            dim = info.config.params.vectors.size
            total_points = info.points_count
            print(f"  Count: {total_points} | Dimension: {dim}")
        except:
            dim = 200
            total_points = "?"

        if total_points == 0:
            print("  Skipping empty collection.")
            continue
            
        # Create destination
        try:
            dest_col = vx.get_or_create_collection(name=name, dimension=dim)
        except Exception as e:
            print(f"  Failed to create/get collection {name}: {e}")
            continue

        # Scroll and Push
        offset = None
        count = 0
        
        while True:
            try:
                points, offset = client.scroll(
                    collection_name=name,
                    limit=200, # Faster batch
                    offset=offset,
                    with_vectors=True,
                    with_payload=True
                )
            except Exception as e:
                print(f"  Read error: {e}")
                break
            
            if not points:
                break
            
            records = []
            for p in points:
                records.append((p.id, p.vector, p.payload))
                
            try:
                dest_col.upsert(records=records)
                count += len(records)
                print(f"  Synced {count} / {total_points}...", end="\r")
            except Exception as e:
                print(f"  Write error: {e}")
            
            if offset is None:
                break
                
        print(f"  ✅ Completed: {count} records.")

    print("\n🏁 ALL DONE.")

if __name__ == "__main__":
    migrate()
