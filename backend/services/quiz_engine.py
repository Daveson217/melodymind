import os
import random
import json
import lyricsgenius
import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from google import genai
from pydantic import BaseModel, Field

# Load environment variables from .env file
load_dotenv()

# --- CONFIG ---
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Init Clients
genius = lyricsgenius.Genius(GENIUS_TOKEN, verbose=False, remove_section_headers=True)
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="lyrics_knowledge_base")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
client = genai.Client(api_key=GEMINI_API_KEY)

class QuizQuestion(BaseModel):
    question: str = Field(description="The text of the question.")
    options: list[str] = Field(description="A list of multiple-choice options.")
    correct_answer: str = Field(description="The correct answer from the options.")
    explanation: str = Field(description="A brief explanation of why the answer is correct.")
    difficulty: str

def quick_ingest(artist, song_title):
    """Fetches lyrics and stores them immediately for the quiz."""
    try:
        # Check if already exists to save API calls
        existing = collection.get(where={"song": song_title})
        if existing['ids']:
            return True

        song = genius.search_song(song_title, artist)
        if not song: return False
        
        lines = [line for line in song.lyrics.split('\n') if line.strip()]
        chunks = []
        for i in range(0, len(lines), 4):
            chunk_text = "\n".join(lines[i:i+4])
            chunks.append({
                "text": chunk_text, "song": song_title, "artist": artist,
                "id": f"{artist}_{song_title}_{i}"
            })
            
        if not chunks: return False

        docs = [c['text'] for c in chunks]
        metas = [{"song": c['song'], "artist": c['artist']} for c in chunks]
        ids = [c['id'] for c in chunks]
        embeds = embedding_model.encode(docs).tolist()
        
        collection.upsert(documents=docs, embeddings=embeds, metadatas=metas, ids=ids)
        return True
    except Exception as e:
        print(f"Ingest Error: {e}")
        return False

def generate_batch_quiz(num_questions=10):
    """Generates a mix of Normal (80%) and Hard (20%) questions."""
    questions = []
    
    # Try to fetch contexts
    all_docs = collection.get(limit=50, include=["documents", "metadatas", "embeddings"])
    if not all_docs['documents']:
        return []

    count = len(all_docs['documents'])
    
    for i in range(num_questions):
        is_hard = (i >= num_questions * 0.8) 
        mode = "Hard" if is_hard else "Normal"
        
        # Pick random context
        idx = random.randint(0, count - 1)
        lyric = all_docs['documents'][idx]
        meta = all_docs['metadatas'][idx]
        
        prompt = ""
        
        if is_hard:
            correct_vec = all_docs['embeddings'][idx]
            # Find distractors via vector search (Hard Negatives)
            results = collection.query(
                query_embeddings=[correct_vec], n_results=5, 
                where={"song": {"$ne": meta['song']}}
            )
            distractors = [m['song'] + " by " + m['artist'] for m in results['metadatas'][0]][:3]
            while len(distractors) < 3: distractors.append("Generic Song by Random Artist")
            
            correct_option = f"{meta['song']} by {meta['artist']}"

            prompt = f"""
                You are a quiz master. Create a multiple-choice question based on this lyric.
                
                LYRIC SEGMENT:
                "{lyric}"
                
                THE CORRECT ANSWER IS:
                "{correct_option}"
                
                THE WRONG OPTIONS (DISTRACTORS) MUST BE:
                {json.dumps(distractors)}
                
                RULES:
                1. The question should be: "Which song contains these lyrics?"
                2. You must use the provided options. Do not make up new ones.
                3. Output purely in JSON format.
                
                OUTPUT JSON:
                {{
                    "question": "Which song features the line...",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_answer": "{correct_option}",
                    "explanation": "Briefly mention why the lyrics fit the correct song's theme vs the others."
                }}
                """
        else:
            # --- NORMAL MODE LOGIC ---
            prompt = f"""
            You are a music trivia generator. I will provide you with a segment of lyrics from the song "{meta['song']}" by "{meta['artist']}".
            
            LYRIC SEGMENT:
            "{lyric}"
            
            TASK:
            Generate a multiple-choice question based specifically on these lyrics. 
            You can ask about the meaning, the metaphor used, or complete the line.
            
            OUTPUT FORMAT (Strict JSON):
            {{
                "question": "The text of the question",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": "Option A",
                "explanation": "Brief explanation of why it is correct."
            }}
    """

        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt + "\nOutput strictly in JSON compatible with QuizQuestion schema.",
                config={"response_mime_type": "application/json", "response_json_schema": QuizQuestion.model_json_schema()}
            )
            q_data = json.loads(resp.text)
            q_data['difficulty'] = mode
            questions.append(q_data)
        except Exception as e:
            print(f"Gen Error: {e}")
            
    return questions