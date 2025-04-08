// src/App.js
import React, { useState } from 'react';
import { jwtDecode } from 'jwt-decode';
import Login from './Login';
import Register from './Register';
import Profile from './Profile';
import AdminPanel from './AdminPanel';
import Posters from './Posters';

function App() {
  const [token, setToken] = useState(localStorage.getItem("access_token") || "");
  const [view, setView] = useState("login"); // "login", "register", "posters", etc.
  
  let username = "";
  if (token) {
    try {
      const decoded = jwtDecode(token);
      username = decoded.sub || decoded.username || "";
      console.log("Logged in as:", username);
    } catch (err) {
      console.error("Error decoding token:", err);
    }
  }

  const handleLogin = (accessToken) => {
    setToken(accessToken);
    localStorage.setItem("access_token", accessToken);
    setView("posters"); // After login, go to posters view
  };

  const handleLogout = () => {
    setToken("");
    localStorage.removeItem("access_token");
    setView("login");
  };

  return (
    <div className="App">
      <h1>Poster Trading App</h1>
      {!token ? (
        <div>
          {view === "login" ? (
            <>
              <Login onLogin={handleLogin} />
              <p>
                Don't have an account?{" "}
                <button onClick={() => setView("register")}>Register</button>
              </p>
            </>
          ) : (
            <>
              <Register />
              <p>
                Already have an account?{" "}
                <button onClick={() => setView("login")}>Login</button>
              </p>
            </>
          )}
        </div>
      ) : (
        <div>
          <p>Logged in as: {username}</p>
          <button onClick={handleLogout}>Logout</button>
          <Profile token={token} />
          {/* Navigation for Posters */}
          <div>
            <button onClick={() => setView("posters")}>View Posters</button>
            {username === "admin" && <button onClick={() => setView("admin")}>Admin Panel</button>}
          </div>
          {view === "posters" && <Posters token={token} />}
          {view === "admin" && username === "admin" && <AdminPanel token={token} />}
        </div>
      )}
    </div>
  );
}

export default App;
