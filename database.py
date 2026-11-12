"""
Music WebApp - Database & Storage Layer
Lightweight, self-healing SQLite database for tracking play history, favorites, and counts.
Includes optional, non-blocking MongoDB synchronization if MONGODB environment variable is set.
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music.db")

def get_db():
    """Connect to SQLite database with row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables if they do not exist."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS played_songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE,
                query TEXT,
                title TEXT,
                artist TEXT,
                thumbnail TEXT,
                duration TEXT,
                play_count INTEGER DEFAULT 1,
                last_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE,
                title TEXT,
                artist TEXT,
                thumbnail TEXT,
                duration TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

def log_song_play(video_id: str, title: str, artist: str = "", thumbnail: str = "", duration: str = "", query: str = ""):
    """Log or increment play count for a song."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO played_songs (video_id, query, title, artist, thumbnail, duration, play_count, last_played)
                VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(video_id) DO UPDATE SET
                    play_count = play_count + 1,
                    last_played = CURRENT_TIMESTAMP
            """, (video_id, query or title, title, artist, thumbnail, duration))
            conn.commit()
    except Exception as e:
        print(f"[!] SQLite log error: {e}")

    # Optional non-blocking MongoDB sync
    mongo_uri = os.getenv("mongodb")
    if mongo_uri:
        try:
            from pymongo import MongoClient
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1500)
            db = client["Sites"]
            log = db["music"]
            log.update_one(
                {"video_id": video_id},
                {"$inc": {"play_count": 1}, "$set": {"title": title, "artist": artist, "last_played": datetime.utcnow()}},
                upsert=True
            )
        except Exception:
            pass

def get_history(limit: int = 24):
    """Retrieve recently played tracks."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT video_id, title, artist, thumbnail, duration, play_count, last_played
                FROM played_songs
                ORDER BY last_played DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"[!] Error reading history: {e}")
        return []

def toggle_favorite(video_id: str, title: str, artist: str = "", thumbnail: str = "", duration: str = ""):
    """Toggle a song in the favorites table."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM favorites WHERE video_id = ?", (video_id,))
            exists = cursor.fetchone()
            if exists:
                cursor.execute("DELETE FROM favorites WHERE video_id = ?", (video_id,))
                conn.commit()
                return False
            else:
                cursor.execute("""
                    INSERT INTO favorites (video_id, title, artist, thumbnail, duration)
                    VALUES (?, ?, ?, ?, ?)
                """, (video_id, title, artist, thumbnail, duration))
                conn.commit()
                return True
    except Exception as e:
        print(f"[!] Error toggling favorite: {e}")
        return False

def get_favorites(limit: int = 50):
    """Retrieve favorite songs."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT video_id, title, artist, thumbnail, duration, added_at
                FROM favorites
                ORDER BY added_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"[!] Error reading favorites: {e}")
        return []
