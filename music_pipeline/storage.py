import boto3
import psycopg2
from psycopg2.extras import Json
import os
from .config import S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET, DATABASE_URL

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY
    )

def upload_to_r2(filepath, object_name):
    """
    Uploads file to Cloudflare R2.
    Returns the public URL (if configured) or S3 URI.
    """
    s3 = get_s3_client()
    try:
        print(f"  Uploading to R2: {object_name}...")
        s3.upload_file(filepath, S3_BUCKET, object_name)
        
        # Construct URL (assuming public access or similar)
        # If R2_PUBLIC_URL is set in config, use it.
        # Otherwise try to construct a public-ish R2 URL if possible or just return object path
        
        from .config import R2_PUBLIC_URL
        if R2_PUBLIC_URL:
            return f"{R2_PUBLIC_URL}/{object_name}"
        else:
            # Fallback: Return a path that the server can use to sign URLs if needed
            # Or just the object key if we assume the bucket is private and we need to sign
            return object_name 
            
    except Exception as e:
        print(f"  Upload failed: {e}")
        return None

def store_vector_db(username, track_metadata, vector, s3_url):
    """
    Stores the vector and metadata in Postgres.
    Creates a table named after the username if it doesn't exist.
    """
    table_name = f"vectors_{username}"
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Create table if not exists
        # We use 'vector' type if pgvector exists, else float[] array
        # Let's check for pgvector extension first or just use array for compatibility
        # User said "vectorise", assuming pgvector is goal.
        
        # Enable pgvector extension if possible
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        except:
            conn.rollback() # Might fail if permissions denied
            # Fallback to float array
        
        # Create table
        # We assume vector dim is 200 (MTT_musicnn penultimate layer usually)
        # Using vector(200)
        
        # Sanitization of table name (username) to avoid SQLi
        safe_table_name = "".join(c for c in table_name if c.isalnum() or c == '_')
        
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {safe_table_name} (
            id SERIAL PRIMARY KEY,
            artist TEXT,
            title TEXT,
            s3_url TEXT,
            embedding vector(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        # If vector type fails, fallback to float8[]
        try:
            cur.execute(create_table_query)
        except Exception as e:
            conn.rollback()
            print(f"  Vector type might not be supported, falling back to array: {e}")
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {safe_table_name} (
                id SERIAL PRIMARY KEY,
                artist TEXT,
                title TEXT,
                s3_url TEXT,
                embedding float8[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            cur.execute(create_table_query)
            
        conn.commit()
        
        # Insert
        insert_query = f"""
        INSERT INTO {safe_table_name} (artist, title, s3_url, embedding)
        VALUES (%s, %s, %s, %s)
        """
        
        cur.execute(insert_query, (
            track_metadata['artist'],
            track_metadata['title'],
            s3_url,
            vector # psycopg2 handles list -> array/vector
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"  Stored in DB table: {safe_table_name}")
        return True
        
    except Exception as e:
        print(f"  DB Error: {e}")
        return False
