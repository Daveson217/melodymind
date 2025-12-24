import os
import lyricsgenius
import chromadb
from sentence_transformers import SentenceTransformer

# --- CONFIGURATION ---
# Get your token from: https://genius.com/api-clients
GENIUS_TOKEN = ""

# 1. Initialize Clients
genius = lyricsgenius.Genius(GENIUS_TOKEN)
genius.verbose = False  # Turn off status messages
genius.remove_section_headers = True # Remove [Chorus], [Verse 1], etc.

# Load a small, fast embedding model (runs locally on CPU)
print("⏳ Loading embedding model...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize Vector DB (Persist to disk so data is saved)
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="lyrics_knowledge_base")

def fetch_and_chunk_lyrics(artist_name, song_title, chunk_size=4):
    """
    Fetches lyrics and breaks them into 'chunks' (e.g., 4 lines at a time).
    Small chunks are better for retrieval than whole songs.
    """
    print(f"🎤 Fetching lyrics for: {song_title} by {artist_name}...")
    song = genius.search_song(song_title, artist_name)
    
    if not song:
        print("❌ Song not found.")
        return []

    lines = [line for line in song.lyrics.split('\n') if line.strip()]
    chunks = []
    
    # Simple chunking: Group every 'chunk_size' lines together
    for i in range(0, len(lines), chunk_size):
        chunk_text = "\n".join(lines[i:i+chunk_size])
        chunks.append({
            "text": chunk_text,
            "song": song_title,
            "artist": artist_name,
            "id": f"{artist_name}_{song_title}_{i}"
        })
        
    print(f"✅ Created {len(chunks)} chunks.")
    return chunks

def embed_and_store(chunks):
    """
    Converts text chunks to vectors and stores them in ChromaDB.
    """
    if not chunks:
        return

    print("🧠 Embedding and storing in Vector DB...")
    
    # Prepare lists for ChromaDB
    documents = [c['text'] for c in chunks]
    metadatas = [{"song": c['song'], "artist": c['artist']} for c in chunks]
    ids = [c['id'] for c in chunks]
    
    # Generate Embeddings (The "Deep Learning" part)
    embeddings = embedding_model.encode(documents).tolist()

    # Upsert (Update if exists, Insert if new)
    collection.upsert(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )
    print(f"💾 Stored {len(chunks)} vectors in ChromaDB.")

def semantic_search(query_text):
    """
    Searches the database for lyrics that match the 'meaning' of the query.
    """
    print(f"\n🔎 Searching for meaning: '{query_text}'...")
    
    # Convert query to vector
    query_vector = embedding_model.encode([query_text]).tolist()
    
    results = collection.query(
        query_embeddings=query_vector,
        n_results=2  # Return top 2 matching chunks
    )
    
    for i, doc in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i]
        print(f"\n--- Match {i+1} (Song: {meta['song']}) ---")
        print(doc)

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # 1. Ingest Data (Do this once per song)
    # Let's use a song known for vivid imagery
    chunks = fetch_and_chunk_lyrics("Pink Floyd", "Time")
    embed_and_store(chunks)
    
    # 2. Test Semantic Search
    # Note: I am NOT using keywords like "Time" or "Clock". 
    # I am describing the FEELING.
    semantic_search("The feeling of getting older and wasting life")