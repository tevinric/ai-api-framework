import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';

import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UserManagementPage from './pages/UserManagementPage';
import EndpointAccessPage from './pages/EndpointAccessPage';
import { isAuthenticated, isLoginDisabled } from './utils/auth';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
      light: '#42a5f5',
      dark: '#1565c0',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
  typography: {
    h4: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        },
      },
    },
  },
});

function App() {
  const loginDisabled = isLoginDisabled();
  const authenticated = isAuthenticated();
  
  // Debug logging
  console.log('App.js - Authentication state:', {
    loginDisabled,
    authenticated,
    env: process.env.REACT_APP_ENVIRONMENT,
    disableLogin: process.env.REACT_APP_DISABLE_LOGIN
  });

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Routes>
          <Route 
            path="/login" 
            element={
              loginDisabled || authenticated ? (
                (() => {
                  console.log('Redirecting from login to dashboard - loginDisabled:', loginDisabled, 'authenticated:', authenticated);
                  return <Navigate to="/" replace />;
                })()
              ) : (
                (() => {
                  console.log('Showing login page');
                  return <LoginPage />;
                })()
              )
            } 
          />
          
          <Route 
            path="/" 
            element={
              <ProtectedRoute>
                <Layout>
                  <DashboardPage />
                </Layout>
              </ProtectedRoute>
            } 
          />
          
          <Route 
            path="/users" 
            element={
              <ProtectedRoute>
                <Layout>
                  <UserManagementPage />
                </Layout>
              </ProtectedRoute>
            } 
          />
          
          <Route 
            path="/endpoints" 
            element={
              <ProtectedRoute>
                <Layout>
                  <EndpointAccessPage />
                </Layout>
              </ProtectedRoute>
            } 
          />
          
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;