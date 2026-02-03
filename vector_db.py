
import os
import psycopg2
import numpy as np
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# We need to know which table to query.
# The server usually queries a specific user's collection or a combined one.
# For now, let's default to 'vectors_russhil' or 'vectors_combined' if we want to support multiple.
# Let's make it configurable or dynamic.
# The current app structure is a bit tailored to single-user Qdrant collection.
# We'll map "COLLECTION_NAME" to a Postgres table.

DEFAULT_TABLE = "vectors_russhil" # Defaulting to the user we just migrated/processed
VECTOR_SIZE = 200

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def get_client():
    """Returns a dummy client or connection object."""
    return "postgres_client"

def get_random_tracks(client, limit=1, avoid_ids=None, youtube_mode=False):
    """
    Retrieves random tracks using Postgres.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    avoid_clause = ""
    params = []
    
    if avoid_ids:
        # Postgres IDs are Integers in our new schema, but Qdrant used UUID strings.
        # We need to handle this.
        # The new pipeline stores SERIAL IDs (int).
        # If the app passes integer IDs, we are good.
        # If avoid_ids contains strings, we might need to filter differently or ignore.
        
        # Let's check if avoid_ids are ints
        valid_ids = [str(i) for i in avoid_ids if isinstance(i, int) or (isinstance(i, str) and i.isdigit())]
        if valid_ids:
            avoid_clause = f"AND id NOT IN ({','.join(valid_ids)})"
            
    # --- YOUTUBE MODE FILTERING ---
    mode_clause = ""
    if youtube_mode:
        # Only tracks with YouTube ID
        mode_clause = "AND youtube_id IS NOT NULL"
    else:
        # Standard mode: Only tracks with S3 URL (MP3s)
        mode_clause = "AND s3_url IS NOT NULL"
    
    query = f"""
        SELECT id, artist, title, s3_url, embedding, youtube_id 
        FROM {DEFAULT_TABLE}
        WHERE 1=1 {avoid_clause} {mode_clause}
        ORDER BY RANDOM()
        LIMIT %s
    """
    params.append(limit)
    
    try:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "filename": f"{row[1]} - {row[2]}", # Construct filename from artist/title for compatibility
                "s3_url": row[3],
                "vector": np.array(row[4]).tolist() if row[4] else [],
                "youtube_id": row[5]
            })
        return results
    except Exception as e:
        print(f"Random fetch failed: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_track_by_id(client, track_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = f"SELECT id, artist, title, s3_url, embedding, youtube_id FROM {DEFAULT_TABLE} WHERE id = %s"
        cur.execute(query, (track_id,))
        row = cur.fetchone()
        if row:
            return {
                "id": row[0],
                "filename": f"{row[1]} - {row[2]}",
                "s3_url": row[3],
                "vector": np.array(row[4]).tolist(),
                "youtube_id": row[5]
            }
        return None
    except Exception as e:
        print(f"Get track failed: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def recommend_tracks(client, positive_vectors, negative_vectors=None, avoid_ids=None, limit=1, youtube_mode=False):
    """
    Uses pgvector Cosine Distance (<=>) for recommendation.
    Postgres vector operator for cosine distance is <=>
    We want NEAREST (smallest distance).
    """
    if not positive_vectors:
        return get_random_tracks(client, limit, avoid_ids, youtube_mode=youtube_mode)
        
    target_vector = positive_vectors[0] # Simplification: use first positive
    if isinstance(target_vector, list) and len(target_vector) > 0 and isinstance(target_vector[0], list):
         target_vector = target_vector[0]
         
    # Convert list to string format for pgvector '[1,2,3]'
    vec_str = str(target_vector)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    avoid_clause = ""
    if avoid_ids:
        valid_ids = [str(i) for i in avoid_ids if isinstance(i, int) or (isinstance(i, str) and i.isdigit())]
        if valid_ids:
            avoid_clause = f"AND id NOT IN ({','.join(valid_ids)})"

    # --- YOUTUBE MODE FILTERING ---
    mode_clause = ""
    if youtube_mode:
        mode_clause = "AND youtube_id IS NOT NULL"
    else:
        mode_clause = "AND s3_url IS NOT NULL"

    # Order by cosine distance
    query = f"""
        SELECT id, artist, title, s3_url, embedding, youtube_id, (embedding <=> %s::vector) as dist
        FROM {DEFAULT_TABLE}
        WHERE 1=1 {avoid_clause} {mode_clause}
        ORDER BY dist ASC
        LIMIT %s
    """
    
    try:
        cur.execute(query, (vec_str, limit))
        rows = cur.fetchall()
        
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "filename": f"{row[1]} - {row[2]}",
                "s3_url": row[3],
                "vector": np.array(row[4]).tolist(),
                "youtube_id": row[5],
                "score": 1 - row[6] # Convert distance to similarity score roughly
            })
        return results
    except Exception as e:
        print(f"Recommend failed: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_all_vectors(client):
    """Retrieves all vectors for clustering."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Fetch everything, we filter later in memory or clustering logic
        # Or better: fetch everything and let the cluster manager know which mode a track belongs to?
        # For now, let's fetch everything.
        query = f"SELECT id, artist, title, s3_url, embedding, youtube_id FROM {DEFAULT_TABLE}"
        cur.execute(query)
        rows = cur.fetchall()
        
        results = []
        for row in rows:
            if row[4] is None: continue
            results.append({
                "id": row[0],
                "filename": f"{row[1]} - {row[2]}",
                "s3_url": row[3],
                "vector": np.array(row[4]).tolist(),
                "youtube_id": row[5]
            })
        return results
    except Exception as e:
        print(f"Get all failed: {e}")
        return []
    finally:
        cur.close()
        conn.close()
