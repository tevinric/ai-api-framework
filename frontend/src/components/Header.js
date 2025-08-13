import React from 'react';
import './Header.css';

const Header = ({ user, currentView, onNavigate }) => {
  console.log('[HEADER] Rendering header for user:', user?.user_name);

  const currentTime = new Date().toLocaleString();

  return (
    <header className="header">
      <div className="header-left">
        <div className="logo-section">
          <div className="logo-icon">🤖</div>
          <div className="logo-text">
            <h1>GAIA</h1>
            <span>Admin Portal</span>
          </div>
        </div>
      </div>

      <div className="header-center">
        <nav className="header-nav">
          <button 
            onClick={() => onNavigate('dashboard')} 
            className={`nav-link ${currentView === 'dashboard' ? 'active' : ''}`}
          >
            <span className="nav-icon">📊</span>
            Dashboard
          </button>
          <button 
            onClick={() => onNavigate('users')} 
            className={`nav-link ${currentView === 'users' ? 'active' : ''}`}
          >
            <span className="nav-icon">👥</span>
            Users
          </button>
          <button 
            onClick={() => onNavigate('models')} 
            className={`nav-link ${currentView === 'models' ? 'active' : ''}`}
          >
            <span className="nav-icon">🧠</span>
            Models
          </button>
          <button 
            onClick={() => onNavigate('analytics')} 
            className={`nav-link ${currentView === 'analytics' ? 'active' : ''}`}
          >
            <span className="nav-icon">📈</span>
            Analytics
          </button>
          <button 
            onClick={() => onNavigate('settings')} 
            className={`nav-link ${currentView === 'settings' ? 'active' : ''}`}
          >
            <span className="nav-icon">⚙️</span>
            Settings
          </button>
        </nav>
      </div>

      <div className="header-right">
        <div className="header-info">
          <div className="system-status">
            <span className="status-dot"></span>
            <span>System Online</span>
          </div>
          <div className="current-time">{currentTime}</div>
        </div>
        <div className="user-profile">
          <div className="user-avatar">{user?.user_name?.charAt(0)?.toUpperCase()}</div>
          <div className="user-details">
            <span className="user-name">{user?.user_name}</span>
            <span className="user-role">Administrator</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;