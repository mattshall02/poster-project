// src/pages/Posters.js
import React, { useState, useEffect } from 'react';

const Posters = ({ token }) => {
  const [posters, setPosters] = useState([]);
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newArtist, setNewArtist] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch posters on mount
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

  // Handler to create a new poster with optional photo
  const handleCreatePoster = async (event) => {
    event.preventDefault();
    setError(null);

    const formData = new FormData();
    formData.append("title", newTitle);
    formData.append("description", newDescription);
    formData.append("artist", newArtist);
    if (selectedFile) {
      formData.append("photo", selectedFile);
    }

    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/posters/upload`, {
        method: 'POST',
        headers: {
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'Failed to create poster');
      }

      const createdPoster = await response.json();
      setPosters([...posters, createdPoster]);
      setNewTitle('');
      setNewDescription('');
      setNewArtist('');
      setSelectedFile(null);
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
            <strong>{poster.title}</strong> by <em>{poster.artist}</em> - {poster.description}
            {poster.photo_url && (
              <div>
                <img src={poster.photo_url} alt={poster.title} style={{ maxWidth: '200px' }} />
              </div>
            )}
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
        <div>
          <label>Artist: </label>
          <input
            type="text"
            value={newArtist}
            onChange={(e) => setNewArtist(e.target.value)}
          />
        </div>
        <div>
          <label>Photo: </label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setSelectedFile(e.target.files[0])}
          />
        </div>
        <button type="submit">Create Poster</button>
      </form>
    </div>
  );
};

export default Posters;
