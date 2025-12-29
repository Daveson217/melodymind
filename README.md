🎵 MelodyMind: Intelligent Music Migration & RAG Agent
MelodyMind is a full-stack AI-driven utility that automates playlist migration between Spotify and YouTube Music. To enhance user retention during migration latency, the platform features an interactive Retrieval-Augmented Generation (RAG) trivia engine that generates personalized quizzes based on the specific lyrical content and "vibe" of the tracks being transferred.

🚀 Technical Core & ML Features
RAG-Powered Trivia Engine: Utilizes Gemini 2.0 Flash and ChromaDB to generate context-aware trivia from song lyrics. Instead of generic facts, the system retrieves specific lyrical "chunks" to create deep-knowledge questions.

Hard Negative Mining: Implements semantic search using Sentence-Transformers (all-MiniLM-L6-v2) to identify "hard negatives"—incorrect options that are mathematically similar in the vector space to the correct answer, ensuring a challenging user experience.

Asynchronous Processing: Built with a FastAPI backend that manages long-running API migration tasks via background workers, keeping the UI responsive for the trivia experience.

Automated Ingestion Pipeline: A custom pipeline using LyricsGenius that fetches, chunks, and embeds lyrical data into a local vector store for low-latency retrieval.

Smart Search Matching: Employs difflib and fuzzy artist matching to prioritize official song versions over covers or remixes during the transfer process.

🛠️ Tech Stack
AI/ML: Gemini API, ChromaDB (Vector DB), Sentence-Transformers (Local Embeddings), RAG.

Backend: Python, FastAPI, Pydantic, Spotipy (Spotify API), ytmusicapi (YouTube Music).

Frontend: React.js, Axios, Vite, Framer Motion.

DevOps: OAuth 2.0 (Google/Spotify), Docker-ready.

📦 System Architecture
Ingestion: The system extracts unique artist data from a Spotify playlist.

Indexing: Lyrics are scraped, chunked into 4-line stanzas, converted to 384-dimensional vectors, and stored in ChromaDB.

Transfer: An asynchronous worker begins batch-adding songs to the destination YouTube Music account.

Generation: The LLM receives retrieved context and specific "hard negative" distractors to generate a JSON-formatted quiz.

🔧 Installation & Setup
Prerequisites
Python 3.10+

Node.js & npm

API Keys for Spotify, Google Cloud (YouTube Data API), Gemini, and Genius.

Backend Setup
Clone the repository and navigate to /backend.

Install dependencies: pip install -r requirements.txt.

Create a .env file with your credentials.

Run the server: uvicorn main:app --reload.

Frontend Setup
Navigate to /frontend.

Install dependencies: npm install.

Start the Vite dev server: npm run dev.

Access the app at http://127.0.0.1:5173.


🗺️ Future Roadmap
To further evolve the technical complexity and scalability of MelodyMind, the following enhancements are planned:

Edge AI & Local Inference: Transition from cloud-based APIs to local LLM inference (e.g., Llama 3 or Mistral via Ollama) to demonstrate proficiency in infrastructure optimization and cost-effective deployment.

Multi-modal Music Embeddings: Expand the RAG pipeline to incorporate audio signal processing (using Librosa). This will allow the system to generate trivia based on audio features like tempo, key, and timbre, moving beyond text-only lyrics.

Fine-tuned Trivia Personalities: Implement LoRA (Low-Rank Adaptation) to fine-tune a lightweight model on specific music genres or critical reviews, giving the trivia agent a unique "personality" or "voice".

Scalable Data Pipelines: Replace the current in-memory status tracking with a distributed task queue like Celery and Redis to handle thousands of concurrent playlist migrations.

Social Graph Integration: Utilize vector similarity to suggest "Music Soulmates"—connecting users whose playlist embeddings show high semantic overlap in their musical taste.