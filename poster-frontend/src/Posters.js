// src/Posters.js
import React, { useState, useEffect } from 'react';

const Posters = ({ token }) => {
  const [posters, setPosters] = useState([]);
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch the list of posters on component mount
  useEffect(() => {
    const fetchPosters = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/posters`);
        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.error || 'Failed to load posters');
        }
        const data = await response.json();
        setPosters(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchPosters();
  }, []);

  // Handler to submit a new poster
  const handleCreatePoster = async (event) => {
    event.preventDefault();
    setError(null);

    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/posters`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // If your POST endpoint requires JWT auth, include it:
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({
          title: newTitle,
          description: newDescription,
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'Failed to create poster');
      }

      const createdPoster = await response.json();
      // Update the list with the new poster
      setPosters([...posters, createdPoster]);
      // Clear the form
      setNewTitle('');
      setNewDescription('');
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <h2>Posters</h2>
      {loading && <p>Loading posters...</p>}
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      <ul>
        {posters.map((poster) => (
          <li key={poster.id}>
            <strong>{poster.title}</strong> - {poster.description}
          </li>
        ))}
      </ul>

      <h3>Create a New Poster</h3>
      <form onSubmit={handleCreatePoster}>
        <div>
          <label>Title: </label>
          <input
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            required
          />
        </div>
        <div>
          <label>Description: </label>
          <textarea
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            required
          />
        </div>
        <button type="submit">Create Poster</button>
      </form>
    </div>
  );
};

export default Posters;
