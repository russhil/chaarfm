
print("Starting debug script...")
import user_db
print("Imported user_db")
from user_recommender import UserRecommender
print("Imported UserRecommender")

def debug_recommender():
    print("Initializing UserRecommender for 'vectors_russhil'...")
    try:
        # Create recommender directly to test loading
        rec = UserRecommender("russhil", collection_name="vectors_russhil")
        
        print(f"\nTrack Map Size: {len(rec.track_map)}")
        
        if len(rec.track_map) == 0:
            print("CRITICAL: Track map is empty!")
            return
            
        print("Sample Track:")
        first_id = list(rec.track_map.keys())[0]
        print(rec.track_map[first_id])
        
        print("\nTesting get_next_track()...")
        track, reason = rec.get_next_track()
        print(f"Result: {track['filename'] if track else 'None'} | Reason: {reason}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_recommender()
