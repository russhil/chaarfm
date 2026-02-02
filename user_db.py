"""
User Database - Supabase (Postgres) storage for user profiles and taste data.

Philosophy: Every decision must be data-justified. No random unless zero data.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, List
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Supabase Connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback/Error
    print("WARNING: DATABASE_URL not found in .env, persistent storage may fail.")
    DATABASE_URL = "sqlite:///users_backup.db" 

# Create Engine
# Intelligent pooling config
connect_args = {"connect_timeout": 10}
pool_config = {
    "pool_size": 10,
    "max_overflow": 20
}

# Check for NullPool need
from sqlalchemy import pool
if DATABASE_URL and ":6543" in DATABASE_URL:
    print("Detected Transaction Pooler (6543). Disabling client-side pooling.")
    pool_config = {"poolclass": pool.NullPool}

engine = create_engine(DATABASE_URL, **pool_config, connect_args=connect_args)

def hash_password(password: str) -> str:
    """Simple password hashing."""
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    """Initialize database schema in Supabase if not exists."""
    print(f"Initializing User DB at {DATABASE_URL.split('@')[-1]}")
    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                password_hash TEXT,
                created_at TEXT,
                total_sessions INTEGER DEFAULT 0,
                is_guest INTEGER DEFAULT 0,
                email TEXT,
                google_id TEXT,
                picture TEXT,
                name TEXT
            )
        '''))
        
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS cluster_affinity (
                user_id TEXT,
                cluster_id INTEGER,
                collection_name TEXT,
                positive_signals INTEGER DEFAULT 0,
                total_listen_seconds REAL DEFAULT 0,
                track_count INTEGER DEFAULT 0,
                session_rejections INTEGER DEFAULT 0,
                last_positive_date TEXT,
                PRIMARY KEY (user_id, cluster_id, collection_name)
            )
        '''))
        
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS cluster_centroids (
                user_id TEXT,
                cluster_id INTEGER,
                collection_name TEXT,
                centroid TEXT,
                sample_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, cluster_id, collection_name)
            )
        '''))
        
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS user_logs (
                id SERIAL PRIMARY KEY,
                timestamp TEXT,
                session_id TEXT,
                user_id TEXT,
                track_id TEXT,
                filename TEXT,
                action TEXT,
                duration REAL,
                justification TEXT,
                details TEXT
            )
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS cluster_negatives (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                cluster_id INTEGER,
                collection_name TEXT,
                vector TEXT,
                track_id TEXT,
                created_at TEXT
            )
        '''))
        
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS waitlist (
                id SERIAL PRIMARY KEY,
                email TEXT,
                created_at TEXT
            )
        '''))
        
        # Seed users
        res = conn.execute(text("SELECT id FROM users WHERE id = 'russhil'")).fetchone()
        if not res:
            conn.execute(text('''
                INSERT INTO users (id, password_hash, created_at, is_guest)
                VALUES (:id, :pw, :date, 0)
            '''), {"id": "russhil", "pw": hash_password('10811'), "date": datetime.now().isoformat()})
            print("Created user: russhil")
            
        res = conn.execute(text("SELECT id FROM users WHERE id = 'guest'")).fetchone()
        if not res:
            conn.execute(text('''
                INSERT INTO users (id, password_hash, created_at, is_guest)
                VALUES (:id, :pw, :date, 1)
            '''), {"id": "guest", "pw": "", "date": datetime.now().isoformat()})
            print("Created user: guest")
        
        conn.commit()

def get_available_collections() -> List[str]:
    """Get list of available vector collections from vecs schema and public vectors_*."""
    try:
        with engine.connect() as conn:
            # Query information_schema for tables in 'vecs' schema
            vecs_tables = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'vecs'
            """)).fetchall()
            
            # Query for public tables starting with 'vectors_' or 'music_' that might be collections
            public_tables = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND (table_name LIKE 'vectors_%' OR table_name LIKE 'music_%')
            """)).fetchall()
            
            collections = [row[0] for row in vecs_tables] + [row[0] for row in public_tables]
            return list(set(collections)) # Deduplicate if needed
            
    except Exception as e:
        print(f"Error fetching collections: {e}")
        return ["music_averaged"] # Fallback

def get_admin_stats() -> Dict:
    """Get aggregated statistics for the admin dashboard."""
    stats = {
        "global": {
            "total_plays": 0,
            "avg_listen_time": 0,
            "skip_rate": 0
        },
        "users": {}
    }
    
    with engine.connect() as conn:
        # Global Stats
        res = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                AVG(duration) as avg_dur,
                SUM(CASE WHEN action='skip' OR duration < 20 THEN 1 ELSE 0 END) as skips
            FROM user_logs
            WHERE action IN ('play', 'feedback', 'skip')
        """)).mappings().fetchone()
        
        if res and res['total'] > 0:
            stats['global']['total_plays'] = res['total']
            stats['global']['avg_listen_time'] = res['avg_dur'] or 0
            stats['global']['skip_rate'] = (res['skips'] or 0) / res['total']
            
        # User Stats
        users_res = conn.execute(text("""
            SELECT 
                user_id,
                COUNT(*) as total,
                AVG(duration) as avg_dur,
                SUM(CASE WHEN action='skip' OR duration < 20 THEN 1 ELSE 0 END) as skips
            FROM user_logs
            WHERE action IN ('play', 'feedback', 'skip') AND user_id IS NOT NULL
            GROUP BY user_id
        """)).mappings().fetchall()
        
        for row in users_res:
            uid = row['user_id']
            total = row['total']
            if total > 0:
                stats['users'][uid] = {
                    "total_plays": total,
                    "avg_listen_time": row['avg_dur'] or 0,
                    "skip_rate": (row['skips'] or 0) / total,
                    "engagement_growth": 0 # Placeholder
                }
                
    return stats

def get_logs(limit: int = 100, user_id: Optional[str] = None) -> List[Dict]:
    """Get recent logs for real-time view."""
    logs = []
    with engine.connect() as conn:
        if user_id:
            res = conn.execute(text("""
                SELECT * FROM user_logs 
                WHERE user_id = :uid
                ORDER BY timestamp DESC 
                LIMIT :lim
            """), {"lim": limit, "uid": user_id}).mappings().fetchall()
        else:
            res = conn.execute(text("""
                SELECT * FROM user_logs 
                ORDER BY timestamp DESC 
                LIMIT :lim
            """), {"lim": limit}).mappings().fetchall()
        
        for row in res:
            logs.append(dict(row))
            
    return logs

def get_history_stats(user_id: str) -> Dict:
    """Get history statistics for a specific user."""
    stats = {
        "total_plays": 0,
        "avg_listen_time": 0,
        "skip_rate": 0,
        "recent_tracks": []
    }
    
    with engine.connect() as conn:
        res = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                AVG(duration) as avg_dur,
                SUM(CASE WHEN action='skip' OR duration < 20 THEN 1 ELSE 0 END) as skips
            FROM user_logs
            WHERE user_id = :uid AND action IN ('play', 'feedback', 'skip')
        """), {"uid": user_id}).mappings().fetchone()
        
        if res and res['total'] > 0:
            stats['total_plays'] = res['total']
            stats['avg_listen_time'] = res['avg_dur'] or 0
            stats['skip_rate'] = (res['skips'] or 0) / res['total']
            
        recent = conn.execute(text("""
            SELECT filename, action, duration, timestamp 
            FROM user_logs
            WHERE user_id = :uid AND action IN ('play', 'feedback')
            ORDER BY timestamp DESC
            LIMIT 10
        """), {"uid": user_id}).mappings().fetchall()
        
        for row in recent:
            stats['recent_tracks'].append(dict(row))
            
    return stats

def clear_user_history(user_id: str, hours: Optional[int] = None) -> Dict:
    """Clear user history logs and reset affinity."""
    if user_id == 'guest': return {"status": "error", "message": "Cannot clear guest"}
    
    with engine.connect() as conn:
        if hours:
            # Clear logs older than X hours? Or clear logs FROM last X hours?
            # Usually "clear history for last 24h" means delete last 24h.
            # But the requirement implies "reset session".
            # Let's assume it means delete recent history to "undo" bad vibes.
            
            # Calculate cutoff time
            cutoff = (datetime.now() - datetime.timedelta(hours=hours)).isoformat()
            
            conn.execute(text("""
                DELETE FROM user_logs 
                WHERE user_id = :uid AND timestamp > :cutoff
            """), {"uid": user_id, "cutoff": cutoff})
            
            # We should also probably decrement cluster affinity signals, but that's complex.
            # For now, just logging clearing is a good start. 
            # Ideally we'd re-calculate affinity from remaining logs, but that's expensive.
            # A simple approach: Just delete the logs so they don't show up in analysis.
            
            return {"status": "ok", "message": f"Cleared history for last {hours} hours"}
            
        else:
            # Clear ALL history
            conn.execute(text("DELETE FROM user_logs WHERE user_id = :uid"), {"uid": user_id})
            conn.execute(text("DELETE FROM cluster_affinity WHERE user_id = :uid"), {"uid": user_id})
            conn.execute(text("DELETE FROM cluster_centroids WHERE user_id = :uid"), {"uid": user_id})
            conn.execute(text("DELETE FROM cluster_negatives WHERE user_id = :uid"), {"uid": user_id})
            
            conn.commit()
            return {"status": "ok", "message": "Full history reset"}
    print("Database schema verified.")

def verify_user(user_id: str, password: str) -> Optional[Dict]:
    if user_id == 'guest': return {"id": "guest", "is_guest": True}
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id}).mappings().fetchone()
        if row and row['password_hash'] == hash_password(password):
            return dict(row)
    return None

def get_or_create_google_user(user_info: Dict) -> Dict:
    """Get existing user by google_id or create new one."""
    email = user_info.get("email")
    google_id = user_info.get("sub")
    picture = user_info.get("picture")
    name = user_info.get("name")
    
    # Use email as the primary ID for now, or fallback to google_id if no email
    # Ideally we'd use a UUID and link them, but to keep compat with existing "russhil" string IDs:
    user_id = email if email else f"google_{google_id}"
    
    with engine.connect() as conn:
        # Check if user exists by ID (email) OR by google_id
        row = conn.execute(text("""
            SELECT * FROM users 
            WHERE id = :uid OR google_id = :gid
        """), {"uid": user_id, "gid": google_id}).mappings().fetchone()
        
        if row:
            # Update info if needed
            if not row['google_id'] or row.get('name') != name:
                conn.execute(text("""
                    UPDATE users SET google_id = :gid, picture = :pic, name = :name 
                    WHERE id = :uid
                """), {"gid": google_id, "pic": picture, "name": name, "uid": row['id']})
                conn.commit()
                
                # Refetch to get updated data
                row = conn.execute(text("SELECT * FROM users WHERE id = :uid"), {"uid": row['id']}).mappings().fetchone()
            return dict(row)
        else:
            # Create new user
            now = datetime.now().isoformat()
            conn.execute(text("""
                INSERT INTO users (id, email, google_id, picture, name, created_at, is_guest)
                VALUES (:uid, :email, :gid, :pic, :name, :date, 0)
            """), {
                "uid": user_id,
                "email": email,
                "gid": google_id,
                "pic": picture,
                "name": name,
                "date": now
            })
            conn.commit()
            return {
                "id": user_id,
                "email": email,
                "google_id": google_id,
                "picture": picture,
                "name": name,
                "created_at": now,
                "is_guest": False
            }

def get_user_profile(user_id: str, collection_name: str = "music_averaged") -> Dict:
    if user_id == 'guest': return {"user_id": "guest", "is_guest": True, "clusters": {}}
    
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT cluster_id, positive_signals, total_listen_seconds, 
                   track_count, session_rejections, last_positive_date
            FROM cluster_affinity
            WHERE user_id = :uid AND collection_name = :col
        '''), {"uid": user_id, "col": collection_name}).mappings().fetchall()
        
    clusters = {}
    for row in result:
        cid = row['cluster_id']
        tc = row['track_count'] or 1
        clusters[cid] = {
            'positive_signals': row['positive_signals'],
            'total_listen_seconds': row['total_listen_seconds'],
            'track_count': tc,
            'avg_listen_time': row['total_listen_seconds'] / tc,
            'session_rejections': row['session_rejections'],
            'last_positive_date': row['last_positive_date']
        }
        
    return {"user_id": user_id, "is_guest": False, "clusters": clusters}

def get_cluster_centroid(user_id: str, cluster_id: int, collection_name: str = "music_averaged") -> Optional[np.ndarray]:
    if user_id == 'guest': return None
    with engine.connect() as conn:
        row = conn.execute(text('''
            SELECT centroid FROM cluster_centroids
            WHERE user_id = :uid AND cluster_id = :cid AND collection_name = :col
        '''), {"uid": user_id, "cid": cluster_id, "col": collection_name}).mappings().fetchone()
    
    if row and row['centroid']:
        try: return np.array(json.loads(row['centroid']))
        except: return None
    return None

def update_cluster_affinity(user_id: str, cluster_id: int, listen_seconds: float, is_positive: bool, collection_name: str = "music_averaged"):
    if user_id == 'guest': return
    with engine.connect() as conn:
        conn.execute(text('''
            INSERT INTO cluster_affinity (user_id, cluster_id, collection_name, positive_signals, total_listen_seconds, track_count, last_positive_date)
            VALUES (:uid, :cid, :col, :is_pos, :sec, 1, :date)
            ON CONFLICT(user_id, cluster_id, collection_name) DO UPDATE SET
                positive_signals = cluster_affinity.positive_signals + :is_pos,
                total_listen_seconds = cluster_affinity.total_listen_seconds + :sec,
                track_count = cluster_affinity.track_count + 1,
                last_positive_date = CASE WHEN :is_pos > 0 THEN :date ELSE cluster_affinity.last_positive_date END
        '''), {
            "uid": user_id, "cid": cluster_id, "col": collection_name,
            "is_pos": 1 if is_positive else 0,
            "sec": listen_seconds,
            "date": datetime.now().isoformat()
        })
        conn.commit()

def update_cluster_centroid(user_id: str, cluster_id: int, new_vector: np.ndarray, weight: float, collection_name: str = "music_averaged"):
    if user_id == 'guest': return
    current = get_cluster_centroid(user_id, cluster_id, collection_name)
    sample_count = 1
    updated = new_vector
    
    if current is not None:
        with engine.connect() as conn:
            row = conn.execute(text('''
                SELECT sample_count FROM cluster_centroids
                WHERE user_id = :uid AND cluster_id = :cid AND collection_name = :col
            '''), {"uid": user_id, "cid": cluster_id, "col": collection_name}).mappings().fetchone()
            if row: sample_count = row['sample_count'] + 1
        alpha = max(0.3, weight)
        updated = (1 - alpha) * current + alpha * new_vector
        
    with engine.connect() as conn:
        conn.execute(text('''
            INSERT INTO cluster_centroids (user_id, cluster_id, collection_name, centroid, sample_count)
            VALUES (:uid, :cid, :col, :vec, :cnt)
            ON CONFLICT(user_id, cluster_id, collection_name) DO UPDATE SET
                centroid = :vec, sample_count = :cnt
        '''), {
            "uid": user_id, "cid": cluster_id, "col": collection_name,
            "vec": json.dumps(updated.tolist()), "cnt": sample_count
        })
        conn.commit()

def increment_session_rejection(user_id: str, cluster_id: int, collection_name: str = "music_averaged"):
    if user_id == 'guest': return
    with engine.connect() as conn:
        conn.execute(text('''
            UPDATE cluster_affinity 
            SET session_rejections = session_rejections + 1
            WHERE user_id = :uid AND cluster_id = :cid AND collection_name = :col
        '''), {"uid": user_id, "cid": cluster_id, "col": collection_name})
        conn.commit()

def add_cluster_negative(user_id: str, cluster_id: int, vector: List[float], track_id: str, collection_name: str = "music_averaged"):
    """Record a negative signal (skip) for a specific cluster."""
    if user_id == 'guest': return
    
    # Limit number of negatives per cluster to avoid bloat (e.g., keep last 50)
    # But for now, just insert. We can clean up later.
    
    with engine.connect() as conn:
        conn.execute(text('''
            INSERT INTO cluster_negatives (user_id, cluster_id, collection_name, vector, track_id, created_at)
            VALUES (:uid, :cid, :col, :vec, :tid, :date)
        '''), {
            "uid": user_id, "cid": cluster_id, "col": collection_name,
            "vec": json.dumps(vector),
            "tid": track_id,
            "date": datetime.now().isoformat()
        })
        conn.commit()

def get_cluster_negatives(user_id: str, cluster_id: int, collection_name: str = "music_averaged", limit: int = 50) -> List[np.ndarray]:
    """Retrieve negative vectors for a specific cluster."""
    if user_id == 'guest': return []
    
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT vector FROM cluster_negatives
            WHERE user_id = :uid AND cluster_id = :cid AND collection_name = :col
            ORDER BY created_at DESC
            LIMIT :lim
        '''), {"uid": user_id, "cid": cluster_id, "col": collection_name, "lim": limit}).mappings().fetchall()
        
    vecs = []
    for row in result:
        try:
            vecs.append(np.array(json.loads(row['vector'])))
        except: pass
    return vecs

def log_interaction_db(session_id: str, user_id: str, track_id: str, filename: str, action: str, duration: float, justification: str = "", details: str = ""):
    """Log user interaction to the database."""
    if user_id == 'guest': return
    
    with engine.connect() as conn:
        conn.execute(text('''
            INSERT INTO user_logs (timestamp, session_id, user_id, track_id, filename, action, duration, justification, details)
            VALUES (:ts, :sid, :uid, :tid, :fname, :act, :dur, :just, :det)
        '''), {
            "ts": datetime.now().isoformat(),
            "sid": session_id,
            "uid": user_id,
            "tid": track_id,
            "fname": filename,
            "act": action,
            "dur": duration,
            "just": justification,
            "det": details
        })
        conn.commit()

def add_waitlist_email(email: str):
    """Add email to waitlist."""
    with engine.connect() as conn:
        conn.execute(text('''
            INSERT INTO waitlist (email, created_at)
            VALUES (:email, :date)
        '''), {"email": email, "date": datetime.now().isoformat()})
        conn.commit()
