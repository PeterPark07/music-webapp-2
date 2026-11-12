# AeroMusic WebApp 🎵⚡

A high-performance, zero-download streaming web music player built with **Flask**, **YouTube Music API (`ytmusicapi`)**, and **yt-dlp**.

Plays any song on YouTube Music with high-resolution album artwork, persistent play history, and an audio streaming relay with HTTP Range header support.

---

## 🚀 Key Architectural Improvements Over Legacy WebApp

| Feature | Legacy `music-webapp-2` | **Revived AeroMusic** |
| :--- | :--- | :--- |
| **Streaming Mechanism** | ❌ Download full MP3 to server disk first (10s lag) | ✅ **Zero-Download Audio Streaming Relay** (Starts in < 500ms) |
| **YouTube 403 CDN Bypass** | ❌ Direct CDN URLs fail with 403 Forbidden | ✅ **Server Relay with Range Headers & Mobile Profiles** (Android/iOS) |
| **Search Engine** | ❌ Broken `youtube-search-python` (Crashes) | ✅ **Official `ytmusicapi`** (Rich metadata, High-res Album Art, Artist Names) |
| **Database Reliability** | ❌ Hard crash on startup without MongoDB | ✅ **Self-Healing Local SQLite** + Optional MongoDB sync |
| **Concurrency** | ❌ Deleted all files in directory on every request | ✅ **Concurrent-safe, zero server disk bloat** |
| **UI & Player** | ❌ Raw HTML with ugly `<audio>` element | ✅ **Modern Spotify/Apple Music-style Dark Mode Player** |

---

## 🛠️ Project Structure

```
music-webapp-2/
├── app.py                # Flask application with /stream audio relay endpoint
├── helper.py             # ytmusicapi search & direct audio stream resolver
├── database.py           # Self-healing SQLite store for history & favorites
├── templates/
│   └── index.html        # Modern responsive music player interface
├── requirements.txt      # Clean dependencies
├── Procfile              # Render.com start command
├── .gitignore            # Clean git tracking
└── README.md             # Documentation
```

---

## 💻 Local Testing

Run with the virtual environment:
```powershell
.\.venv\Scripts\python.exe app.py
```
Open **`http://localhost:5000`** in your browser.

---

## ☁️ Deployment on Render.com

1. Push your repository to GitHub.
2. In Render, create a new **Web Service**.
3. Set the following:
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
   * **Plan**: `Free`
