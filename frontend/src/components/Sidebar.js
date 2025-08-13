import React from 'react';
import './Sidebar.css';

const Sidebar = ({ user, onLogout }) => {
  console.log('[SIDEBAR] Rendering sidebar with user:', user ? {
    user_name: user.user_name,
    department: user.department,
    user_id: user.user_id
  } : 'No user');

  if (!user) {
    console.log('[SIDEBAR] No user data available');
    return null;
  }

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>Admin Portal</h2>
      </div>
      
      <div className="user-details-section">
        <h3>User Details</h3>
        <div className="user-info">
          <div className="user-field">
            <label>Username:</label>
            <span>{user.user_name}</span>
          </div>
          <div className="user-field">
            <label>Department:</label>
            <span>{user.department || 'N/A'}</span>
          </div>
          <div className="user-field">
            <label>User ID:</label>
            <span>{user.user_id}</span>
          </div>
        </div>
      </div>

      <div className="sidebar-menu">
        <h3>Navigation</h3>
        <ul>
          <li><a href="#dashboard">Dashboard</a></li>
          <li><a href="#users">User Management</a></li>
          <li><a href="#models">Model Management</a></li>
          <li><a href="#endpoints">Endpoint Management</a></li>
          <li><a href="#settings">Settings</a></li>
        </ul>
      </div>

      <div className="sidebar-footer">
        <button onClick={onLogout} className="logout-button">
          Logout
        </button>
      </div>
    </div>
  );
};

export default Sidebar;