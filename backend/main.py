import difflib
import os
import random
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic
from services.quiz_engine import quick_ingest, generate_batch_quiz
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://127.0.0.1:3000"], # Vite default port is 5173
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
# The scopes define what permissions we ask the user for
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]
GOOGLE_CLIENT_SECRETS_FILE = "client_secret.json" # Downloaded from Google Cloud

# In-memory storage for demo (to Use a Database in production!)
user_google_tokens = {}

# --- AUTH SETUP ---
SPOTIFY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

sp_oauth = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope="playlist-read-private"
)

user_token_info = None

# Global store for transfer statuses: { "user_id": {"status": "processing", "error": None} }
transfer_statuses = {}

class PlaylistRequest(BaseModel):
    playlist_id: str
    playlist_name: str

# --- HELPER FUNCTIONS ---
def get_spotify_client():
    if not user_token_info:
        raise HTTPException(status_code=401, detail="Not logged in")
    return spotipy.Spotify(auth=user_token_info['access_token'])

def find_best_match(results, target_title, target_artist):
    """
    Scans top results for a matching artist. 
    Returns the specific match if found, otherwise returns the top result.
    """
    if not results:
        return None

    # Normalize target strings
    t_title = target_title.lower()
    t_artist = target_artist.lower()

    # 1. PRIORITY: Look for the correct artist in the top 5 results
    for item in results[:5]:
        # Extract result details (YT Music returns a list of artists)
        res_title = item['title'].lower()
        res_artists = [a['name'].lower() for a in item['artists']]
        
        # Check if the target artist appears in the result's artist list
        # We use strict containment because "The Beatles" should match "The Beatles"
        artist_match = any(t_artist in a or a in t_artist for a in res_artists)

        # Check title similarity (handles "Remastered", "Radio Edit", etc.)
        # SequenceMatcher ratio > 0.6 is a loose match, > 0.8 is strong.
        title_similarity = difflib.SequenceMatcher(None, t_title, res_title).ratio()

        if artist_match and title_similarity > 0.7:
            return item['videoId']

    # 2. FALLBACK: If no specific artist match found, trust YouTube's top rank
    print(f" ⚠️ No strict match found for '{target_artist}'. Using top result: {results[0]['title']}")
    return results[0]['videoId']


def run_transfer_task(name, tracks):
    """Background task to move songs to YT Music"""
    # Set initial status
    global transfer_statuses
    total_tracks = len(tracks)
    
    # Initialize status
    transfer_statuses["current_user"] = {
        "status": "processing",
        "current_song": "Initializing...",
        "progress": 0,
        "total": total_tracks,
        "error": None
    }
    
    print(f"🚀 Starting Transfer: {name}")
    # 1. Retrieve the user's token (Logic A: From Memory)
    if 'current_user' not in user_google_tokens:
        print("❌ User not logged into YouTube Music")
        return

    # 1. Setup Credentials
    raw_creds = user_google_tokens['current_user']
    oauth_creds = {
        'access_token': raw_creds['token'],  # Mapping 'token' -> 'access_token'
        'refresh_token': raw_creds['refresh_token'],
        'scope': raw_creds['scopes'],
        'token_type': 'Bearer',
        'expires_in': 3600 # Approximate, helps library know when to refresh
    }
    
    try:
        yt = YTMusic(GOOGLE_CLIENT_SECRETS_FILE, oauth_credentials=oauth_creds)
        
        # PROBE: Verify the connection actually works by asking for the user's library
        # This forces an error immediately if the credentials are bad
        yt.get_liked_songs(limit=1)
        
    except Exception as e:
        # This block catches 401 Unauthorized or 400 Bad Request
        print(f"⛔ AUTHENTICATION FAILED")
        transfer_statuses["current_user"] = {"status": "error", "error": "AUTH_EXPIRED"}
        return
    
    try:
        # 2. Create the Playlist first
        pl_id = yt.create_playlist(title=name, description="Transferred by MelodyMind")
        print(f"✅ Playlist Created: {pl_id}")
        
        # 3. Collect Video IDs (Don't add them yet!)
        video_ids_to_add = []
        
        for i, t in enumerate(tracks):
            # Update status for the frontend to see
            transfer_statuses["current_user"].update({
                "current_song": f"{t['name']} by {t['artist']}",
                "progress": i + 1
            })
            
            query = f"{t['name']} by {t['artist']}"
            search = yt.search(query, filter="songs")
            if search:
                best_video_id = find_best_match(search, t['name'], t['artist'])
                if best_video_id:
                    video_ids_to_add.append(best_video_id)
                    print(f"   found: {t['name']}")
                    # yt.add_playlist_items(pl_id, [best_video_id])
                    # print(f"✅ Added {t['name']}")
                else:
                    print(f"❌ Could not find valid match for {t['name']}")  
                         
        # 4. Batch Add (Chunks of 50 to avoid timeouts)
        if video_ids_to_add:
            transfer_statuses["current_user"]["current_song"] = "Finalizing playlist..."
            print(f"📥 Batch adding {len(video_ids_to_add)} songs...")
            
            chunk_size = 50
            for i in range(0, len(video_ids_to_add), chunk_size):
                chunk = video_ids_to_add[i:i + chunk_size]
                yt.add_playlist_items(pl_id, chunk)
                print(f"   ✅ Added batch {i // chunk_size + 1}")   
        
        # 4. Mark Complete
        transfer_statuses["current_user"].update({
            "status": "completed",
            "current_song": "All songs added!",
            "progress": total_tracks
        })
        print(f"🎉 Transfer Completed Successfully!")
        
    except Exception as e:
        print(f"Transfer Failed: {e}")
        transfer_statuses["current_user"] = {
            "status": "error", 
            "error": str(e)
        }

async def prepare_quiz_for_playlist(playlist_id):
    """Common logic: Scrape top songs from playlist -> Generate Quiz"""
    sp = get_spotify_client()
    response = sp.playlist_items(playlist_id, limit=10)
    # select random 5 songs from the playlist
    selected_tracks = random.sample(response['items'], min(5, len(response['items'])))
    
    clean_tracks = []
    for item in selected_tracks:
        if item['track']:
            clean_tracks.append({
                "name": item['track']['name'],
                "artist": item['track']['artists'][0]['name']
            })
        
    # Ingest Top 5 songs to ensure quiz has relevant content
    print(f"⚡ Ingesting {len(clean_tracks[:5])} songs for context...")
    for t in clean_tracks[:5]: 
        quick_ingest(t['artist'], t['name'])
        
    print("🧠 Generating Quiz...")
    quiz_data = generate_batch_quiz(num_questions=5, clean_tracks=clean_tracks)
    
    return quiz_data, clean_tracks

# --- ENDPOINTS ---
@app.get("/login")
def login():
    auth_url = sp_oauth.get_authorize_url()
    return {"url": auth_url}

@app.get("/callback")
def callback(code: str):
    global user_token_info
    user_token_info = sp_oauth.get_access_token(code)
    return {"message": "Login successful. Close this window."}

@app.get("/login_google")
def login_google():
    """Step 1: User clicks 'Connect YouTube Music'"""
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=GOOGLE_SCOPES,
        redirect_uri="http://127.0.0.1:8000/google_callback"
    )
    
    # Generate the Google Login URL
    auth_url, _ = flow.authorization_url(prompt='consent')
    return {"url": auth_url}

@app.get("/google_callback")
def google_callback(code: str):
    """Step 2: Google redirects back here with a code"""
    global user_google_tokens
    
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=GOOGLE_SCOPES,
        redirect_uri="http://127.0.0.1:8000/google_callback"
    )
    
    # Exchange code for tokens (Access + Refresh)
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    # Store these credentials (associated with a session ID in real app)
    # We serialize it to JSON to store simply
    user_google_tokens['current_user'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    # Redirect frontend to dashboard
    # Return a script that closes the popup immediately
    return HTMLResponse("""
    <html>
        <body>
            <h1>Login Successful!</h1>
            <script>
                window.close();
            </script>
        </body>
    </html>
    """)

@app.get("/playlists")
def get_playlists():
    sp = get_spotify_client()
    results = sp.current_user_playlists(limit=30)
    return [{"name": item['name'], "id": item['id'], "image": item['images'][0]['url'] if item['images'] else ""} for item in results['items']]

@app.post("/start_transfer")
async def start_transfer(req: PlaylistRequest, background_tasks: BackgroundTasks):
    """Mode A: Transfer + Quiz"""
    quiz_data, clean_tracks = await prepare_quiz_for_playlist(req.playlist_id)
    background_tasks.add_task(run_transfer_task, req.playlist_name, clean_tracks)
    return {"quiz": quiz_data, "mode": "transfer"}

@app.post("/start_trivia")
async def start_trivia(req: PlaylistRequest):
    """Mode B: Quiz Only (No background task)"""
    quiz_data, _ = await prepare_quiz_for_playlist(req.playlist_id)
    return {"quiz": quiz_data, "mode": "trivia"}

@app.get("/transfer_status")
def get_transfer_status():
    # In a real app, use a unique session ID. For now, we use a global key.
    return transfer_statuses.get("current_user", {"status": "idle"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)     