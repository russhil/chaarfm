import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
TABLE_NAME = "vectors_russhil"

def add_column():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # Check if column exists
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='{TABLE_NAME}' AND column_name='youtube_id';
        """)
        exists = cur.fetchone()
        
        if not exists:
            print(f"Adding youtube_id column to {TABLE_NAME}...")
            cur.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN youtube_id TEXT;")
            conn.commit()
            print("Column added successfully.")
        else:
            print(f"Column youtube_id already exists in {TABLE_NAME}.")
            
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    add_column()
