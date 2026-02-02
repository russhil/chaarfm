import sqlite3
import os
import json
from sqlalchemy import create_engine, text, MetaData, Table

import config_manager
config_manager.load_env_vars()

DB_URL = os.environ.get("DATABASE_URL")
SQLITE_FILE = "users.db"

def migrate():
    print("🚀 MIGRATION: Local Users/History -> Supabase")
    
    if not DB_URL:
        print("❌ ERROR: DATABASE_URL not found.")
        exit(1)

    if not os.path.exists(SQLITE_FILE):
        print(f"❌ {SQLITE_FILE} not found. Skipping user migration.")
        return

    print(f"📂 Reading {SQLITE_FILE}...")
    pg_engine = create_engine(DB_URL)
    sqlite_conn = sqlite3.connect(SQLITE_FILE)
    sqlite_conn.row_factory = sqlite3.Row

    TABLES = [
        "users",
        "cluster_affinity",
        "cluster_centroids",
        "session_logs",
        "track_logs"
    ]

    try:
        with pg_engine.begin() as pg_conn:
            meta = MetaData()
            
            for table in TABLES:
                print(f"\nProcessing table '{table}'...")
                
                # 1. Read Local
                try:
                    rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
                except Exception as e:
                    print(f"  ⚠️ Skipping {table} (Not found in SQLite): {e}")
                    continue
                    
                if not rows:
                    print("  ℹ️ Local table is empty.")
                    # Still truncate remote to match empty state? 
                    # Yes, "Move" implies exact state.
                    pg_conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
                    continue
                    
                # 2. Clear Remote
                print(f"  Clearing remote table...")
                try:
                    # DELETE is safer against locks than TRUNCATE
                    pg_conn.execute(text(f"DELETE FROM {table}"))
                except Exception as e:
                    print(f"  Delete failed: {e}")
                
                # 3. Insert
                data_list = [dict(row) for row in rows]
                
                # Filter 'track_logs' columns if schema changed?
                # Assuming exact match or PG has superset.
                # SQLAlchemy insert with list of dicts matches keys to columns.
                
                try:
                    pg_table = Table(table, meta, autoload_with=pg_engine)
                    pg_conn.execute(pg_table.insert(), data_list)
                    print(f"  ✅ Migrated {len(data_list)} rows.")
                except Exception as e:
                    print(f"  ❌ Insert failed: {e}")

            # 4. Reset Sequences
            print("\nSyncing sequences...")
            for t in ["track_logs", "session_logs"]:
                try:
                    pg_conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), COALESCE(max(id), 1)) FROM {t}"))
                    print(f"  {t} sequence updated.")
                except Exception as e:
                    print(f"  {t} sequence skip: {e}")

        print("\n🏁 User Migration Complete.")
        
    except Exception as e:
        print(f"\n❌ Migration Failed: {e}")

if __name__ == "__main__":
    migrate()
