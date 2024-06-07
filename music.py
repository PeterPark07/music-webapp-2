from youtubesearchpython import VideosSearch
import yt_dlp

def search_youtube(query, max_results=1):
    videos_search = VideosSearch(query, limit=max_results)
    results = videos_search.result()
    video_urls = [result['link'] for result in results['result']]
    return video_urls

def download(query):

    url = search_youtube(query, max_results=1)[0]
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '%(title)s.%(ext)s',
        'noplaylist': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
