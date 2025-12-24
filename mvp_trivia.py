import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from google import genai
from collections import Counter
import random

# --- CONFIGURATION (Load these from a .env file in production) ---
os.environ['SPOTIPY_CLIENT_ID'] = ''
os.environ['SPOTIPY_CLIENT_SECRET'] = ''
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://127.0.0.1:8000/callback'
os.environ['GEMINI_API_KEY'] = ''

# Initialize Clients
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope="playlist-read-private"))
# client = OpenAI(api_key=OPENAI_API_KEY)
client = genai.Client()


def get_playlist_artists(playlist_id, limit=50):
    """
    Fetches tracks from a Spotify playlist and returns a list of the most 
    common artists to ensure the trivia is relevant to the 'vibe'.
    """
    print(f"🎵 Fetching tracks from playlist {playlist_id}...")
    results = sp.playlist_items(playlist_id, limit=limit)
    artists = []

    for item in results['items']:
        track = item['track']
        if track:
            # Get the main artist for each track
            artists.append(track['artists'][0]['name'])

    # Get top 10 most frequent artists in this playlist
    top_artists = [artist for artist, count in Counter(artists).most_common(10)]
    return top_artists


def generate_trivia(artists):
    """
    Uses an LLM to generate trivia questions based on the artists found.
    """
    artist_list_str = ", ".join(artists)
    print(f"🤖 Generating trivia for: {artist_list_str}...")

    prompt = (
        f"Create 3 engaging multiple-choice trivia questions based on these musical artists: {artist_list_str}. "
        "Format the output strictly as:\n"
        "Q: [Question]\n"
        "A) [Option 1]\n"
        "B) [Option 2]\n"
        "C) [Option 3]\n"
        "D) [Option 4]\n"
        "Answer: [Correct Option]\n"
    )

    # response = client.chat.completions.create(
    #     model="gpt-3.5-turbo",  # Swap for 'llama3' via Ollama for local dev
    #     messages=[
    #         {"role": "system", "content": "You are a music trivia master."},
    #         {"role": "user", "content": prompt}
    #     ],
    #     temperature=0.7
    # )

    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
    )

    #return response.choices[0].message.content
    return response.text


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # 1. Ask user for a Playlist Link
    # Example format: https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
    pl_link = input("Enter Spotify Playlist URL: ")
    playlist_id = pl_link.split("/")[-1].split("?")[0]

    # 2. Extract Data
    try:
        top_artists = get_playlist_artists(playlist_id)

        # 3. Generate Content
        trivia = generate_trivia(top_artists)

        print("\n" + "="*30)
        print("   🎶 YOUR PLAYLIST TRIVIA 🎶")
        print("="*30 + "\n")
        print(trivia)

    except Exception as e:
        print(f"Error: {e}")
