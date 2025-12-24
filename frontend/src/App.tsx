import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css'; 

const styles = {
  container: { padding: '20px', fontFamily: 'Arial, sans-serif', maxWidth: '600px', margin: 'auto' },
  card: { border: '1px solid #ddd', borderRadius: '8px', padding: '15px', marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  button: { padding: '8px 16px', backgroundColor: '#1DB954', color: 'white', border: 'none', borderRadius: '20px', cursor: 'pointer', fontSize: '14px', marginLeft: '5px' },
  secButton: { padding: '8px 16px', backgroundColor: '#535353', color: 'white', border: 'none', borderRadius: '20px', cursor: 'pointer', fontSize: '14px', marginLeft: '5px' },
  quizBox: { backgroundColor: '#282c34', color: 'white', padding: '20px', borderRadius: '10px', marginTop: '20px' }
};

function App() {
  const [view, setView] = useState('login'); 
  const [playlists, setPlaylists] = useState([]);
  const [quiz, setQuiz] = useState(null); // Fix: Init as null to differentiate from empty array
  const [currentQ, setCurrentQ] = useState(0);
  const [score, setScore] = useState(0);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState(''); // 'transfer' or 'trivia'

  const handleLogin = async () => {
    const res = await axios.get('http://127.0.0.1:8000/login');
    window.location.href = res.data.url;
  };

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const code = query.get('code');
    if (code) {
      axios.get(`http://127.0.0.1:8000/callback?code=${code}`)
        .then(() => {
            // Fix: Pass empty string instead of null for title
            window.history.pushState({}, "", "/"); 
            fetchPlaylists();
        });
    }
  }, []);

  const fetchPlaylists = async () => {
    try {
        const res = await axios.get('http://127.0.0.1:8000/playlists');
        setPlaylists(res.data);
        setView('dashboard');
    } catch (e) {
        console.error("Login needed", e);
    }
  };

  const handleAction = async (id, name, actionType) => {
    setLoading(true);
    setMode(actionType);
    
    // Choose endpoint based on button clicked
    const endpoint = actionType === 'transfer' 
        ? 'http://127.0.0.1:8000/start_transfer' 
        : 'http://127.0.0.1:8000/start_trivia';

    try {
        const res = await axios.post(endpoint, {
          playlist_id: id,
          playlist_name: name
        });
        setQuiz(res.data.quiz);
        setCurrentQ(0);
        setScore(0);
        setView('quiz');
    } catch (e) {
        alert("Error starting process");
    }
    setLoading(false);
  };

  const handleAnswer = (option) => {
    if (!quiz) return;

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
          <h3>Your Playlists ({playlists.length})</h3>
          {loading ? <p>⚡ Analyzing Vibe & Generating Quiz...</p> : 
            playlists.map(pl => (
              <div key={pl.id} style={styles.card}>
                <span><strong>{pl.name}</strong></span>
                <div>
                    <button style={styles.secButton} onClick={() => handleAction(pl.id, pl.name, 'trivia')}>Play Trivia</button>
                    <button style={styles.button} onClick={() => handleAction(pl.id, pl.name, 'transfer')}>Transfer</button>
                </div>
              </div>
            ))
          }
        </div>
      )}

      {view === 'quiz' && quiz && quiz.length > 0 && (
        <div style={styles.quizBox}>
          <h4>Question {currentQ + 1} / {quiz.length} <span style={{fontSize:'0.8em', color:'yellow'}}>({quiz[currentQ].difficulty})</span></h4>
          <p style={{fontSize: '1.2em'}}>"{quiz[currentQ].question}"</p>
          <div style={{display: 'flex', flexDirection: 'column', gap: '10px'}}>
            {quiz[currentQ].options.map(opt => (
              <button key={opt} onClick={() => handleAnswer(opt)} style={{padding: '10px', cursor:'pointer', border: 'none', borderRadius: '5px'}}>
                {opt}
              </button>
            ))}
          </div>
          {mode === 'transfer' && (
             <p style={{marginTop:'20px', fontSize:'0.8em', fontStyle:'italic', color: '#888'}}>
               Transferring in background...
             </p>
          )}
        </div>
      )}

      {view === 'result' && (
        <div style={{textAlign: 'center'}}>
          <h2>{mode === 'transfer' ? '🎉 Transfer Complete!' : '🎉 Quiz Finished!'}</h2>
          <h3>Your Score: {score} / {quiz ? quiz.length : 0}</h3>
          <button style={styles.button} onClick={() => { fetchPlaylists(); setView('dashboard'); }}>Back to Dashboard</button>
        </div>
      )}
    </div>
  );
}

export default App;