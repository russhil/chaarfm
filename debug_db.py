
import user_db
from sqlalchemy import text

def inspect_constraints():
    print("Inspecting cluster_affinity constraints...")
    try:
        with user_db.engine.connect() as conn:
            # Check table existence
            exists = conn.execute(text("SELECT to_regclass('public.cluster_affinity')")).scalar()
            if not exists:
                print("Table cluster_affinity does not exist.")
                return

            # Get constraints
            result = conn.execute(text("""
                SELECT conname, pg_get_constraintdef(oid) 
                FROM pg_constraint 
                WHERE conrelid = 'public.cluster_affinity'::regclass
            """)).fetchall()
            
            print("\nConstraints:")
            for name, definition in result:
                print(f"  {name}: {definition}")
                
            # Check Primary Key columns
            pk = conn.execute(text("""
                SELECT a.attname
                FROM   pg_index i
                JOIN   pg_attribute a ON a.attrelid = i.indrelid
                                     AND a.attnum = ANY(i.indkey)
                WHERE  i.indrelid = 'public.cluster_affinity'::regclass
                AND    i.indisprimary
            """)).fetchall()
            print("\nPrimary Key Columns:", [row[0] for row in pk])

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_constraints()
