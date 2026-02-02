import os
import vecs
import sqlalchemy
from sqlalchemy import text
import config_manager
config_manager.load_env_vars()

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    print("Database URL missing")
    exit(1)

print("Creating 'music_averaged' from 'music_collection'...")

vx = vecs.create_client(DB_URL)
# Create destination collection
tgt = vx.get_or_create_collection("music_averaged", dimension=200)

# Copy data via SQL (Efficient)
engine = sqlalchemy.create_engine(DB_URL)

try:
    with engine.begin() as conn:
        # Check if source exists
        check = conn.execute(text("SELECT to_regclass('vecs.\"music_collection\"')")).scalar()
        if not check:
            print("Source 'music_collection' does not exist in Supabase yet.")
        else:
            result = conn.execute(text("""
                INSERT INTO vecs."music_averaged" (id, vec, metadata)
                SELECT id, vec, metadata FROM vecs."music_collection"
                ON CONFLICT (id) DO NOTHING
            """))
            print(f"Copied rows.")
            
    print("✅ Successfully synchronized 'music_averaged'.")
except Exception as e:
    print(f"❌ Error: {e}")
