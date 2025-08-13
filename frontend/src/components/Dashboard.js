import React from 'react';
import './Dashboard.css';

const Dashboard = ({ user, token }) => {
  console.log('[DASHBOARD] Rendering dashboard for user:', user?.user_name);

  const stats = [
    {
      title: 'Total Users',
      value: '—',
      icon: '👥',
      color: '#4CAF50'
    },
    {
      title: 'API Endpoints',
      value: '—',
      icon: '🔗',
      color: '#2196F3'
    },
    {
      title: 'Active Sessions',
      value: '—',
      icon: '📊',
      color: '#FF9800'
    },
    {
      title: 'System Status',
      value: 'Online',
      icon: '✅',
      color: '#4CAF50'
    }
  ];

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Welcome to GAIA Admin Portal</h1>
        <p>Manage users, endpoints, and system configuration</p>
      </div>

      <div className="stats-grid">
        {stats.map((stat, index) => (
          <div key={index} className="stat-card" style={{'--accent-color': stat.color}}>
            <div className="stat-icon" style={{color: stat.color}}>
              {stat.icon}
            </div>
            <div className="stat-content">
              <div className="stat-value">{stat.value}</div>
              <div className="stat-title">{stat.title}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-section session-info-section">
          <div className="section-header">
            <h3>Current Session</h3>
          </div>
          <div className="session-details">
            <div className="session-item">
              <span className="session-label">User</span>
              <span className="session-value">{user?.common_name || user?.user_name}</span>
            </div>
            <div className="session-item">
              <span className="session-label">Email</span>
              <span className="session-value">{user?.user_email}</span>
            </div>
            <div className="session-item">
              <span className="session-label">Department</span>
              <span className="session-value">{user?.department || 'Administrator'}</span>
            </div>
            <div className="session-item">
              <span className="session-label">Access Level</span>
              <span className="session-value admin-badge">Administrator</span>
            </div>
            <div className="session-item">
              <span className="session-label">Session Status</span>
              <span className="session-value token-active">Active</span>
            </div>
          </div>
        </div>

        <div className="dashboard-section welcome-section">
          <div className="section-header">
            <h3>Getting Started</h3>
          </div>
          <div className="welcome-content">
            <p>Use the navigation menu to:</p>
            <ul>
              <li>Manage system users and permissions</li>
              <li>Configure API endpoints and costs</li>
              <li>Monitor system analytics and usage</li>
              <li>View system logs and configurations</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;