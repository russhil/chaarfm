
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
        
        # Check if users table exists
        res = conn.execute(text("SELECT to_regclass('public.users')")).fetchone()
        if res[0]:
            print("✅ 'users' table exists.")
        else:
            print("⚠️ 'users' table NOT found (might need initialization).")
            
        # Check vecs schema
        res = conn.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'vecs'")).fetchone()
        if res:
            print("✅ 'vecs' schema exists (pgvector extension likely active).")
        else:
            print("⚠️ 'vecs' schema NOT found.")

except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)
