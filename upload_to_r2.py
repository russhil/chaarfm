
import os
import sys
import boto3
from pathlib import Path
from botocore.exceptions import NoCredentialsError
from botocore.config import Config
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

import config_manager

# Configuration
EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}

def get_s3_client():
    """Get S3 client from Env Vars or Input."""
    endpoint = os.environ.get("S3_ENDPOINT")
    bucket = os.environ.get("S3_BUCKET")
    access_key = os.environ.get("S3_ACCESS_KEY")
    secret_key = os.environ.get("S3_SECRET_KEY")
    
    if not (endpoint and bucket and access_key and secret_key):
        print("⚠️  R2/S3 Environment Variables Missing (S3_ENDPOINT, S3_BUCKET, ...)")
        print("Please export them or create a .env file.")
        sys.exit(1)
        
    client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )
    return client, bucket

def upload_file(args):
    """Upload single file."""
    client, bucket, local_path, s3_key = args
    try:
        # Check existence (head object)
        try:
            client.head_object(Bucket=bucket, Key=s3_key)
            return "exists"
        except:
            pass
            
        # Upload
        client.upload_file(local_path, bucket, s3_key)
        return "uploaded"
    except Exception as e:
        return f"error: {e}"

def main():
    print("☁️  ChaarFM R2 Stream Synchronizer")
    print("==================================")
    
    try:
        client, bucket = get_s3_client()
        print(f"✅ Connected to Bucket: {bucket}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    # Load local folders
    config = config_manager.load_config()
    folders = config.get("folders", {})
    
    if not folders:
        print("⚠️ No folders configured. Run Control Panel -> Configure.")
        return
        
    # Scan files
    tasks = []
    print("\n📂 Scanning local files...")
    for source, folder_path in folders.items():
        p = Path(folder_path)
        if not p.exists(): continue
        
        for f in p.rglob("*"):
            if f.suffix.lower() in EXTENSIONS:
                # Flat key structure: filename only (as assumed by server streaming)
                # To prevent collisions, we ideally prefer source/filename, but server assumes filename.
                # We will check if we can use source/filename later.
                # For now, let's stick to filename to match server_user.py logic.
                key = f.name
                tasks.append((client, bucket, str(f), key))
                
    print(f"  Found {len(tasks)} files.")
    
    # Process
    print("\n🚀 Syncing to Cloud...")
    uploaded = 0
    exists = 0
    errors = 0
    
    # Use ThreadPool for network IO
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(tqdm(executor.map(upload_file, tasks), total=len(tasks), unit="file"))
        
    for r in results:
        if r == "uploaded": uploaded += 1
        elif r == "exists": exists += 1
        else: errors += 1
        
    print("\n" + "="*40)
    print(f"🏁 Sync Complete")
    print(f"   Uploaded: {uploaded}")
    print(f"   Skipped:  {exists} (Already on Cloud)")
    print(f"   Errors:   {errors}")
    print("="*40)

if __name__ == "__main__":
    main()
