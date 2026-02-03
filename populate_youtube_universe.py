import os
import sys
import time
import json
import glob
import shutil
import logging
import numpy as np

# Add project root to path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Lazy load configuration to allow worker script to run without DB creds
DATABASE_URL = None
LASTFM_API_KEY = "f3d0dfdb4bb8c0fbe7e41400c6ff979e" 
LASTFM_API_SECRET = "072547e52c6e1f3b890b9af5a10103e8"

try:
    from music_pipeline.config import DATABASE_URL as CFG_DB_URL
    DATABASE_URL = CFG_DB_URL
except ImportError:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")

try:
    from music_pipeline.vectorizer import vectorize_audio
except ImportError:
    # If vectorizer missing, we might be in a minimal env, but worker needs it
    pass

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("youtube_ingestion.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
TEMP_DIR = "temp_ingest"

def ensure_schema(username):
    """
    Ensures the database table exists and has the youtube_id column.
    """
    import psycopg2
    table_name = f"vectors_{username}"
    safe_table_name = "".join(c for c in table_name if c.isalnum() or c == '_')
    
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # Check if table exists
        cur.execute(f"SELECT to_regclass('{safe_table_name}');")
        if not cur.fetchone()[0]:
            logger.info(f"Creating table {safe_table_name}...")
            cur.execute(f"CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {safe_table_name} (
                id SERIAL PRIMARY KEY,
                artist TEXT,
                title TEXT,
                s3_url TEXT,
                youtube_id TEXT,
                embedding vector(200),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
        else:
            # Check for youtube_id column
            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{safe_table_name}' AND column_name='youtube_id';")
            if not cur.fetchone():
                logger.info(f"Adding youtube_id column to {safe_table_name}...")
                cur.execute(f"ALTER TABLE {safe_table_name} ADD COLUMN youtube_id TEXT;")
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Schema check failed: {e}")
        raise e
    finally:
        cur.close()
        conn.close()
        
    return safe_table_name

def get_existing_tracks(table_name):
    """
    Returns a set of (artist, title) tuples that are already in the DB.
    """
    import psycopg2
    if not DATABASE_URL:
        return set()

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    existing = set()
    try:
        cur.execute(f"SELECT artist, title FROM {table_name}")
        for row in cur.fetchall():
            existing.add((row[0], row[1]))
    except Exception as e:
        logger.error(f"Failed to fetch existing tracks: {e}")
    finally:
        cur.close()
        conn.close()
    return existing

def download_temp_youtube(artist, title):
    """
    Downloads audio temporarily and returns (filepath, youtube_id).
    """
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    import yt_dlp
    search_query = f"{artist} {title} lyrics"
    filename_template = f"{TEMP_DIR}/%(id)s.%(ext)s"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128', # Lower quality is fine for vectorization
        }],
        'default_search': 'ytsearch1',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        # Avoid long mixes
        'match_filter': yt_dlp.utils.match_filter_func("duration > 60 & duration < 600"), 
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=True)
            if 'entries' in info:
                info = info['entries'][0]
                
            youtube_id = info['id']
            # Find the file
            files = glob.glob(f"{TEMP_DIR}/{youtube_id}.*")
            if files:
                return files[0], youtube_id
                
    except Exception as e:
        logger.warning(f"Download failed for {artist} - {title}: {e}")
        
    return None, None

def download_temp_youtube_by_url(url):
    """
    Downloads audio from a specific YouTube URL.
    Returns (filepath, youtube_id, metadata).
    """
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    import yt_dlp
    # Extract ID first to set filename
    # We can rely on yt-dlp to give us the ID
    filename_template = f"{TEMP_DIR}/%(id)s.%(ext)s"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            youtube_id = info['id']
            metadata = {
                'artist': info.get('artist') or info.get('uploader'),
                'title': info.get('title')
            }
            
            # Find the file
            files = glob.glob(f"{TEMP_DIR}/{youtube_id}.*")
            if files:
                return files[0], youtube_id, metadata
                
    except Exception as e:
        logger.warning(f"Download failed for {url}: {e}")
        
    return None, None, None

def store_entry(table_name, artist, title, youtube_id, vector):
    import psycopg2
    if not DATABASE_URL:
        logger.error("Database URL not set")
        return False

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        query = f"""
        INSERT INTO {table_name} (artist, title, youtube_id, embedding, s3_url)
        VALUES (%s, %s, %s, %s, NULL)
        """
        cur.execute(query, (artist, title, youtube_id, vector))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"DB Insert failed: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def fetch_universe(username):
    """
    Uses pylast to fetch top tracks from Last.fm
    """
    import pylast
    logger.info(f"Fetching Last.fm universe for {username}...")
    network = pylast.LastFMNetwork(api_key=LASTFM_API_KEY, api_secret=LASTFM_API_SECRET)
    user = network.get_user(username)
    
    tracks_to_process = []
    
    try:
        # Get Top Tracks
        top = user.get_top_tracks(period=pylast.PERIOD_OVERALL, limit=100)
        for item in top:
            tracks_to_process.append((item.item.artist.name, item.item.title))
            
        # Get Loved Tracks
        loved = user.get_loved_tracks(limit=100)
        for item in loved:
            tracks_to_process.append((item.track.artist.name, item.track.title))
            
        # Get Recent Tracks (for variety)
        recent = user.get_recent_tracks(limit=50)
        for item in recent:
            tracks_to_process.append((item.track.artist.name, item.track.title))
            
    except Exception as e:
        logger.error(f"Last.fm fetch failed: {e}")
        
    # Deduplicate list
    unique_tracks = list(set(tracks_to_process))
    logger.info(f"Found {len(unique_tracks)} unique tracks from Last.fm")
    return unique_tracks

def main():
    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = input("Enter Last.fm Username: ").strip()
        
    if not username:
        print("Username required.")
        return

    logger.info(f"Starting YouTube Ingestion for {username}")
    
    # 1. Prepare DB
    try:
        table_name = ensure_schema(username)
    except Exception as e:
        logger.error("Could not setup database. Exiting.")
        return
        
    # 2. Get Target List
    universe_tracks = fetch_universe(username)
    existing_tracks = get_existing_tracks(table_name)
    
    # Filter
    targets = [t for t in universe_tracks if t not in existing_tracks]
    logger.info(f"New tracks to process: {len(targets)}")
    
    if not targets:
        print("No new tracks to ingest.")
        return

    # 3. Process Loop
    success_count = 0
    fail_count = 0
    
    print(f"Starting processing of {len(targets)} tracks...")
    
    for i, (artist, title) in enumerate(targets):
        print(f"[{i+1}/{len(targets)}] Processing: {artist} - {title}")
        
        # Download
        filepath, youtube_id = download_temp_youtube(artist, title)
        if not filepath:
            logger.warning(f"  Failed to find/download: {artist} - {title}")
            fail_count += 1
            continue
            
        # Vectorize
        vector = vectorize_audio(filepath)
        
        # Cleanup immediately to save space
        try:
            os.remove(filepath)
        except:
            pass
            
        if not vector:
            logger.warning(f"  Failed to vectorize: {artist} - {title}")
            fail_count += 1
            continue
            
        # Store
        if store_entry(table_name, artist, title, youtube_id, vector):
            logger.info(f"  Success: {artist} - {title} ({youtube_id})")
            success_count += 1
        else:
            fail_count += 1
            
        # Rate limit to be nice to YouTube
        time.sleep(2)
        
    # Final cleanup
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
        
    print(f"\nIngestion Complete.")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")

if __name__ == "__main__":
    main()