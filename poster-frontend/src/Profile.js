// src/Profile.js
import React, { useEffect, useState } from 'react';

const Profile = ({ token }) => {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/profile`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Failed to load profile');
        }

        const data = await response.json();
        setProfile(data);
      } catch (err) {
        setError(err.message);
      }
    };

    if (token) {
      fetchProfile();
    }
  }, [token]);

  return (
    <div>
      <h2>User Profile</h2>
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {profile ? (
        <div>
          <p><strong>ID:</strong> {profile.id}</p>
          <p><strong>Username:</strong> {profile.username}</p>
          <p><strong>Email:</strong> {profile.email}</p>
          <p><strong>Verified:</strong> {profile.is_verified ? "Yes" : "No"}</p>
          <p><strong>Created At:</strong> {profile.created_at}</p>
        </div>
      ) : (
        <p>Loading profile...</p>
      )}
    </div>
  );
};

export default Profile;
