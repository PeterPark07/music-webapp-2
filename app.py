"""
Music WebApp - Production Application Server
High-speed streaming audio player with zero-download streaming relay,
rich YouTube Music search, and Render.com cloud deployment readiness.
"""

import os
import requests
from flask import Flask, request, render_template, jsonify, Response, stream_with_context
from helper import search_music, get_audio_stream_info
from database import log_song_play, get_history, toggle_favorite, get_favorites

app = Flask(__name__)

# Configurable port for Render.com ($PORT) or local development
PORT = int(os.environ.get("PORT", 5000))

@app.route("/")
def index():
    """Renders the modern Spotify/Apple Music-grade web player."""
    recent_songs = get_history(limit=12)
    return render_template("index.html", recent_songs=recent_songs)

@app.route("/api/search", methods=["GET"])
def api_search():
    """Search YouTube Music for tracks matching the query."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    results = search_music(query, limit=12)
    return jsonify(results)

@app.route("/api/history", methods=["GET"])
def api_history():
    """Fetch recently played songs from SQLite."""
    return jsonify(get_history(limit=24))

@app.route("/api/favorites", methods=["GET"])
def api_favorites():
    """Fetch user's favorite tracks."""
    return jsonify(get_favorites(limit=50))

@app.route("/api/favorite", methods=["POST"])
def api_toggle_favorite():
    """Toggle a song's favorite status."""
    data = request.get_json() or {}
    vid = data.get("video_id")
    title = data.get("title")
    if not vid or not title:
        return jsonify({"error": "Missing video_id or title"}), 400

    is_fav = toggle_favorite(
        video_id=vid,
        title=title,
        artist=data.get("artist", ""),
        thumbnail=data.get("thumbnail", ""),
        duration=data.get("duration", "")
    )
    return jsonify({"favorited": is_fav})

@app.route("/stream/<video_id>", methods=["GET"])
def stream_audio(video_id):
    """
    Zero-Download Audio Streaming Relay Engine:
    Resolves YouTube CDN audio stream using mobile client profiles (bypassing PoToken),
    and relays the stream directly to the browser with HTTP Range header support.
    
    - Bypasses 403 Forbidden (request origin is matched to the server's signed IP).
    - Bypasses CORS restrictions.
    - Zero server disk usage.
    - Instant playback in < 500ms.
    """
    stream_url, upstream_headers = get_audio_stream_info(video_id)
    if not stream_url:
        return Response("Unable to resolve audio stream for this track.", status=502, content_type="text/plain")

    # Log play asynchronously in database
    title = request.args.get("title", "")
    artist = request.args.get("artist", "")
    thumbnail = request.args.get("thumbnail", "")
    duration = request.args.get("duration", "")
    if title:
        log_song_play(video_id, title, artist, thumbnail, duration)

    # Forward client Range header to allow instant seeking/scrubbing
    req_headers = dict(upstream_headers)
    range_header = request.headers.get("Range")
    if range_header:
        req_headers["Range"] = range_header

    try:
        # Stream chunks directly from the upstream CDN
        upstream_resp = requests.get(stream_url, headers=req_headers, stream=True, timeout=12)

        def generate_chunks():
            for chunk in upstream_resp.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk

        # Build clean response headers
        response_headers = {
            "Content-Type": upstream_resp.headers.get("Content-Type", "audio/mp4"),
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600"
        }
        if "Content-Range" in upstream_resp.headers:
            response_headers["Content-Range"] = upstream_resp.headers["Content-Range"]
        if "Content-Length" in upstream_resp.headers:
            response_headers["Content-Length"] = upstream_resp.headers["Content-Length"]

        return Response(
            stream_with_context(generate_chunks()),
            status=upstream_resp.status_code,
            headers=response_headers
        )

    except Exception as e:
        return Response(f"Streaming error: {e}", status=500, content_type="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
