import { PublicClientApplication } from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";
import apiService from './api';

// MSAL configuration
const msalConfig = {
  auth: {
    clientId: process.env.REACT_APP_AZURE_CLIENT_ID || "your-client-id",
    authority: `https://login.microsoftonline.com/${process.env.REACT_APP_AZURE_TENANT_ID || "your-tenant-id"}`,
    redirectUri: process.env.REACT_APP_AZURE_REDIRECT_URI || window.location.origin
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  }
};

// Create MSAL instance
export const msalInstance = new PublicClientApplication(msalConfig);

// Login request configuration
const loginRequest = {
  scopes: ["openid", "profile", "email"],
};

class AuthService {
  constructor() {
    this.isDevelopment = process.env.REACT_APP_ENVIRONMENT === 'DEV';
    this.disableLogin = process.env.REACT_APP_DISABLE_LOGIN === 'true';
    this.devUserEmail = process.env.REACT_APP_DEV_USER_EMAIL || 'gaiatester@test.com';
  }

  // Check if we're in development mode with login bypass
  isLoginBypassEnabled() {
    return this.isDevelopment && this.disableLogin;
  }

  // Get current authentication state
  isAuthenticated() {
    if (this.isLoginBypassEnabled()) {
      return true;
    }
    
    const accounts = msalInstance.getAllAccounts();
    const hasValidTokens = localStorage.getItem('adminApiKey') && localStorage.getItem('adminToken');
    
    return accounts.length > 0 && hasValidTokens;
  }

  // Handle login process
  async login() {
    try {
      if (this.isLoginBypassEnabled()) {
        // Development mode - bypass authentication
        console.log('Development mode: bypassing authentication');
        
        // Try to get user details and validate admin access
        const userDetails = await this.validateDevUser();
        if (userDetails) {
          // Store the API key and generate token
          await this.setupDevAuthentication(userDetails);
          return { success: true, user: userDetails };
        } else {
          return { 
            success: false, 
            error: 'Development user not found or not authorized for admin access' 
          };
        }
      } else {
        // Production mode - use Azure AD
        const loginResponse = await msalInstance.loginPopup(loginRequest);
        console.log('Azure AD login successful:', loginResponse);
        
        // Get user email from Azure AD response
        const userEmail = loginResponse.account.username;
        
        // Validate user has admin access
        const userDetails = await this.validateAdminUser(userEmail);
        if (userDetails) {
          // Generate and store tokens
          await this.setupProdAuthentication(userDetails);
          return { success: true, user: userDetails };
        } else {
          // User doesn't have admin access, logout from Azure
          await this.logout();
          return { 
            success: false, 
            error: 'You are not authorized to access this application' 
          };
        }
      }
    } catch (error) {
      console.error('Login error:', error);
      return { 
        success: false, 
        error: error.message || 'Login failed' 
      };
    }
  }

  // Validate development user
  async validateDevUser() {
    try {
      console.log('Validating dev user:', this.devUserEmail);
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/admin/user-details?email=${encodeURIComponent(this.devUserEmail)}`);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Dev user validation response:', data);
        
        // Check if user has admin scope (scope = 0)
        if (data.scope !== 0) {
          console.log('Dev user does not have admin scope:', data.scope);
          return null;
        }
        
        return data;
      } else {
        console.log('Dev user validation failed with status:', response.status);
        return null;
      }
    } catch (error) {
      console.error('Error validating dev user:', error);
      return null;
    }
  }

  // Validate admin user for production
  async validateAdminUser(email) {
    try {
      console.log('Validating admin user:', email);
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/admin/user-details?email=${encodeURIComponent(email)}`);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Admin user validation response:', data);
        
        // Check if user has admin scope (scope = 0)
        if (data.scope !== 0) {
          console.log('User does not have admin scope:', data.scope);
          return null;
        }
        
        return data;
      } else {
        console.log('Admin user validation failed with status:', response.status);
        return null;
      }
    } catch (error) {
      console.error('Error validating admin user:', error);
      return null;
    }
  }

  // Setup authentication for development
  async setupDevAuthentication(userDetails) {
    try {
      // Generate token using the user's API key
      const tokenResponse = await fetch(`${process.env.REACT_APP_API_BASE_URL}/token`, {
        headers: {
          'API-Key': userDetails.api_key,
          'Content-Type': 'application/json'
        }
      });

      if (tokenResponse.ok) {
        const tokenData = await tokenResponse.json();
        
        // Store credentials
        apiService.setCredentials(userDetails.api_key, tokenData.access_token);
        
        // Store user details
        localStorage.setItem('currentUser', JSON.stringify(userDetails));
        
        console.log('Development authentication setup complete');
      } else {
        throw new Error('Failed to generate token');
      }
    } catch (error) {
      console.error('Error setting up dev authentication:', error);
      throw error;
    }
  }

  // Setup authentication for production
  async setupProdAuthentication(userDetails) {
    try {
      // Generate token using the user's API key
      const tokenResponse = await fetch(`${process.env.REACT_APP_API_BASE_URL}/token`, {
        headers: {
          'API-Key': userDetails.api_key,
          'Content-Type': 'application/json'
        }
      });

      if (tokenResponse.ok) {
        const tokenData = await tokenResponse.json();
        
        // Store credentials
        apiService.setCredentials(userDetails.api_key, tokenData.access_token);
        
        // Store user details
        localStorage.setItem('currentUser', JSON.stringify(userDetails));
        
        console.log('Production authentication setup complete');
      } else {
        throw new Error('Failed to generate token');
      }
    } catch (error) {
      console.error('Error setting up prod authentication:', error);
      throw error;
    }
  }

  // Handle logout
  async logout() {
    try {
      // Clear stored credentials
      apiService.clearCredentials();
      localStorage.removeItem('currentUser');
      
      if (!this.isLoginBypassEnabled()) {
        // Production mode - logout from Azure AD
        const accounts = msalInstance.getAllAccounts();
        if (accounts.length > 0) {
          await msalInstance.logoutPopup();
        }
      }
      
      console.log('Logout successful');
    } catch (error) {
      console.error('Logout error:', error);
    }
  }

  // Get current user details
  getCurrentUser() {
    const userString = localStorage.getItem('currentUser');
    return userString ? JSON.parse(userString) : null;
  }

  // Check and refresh token if needed
  async checkAndRefreshToken() {
    try {
      const user = this.getCurrentUser();
      if (!user || !user.api_key) {
        return false;
      }

      // Try to get token details to check if it's valid
      const storedToken = localStorage.getItem('adminToken');
      if (!storedToken) {
        return false;
      }

      const tokenResponse = await fetch(`${process.env.REACT_APP_API_BASE_URL}/token-details`, {
        headers: {
          'API-Key': user.api_key,
          'Content-Type': 'application/json'
        },
        method: 'POST',
        body: JSON.stringify({ token: storedToken })
      });

      if (tokenResponse.ok) {
        const tokenDetails = await tokenResponse.json();
        
        // Check if token is near expiration (refresh if less than 5 minutes left)
        const expirationTime = new Date(tokenDetails.expires_on);
        const now = new Date();
        const timeUntilExpiration = expirationTime - now;
        const fiveMinutes = 5 * 60 * 1000;
        
        if (timeUntilExpiration <= fiveMinutes) {
          console.log('Token near expiration, refreshing...');
          
          // Refresh token
          const refreshResponse = await fetch(`${process.env.REACT_APP_API_BASE_URL}/refresh-token`, {
            headers: {
              'API-Key': user.api_key,
              'Content-Type': 'application/json'
            },
            method: 'POST',
            body: JSON.stringify({ token: storedToken })
          });

          if (refreshResponse.ok) {
            const newTokenData = await refreshResponse.json();
            localStorage.setItem('adminToken', newTokenData.access_token);
            
            // Update session state with token details
            const tokenExpiration = new Date(Date.now() + (newTokenData.expires_in * 1000));
            sessionStorage.setItem('tokenExpiration', tokenExpiration.toISOString());
            sessionStorage.setItem('tokenLastRefresh', new Date().toISOString());
            
            console.log('Token refreshed successfully');
            return true;
          }
        }
        
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Error checking/refreshing token:', error);
      return false;
    }
  }

  // Initialize automatic token refresh checking
  startTokenRefreshTimer() {
    // Check token every 4 minutes (240000 ms)
    setInterval(() => {
      this.checkAndRefreshToken();
    }, 240000);
  }
}

export default new AuthService();