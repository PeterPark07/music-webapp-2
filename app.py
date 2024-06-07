from flask import Flask, request, render_template, jsonify
import os
from music import download

app = Flask(__name__)

# Directory to save downloaded music files
MUSIC_DIR = 'static/music'

# Ensure the music directory exists
if not os.path.exists(MUSIC_DIR):
    os.makedirs(MUSIC_DIR)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/request_music', methods=['POST'])
def request_music():
    query = request.form['query']
    filename = download_music(query, MUSIC_DIR)
    if filename:
        return jsonify({'url': f'/static/music/{filename}'})
    else:
        return jsonify({'error': 'Unable to download music'}), 500

if __name__ == '__main__':
    app.run(debug=True)
