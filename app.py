import os
from flask import Flask, request, render_template, jsonify, send_from_directory
from helper import search_youtube, get_current_time, save_cookie_to_file
import yt_dlp
import random
from database import log  # Assuming log is your MongoDB collection


app = Flask(__name__)



# Directory to save downloaded music files
MUSIC_DIR = './m'

# Ensure the music directory exists
if not os.path.exists(MUSIC_DIR):
    os.makedirs(MUSIC_DIR)

# List to store previously played songs (persistent across restarts)
played_songs = [doc['query'] for doc in log.find({}, {'query': 1})]  # Initialize from MongoDB


cookie_file = save_cookie_to_file()




def download_music(query, download_dir):
    try:
        # Search for the video URL and title
        search_results = search_youtube(query, max_results=1)
        url = search_results[0][0]
        title = search_results[1][0]

        # Define custom user-agent to bypass possible restrictions
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"


        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'cookiefile': cookie_file,  # Use the temporary cookie file
            'nocheckcertificate': True,
            'user-agent': user_agent,  # Custom user-agent
        }

        # Download the music using yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)
            length = info_dict.get('duration', 0)  # Duration in seconds

        # Log the song in MongoDB
        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        log_entry = log.find_one({'query': query})
        if log_entry:
            # Increment the play count if the entry exists
            log.update_one(
                {'_id': log_entry['_id']},
                {'$inc': {'play_count': 1}, '$set': {'last_played': get_current_time()}}
            )
        else:
            # Insert a new log entry
            log.insert_one({
                'query': query,
                'title': title,
                'length': length,
                'user_ip': user_ip,
                'play_count': 1,
                'first_played': get_current_time(),
                'last_played': get_current_time(),
            })

        # Add the song to the list of played songs
        if query not in played_songs:
            played_songs.append(query)

        return filename

    except Exception as e:
        print(f"Error downloading music: {e}")
        return None


def clear_music_directory(directory):
    # Clear all files in the specified directory
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            


@app.route('/')
def index():
    global played_songs

    # Shuffle the played_songs list for random order
    random.shuffle(played_songs)
    return render_template('index.html', played_songs=played_songs)


@app.route('/request_music', methods=['POST'])
def request_music():
    query = request.form['query']

    # Clear existing files in MUSIC_DIR before downloading new music
    clear_music_directory(MUSIC_DIR)

    try:
        filename = download_music(query, MUSIC_DIR)
        
        if filename:
            # Return the relative path to the file for direct access
            relative_path = os.path.relpath(filename, start=os.getcwd())
            return jsonify({'url': f'/{relative_path}'}), 200
        else:
            return jsonify({'error': 'Unable to download music. Please try again.'}), 500
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred. Please try again later.'}), 500


@app.route('/m/<path:filename>', methods=['GET'])
def serve_music(filename):
    return send_from_directory(MUSIC_DIR, filename)


if __name__ == '__main__':
    app.run(debug=True)
