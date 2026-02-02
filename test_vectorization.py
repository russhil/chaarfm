import os
# Force legacy Keras (Keras 2) behavior for compatibility with musicnn
os.environ["TF_USE_LEGACY_KERAS"] = "1"

from music_pipeline.downloader import download_song
from music_pipeline.vectorizer import vectorize_audio

def test_single_song():
    print("--- Testing Vectorization on Single Song ---")
    
    # Use a known song
    artist = "Seedhe Maut"
    title = "Nanchaku"
    
    # We can reuse the file if it exists
    filepath = f"debug_downloads/{artist} - {title}.mp3"
    if not os.path.exists(filepath):
        print(f"Downloading {artist} - {title}...")
        filepath = download_song(artist, title, output_dir="debug_downloads")
    
    if not filepath:
        print("Download failed!")
        return
        
    print(f"File: {filepath}")
    
    print("Vectorizing...")
    try:
        vector = vectorize_audio(filepath)
        if vector:
            print(f"Vectorization successful! Vector length: {len(vector)}")
            print(f"Sample: {vector[:5]}")
        else:
            print("Vectorization returned None.")
    except Exception as e:
        print(f"Vectorization crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_single_song()
