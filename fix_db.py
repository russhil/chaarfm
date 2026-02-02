
import user_db
from sqlalchemy import text

def fix_schema():
    print("Fixing database schema...")
    try:
        with user_db.engine.connect() as conn:
            print("Dropping cluster_affinity...")
            conn.execute(text("DROP TABLE IF EXISTS cluster_affinity"))
            
            print("Dropping cluster_centroids...")
            conn.execute(text("DROP TABLE IF EXISTS cluster_centroids"))
            
            print("Dropping cluster_negatives...")
            conn.execute(text("DROP TABLE IF EXISTS cluster_negatives"))
            
            conn.commit()
            
        print("Re-initializing tables...")
        user_db.init_db()
        print("Done.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_schema()
