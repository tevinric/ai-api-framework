import { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../services/apiService';
import config from '../config/config';

export const useAuth = () => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  console.log('[USE_AUTH] Hook initialized');

  // Initialize authentication on component mount
  useEffect(() => {
    console.log('[USE_AUTH] Starting authentication process...');
    initializeAuth();
  }, []);

  const initializeAuth = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('[USE_AUTH] Getting admin email from config:', config.ADMIN_EMAIL);
      
      // Step 1: Get user details using email from .env
      console.log('[USE_AUTH] Step 1: Fetching user details...');
      const userDetails = await adminAPI.getUserDetails(config.ADMIN_EMAIL);
      
      // Step 2: Validate user scope (must be 0 for admin access)
      console.log('[USE_AUTH] Step 2: Validating user scope...');
      if (userDetails.scope !== 0) {
        const errorMsg = 'User is not authorized to access this admin portal';
        console.error('[USE_AUTH]', errorMsg);
        throw new Error(errorMsg);
      }
      
      console.log('[USE_AUTH] User scope validation passed. User details:', {
        user_id: userDetails.user_id,
        user_name: userDetails.user_name,
        department: userDetails.department,
        scope: userDetails.scope
      });
      
      // Step 3: Generate token using API key
      console.log('[USE_AUTH] Step 3: Generating authentication token...');
      const tokenData = await adminAPI.getToken(userDetails.api_key);
      
      console.log('[USE_AUTH] Token generated successfully:', {
        token_type: tokenData.token_type,
        expires_in: tokenData.expires_in,
        expires_on: tokenData.expires_on
      });
      
      // Step 4: Set user and token in state
      setUser(userDetails);
      setToken(tokenData.access_token);
      
      console.log('[USE_AUTH] Authentication completed successfully');
      
    } catch (err) {
      console.error('[USE_AUTH] Authentication failed:', err);
      setError(err.message || 'Authentication failed');
      setUser(null);
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    console.log('[USE_AUTH] Logging out user...');
    setUser(null);
    setToken(null);
    setError(null);
  }, []);

  return {
    user,
    token,
    loading,
    error,
    logout,
    retry: initializeAuth
  };
};