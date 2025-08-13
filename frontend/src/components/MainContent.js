import React from 'react';
import './MainContent.css';

const MainContent = ({ user, token }) => {
  console.log('[MAIN_CONTENT] Rendering main content for user:', user?.user_name);
  
  return (
    <div className="main-content">
      <div className="content-header">
        <h1>Welcome to Admin Portal</h1>
        <p>Manage your AI API Framework from this admin dashboard</p>
      </div>
      
      <div className="dashboard-cards">
        <div className="dashboard-card">
          <h3>User Management</h3>
          <p>Manage system users, roles, and permissions</p>
          <div className="card-stats">
            <span className="stat-label">Status:</span>
            <span className="stat-value authenticated">Authenticated</span>
          </div>
        </div>
        
        <div className="dashboard-card">
          <h3>Model Management</h3>
          <p>Configure and manage AI models and their metadata</p>
          <div className="card-stats">
            <span className="stat-label">Token:</span>
            <span className="stat-value">Active</span>
          </div>
        </div>
        
        <div className="dashboard-card">
          <h3>Endpoint Management</h3>
          <p>Monitor and configure API endpoints</p>
          <div className="card-stats">
            <span className="stat-label">Session:</span>
            <span className="stat-value">Valid</span>
          </div>
        </div>
        
        <div className="dashboard-card">
          <h3>System Settings</h3>
          <p>Configure system-wide settings and preferences</p>
          <div className="card-stats">
            <span className="stat-label">Access Level:</span>
            <span className="stat-value admin">Admin</span>
          </div>
        </div>
      </div>
      
      <div className="debug-info">
        <h3>Debug Information</h3>
        <div className="debug-grid">
          <div className="debug-item">
            <label>User ID:</label>
            <span>{user?.user_id}</span>
          </div>
          <div className="debug-item">
            <label>Username:</label>
            <span>{user?.user_name}</span>
          </div>
          <div className="debug-item">
            <label>Email:</label>
            <span>{user?.user_email}</span>
          </div>
          <div className="debug-item">
            <label>Department:</label>
            <span>{user?.department || 'N/A'}</span>
          </div>
          <div className="debug-item">
            <label>Scope:</label>
            <span>{user?.scope}</span>
          </div>
          <div className="debug-item">
            <label>Token Status:</label>
            <span>{token ? 'Active' : 'Inactive'}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MainContent;