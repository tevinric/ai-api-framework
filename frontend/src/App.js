import React from 'react';
import { useAuth } from './hooks/useAuth';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import MainContent from './components/MainContent';
import LoadingScreen from './components/LoadingScreen';
import ErrorScreen from './components/ErrorScreen';
import './App.css';

function App() {
  console.log('[APP] Application starting...');
  
  const { user, token, loading, error, logout, retry } = useAuth();

  console.log('[APP] Current state:', {
    loading,
    hasUser: !!user,
    hasToken: !!token,
    hasError: !!error
  });

  // Show loading screen while authenticating
  if (loading) {
    return <LoadingScreen />;
  }

  // Show error screen if authentication failed
  if (error || !user || !token) {
    return <ErrorScreen error={error || 'Authentication failed'} onRetry={retry} />;
  }

  // Show main application
  console.log('[APP] Rendering main application interface');
  return (
    <div className="app">
      <Header user={user} />
      <Sidebar user={user} onLogout={logout} />
      <MainContent user={user} token={token} />
    </div>
  );
}

export default App;