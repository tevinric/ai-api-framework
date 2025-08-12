import React, { useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { isAuthenticated } from '../utils/auth';
import authService from '../services/authService';

const ProtectedRoute = ({ children }) => {
  useEffect(() => {
    // Start token refresh timer when protected route is accessed
    if (isAuthenticated() && !authService.isLoginBypassEnabled()) {
      authService.startTokenRefreshTimer();
    }
  }, []);

  return isAuthenticated() ? children : <Navigate to="/login" replace />;
};

export default ProtectedRoute;