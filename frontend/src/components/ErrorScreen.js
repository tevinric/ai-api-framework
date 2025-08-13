import React from 'react';
import './ErrorScreen.css';

const ErrorScreen = ({ error, onRetry }) => {
  console.log('[ERROR_SCREEN] Rendering error screen with error:', error);
  
  return (
    <div className="error-screen">
      <div className="error-content">
        <div className="error-icon">⚠️</div>
        <h2>Access Denied</h2>
        <p className="error-message">{error}</p>
        <div className="error-details">
          <p>This could happen if:</p>
          <ul>
            <li>Your email is not configured correctly in the .env file</li>
            <li>Your user account doesn't have admin privileges (scope must be 0)</li>
            <li>The backend API is not accessible</li>
            <li>Network connectivity issues</li>
          </ul>
        </div>
        <button onClick={onRetry} className="retry-button">
          Retry Authentication
        </button>
      </div>
    </div>
  );
};

export default ErrorScreen;