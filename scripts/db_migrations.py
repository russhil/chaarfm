#!/usr/bin/env python3
"""
Consolidated Database Migration and Maintenance Tools for ChaarFM
Handles schema fixes, migrations, and database utilities
"""
import sys
import os
import argparse
from sqlalchemy import text


def add_youtube_id_column(table_name="vectors_russhil"):
    """Add youtube_id column to a vectors table"""
    print(f"=== Adding youtube_id column to {table_name} ===")
    try:
        import psycopg2
        from dotenv import load_dotenv
        
        load_dotenv()
        DATABASE_URL = os.getenv("DATABASE_URL")
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Check if column exists
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='{table_name}' AND column_name='youtube_id';
        """)
        exists = cur.fetchone()
        
        if not exists:
            print(f"Adding youtube_id column to {table_name}...")
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN youtube_id TEXT;")
            conn.commit()
            print("✓ Column added successfully.")
        else:
            print(f"⚠ Column youtube_id already exists in {table_name}.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def fix_schema():
    """Fix database schema by recreating cluster tables"""
    print("=== Fixing Database Schema ===")
    try:
        import user_db
        
        print("Dropping old cluster tables...")
        with user_db.engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS cluster_affinity CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS cluster_centroids CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS cluster_negatives CASCADE"))
            conn.commit()
            
        print("Re-initializing tables...")
        user_db.init_db()
        print("✓ Schema fixed successfully.")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def fix_cluster_affinity_constraint():
    """Fix cluster_affinity table constraints"""
    print("=== Fixing Cluster Affinity Constraints ===")
    try:
        import user_db
        from sqlalchemy import text
        
        with user_db.engine.begin() as conn:
            # Drop existing table
            print("Dropping existing cluster_affinity table...")
            conn.execute(text("DROP TABLE IF EXISTS cluster_affinity CASCADE"))
            
            # Recreate with correct schema
            print("Creating new cluster_affinity table...")
            conn.execute(text("""
                CREATE TABLE cluster_affinity (
                    user_id TEXT NOT NULL,
                    cluster_id INTEGER NOT NULL,
                    affinity_score REAL DEFAULT 0.5,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, cluster_id)
                )
            """))
            
        print("✓ Cluster affinity constraints fixed.")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def migrate_qdrant_to_supabase():
    """Migrate data from local Qdrant to Supabase/pgvector"""
    print("=== Migrating: Local Qdrant -> Supabase ===")
    try:
        from qdrant_client import QdrantClient
        import vecs
        import config_manager
        
        config_manager.load_env_vars()
        DB_URL = os.environ.get("DATABASE_URL")
        
        if not DB_URL:
            print("✗ ERROR: DATABASE_URL not found in .env")
            return
        
        # Connect to local Qdrant
        q_path = "./qdrant_data"
        if not os.path.exists(q_path):
            print("✗ No local qdrant_data directory found.")
            return
            
        print(f"Opening local Qdrant storage: {q_path}")
        client = QdrantClient(path=q_path)
        
        # Get collections
        collections = client.get_collections().collections
        print(f"Found {len(collections)} collections.")
        
        # Connect to Supabase
        print("Connecting to Supabase...")
        vx = vecs.create_client(DB_URL)
        print("✓ Connected to Postgres/Pgvector")
        
        # Migrate each collection
        for col in collections:
            name = col.name
            print(f"\nMigrating '{name}'...")
            
            # Get dimension
            try:
                info = client.get_collection(name)
                dim = info.config.params.vectors.size
            except:
                dim = 200  # Default fallback
                
            print(f"  Dimension: {dim}")
            
            # Create destination
            dest_col = vx.get_or_create_collection(name=name, dimension=dim)
            
            # Scroll and push
            offset = None
            count = 0
            
            while True:
                points, offset = client.scroll(
                    collection_name=name,
                    limit=100,
                    offset=offset,
                    with_vectors=True,
                    with_payload=True
                )
                
                if not points:
                    break
                
                # Prepare batch
                records = [(p.id, p.vector, p.payload) for p in points]
                
                # Upsert
                dest_col.upsert(records=records)
                count += len(records)
                print(f"  Synced {count} records...", end="\r")
                
                if offset is None:
                    break
                    
            print(f"\n  ✓ Completed: {count} records.")

        print("\n✓ Migration complete!")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def migrate_to_averaged():
    """Create 'music_averaged' collection from 'music_collection'"""
    print("=== Creating music_averaged collection ===")
    try:
        import vecs
        import sqlalchemy
        import config_manager
        
        config_manager.load_env_vars()
        DB_URL = os.environ.get("DATABASE_URL")
        
        if not DB_URL:
            print("✗ Database URL missing")
            return
        
        print("Creating 'music_averaged' from 'music_collection'...")
        
        vx = vecs.create_client(DB_URL)
        tgt = vx.get_or_create_collection("music_averaged", dimension=200)
        
        # Copy data via SQL (efficient)
        engine = sqlalchemy.create_engine(DB_URL)
        
        with engine.begin() as conn:
            # Check if source exists
            check = conn.execute(text("SELECT to_regclass('vecs.\"music_collection\"')")).scalar()
            if not check:
                print("⚠ Source 'music_collection' does not exist yet.")
            else:
                conn.execute(text("""
                    INSERT INTO vecs."music_averaged" (id, vec, metadata)
                    SELECT id, vec, metadata FROM vecs."music_collection"
                    ON CONFLICT (id) DO NOTHING
                """))
                print("✓ Data copied successfully.")
                
        print("✓ Successfully synchronized 'music_averaged'.")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def migrate_users_to_supabase():
    """Migrate users from local SQLite to Supabase"""
    print("=== Migrating Users: SQLite -> Supabase ===")
    try:
        import sqlite3
        import user_db
        
        # Connect to local SQLite
        if not os.path.exists("users.db"):
            print("⚠ No local users.db found.")
            return
            
        sqlite_conn = sqlite3.connect("users.db")
        cursor = sqlite_conn.cursor()
        
        # Get all users
        cursor.execute("SELECT user_id, hashed_password, salt FROM users")
        users = cursor.fetchall()
        
        print(f"Found {len(users)} users in SQLite")
        
        # Initialize Supabase DB
        user_db.init_db()
        
        # Migrate each user
        migrated = 0
        for user_id, hashed_pw, salt in users:
            try:
                with user_db.engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO users (user_id, hashed_password, salt)
                        VALUES (:user_id, :hashed_password, :salt)
                        ON CONFLICT (user_id) DO NOTHING
                    """), {
                        "user_id": user_id,
                        "hashed_password": hashed_pw,
                        "salt": salt
                    })
                    conn.commit()
                migrated += 1
                print(f"  Migrated: {user_id}")
            except Exception as e:
                print(f"  ✗ Failed to migrate {user_id}: {e}")
        
        sqlite_conn.close()
        print(f"\n✓ Migrated {migrated}/{len(users)} users successfully.")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description='ChaarFM Database Migration and Maintenance Tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available Commands:
  add-youtube-col      - Add youtube_id column to vectors table
  fix-schema          - Fix database schema (recreate cluster tables)
  fix-constraints     - Fix cluster_affinity constraints
  migrate-qdrant      - Migrate from local Qdrant to Supabase
  migrate-averaged    - Create music_averaged collection
  migrate-users       - Migrate users from SQLite to Supabase

Examples:
  python scripts/db_migrations.py add-youtube-col
  python scripts/db_migrations.py fix-schema
  python scripts/db_migrations.py migrate-qdrant
        """
    )
    
    parser.add_argument('command',
                       choices=['add-youtube-col', 'fix-schema', 'fix-constraints',
                               'migrate-qdrant', 'migrate-averaged', 'migrate-users'],
                       help='Migration command to run')
    
    parser.add_argument('--table', default='vectors_russhil',
                       help='Table name for add-youtube-col command')
    
    args = parser.parse_args()
    
    commands = {
        'add-youtube-col': lambda: add_youtube_id_column(args.table),
        'fix-schema': fix_schema,
        'fix-constraints': fix_cluster_affinity_constraint,
        'migrate-qdrant': migrate_qdrant_to_supabase,
        'migrate-averaged': migrate_to_averaged,
        'migrate-users': migrate_users_to_supabase,
    }
    
    commands[args.command]()


if __name__ == "__main__":
    main()
