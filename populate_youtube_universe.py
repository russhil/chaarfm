import os
import sys
import time
import json
import glob
import shutil
import logging
import random
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

# yt-dlp options to reduce HTTP 403 from YouTube (browser-like client + User-Agent)
def _get_ydl_base_opts(outtmpl):
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': outtmpl,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'quiet': True,
        'no_warnings': True,
        # Prefer android client then web; often avoids 403 when default clients are blocked
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        },
    }
    # Optional: use cookies from file to reduce 403 (export from browser and set YTDL_COOKIES path)
    cookies_path = os.getenv('YTDL_COOKIES')
    if cookies_path and os.path.isfile(cookies_path):
        opts['cookiefile'] = cookies_path
    return opts

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

def normalize_track_key(artist, title):
    """Normalize artist and title for comparison (case-insensitive, trimmed)."""
    a = (artist or "").strip().lower()
    t = (title or "").strip().lower()
    return (a, t)

def get_existing_tracks(table_name):
    """
    Returns a set of normalized (artist, title) tuples and youtube_ids that are already in the DB.
    Returns: (existing_tracks_set, existing_youtube_ids_set)
    """
    import psycopg2
    if not DATABASE_URL:
        return set(), set()

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    existing_tracks = set()
    existing_youtube_ids = set()
    try:
        cur.execute(f"SELECT artist, title, youtube_id FROM {table_name}")
        for row in cur.fetchall():
            artist, title, youtube_id = row
            # Normalize and add artist/title combination
            if artist and title:
                normalized = normalize_track_key(artist, title)
                existing_tracks.add(normalized)
            # Add youtube_id if present
            if youtube_id:
                existing_youtube_ids.add(youtube_id.strip().lower())
    except Exception as e:
        logger.error(f"Failed to fetch existing tracks: {e}")
    finally:
        cur.close()
        conn.close()
    return existing_tracks, existing_youtube_ids

def download_temp_youtube(artist, title):
    """
    Downloads audio temporarily and returns (filepath, youtube_id).
    """
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    import yt_dlp
    search_query = f"{artist} {title} lyrics"
    filename_template = f"{TEMP_DIR}/%(id)s.%(ext)s"
    
    ydl_opts = _get_ydl_base_opts(filename_template)
    ydl_opts['default_search'] = 'ytsearch1'
    ydl_opts['noplaylist'] = True
    ydl_opts['match_filter'] = yt_dlp.utils.match_filter_func("duration > 60 & duration < 600")
    
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
    filename_template = f"{TEMP_DIR}/%(id)s.%(ext)s"
    ydl_opts = _get_ydl_base_opts(filename_template)
    
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
    """
    Store entry with duplicate checking. Returns True if stored, False if duplicate or error.
    """
    import psycopg2
    if not DATABASE_URL:
        logger.error("Database URL not set")
        return False

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        # Check for duplicates before inserting
        normalized_key = normalize_track_key(artist, title)
        
        # Check by normalized artist/title
        cur.execute(f"""
            SELECT id FROM {table_name} 
            WHERE LOWER(TRIM(artist)) = %s AND LOWER(TRIM(title)) = %s
        """, (normalized_key[0], normalized_key[1]))
        
        if cur.fetchone():
            logger.info(f"Duplicate detected (artist/title): {artist} - {title}")
            return False
        
        # Check by youtube_id if present
        if youtube_id:
            cur.execute(f"""
                SELECT id FROM {table_name} 
                WHERE youtube_id = %s
            """, (youtube_id,))
            
            if cur.fetchone():
                logger.info(f"Duplicate detected (youtube_id): {youtube_id}")
                return False
        
        # Insert new entry
        query = f"""
        INSERT INTO {table_name} (artist, title, youtube_id, embedding, s3_url)
        VALUES (%s, %s, %s, %s, NULL)
        """
        cur.execute(query, (artist, title, youtube_id, vector))
        conn.commit()
        return True
    except psycopg2.IntegrityError as e:
        # Handle unique constraint violations
        conn.rollback()
        logger.info(f"Duplicate detected (DB constraint): {artist} - {title}")
        return False
    except Exception as e:
        conn.rollback()
        logger.error(f"DB Insert failed: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def fetch_universe(username):
    """
    Builds a music universe of 2000+ tracks from Last.fm by:
    - User top tracks, loved tracks, recent tracks
    - Top artists' discographies (top tracks per artist)
    - Related/similar artists' top tracks
    - Forgotten favorites (top artists/tracks from 1month, 3month, 6month, 12month)
    Returns a list of (artist, title) tuples. Deduplication is done in-memory here;
    DB-level deduplication (skip already-ingested) is done by the caller via get_existing_tracks.
    """
    import pylast
    logger.info(f"Fetching Last.fm universe for {username} (target 2k+ tracks)...")
    network = pylast.LastFMNetwork(api_key=LASTFM_API_KEY, api_secret=LASTFM_API_SECRET)
    user = network.get_user(username)

    # Use dict keyed by (artist, title) to avoid duplicates across all sources
    universe = {}

    def add(artist, title):
        a, t = (artist or "").strip(), (title or "").strip()
        if a and t:
            universe[(a, t)] = True

    try:
        # 1. User top tracks (overall)
        logger.info("  Fetching top tracks (overall)...")
        for item in user.get_top_tracks(period=pylast.PERIOD_OVERALL, limit=100):
            track = item.item
            add(track.artist.name, track.title)
        time.sleep(0.2)

        # 2. Loved tracks
        logger.info("  Fetching loved tracks...")
        for item in user.get_loved_tracks(limit=150):
            track = item.track
            add(track.artist.name, track.title)
        time.sleep(0.2)

        # 3. Recent tracks (for variety)
        logger.info("  Fetching recent tracks...")
        for item in user.get_recent_tracks(limit=150):
            track = item.track
            add(track.artist.name, track.title)
        time.sleep(0.2)

        # 4. Top artists (overall) -> discography: top tracks per artist (target 2k+ total)
        logger.info("  Fetching top artists and their top tracks...")
        top_artists = user.get_top_artists(period=pylast.PERIOD_OVERALL, limit=60)
        for i, item in enumerate(top_artists, 1):
            artist = item.item
            try:
                for t in artist.get_top_tracks(limit=25):
                    track = t.item
                    add(track.artist.name, track.title)
                if i % 10 == 0:
                    logger.info(f"    Top artists progress: {i}/60")
                time.sleep(0.2)
            except Exception as e:
                logger.warning(f"    Error fetching tracks for {artist.name}: {e}")

        # 5. Related artists: similar to top 12 artists -> their top tracks
        logger.info("  Fetching similar artists and their top tracks...")
        top_for_similar = user.get_top_artists(period=pylast.PERIOD_OVERALL, limit=12)
        seen_artists = set()
        for item in top_for_similar:
            main_artist = item.item
            try:
                similar = main_artist.get_similar(limit=10)
                for sim_item in similar:
                    sim_artist = sim_item.item
                    if sim_artist.name in seen_artists:
                        continue
                    seen_artists.add(sim_artist.name)
                    try:
                        for t in sim_artist.get_top_tracks(limit=15):
                            track = t.item
                            add(track.artist.name, track.title)
                        time.sleep(0.2)
                    except Exception:
                        pass
                time.sleep(0.2)
            except Exception as e:
                logger.warning(f"    Error getting similar to {main_artist.name}: {e}")

        # 6. Forgotten favorites: top artists from other time periods
        for period_name, period_val in [
            ("1month", pylast.PERIOD_1MONTH),
            ("3month", pylast.PERIOD_3MONTHS),
            ("6month", pylast.PERIOD_6MONTHS),
            ("12month", pylast.PERIOD_12MONTHS),
        ]:
            logger.info(f"  Fetching top artists ({period_name}) and their tracks...")
            try:
                period_artists = user.get_top_artists(period=period_val, limit=25)
                for item in period_artists:
                    artist = item.item
                    try:
                        for t in artist.get_top_tracks(limit=15):
                            track = t.item
                            add(track.artist.name, track.title)
                        time.sleep(0.2)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"    Error fetching {period_name} artists: {e}")

    except Exception as e:
        logger.error(f"Last.fm fetch failed: {e}")

    unique_tracks = list(universe.keys())
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
    existing_tracks_set, existing_youtube_ids = get_existing_tracks(table_name)
    
    # Filter using normalized comparison
    targets = []
    for artist, title in universe_tracks:
        normalized = normalize_track_key(artist, title)
        if normalized not in existing_tracks_set:
            targets.append((artist, title))
    
    logger.info(f"Universe: {len(universe_tracks)} tracks")
    logger.info(f"Existing: {len(existing_tracks_set)} tracks")
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

def prepare_random_track_batch(tracks, requested_count=None, use_max=False):
    """
    Deduplicate and randomize track list, then slice to requested size.
    """
    seen = set()
    deduped = []
    for artist, title in tracks:
        key = ((artist or "").strip(), (title or "").strip())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(key)

    if not deduped:
        return []

    random.shuffle(deduped)

    if use_max or requested_count is None or requested_count >= len(deduped):
        return deduped

    return deduped[:requested_count]

def ensure_test_collection():
    """
    Convenience helper for dedicated test ingest table.
    """
    return ensure_schema("test")

if __name__ == "__main__":
    main()