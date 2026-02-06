import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load env vars
load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL is missing in .env")
    sys.exit(1)

print(f"Testing connection to: {DATABASE_URL.split('@')[-1]}")

try:
    # Use standard timeout to fail fast
    engine = create_engine(DATABASE_URL, connect_args={'connect_timeout': 10})
    
    with engine.connect() as conn:
        print("✅ Connection successful!")
        
        # Check version
        res = conn.execute(text("SELECT version()")).fetchone()
        print(f"Database Version: {res[0]}")
        
        # Check if users table exists and has data
        res = conn.execute(text("SELECT count(*) FROM users")).fetchone()
        print(f"✅ 'users' table count: {res[0]}")
            
        # Check vecs schema and vectors
        res = conn.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'vecs'")).fetchone()
        if res:
            print("✅ 'vecs' schema exists.")
            # Check music_collection count
            try:
                res = conn.execute(text("SELECT count(*) FROM vecs.music_collection")).fetchone()
                print(f"✅ 'vecs.music_collection' count: {res[0]}")
            except Exception as e:
                try:
                    res = conn.execute(text("SELECT count(*) FROM vecs.music_averaged")).fetchone()
                    print(f"✅ 'vecs.music_averaged' count: {res[0]}")
                except Exception as e2:
                    print(f"⚠️ Could not read music collections: {e}")
        else:
            print("⚠️ 'vecs' schema NOT found.")

except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)
