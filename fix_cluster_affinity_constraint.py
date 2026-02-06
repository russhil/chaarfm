"""
Fix cluster_affinity table constraint issue.

This script adds the missing PRIMARY KEY or UNIQUE constraint to the cluster_affinity table
so that ON CONFLICT clauses work properly.
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env")
    exit(1)

engine = create_engine(DATABASE_URL)

def fix_constraint():
    """Add the missing constraint to cluster_affinity table."""
    print("Fixing cluster_affinity table constraint...")
    
    with engine.connect() as conn:
        # First, check if the constraint already exists
        result = conn.execute(text("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'cluster_affinity' 
            AND constraint_type IN ('PRIMARY KEY', 'UNIQUE')
        """)).fetchall()
        
        print(f"Current constraints: {result}")
        
        # Check if there are any existing constraints on these columns
        if result:
            print("Constraint already exists. Checking if it's correct...")
            
            # Check the columns in the constraint
            constraint_cols = conn.execute(text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = 'cluster_affinity'
                AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
                ORDER BY kcu.ordinal_position
            """)).fetchall()
            
            cols = [row[0] for row in constraint_cols]
            print(f"Constraint columns: {cols}")
            
            expected_cols = ['user_id', 'cluster_id', 'collection_name']
            if set(cols) == set(expected_cols):
                print("✅ Constraint is correct!")
                return
            else:
                print("⚠️  Constraint exists but with wrong columns. Need to drop and recreate.")
                # Drop the existing constraint
                constraint_name = result[0][0]
                conn.execute(text(f"ALTER TABLE cluster_affinity DROP CONSTRAINT {constraint_name}"))
                conn.commit()
                print(f"Dropped constraint: {constraint_name}")
        
        # Now add the correct PRIMARY KEY constraint
        try:
            # First, remove any duplicate rows
            print("Checking for duplicate rows...")
            duplicates = conn.execute(text("""
                SELECT user_id, cluster_id, collection_name, COUNT(*)
                FROM cluster_affinity
                GROUP BY user_id, cluster_id, collection_name
                HAVING COUNT(*) > 1
            """)).fetchall()
            
            if duplicates:
                print(f"Found {len(duplicates)} duplicate groups. Consolidating...")
                
                for user_id, cluster_id, collection_name, count in duplicates:
                    print(f"  Consolidating: {user_id}, {cluster_id}, {collection_name} ({count} duplicates)")
                    
                    # Get aggregated data
                    agg_data = conn.execute(text("""
                        SELECT 
                            SUM(positive_signals) as total_pos,
                            SUM(total_listen_seconds) as total_sec,
                            SUM(track_count) as total_tracks,
                            MAX(last_positive_date) as last_date
                        FROM cluster_affinity
                        WHERE user_id = :uid AND cluster_id = :cid AND collection_name = :col
                    """), {"uid": user_id, "cid": cluster_id, "col": collection_name}).fetchone()
                    
                    # Delete all duplicates
                    conn.execute(text("""
                        DELETE FROM cluster_affinity
                        WHERE user_id = :uid AND cluster_id = :cid AND collection_name = :col
                    """), {"uid": user_id, "cid": cluster_id, "col": collection_name})
                    
                    # Insert consolidated row
                    conn.execute(text("""
                        INSERT INTO cluster_affinity 
                        (user_id, cluster_id, collection_name, positive_signals, total_listen_seconds, track_count, last_positive_date, session_rejections)
                        VALUES (:uid, :cid, :col, :pos, :sec, :tracks, :date, 0)
                    """), {
                        "uid": user_id,
                        "cid": cluster_id,
                        "col": collection_name,
                        "pos": agg_data[0] or 0,
                        "sec": agg_data[1] or 0,
                        "tracks": agg_data[2] or 0,
                        "date": agg_data[3]
                    })
                    
                conn.commit()
                print("✅ Duplicates consolidated")
            
            # Now add the PRIMARY KEY
            print("Adding PRIMARY KEY constraint...")
            conn.execute(text("""
                ALTER TABLE cluster_affinity 
                ADD PRIMARY KEY (user_id, cluster_id, collection_name)
            """))
            conn.commit()
            
            print("✅ PRIMARY KEY constraint added successfully!")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            print("\nTrying alternative approach with UNIQUE constraint...")
            
            try:
                conn.execute(text("""
                    ALTER TABLE cluster_affinity 
                    ADD CONSTRAINT cluster_affinity_unique 
                    UNIQUE (user_id, cluster_id, collection_name)
                """))
                conn.commit()
                print("✅ UNIQUE constraint added successfully!")
            except Exception as e2:
                print(f"❌ Error with UNIQUE constraint: {e2}")
                print("\nPlease run this SQL manually:")
                print("""
                -- First check for duplicates:
                SELECT user_id, cluster_id, collection_name, COUNT(*)
                FROM cluster_affinity
                GROUP BY user_id, cluster_id, collection_name
                HAVING COUNT(*) > 1;
                
                -- If duplicates exist, consolidate them first
                -- Then add constraint:
                ALTER TABLE cluster_affinity 
                ADD PRIMARY KEY (user_id, cluster_id, collection_name);
                """)

if __name__ == "__main__":
    fix_constraint()
