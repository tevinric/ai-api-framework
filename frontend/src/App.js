import React from 'react';
import { useAuth } from './hooks/useAuth';
import { useNavigation } from './hooks/useNavigation';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import MainContent from './components/MainContent';
import LoadingScreen from './components/LoadingScreen';
import ErrorScreen from './components/ErrorScreen';
import './App.css';

function App() {
  console.log('[APP] Application starting...');
  
  const { user, token, loading, error, logout, retry } = useAuth();
  const { currentView, navigateTo } = useNavigation();

  console.log('[APP] Current state:', {
    loading,
    hasUser: !!user,
    hasToken: !!token,
    hasError: !!error,
    currentView
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
      <Header user={user} currentView={currentView} onNavigate={navigateTo} />
      <Sidebar user={user} currentView={currentView} onNavigate={navigateTo} onLogout={logout} />
      <MainContent user={user} token={token} currentView={currentView} />
    </div>
  );
}

export default App;