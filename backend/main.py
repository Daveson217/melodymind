import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic
from services.quiz_engine import quick_ingest, generate_batch_quiz

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"], # Vite default port is 5173
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AUTH SETUP ---
SPOTIFY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"

sp_oauth = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope="playlist-read-private"
)

user_token_info = None

class PlaylistRequest(BaseModel):
    playlist_id: str
    playlist_name: str

# --- HELPER FUNCTIONS ---
def get_spotify_client():
    if not user_token_info:
        raise HTTPException(status_code=401, detail="Not logged in")
    return spotipy.Spotify(auth=user_token_info['access_token'])

def run_transfer_task(name, tracks):
    """Background task to move songs to YT Music"""
    print(f"🚀 Starting Transfer: {name}")
    try:
        if os.path.exists("oauth.json"):
            yt = YTMusic("oauth.json")
            pl_id = yt.create_playlist(title=name, description="Transferred by MelodyMind")
            for t in tracks:
                query = f"{t['name']} by {t['artist']}"
                search = yt.search(query, filter="songs")
                if search:
                    yt.add_playlist_items(pl_id, [search[0]['videoId']])
                    print(f"✅ Added {t['name']}")
        else:
            print("❌ No oauth.json found. Skipping actual YTM transfer.")
    except Exception as e:
        print(f"Transfer Failed: {e}")

async def prepare_quiz_for_playlist(playlist_id):
    """Common logic: Scrape top songs from playlist -> Generate Quiz"""
    sp = get_spotify_client()
    tracks = sp.playlist_items(playlist_id, limit=10)
    
    clean_tracks = []
    for item in tracks['items']:
        if item['track']:
            clean_tracks.append({
                "name": item['track']['name'],
                "artist": item['track']['artists'][0]['name']
            })
            
    # Ingest Top 3 songs to ensure quiz has relevant content
    print(f"⚡ Ingesting {len(clean_tracks[:3])} songs for context...")
    for t in clean_tracks[:3]: 
        quick_ingest(t['artist'], t['name'])
        
    print("🧠 Generating Quiz...")
    quiz_data = generate_batch_quiz(num_questions=5)
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

@app.get("/playlists")
def get_playlists():
    sp = get_spotify_client()
    results = sp.current_user_playlists(limit=10)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)