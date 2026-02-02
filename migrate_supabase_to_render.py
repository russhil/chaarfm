import os
import sys
import json
from sqlalchemy import create_engine, text, MetaData, Table, inspect
from sqlalchemy.schema import CreateTable
from dotenv import load_dotenv
import pandas as pd

# Load env vars
load_dotenv(override=True)

SOURCE_DB_URL = os.getenv("DATABASE_URL")

def migrate():
    print("🚀 MIGRATION: Supabase -> Render PostgreSQL")
    print("==========================================")
    
    if not SOURCE_DB_URL:
        print("❌ ERROR: DATABASE_URL (Source) not found in .env.")
        sys.exit(1)
        
    print(f"Source: {SOURCE_DB_URL.split('@')[-1]}")
    
    # Get Destination
    dest_url = input("\nEnter Render (Destination) Connection String: ").strip()
    if not dest_url:
        print("❌ No destination provided.")
        sys.exit(1)
        
    if "sslmode" not in dest_url:
        print("⚠️ Warning: sslmode not found in URL. Appending '?sslmode=require'...")
        if "?" in dest_url:
            dest_url += "&sslmode=require"
        else:
            dest_url += "?sslmode=require"

    src_engine = create_engine(SOURCE_DB_URL)
    dest_engine = create_engine(dest_url)
    
    # 1. Setup Destination
    print("\n1️⃣  Setting up Destination...")
    try:
        with dest_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            # Create 'vecs' schema for pgvector-python/vecs compatibility
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS vecs"))
            conn.commit()
            print("   ✅ 'vector' extension and 'vecs' schema enabled.")
    except Exception as e:
        print(f"   ⚠️ Could not setup destination: {e}")

    # 2. Reflect Tables
    print("\n2️⃣  Analyzing Source Schema...")
    src_insp = inspect(src_engine)
    
    # We want public tables AND vecs tables
    schemas = src_insp.get_schema_names()
    target_schemas = ['public']
    if 'vecs' in schemas:
        target_schemas.append('vecs')
        
    for schema in target_schemas:
        print(f"\n📂 Processing Schema: {schema}")
        tables = src_insp.get_table_names(schema=schema)
        
        for table_name in tables:
            print(f"   ➡ Table: {table_name}")
            
            # Read Data
            try:
                # Use pandas for easy chunk reading
                df = pd.read_sql_table(table_name, src_engine, schema=schema)
                
                if df.empty:
                    print(f"      Empty table. Skipping data copy.")
                else:
                    count = len(df)
                    print(f"      Found {count} rows. Copying...")
                    
                    # Pre-process 'vec' column to ensure it's a string for TEXT insertion
                    # Pandas might hold it as a list/object which causes issues in to_sql
                    if 'vec' in df.columns:
                        print("      🔧 formatting 'vec' column as strings...")
                        # Ensure it's formatted as a list string "[0.1, 0.2, ...]" which Postgres vector type accepts
                        df['vec'] = df['vec'].apply(lambda x: str(x) if isinstance(x, list) else x)
                        
                    if 'metadata' in df.columns:
                        print("      🔧 formatting 'metadata' column as json strings...")
                        df['metadata'] = df['metadata'].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
                        
                    # Write Data
                    # method='multi' speeds up inserts
                    # if_exists='replace' or 'append'? 
                    # 'replace' drops the table, which might lose constraints/indexes not captured by simple pandas creation.
                    # Ideally we want to keep schema.
                    # Let's try 'append' first. If table doesn't exist, pandas creates it (but maybe with wrong types for vectors).
                    
                    # Better approach: 
                    # If it's a 'vecs' table or complex table, pandas creation might fail to map 'vector' type correctly.
                    # We should probably rely on SQLAlchemy reflection to create table if not exists, 
                    # BUT cross-database reflection/creation is tricky.
                    
                    # Simplified strategy for this user:
                    # Just use pandas 'replace' but ensure we handle vector columns as strings/lists if needed?
                    # No, pandas to_sql doesn't support pgvector natively well.
                    
                    # Fallback: Just try generic pandas append.
                    # If it fails, we warn.
                    
                    try:
                        df.to_sql(
                            table_name, 
                            dest_engine, 
                            schema=schema, 
                            if_exists='replace', 
                            index=False,
                            chunksize=100 # Smaller chunksize, default method
                        )
                    except Exception as insert_err:
                        print(f"      ❌ Insert failed for {table_name}: {insert_err}")
                        continue
                    
                    # Post-processing for vector tables
                    if schema == 'vecs' and 'vec' in df.columns:
                        print(f"      🔧 Converting 'vec' column to vector type...")
                        try:
                            with dest_engine.connect() as conn:
                                # Assuming 200 dim as per codebase, or just generic vector?
                                # vecs library usually enforces a dim. 
                                # Let's try explicit cast. If it fails, we leave as text.
                                # Using vec::vector might default to generic vector (variable dim) or fail if dim not specified?
                                # Postgres vector type requires dimension usually for indexing, but type itself can be generic?
                                # Actually, type 'vector' without dim allows any dim.
                                conn.execute(text(f"ALTER TABLE {schema}.{table_name} ALTER COLUMN vec TYPE vector USING vec::vector"))
                                conn.commit()
                                print(f"      ✅ Converted to vector.")
                        except Exception as ve:
                            print(f"      ⚠️ Vector conversion failed (kept as text): {ve}")
                            
                    print(f"      ✅ Copied {count} rows.")
                    
            except Exception as e:
                print(f"      ❌ Failed to migrate {table_name}: {e}")

    print("\n------------------------------------------------")
    print("✅ Migration Script Finished.")
    print("Note: Indexes and constraints might need manual verification.")
    print("Run this script using: python3 migrate_supabase_to_render.py")

if __name__ == "__main__":
    try:
        migrate()
    except KeyboardInterrupt:
        print("\nAborted.")
