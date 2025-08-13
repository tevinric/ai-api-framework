import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

console.log('[INDEX] Starting React application...');
console.log('[INDEX] Environment variables loaded:', {
  NODE_ENV: process.env.NODE_ENV,
  API_BASE_URL: process.env.REACT_APP_API_BASE_URL,
  ADMIN_EMAIL: process.env.REACT_APP_ADMIN_EMAIL
});

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

console.log('[INDEX] React application mounted successfully');