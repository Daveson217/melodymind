import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'


import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css'; 

// Simple Styling inline for brevity
const styles = {
  container: { padding: '20px', fontFamily: 'Arial, sans-serif', maxWidth: '600px', margin: 'auto' },
  card: { border: '1px solid #ddd', borderRadius: '8px', padding: '15px', marginBottom: '10px', cursor: 'pointer' },
  button: { padding: '10px 20px', backgroundColor: '#1DB954', color: 'white', border: 'none', borderRadius: '20px', cursor: 'pointer', fontSize: '16px' },
  quizBox: { backgroundColor: '#282c34', color: 'white', padding: '20px', borderRadius: '10px', marginTop: '20px' }
};

function App() {
  const [view, setView] = useState('login'); // login, dashboard, quiz
  const [playlists, setPlaylists] = useState([]);
  const [quiz, setQuiz] = useState([]);
  const [currentQ, setCurrentQ] = useState(0);
  const [score, setScore] = useState(0);
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    const res = await axios.get('http://localhost:8000/login');
    window.location.href = res.data.url;
  };

  // Check URL for callback code
  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const code = query.get('code');
    if (code) {
      axios.get(`http://localhost:8000/callback?code=${code}`)
        .then(() => {
            window.history.pushState({}, null, "/");
            fetchPlaylists();
        });
    }
  }, []);

  const fetchPlaylists = async () => {
    const res = await axios.get('http://localhost:8000/playlists');
    setPlaylists(res.data);
    setView('dashboard');
  };

  const startTransfer = async (id, name) => {
    setLoading(true);
    // Request backend to start transfer and generate quiz
    const res = await axios.post('http://localhost:8000/start_process', {
      playlist_id: id,
      playlist_name: name
    });
    setQuiz(res.data.quiz);
    setLoading(false);
    setView('quiz');
  };

  const handleAnswer = (option) => {
    if (option === quiz[currentQ].correct_answer) {
      setScore(score + 1);
    }
    if (currentQ < quiz.length - 1) {
      setCurrentQ(currentQ + 1);
    } else {
      setView('result');
    }
  };

  return (
    <div style={styles.container}>
      <h1>🎵 MelodyMind</h1>
      
      {view === 'login' && (
        <div style={{textAlign: 'center', marginTop: '50px'}}>
          <p>Transfer Playlists & Play Trivia.</p>
          <button style={styles.button} onClick={handleLogin}>Connect with Spotify</button>
        </div>
      )}

      {view === 'dashboard' && (
        <div>
          <h3>Select a Playlist to Transfer</h3>
          {loading ? <p>⚡ Analyzing Vibe & Generating Quiz...</p> : 
            playlists.map(pl => (
              <div key={pl.id} style={styles.card} onClick={() => startTransfer(pl.id, pl.name)}>
                <strong>{pl.name}</strong>
              </div>
            ))
          }
        </div>
      )}

      {view === 'quiz' && quiz.length > 0 && (
        <div style={styles.quizBox}>
          <h4>Question {currentQ + 1} / {quiz.length} <span style={{fontSize:'0.8em', color:'yellow'}}>({quiz[currentQ].difficulty})</span></h4>
          <p style={{fontSize: '1.2em'}}>"{quiz[currentQ].question}"</p>
          <div style={{display: 'flex', flexDirection: 'column', gap: '10px'}}>
            {quiz[currentQ].options.map(opt => (
              <button key={opt} onClick={() => handleAnswer(opt)} style={{padding: '10px', cursor:'pointer'}}>
                {opt}
              </button>
            ))}
          </div>
          <p style={{marginTop:'20px', fontSize:'0.8em', fontStyle:'italic'}}>
            Transferring in background...
          </p>
        </div>
      )}

      {view === 'result' && (
        <div style={{textAlign: 'center'}}>
          <h2>🎉 Transfer Complete!</h2>
          <h3>Your Trivia Score: {score} / {quiz.length}</h3>
          <button style={styles.button} onClick={() => setView('dashboard')}>Transfer Another</button>
        </div>
      )}
    </div>
  );
}

export default App;