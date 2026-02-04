"""
Genre-based universe extraction and quality filtering.

Provides functions to fetch tracks by genre from YouTube (or other sources),
with quality filtering and diversity bucketing to ensure a mix of famous and
underrated tracks.
"""

import os
import sys
import re
import logging
import psycopg2
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from music_pipeline.config import DATABASE_URL as CFG_DB_URL
    DATABASE_URL = CFG_DB_URL
except ImportError:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")

logger = logging.getLogger(__name__)

# Default quality configuration
DEFAULT_QUALITY_CONFIG = {
    "min_views": 1000,
    "min_likes": 10,
    "min_like_ratio": 0.001,  # 0.1% like ratio
    "min_duration": 60,
    "max_duration": 600,
    "diversity_top_pct": 0.2,  # 20% from top bucket
    "diversity_mid_pct": 0.6,  # 60% from middle
    "diversity_bottom_pct": 0.2,  # 20% from bottom
    "post_download_min_size_mb": 0.5,
    "post_download_max_size_mb": 50.0
}


def genre_to_slug(genre: str) -> str:
    """Convert genre name to a safe table slug (e.g., 'Lo-Fi Hip Hop' -> 'lofi_hip_hop')."""
    slug = genre.lower().strip()
    # Replace spaces and special chars with underscores
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    # Remove leading/trailing underscores
    slug = slug.strip('_')
    return slug or "genre"


def ensure_genre_schema(genre_slug: str) -> str:
    """
    Ensures the database table exists for a genre collection.
    Returns the table name (e.g., 'vectors_genre_lofi_hip_hop').
    """
    table_name = f"vectors_genre_{genre_slug}"
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


def get_existing_for_genre(table_name: str) -> Set[Tuple[str, Optional[str]]]:
    """
    Returns a set of (youtube_id, (artist, title)) tuples that are already in the genre table.
    If youtube_id is None, the tuple is (None, (artist, title)).
    """
    if not DATABASE_URL:
        return set()

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    existing = set()
    try:
        cur.execute(f"SELECT youtube_id, artist, title FROM {table_name}")
        for row in cur.fetchall():
            youtube_id, artist, title = row
            if youtube_id:
                existing.add((youtube_id, None))
            if artist and title:
                existing.add((None, (artist, title)))
    except Exception as e:
        logger.error(f"Failed to fetch existing tracks: {e}")
    finally:
        cur.close()
        conn.close()
    return existing


def fetch_genre_universe_youtube(genre: str, limit: Optional[int] = None, quality_config: Optional[Dict] = None) -> List[Dict]:
    """
    Fetch tracks for a genre from YouTube using playlists or search.
    
    Uses yt-dlp to extract video metadata (views, likes, duration) without downloading,
    then filters by quality thresholds and applies diversity bucketing.
    
    Returns list of dicts with 'youtube_url' and optional metadata.
    """
    import yt_dlp
    
    config = quality_config or DEFAULT_QUALITY_CONFIG.copy()
    
    # Search query for genre playlists or mixes
    search_queries = [
        f"{genre} music playlist",
        f"{genre} mix",
        f"best {genre} songs"
    ]
    
    all_candidates = []
    
    # Try to find playlists or search results
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,  # Don't download, just get metadata
        'default_search': 'ytsearch',  # Search mode
        'noplaylist': False,  # Allow playlists
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Try first search query
            search_query = search_queries[0]
            logger.info(f"Searching YouTube for: {search_query}")
            
            # Extract info (this returns search results or playlist entries)
            info = ydl.extract_info(search_query, download=False)
            
            entries = []
            if 'entries' in info:
                entries = [e for e in info['entries'] if e]
            elif info:
                entries = [info]
            
            # Now extract full metadata for each entry (requires another call per video)
            for entry in entries[:500]:  # Limit initial fetch to avoid too many requests
                video_id = entry.get('id') or entry.get('url', '').split('watch?v=')[-1].split('&')[0]
                if not video_id:
                    continue
                
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                # Extract full metadata (views, likes, etc.)
                try:
                    video_info = ydl.extract_info(video_url, download=False)
                    view_count = video_info.get('view_count', 0) or 0
                    like_count = video_info.get('like_count', 0) or 0
                    duration = video_info.get('duration', 0) or 0
                    title = video_info.get('title', '')
                    artist = video_info.get('artist') or video_info.get('uploader', '')
                    
                    # Calculate like ratio
                    like_ratio = (like_count / view_count) if view_count > 0 else 0
                    
                    all_candidates.append({
                        'youtube_url': video_url,
                        'youtube_id': video_id,
                        'view_count': view_count,
                        'like_count': like_count,
                        'like_ratio': like_ratio,
                        'duration': duration,
                        'title': title,
                        'artist': artist
                    })
                except Exception as e:
                    logger.debug(f"Failed to extract metadata for {video_id}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"Failed to search YouTube for genre {genre}: {e}")
        return []
    
    if not all_candidates:
        logger.warning(f"No candidates found for genre: {genre}")
        return []
    
    # Apply quality filters
    filtered = []
    for candidate in all_candidates:
        if (candidate['view_count'] >= config['min_views'] and
            candidate['like_count'] >= config['min_likes'] and
            candidate['like_ratio'] >= config['min_like_ratio'] and
            config['min_duration'] <= candidate['duration'] <= config['max_duration']):
            filtered.append(candidate)
    
    logger.info(f"Quality filtering: {len(all_candidates)} -> {len(filtered)} candidates")
    
    if not filtered:
        return []
    
    # Diversity bucketing: sort by views, divide into buckets, sample proportionally
    filtered.sort(key=lambda x: x['view_count'], reverse=True)
    total = len(filtered)
    
    top_end = int(total * config['diversity_top_pct'])
    mid_end = int(total * (config['diversity_top_pct'] + config['diversity_mid_pct']))
    
    top_bucket = filtered[:top_end]
    mid_bucket = filtered[top_end:mid_end]
    bottom_bucket = filtered[mid_end:]
    
    # Sample proportionally
    result = []
    if limit:
        top_count = int(limit * config['diversity_top_pct'])
        mid_count = int(limit * config['diversity_mid_pct'])
        bottom_count = limit - top_count - mid_count
        
        # Sample from each bucket
        import random
        result.extend(random.sample(top_bucket, min(top_count, len(top_bucket))))
        result.extend(random.sample(mid_bucket, min(mid_count, len(mid_bucket))))
        result.extend(random.sample(bottom_bucket, min(bottom_count, len(bottom_bucket))))
    else:
        result = filtered
    
    # Return simplified format (just youtube_url for worker)
    return [{'youtube_url': item['youtube_url']} for item in result]


def fetch_genre_universe(genre: str, limit: Optional[int] = None, quality_config: Optional[Dict] = None) -> List[Dict]:
    """
    Main entry point for fetching genre universe.
    
    Currently uses YouTube as the source. Can be extended to support file-based
    or Spotify sources.
    
    Returns list of dicts with 'youtube_url' (or 'artist'/'title' for other sources).
    """
    return fetch_genre_universe_youtube(genre, limit, quality_config)
