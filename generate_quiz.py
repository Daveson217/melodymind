print('Imports...')
import os
import chromadb
import json
import random
# from openai import OpenAI
from google import genai
from pydantic import BaseModel, Field

print('GEMINI_API_KEY set up.')
# --- CONFIGURATION ---
#os.environ['OPENAI_API_KEY'] = 'YOUR_OPENAI_API_KEY'  # Or use DotEnv
os.environ['GEMINI_API_KEY'] = ''
# client = OpenAI(api_key=OPENAI_API_KEY)
client = genai.Client()

# 1. Connect to the Vector DB (The "Brain")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_collection(name="lyrics_knowledge_base")

class QuizQuestion(BaseModel):
    question: str = Field(description="The text of the question.")
    options: list[str] = Field(description="A list of multiple-choice options.")
    correct_answer: str = Field(description="The correct answer from the options.")
    explanation: str = Field(description="A brief explanation of why the answer is correct.")


def get_random_lyric_context():
    """
    Retrieves a random lyric chunk from the database to base a question on.
    In a real app, you might iterate through specific songs in the playlist.
    """
    # Chroma doesn't have a native "random" fetch, so we fetch the first few
    # and pick one. In production, you'd track IDs.
    results = collection.get(limit=10, include=["documents", "metadatas"])

    if not results['documents']:
        return None, None

    # Pick a random index
    idx = random.randint(0, len(results['documents']) - 1)
    lyric_segment = results['documents'][idx]
    metadata = results['metadatas'][idx]

    return lyric_segment, metadata


def generate_quiz_question(lyric_segment, metadata):
    """
    The RAG Step: Injects the retrieved lyric into the LLM prompt.
    """
    artist = metadata['artist']
    song = metadata['song']

    print(f"🤖 Context Found: Generating question for '{song}' by {artist}...")

    # PROMPT ENGINEERING:
    # We ask for JSON output so our frontend (React/Streamlit) can parse it easily.
    prompt = f"""
    You are a music trivia generator. I will provide you with a segment of lyrics from the song "{song}" by "{artist}".
    
    LYRIC SEGMENT:
    "{lyric_segment}"
    
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

    # response = client.chat.completions.create(
    #     model="gpt-3.5-turbo", # Or "gpt-4-turbo" for better reasoning
    #     messages=[
    #         {"role": "system", "content": "You are a helpful AI assistant that outputs JSON."},
    #         {"role": "user", "content": prompt}
    #     ],
    #     temperature=0.7,
    #     response_format={"type": "json_object"} # JSON Mode (Critical for App Dev)
    # )
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": QuizQuestion.model_json_schema(),
        },
    )

    # return response.choices[0].message.content
    return response.text


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # 1. Retrieve (R)
    lyric, meta = get_random_lyric_context()

    if lyric:
        # 2. Augment & Generate (AG)
        json_quiz = generate_quiz_question(lyric, meta)

        # 3. Parse and Display
        quiz_data = json.loads(json_quiz)

        print("\n" + "="*40)
        print(f"   🎤 TRIVIA: {meta['song']} 🎤")
        print("="*40)
        print(f"Q: {quiz_data['question']}")
        print("-" * 20)
        for opt in quiz_data['options']:
            print(f"[ ] {opt}")
        print("-" * 20)
        print(f"✅ Answer: {quiz_data['correct_answer']}")
        print(f"ℹ️  Info: {quiz_data['explanation']}")
    else:
        print("❌ No data found in ChromaDB. Run Phase 2 script first!")
