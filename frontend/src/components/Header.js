import React from 'react';
import './Header.css';

const Header = ({ user }) => {
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
          <a href="#dashboard" className="nav-link active">
            <span className="nav-icon">📊</span>
            Dashboard
          </a>
          <a href="#users" className="nav-link">
            <span className="nav-icon">👥</span>
            Users
          </a>
          <a href="#models" className="nav-link">
            <span className="nav-icon">🧠</span>
            Models
          </a>
          <a href="#analytics" className="nav-link">
            <span className="nav-icon">📈</span>
            Analytics
          </a>
          <a href="#settings" className="nav-link">
            <span className="nav-icon">⚙️</span>
            Settings
          </a>
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