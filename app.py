from dotenv import load_dotenv

load_dotenv()

import os
import requests
from flask import Flask, session, redirect, url_for, render_template, request
import spotipy
from setuptools.package_index import user_agent
from spotipy.oauth2 import SpotifyOAuth


from flask import Flask, render_template, request

app = Flask(__name__)


@app.route('/')
def index():
    # renders the main page
    return render_template('index.html')


# Explicitly define '/result' route with GET and POST
@app.route('/result', methods=['POST', 'GET'])
def result():
    if request.method == 'POST':
        city = request.form['city']
        mood = request.form['mood']
        # Call functions to fetch weather and Spotify playlist
        # Assume you have a function get_playlist(city, mood)
        playlist, weather, temp, error = get_playlist(city, mood)

        # Render the result template passing necessary context
        return render_template('result.html', playlist=playlist, city=city, mood=mood, weather=weather, temp=temp,
                               error=error)
    else:
        # Redirect users manually accessing by GET back to homepage
        return render_template('index.html')
# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure key for session management

# Load API keys from environment variables
SPOTIFY_CLIENT_ID = os.environ.get('b64cc448fc474e15a0e1148dc3debe69')
SPOTIFY_CLIENT_SECRET = os.environ.get('2b56310a143e430ea833d0f97a0acf39')
OPENWEATHER_API_KEY = os.environ.get('4c2785dfdad5e3ef91c5ebf685ea7a38')

# Configure Spotify OAuth
sp_oauth = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri="http://localhost:5000/callback",
    scope="playlist-modify-private user-read-private"
)

# Function to get Spotify client with token handling
def get_spotify_client():
    if 'token_info' not in session:
        return None
    token_info = session['token_info']
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info
    return spotipy.Spotify(auth=token_info['access_token'])

# Function to fetch weather data
def get_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['weather'][0]['main']
    return None

# Mappings for weather and mood to Spotify audio features (energy and valence)
weather_mapping = {
    "Clear": {"energy": 0.8, "valence": 0.8},
    "Clouds": {"energy": 0.5, "valence": 0.5},
    "Rain": {"energy": 0.3, "valence": 0.3},
    "Thunderstorm": {"energy": 0.7, "valence": 0.4},
    "Snow": {"energy": 0.4, "valence": 0.4},
    "Drizzle": {"energy": 0.3, "valence": 0.3},
    "Mist": {"energy": 0.4, "valence": 0.4}
}

mood_mapping = {
    "happy": {"energy": 0.7, "valence": 0.9},
    "sad": {"energy": 0.3, "valence": 0.2},
    "energetic": {"energy": 0.9, "valence": 0.6},
    "relaxed": {"energy": 0.2, "valence": 0.5}
}

# Routes
@app.route('/')
def index():
    sp = get_spotify_client()
    return render_template('index.html', authenticated=sp is not None)

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect(url_for('index'))

@app.route('/generate_playlist', methods=['POST'])
def generate_playlist():
    sp = get_spotify_client()
    if sp is None:
        return redirect(url_for('login'))

    # Get form data
    city = request.form['city']
    mood = request.form['mood']
    weather = get_weather(city)

    if weather is None:
        return "Invalid city or weather API error", 400

    # Map weather and mood to energy and valence
    w_energy, w_valence = weather_mapping.get(weather, {"energy": 0.5, "valence": 0.5}).values()
    m_energy, m_valence = mood_mapping[mood].values()
    target_energy = (w_energy + m_energy) / 2
    target_valence = (w_valence + m_valence) / 2

    # Fetch recommendations from Spotify
    recommendations = sp.recommendations(
        seed_genres=["pop", "rock", "electronic"],
        limit=20,
        target_energy=target_energy,
        target_valence=target_valence
    )
    track_uris = [track['uri'] for track in recommendations['tracks']]

    # Get Spotify user ID
    user_id = sp.current_user()['id']

    # Check for existing playlist or create a new one
    playlists = sp.current_user_playlists()
    playlist_id = None
    playlist_url = None
    for playlist in playlists['items']:
        if playlist['name'] == "Weather and Mood Playlist":
            playlist_id = playlist['id']
            playlist_url = playlist['external_urls']['spotify']
            break

    if playlist_id:
        sp.playlist_replace_items(playlist_id, track_uris)
    else:
        new_playlist = sp.user_playlist_create(
            user_id,
            "Weather and Mood Playlist",
            public=False,
            description="Generated by WeatherMoodPlaylist app"
        )
        playlist_id = new_playlist['id']
        playlist_url = new_playlist['external_urls']['spotify']
        sp.playlist_add_items(playlist_id, track_uris)

    return render_template('result.html', playlist_url=playlist_url)

if __name__ == '__main__':
    app.run(debug=True)