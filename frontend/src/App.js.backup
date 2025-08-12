import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { MsalProvider } from "@azure/msal-react";

import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UserManagementPage from './pages/UserManagementPage';
import EndpointAccessPage from './pages/EndpointAccessPage';
import { isAuthenticated, isLoginDisabled } from './utils/auth';
import { msalInstance } from './services/authService';

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

  const AppContent = () => (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Routes>
          <Route 
            path="/login" 
            element={
              loginDisabled || isAuthenticated() ? 
                <Navigate to="/" replace /> : 
                <LoginPage />
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

  // Only wrap with MsalProvider in production mode
  if (loginDisabled) {
    return <AppContent />;
  } else {
    return (
      <MsalProvider instance={msalInstance}>
        <AppContent />
      </MsalProvider>
    );
  }
}

export default App;