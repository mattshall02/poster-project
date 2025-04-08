// src/AdminPanel.js
import React, { useEffect, useState } from 'react';

const AdminPanel = ({ token }) => {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState(null);

  // Fetch users on mount
  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/admin/users`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.error || 'Failed to fetch users');
        }
        const data = await response.json();
        setUsers(data);
      } catch (err) {
        setError(err.message);
      }
    };

    fetchUsers();
  }, [token]);

  const deleteUser = async (username) => {
    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/admin/users/${username}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'Failed to delete user');
      }
      // Remove deleted user from the list.
      setUsers(users.filter(user => user.username !== username));
      alert(`User ${username} deleted successfully.`);
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  return (
    <div>
      <h2>Admin Panel - User Management</h2>
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      <ul>
        {users.map(user => (
          <li key={user.id}>
            <strong>{user.username}</strong> ({user.email}) - Verified: {user.is_verified ? "Yes" : "No"}
            {user.username !== 'admin' && (
              <button onClick={() => deleteUser(user.username)} style={{ marginLeft: '10px' }}>
                Delete
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default AdminPanel;
