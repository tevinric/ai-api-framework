import React from 'react';
import './Sidebar.css';

const Sidebar = ({ user, currentView, onNavigate, onLogout }) => {
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
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'users', label: 'User Management', icon: '👥' },
    { id: 'endpoints', label: 'Endpoint Management', icon: '🔗' },
    { id: 'analytics', label: 'Analytics', icon: '📈' },
    { id: 'balance', label: 'Balance & Usage', icon: '💰' },
    { id: 'logs', label: 'System Logs', icon: '📋' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
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
            {menuItems.slice(0, 3).map(item => (
              <li key={item.id} className={currentView === item.id ? 'active' : ''}>
                <button onClick={() => onNavigate(item.id)}>
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                  {currentView === item.id && <span className="active-indicator"></span>}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="nav-section">
          <h4>MANAGEMENT</h4>
          <ul>
            {menuItems.slice(3, 7).map(item => (
              <li key={item.id} className={currentView === item.id ? 'active' : ''}>
                <button onClick={() => onNavigate(item.id)}>
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                  {currentView === item.id && <span className="active-indicator"></span>}
                </button>
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