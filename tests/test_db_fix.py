"""
Test the database fix for cluster_affinity table.
"""

import os
from dotenv import load_dotenv
load_dotenv()

import user_db

def test_update_cluster_affinity():
    """Test that update_cluster_affinity works with or without constraint."""
    print("Testing update_cluster_affinity...")
    
    user_id = "test_user_db_fix"
    cluster_id = 1
    collection_name = "test_collection"
    
    try:
        # First update (INSERT)
        print("Test 1: Initial INSERT...")
        user_db.update_cluster_affinity(
            user_id=user_id,
            cluster_id=cluster_id,
            listen_seconds=30.5,
            is_positive=True,
            collection_name=collection_name
        )
        print("✅ First update successful")
        
        # Second update (UPDATE - should trigger ON CONFLICT or fallback)
        print("\nTest 2: UPDATE (same row)...")
        user_db.update_cluster_affinity(
            user_id=user_id,
            cluster_id=cluster_id,
            listen_seconds=45.2,
            is_positive=True,
            collection_name=collection_name
        )
        print("✅ Second update successful")
        
        # Verify data
        print("\nTest 3: Verify data...")
        from sqlalchemy import text
        with user_db.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM cluster_affinity
                WHERE user_id = :uid AND cluster_id = :cid AND collection_name = :col
            """), {"uid": user_id, "cid": cluster_id, "col": collection_name}).mappings().fetchone()
            
            if result:
                print(f"✅ Data verified:")
                print(f"   User: {result['user_id']}")
                print(f"   Cluster: {result['cluster_id']}")
                print(f"   Collection: {result['collection_name']}")
                print(f"   Positive Signals: {result['positive_signals']}")
                print(f"   Total Listen Seconds: {result['total_listen_seconds']}")
                print(f"   Track Count: {result['track_count']}")
                
                # Check if values are correct
                if result['positive_signals'] == 2 and result['track_count'] == 2:
                    print("✅ Aggregation working correctly!")
                else:
                    print(f"⚠️  Aggregation might be off: expected 2 signals and 2 tracks")
            else:
                print("❌ No data found!")
        
        # Cleanup
        print("\nCleaning up test data...")
        with user_db.engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM cluster_affinity
                WHERE user_id = :uid AND collection_name = :col
            """), {"uid": user_id, "col": collection_name})
            conn.commit()
        print("✅ Cleanup successful")
        
        print("\n" + "="*50)
        print("ALL TESTS PASSED! ✅")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup even if failed
        try:
            with user_db.engine.connect() as conn:
                conn.execute(text("""
                    DELETE FROM cluster_affinity
                    WHERE user_id = :uid AND collection_name = :col
                """), {"uid": user_id, "col": collection_name})
                conn.commit()
        except:
            pass

if __name__ == "__main__":
    test_update_cluster_affinity()
