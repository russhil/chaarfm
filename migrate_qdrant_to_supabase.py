import sys
import os
import json
import time

try:
    from qdrant_client import QdrantClient
    import vecs
except ImportError:
    print("⚠️  Dependencies missing.")
    print("Run: pip install qdrant-client vecs")
    sys.exit(1)

import config_manager
config_manager.load_env_vars()

DB_URL = os.environ.get("DATABASE_URL")

def migrate():
    print("🚀 MIGRATION: Local Qdrant -> Supabase")
    
    if not DB_URL:
        print("❌ ERROR: DATABASE_URL not found in .env.")
        print("Please set up your Supabase connection string first.")
        sys.exit(1)
    
    # 1. Connect to Local Qdrant
    q_path = "./qdrant_data"
    if not os.path.exists(q_path):
        print("❌ No local qdrant_data directory found. Nothing to migrate.")
        return
        
    print(f"📂 Opening local Qdrant storage: {q_path}")
    try:
        client = QdrantClient(path=q_path)
    except Exception as e:
        print(f"❌ Failed to load local Qdrant: {e}")
        return
    
    # 2. Get Collections
    try:
        collections = client.get_collections().collections
    except Exception as e:
        print(f"❌ Failed to list collections: {e}")
        return
        
    print(f"Found {len(collections)} collections.")
    
    # 3. Connect to Supabase
    print(f"☁️ Connecting to Supabase...")
    try:
        vx = vecs.create_client(DB_URL)
        print("  ✅ Connected to Postgres/Pgvector")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return
    
    # 4. Migrate
    for col in collections:
        name = col.name
        print(f"\nMigrating '{name}'...")
        
        # Get dimension
        try:
            info = client.get_collection(name)
            dim = info.config.params.vectors.size
        except:
            dim = 200 # Default fallback
            
        print(f"  Dimension: {dim}")
        
        # Create destination
        dest_col = vx.get_or_create_collection(name=name, dimension=dim)
        
        # Scroll and Push
        offset = None
        count = 0
        total_batches = 0
        
        while True:
            # Scroll local
            points, offset = client.scroll(
                collection_name=name,
                limit=100,
                offset=offset,
                with_vectors=True,
                with_payload=True
            )
            
            if not points:
                break
            
            # Prepare batch for vecs
            records = []
            for p in points:
                # vecs needs (id, vector, metadata)
                records.append((p.id, p.vector, p.payload))
                
            # Upsert
            dest_col.upsert(records=records)
            count += len(records)
            total_batches += 1
            print(f"  Synced {count} records...", end="\r")
            
            if offset is None:
                break
                
        print(f"  ✅ Completed: {count} records.")

    print("\n🏁 ALL DONE.")

if __name__ == "__main__":
    migrate()
