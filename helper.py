"""
Music WebApp - Helper Module
High-accuracy YouTube Music search and multi-tier audio stream resolver.
Bypasses datacenter "Sign in to confirm you're not a bot" blocks on Render/AWS via:
1. yt-dlp with TV Embedded & MWeb client profiles (never challenge with PoToken)
2. Optional cookie support (YOUTUBE_COOKIES / cookies environment variable)
3. Piped API federated stream fallback
4. Invidious API federated stream fallback
"""

import time
import os
import tempfile
import requests
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

# Public federated Piped and Invidious API instances for datacenter IP failover
PIPED_INSTANCES = [
    "https://api.piped.privacydev.net",
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.tokhmi.xyz",
    "https://api.piped.projectsegfau.lt"
]

INVIDIOUS_INSTANCES = [
    "https://inv.tux.pizza",
    "https://invidious.nerdvpn.de",
    "https://invidious.flokinet.to",
    "https://vid.puffyan.us"
]

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

def _fetch_from_piped(video_id: str):
    """Fallback: Resolve direct audio stream URL via Piped API."""
    for base in PIPED_INSTANCES:
        try:
            resp = requests.get(f"{base}/streams/{video_id}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                audio_streams = data.get("audioStreams", [])
                if audio_streams:
                    # Pick highest bitrate stream
                    best = max(audio_streams, key=lambda s: s.get("bitrate", 0))
                    url = best.get("url")
                    if url:
                        print(f"[+] Successfully resolved stream via Piped instance: {base}")
                        return url, {"User-Agent": "Mozilla/5.0"}
        except Exception:
            continue
    return None, {}

def _fetch_from_invidious(video_id: str):
    """Fallback: Resolve direct audio stream URL via Invidious API."""
    for base in INVIDIOUS_INSTANCES:
        try:
            resp = requests.get(f"{base}/api/v1/videos/{video_id}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                formats = data.get("adaptiveFormats", [])
                audio_formats = [f for f in formats if (f.get("type") or "").startswith("audio/")]
                if audio_formats:
                    best = max(audio_formats, key=lambda s: int(s.get("bitrate", 0) or 0))
                    url = best.get("url")
                    if url:
                        print(f"[+] Successfully resolved stream via Invidious instance: {base}")
                        return url, {"User-Agent": "Mozilla/5.0"}
        except Exception:
            continue
    return None, {}

def get_audio_stream_info(video_id: str):
    """
    Extracts the direct YouTube CDN audio stream URL and necessary request headers.
    Bypasses datacenter 'Sign in to confirm you're not a bot' blocks via multi-tier failover.
    """
    now = time.time()
    # Check cache
    if video_id in _STREAM_CACHE:
        cached = _STREAM_CACHE[video_id]
        if now - cached["timestamp"] < _CACHE_TTL:
            return cached["url"], cached["headers"]

    # --- Tier 1: yt-dlp with TV Embedded & MWeb client profiles ---
    # TV Embedded (Smart TVs) and MWeb do not have SABR / PoToken / Bot challenge walls
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "extractor_args": {
            "youtube": {
                # tv_embedded and tv bypass bot verification on AWS/Render datacenters
                "player_client": ["tv_embedded", "mweb", "android_music", "ios"],
                "player_skip": ["webpage", "configs"]
            }
        },
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    # Optional Cookie Injection from environment variable if configured on Render
    cookie_str = os.getenv("YOUTUBE_COOKIES") or os.getenv("cookies")
    cookie_file_path = None
    if cookie_str:
        try:
            tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt")
            tmp.write(cookie_str)
            tmp.close()
            cookie_file_path = tmp.name
            ydl_opts["cookiefile"] = cookie_file_path
        except Exception:
            pass

    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
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
        print(f"[!] Tier 1 yt-dlp extraction failed: {e}")
    finally:
        if cookie_file_path and os.path.exists(cookie_file_path):
            try:
                os.remove(cookie_file_path)
            except Exception:
                pass

    # --- Tier 2: Piped Federated Stream API ---
    print("[*] Engaging Tier 2 failover: Piped Stream API...")
    url, headers = _fetch_from_piped(video_id)
    if url:
        _STREAM_CACHE[video_id] = {"url": url, "headers": headers, "timestamp": now}
        return url, headers

    # --- Tier 3: Invidious Federated Stream API ---
    print("[*] Engaging Tier 3 failover: Invidious Stream API...")
    url, headers = _fetch_from_invidious(video_id)
    if url:
        _STREAM_CACHE[video_id] = {"url": url, "headers": headers, "timestamp": now}
        return url, headers

    print(f"[!] All extraction tiers exhausted for {video_id}")
    return None, {}
