import os
import time
import sqlalchemy
from sqlalchemy import text
import config_manager
config_manager.load_env_vars()

DB_URL = os.environ.get("DATABASE_URL")

sql_commands = [
    # 1. Create View for public access (vecs schema is hidden from PostgREST)
    """
    CREATE OR REPLACE VIEW public.music_tracks AS 
    SELECT id, vec, metadata 
    FROM vecs."music_averaged";
    """,
    # 2. Grant permissions
    "GRANT SELECT ON public.music_tracks TO anon, authenticated, service_role;",
    
    # 3. Create Search Function (RPC)
    """
    CREATE OR REPLACE FUNCTION match_music(query_embedding vector(200), match_threshold float, match_count int)
    RETURNS TABLE (
      id varchar,
      metadata jsonb,
      similarity float
    )
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    BEGIN
      RETURN QUERY
      SELECT
        m.id,
        m.metadata,
        1 - (m.vec <=> query_embedding) as similarity
      FROM vecs."music_averaged" m
      WHERE 1 - (m.vec <=> query_embedding) > match_threshold
      ORDER BY m.vec <=> query_embedding
      LIMIT match_count;
    END;
    $$;
    """
]

def run_sql():
    print("Attempting to configure Supabase for HTTP access...")
    try:
        engine = sqlalchemy.create_engine(DB_URL)
        with engine.begin() as conn:
            for sql in sql_commands:
                conn.execute(text(sql))
        print("✅ SUCCESS! Tables/Functions created.")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    # Retry loop to maximize chance of IPv4/IPv6 handshake success
    for i in range(5):
        if run_sql():
            break
        print(f"Retrying in 2s ({i+1}/5)...")
        time.sleep(2)
