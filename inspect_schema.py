
import user_db
from sqlalchemy import text

def inspect_table():
    print("Inspecting public.vectors_russhil schema...")
    try:
        with user_db.engine.connect() as conn:
            # Get column names
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'vectors_russhil'
            """)).fetchall()
            
            print("\nColumns:")
            for col, dtype in result:
                print(f"  {col}: {dtype}")
                
            # Sample row
            print("\nSample Row:")
            row = conn.execute(text('SELECT * FROM public."vectors_russhil" LIMIT 1')).mappings().fetchone()
            if row:
                print(dict(row))
            else:
                print("Table is empty")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_table()
