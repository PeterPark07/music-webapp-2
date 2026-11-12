"""
Music WebApp - Helper Module
High-accuracy YouTube Music search and direct audio stream resolver.
Bypasses CDN copyright/IP blocks using mobile client profiles (Android/iOS).
"""

import time
import yt_dlp
from ytmusicapi import YTMusic

# In-memory stream URL cache to avoid redundant extraction latency (TTL: 2 hours)
_STREAM_CACHE = {}
_CACHE_TTL = 7200

# Initialize YouTube Music client (stateless, never requires login)
try:
    _ytmusic = YTMusic()
except Exception:
    _ytmusic = None

def search_music(query: str, limit: int = 15):
    """
    Search YouTube Music for high-fidelity tracks with rich metadata:
    Title, Artist, Album, Duration, and high-res Thumbnail.
    """
    results = []
    query = (query or "").strip()
    if not query:
        return results

    # Strategy 1: YouTube Music API (Fastest, highest metadata quality)
    if _ytmusic:
        try:
            raw_results = _ytmusic.search(query, filter="songs", limit=limit)
            for item in raw_results:
                vid = item.get("videoId")
                if not vid:
                    continue
                artists = ", ".join([a.get("name", "") for a in item.get("artists", []) if a.get("name")])
                album = item.get("album", {}).get("name", "") if item.get("album") else ""
                thumbnails = item.get("thumbnails", [])
                thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
                # Upgrade thumbnail resolution from 60x60/120x120 to high quality
                if thumb_url and "=w" in thumb_url:
                    thumb_url = thumb_url.split("=")[0] + "=w500-h500-l90-rj"

                results.append({
                    "video_id": vid,
                    "title": item.get("title", "Unknown Title"),
                    "artist": artists or "Unknown Artist",
                    "album": album,
                    "duration": item.get("duration", "--:--"),
                    "thumbnail": thumb_url
                })
            if results:
                return results
        except Exception as e:
            print(f"[!] ytmusicapi search fallback: {e}")

    # Strategy 2: Fallback to yt-dlp search
    try:
        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_data = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            for entry in search_data.get("entries", []):
                vid = entry.get("id")
                if not vid:
                    continue
                dur_sec = entry.get("duration", 0)
                dur_str = f"{int(dur_sec // 60)}:{int(dur_sec % 60):02d}" if dur_sec else "--:--"
                results.append({
                    "video_id": vid,
                    "title": entry.get("title", "Unknown Title"),
                    "artist": entry.get("uploader", "YouTube"),
                    "album": "",
                    "duration": dur_str,
                    "thumbnail": entry.get("thumbnail", f"https://img.youtube.com/vi/{vid}/hqdefault.jpg")
                })
    except Exception as e:
        print(f"[!] yt-dlp fallback search error: {e}")

    return results

def get_audio_stream_info(video_id: str):
    """
    Extracts the direct YouTube CDN audio stream URL and necessary request headers.
    Uses Android/iOS player clients to bypass YouTube's IP/PoToken copyright restrictions.
    """
    now = time.time()
    # Check cache
    if video_id in _STREAM_CACHE:
        cached = _STREAM_CACHE[video_id]
        if now - cached["timestamp"] < _CACHE_TTL:
            return cached["url"], cached["headers"]

    url = f"https://www.youtube.com/watch?v={video_id}"

    # Use Android & iOS mobile client profiles to bypass SABR / PoToken / n-sig restrictions
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web_creator"]
            }
        },
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info.get("url")
            headers = info.get("http_headers", {})

            if audio_url:
                _STREAM_CACHE[video_id] = {
                    "url": audio_url,
                    "headers": headers,
                    "timestamp": now
                }
                return audio_url, headers
    except Exception as e:
        print(f"[!] Stream extraction error for {video_id}: {e}")

    return None, {}
