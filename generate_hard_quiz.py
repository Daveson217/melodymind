import os
import chromadb
import json
import random
#from openai import OpenAI
from google import genai
from pydantic import BaseModel, Field

os.environ['GEMINI_API_KEY'] = ''

# --- CONFIGURATION ---
# Ensure you run the Phase 2 (Ingest) script first so you have data!
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_collection(name="lyrics_knowledge_base")
client = genai.Client()

class QuizQuestion(BaseModel):
    question: str = Field(description="The text of the question.")
    options: list[str] = Field(description="A list of multiple-choice options.")
    correct_answer: str = Field(description="The correct answer from the options.")
    explanation: str = Field(description="A brief explanation of why the answer is correct.")


def get_challenge_data():
    """
    1. Picks a random lyric (Correct Answer).
    2. Finds 'Hard Negatives' (Semantically similar lyrics from DIFFERENT songs).
    """
    # Step A: Get a Random Anchor (Correct Answer)
    # (In prod, use a random offset or ID tracking)
    all_ids = collection.get()['ids'] 
    if not all_ids: return None
    
    anchor_id = random.choice(all_ids)
    anchor_data = collection.get(ids=[anchor_id], include=["embeddings", "documents", "metadatas"])
    
    correct_lyric = anchor_data['documents'][0]
    correct_meta = anchor_data['metadatas'][0]
    correct_vector = anchor_data['embeddings'][0]
    
    print(f"🎯 Target Song: {correct_meta['song']} ({correct_meta['artist']})")

    # Step B: Hard Negative Mining (The ML Magic)
    # We query for vectors close to the answer, BUT exclude the answer's song.
    results = collection.query(
        query_embeddings=[correct_vector],
        n_results=10, # Fetch extra in case we get duplicates
        where={"song": {"$ne": correct_meta['song']}} # <--- CRITICAL: Exclude correct answer
    )
    
    # Extract unique wrong options (Distractors)
    distractors = []
    seen_artists = {correct_meta['artist']} # Don't repeat the correct artist
    
    for i, meta in enumerate(results['metadatas'][0]):
        artist = meta['artist']
        song = meta['song']
        
        # Only add if we haven't seen this artist/song yet
        if artist not in seen_artists:
            distractors.append(f"{song} by {artist}")
            seen_artists.add(artist)
            
        if len(distractors) >= 3:
            break
            
    # Fallback: If database is too small, just fill with randoms (Safety net)
    if len(distractors) < 3:
        print("⚠️ Not enough hard negatives found. Database too small?")
        distractors.append("Generic Pop Song by Generic Artist")

    return correct_lyric, correct_meta, distractors

def generate_hard_question(lyric, meta, distractors):
    """
    Asks the LLM to create a question using the SPECIFIC hard negatives we found.
    """
    correct_option = f"{meta['song']} by {meta['artist']}"
    options = distractors + [correct_option]
    random.shuffle(options) # Shuffle so D isn't always the answer
    
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
    
    # response = client.chat.completions.create(
    #     model="gpt-3.5-turbo",
    #     messages=[{"role": "user", "content": prompt}],
    #     response_format={"type": "json_object"}
    # )
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": QuizQuestion.model_json_schema(),
        },
    )

    return response.text

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    data = get_challenge_data()
    
    if data:
        lyric, meta, distractors = data
        json_quiz = generate_hard_question(lyric, meta, distractors)
        
        # Display
        q = json.loads(json_quiz)
        print("\n" + "="*40)
        print(f"🔥 HARD MODE QUIZ: {meta['artist']} 🔥")
        print("="*40)
        print(f"Q: {q['question']}") 
        print(f"\n(Lyric Snippet: {lyric[:50]}...)")
        print("-" * 20)
        for opt in q['options']:
            print(f"[ ] {opt}")
        print("-" * 20)
        print(f"✅ Answer: {q['correct_answer']}")
        print(f"🧠 Logic: {q['explanation']}")