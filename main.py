
import os
import argparse
import random
import uuid
import numpy as np
import gc
from tqdm import tqdm
from audio_processor import MusicNNExtractor, download_model
from vector_db import get_client, init_collection, upload_batch

EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
import config_manager
# Fallback to combined or cwd
_cfg = config_manager.load_config()
DEFAULT_MUSIC_DIR = _cfg.get("folders", {}).get("russhil") or os.getcwd()

def scan_directory(path):
    files = []
    print(f"Scanning directory: {path} ...")
    for root, _, filenames in os.walk(path):
        for f in filenames:
            if os.path.splitext(f)[1].lower() in EXTENSIONS:
                files.append(os.path.join(root, f))
    return files

def main():
    parser = argparse.ArgumentParser(description="Index music files (Sequential/Fast).")
    parser.add_argument("--data_dir", type=str, default=DEFAULT_MUSIC_DIR)
    parser.add_argument("--sample", type=int, default=100)
    parser.add_argument("--batch_size", type=int, default=32)
    args = parser.parse_args()
    
    # Setup
    print("Initializing...")
    download_model()
    
    print("Loading MusicNN model...")
    # Single instance in main process
    extractor = MusicNNExtractor()
    
    client = get_client()
    init_collection(client)
    
    # Scan
    if not os.path.exists(args.data_dir):
        print("Data dir not found.")
        return

    audio_files = scan_directory(args.data_dir)
    print(f"Found {len(audio_files)} audio files.")
    
    if args.sample > 0 and len(audio_files) > args.sample:
        print(f"Randomly sampling {args.sample} tracks...")
        random.seed(42)
        audio_files = random.sample(audio_files, args.sample)
    
    # Reset Logic
    # We should recreate collection to ensure schema/clean slate
    try:
        client.delete_collection(COLLECTION_NAME)
        print("Deleted old collection.")
    except:
        pass
    init_collection(client)
    
    # Process Sequentially
    print(f"Processing {len(audio_files)} tracks with VIBE SEGMENTATION...")
    
    results_buffer = []
    failed = 0
    total_segments = 0
    
    with tqdm(total=len(audio_files), unit="track", dynamic_ncols=True) as pbar:
        for file_path in audio_files:
            try:
                # Direct extraction - returns dict now
                data = extractor.extract(file_path)
                
                filename = os.path.basename(file_path)
                parent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, filename))
                
                # 1. Add Full/Average Vector (Legacy compatible + General Search)
                results_buffer.append((
                    parent_id, 
                    data['average_vector'], 
                    {"filename": filename, "type": "full"}
                ))
                
                # 2. Add Segments
                for i, seg in enumerate(data['segments']):
                    seg_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{filename}_seg_{i}"))
                    results_buffer.append((
                        seg_id, 
                        seg['vector'], 
                        {
                            "filename": filename, 
                            "type": "segment", 
                            "parent_id": parent_id,
                            "start": seg['start'],
                            "end": seg['end'],
                            "label": seg.get('label', 0)
                        }
                    ))
                    total_segments += 1
                
                # Check Batch
                if len(results_buffer) >= args.batch_size:
                    upload_batch(client, results_buffer)
                    results_buffer = [] 
                    gc.collect() 
                
                pbar.set_postfix(file=filename[:10]+"...", segs=len(data['segments']))
                
            except Exception as e:
                failed += 1
                if failed <= 5: 
                    pbar.write(f"Error {os.path.basename(file_path)}: {e}")
            
            pbar.update(1)

    # Remaining
    if results_buffer:
        upload_batch(client, results_buffer)

    print(f"\nDone! Indexed {len(audio_files) - failed} tracks.")
    print(f"Total Vectors: {len(audio_files)*1 + total_segments} (Songs + Segments)")
    print("Run 'python server.py' to start the upgraded server.")

if __name__ == "__main__":
    main()
