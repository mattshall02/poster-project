// src/App.js
import React, { useState } from 'react';
import Login from './Login';
import Profile from './Profile';

function App() {
  const [token, setToken] = useState(localStorage.getItem("access_token") || '');

  const handleLogin = (accessToken) => {
    setToken(accessToken);
    localStorage.setItem("access_token", accessToken);
  };

  const handleLogout = () => {
    setToken('');
    localStorage.removeItem("access_token");
  };

  return (
    <div className="App">
      <h1>Poster Trading App</h1>
      {!token ? (
        <Login onLogin={handleLogin} />
      ) : (
        <div>
          <button onClick={handleLogout}>Logout</button>
          <Profile token={token} />
        </div>
      )}
    </div>
  );
}

export default App;
