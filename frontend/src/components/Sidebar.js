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

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊', active: true },
    { id: 'users', label: 'User Management', icon: '👥', active: false },
    { id: 'models', label: 'AI Models', icon: '🧠', active: false },
    { id: 'endpoints', label: 'API Endpoints', icon: '🔗', active: false },
    { id: 'analytics', label: 'Analytics', icon: '📈', active: false },
    { id: 'balance', label: 'Balance & Usage', icon: '💰', active: false },
    { id: 'logs', label: 'System Logs', icon: '📋', active: false },
    { id: 'settings', label: 'Settings', icon: '⚙️', active: false },
  ];

  return (
    <div className="sidebar">
      <div className="user-profile-card">
        <div className="profile-avatar">
          {user.user_name?.charAt(0)?.toUpperCase()}
        </div>
        <div className="profile-info">
          <h3>{user.user_name}</h3>
          <p className="department">{user.department || 'Administrator'}</p>
          <div className="user-badge">
            <span className="badge-icon">🛡️</span>
            <span>Admin Access</span>
          </div>
        </div>
      </div>

      <div className="quick-stats">
        <div className="stat-item">
          <span className="stat-icon">⚡</span>
          <div>
            <span className="stat-value">Online</span>
            <span className="stat-label">Status</span>
          </div>
        </div>
        <div className="stat-item">
          <span className="stat-icon">🔑</span>
          <div>
            <span className="stat-value">Active</span>
            <span className="stat-label">Session</span>
          </div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section">
          <h4>MAIN MENU</h4>
          <ul>
            {menuItems.slice(0, 4).map(item => (
              <li key={item.id} className={item.active ? 'active' : ''}>
                <a href={`#${item.id}`}>
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                  {item.active && <span className="active-indicator"></span>}
                </a>
              </li>
            ))}
          </ul>
        </div>

        <div className="nav-section">
          <h4>MANAGEMENT</h4>
          <ul>
            {menuItems.slice(4, 8).map(item => (
              <li key={item.id} className={item.active ? 'active' : ''}>
                <a href={`#${item.id}`}>
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                  {item.active && <span className="active-indicator"></span>}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </nav>

      <div className="sidebar-footer">
        <div className="user-details-mini">
          <div className="detail-row">
            <span className="detail-label">ID:</span>
            <span className="detail-value">{user.user_id?.substring(0, 8)}...</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Scope:</span>
            <span className="detail-value admin-scope">Admin ({user.scope})</span>
          </div>
        </div>
        <button onClick={onLogout} className="logout-button">
          <span className="logout-icon">🚪</span>
          <span>Sign Out</span>
        </button>
      </div>
    </div>
  );
};

export default Sidebar;