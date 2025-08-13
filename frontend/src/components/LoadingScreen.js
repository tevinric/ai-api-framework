import React from 'react';
import './LoadingScreen.css';

const LoadingScreen = () => {
  console.log('[LOADING_SCREEN] Rendering loading screen');
  
  return (
    <div className="loading-screen">
      <div className="loading-content">
        <div className="spinner"></div>
        <h2>Loading Admin Portal</h2>
        <p>Authenticating user and initializing application...</p>
      </div>
    </div>
  );
};

export default LoadingScreen;