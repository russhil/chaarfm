import argparse
from .universe import extract_universe
from .downloader import download_song
from .tagger import tag_mp3
from .vectorizer import vectorize_audio
from .storage import upload_to_r2, store_vector_db
import os
import shutil

def process_user(username, limit_per_artist=5):
    print(f"--- Starting Pipeline for User: {username} ---")
    
    # 1. Extract Universe
    tracks = extract_universe(username, limit_per_artist=limit_per_artist)
    print(f"Universe extracted. {len(tracks)} songs to process.")
    
    # 2. Process each track
    processed_count = 0
    
    for i, track in enumerate(tracks, 1):
        artist = track['artist']
        title = track['title']
        print(f"\nProcessing [{i}/{len(tracks)}]: {artist} - {title}")
        
        # Download
        filepath = download_song(artist, title)
        if not filepath:
            print("  Skipping (Download failed)")
            continue
            
        # Tag
        tag_mp3(filepath, artist, title)
        
        # Vectorize
        vector = vectorize_audio(filepath)
        if not vector:
            print("  Skipping (Vectorization failed)")
            # Optional: Delete file if vectorization fails?
            continue
            
        # Upload to R2
        object_name = os.path.basename(filepath)
        s3_url = upload_to_r2(filepath, object_name)
        if not s3_url:
            print("  Skipping (Upload failed)")
            continue
            
        # Store in DB
        success = store_vector_db(username, track, vector, s3_url)
        
        if success:
            processed_count += 1
            # Cleanup local file to save space
            try:
                os.remove(filepath)
                # print("  Local file cleaned up.")
            except:
                pass
        else:
            print("  Skipping (DB storage failed)")

    print(f"\n--- Pipeline Complete ---")
    print(f"Successfully processed {processed_count}/{len(tracks)} songs.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Last.fm to Vector DB Pipeline")
    parser.add_argument("username", help="Last.fm Username")
    parser.add_argument("--limit", type=int, default=5, help="Limit songs per artist")
    
    args = parser.parse_args()
    
    process_user(args.username, limit_per_artist=args.limit)
