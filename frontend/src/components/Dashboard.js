import React, { useState, useEffect } from 'react';
import { adminAPI, endpointAPI } from '../services/apiService';
import './Dashboard.css';

const Dashboard = ({ user, token }) => {
  console.log('[DASHBOARD] Rendering dashboard for user:', user?.user_name);
  
  const [userCount, setUserCount] = useState('—');
  const [endpointCount, setEndpointCount] = useState('—');

  useEffect(() => {
    loadDashboardData();
  }, [user, token]);

  const loadDashboardData = async () => {
    try {
      // Load user count
      const usersResponse = await adminAPI.getAllUsers(user.api_key, token);
      setUserCount(usersResponse.users?.length || 0);
    } catch (err) {
      console.error('[DASHBOARD] Failed to load user count:', err);
    }

    try {
      // Load endpoint count
      const endpointsResponse = await endpointAPI.getAllEndpoints(user.api_key, token);
      setEndpointCount(endpointsResponse.endpoints?.length || 0);
    } catch (err) {
      console.error('[DASHBOARD] Failed to load endpoint count:', err);
    }
  };

  const stats = [
    {
      title: 'Total Users',
      value: userCount,
      icon: '👥',
      color: '#4CAF50'
    },
    {
      title: 'API Endpoints',
      value: endpointCount,
      icon: '🔗',
      color: '#2196F3'
    },
    {
      title: 'Admin Sessions',
      value: '1',
      icon: '🔐',
      color: '#9C27B0'
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