from youtubesearchpython import VideosSearch
import pytz
from datetime import datetime
import tempfile
import os


def get_current_time():
    return datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")

def save_cookie_to_file():
    raw_cookie_value = os.getenv('cookies')    
    temp_cookie_file = tempfile.NamedTemporaryFile(delete=False)
    temp_cookie_file.write(raw_cookie_value.encode())
    temp_cookie_file.close()
    return temp_cookie_file.name

def search_youtube(query, max_results=1):
    videos_search = VideosSearch(query, limit=max_results)
    results = videos_search.result()
    video_urls = [result['link'] for result in results['result']]
    titles = [result['title'] for result in results['result']]
    return video_urls, titles
