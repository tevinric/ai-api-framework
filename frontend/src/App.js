import React, { useState, useEffect } from 'react';
import { 
  Container, 
  Paper, 
  Button, 
  Typography, 
  Box, 
  Alert,
  CircularProgress,
  ThemeProvider,
  createTheme,
  CssBaseline
} from '@mui/material';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
  },
});

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';
const DEV_USER_EMAIL = process.env.REACT_APP_DEV_USER_EMAIL || 'gaiatester@test.com';
const IS_DEV_MODE = process.env.REACT_APP_DISABLE_LOGIN === 'true';

function App() {
  const [loading, setLoading] = useState(IS_DEV_MODE); // Start loading if in dev mode
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [user, setUser] = useState(null);

  const handleLogin = async () => {
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      console.log('Starting login process...');
      console.log('API Base URL:', API_BASE_URL);
      console.log('Dev User Email:', DEV_USER_EMAIL);

      // Try to get user details from the admin endpoint
      const userUrl = `${API_BASE_URL}/admin/user-details?email=${encodeURIComponent(DEV_USER_EMAIL)}`;
      console.log('Fetching user from:', userUrl);
      
      const userResponse = await fetch(userUrl, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      console.log('User response status:', userResponse.status);

      if (!userResponse.ok) {
        const errorText = await userResponse.text();
        console.log('User lookup error:', errorText);
        throw new Error(`User lookup failed: ${userResponse.status} - ${errorText}`);
      }

      const userData = await userResponse.json();
      console.log('User data received:', userData);

      if (userData.scope !== 0) {
        throw new Error(`User does not have admin privileges. Current scope: ${userData.scope}, required scope: 0`);
      }

      // Generate token using user's API key
      console.log('Generating token...');
      const tokenResponse = await fetch(`${API_BASE_URL}/token`, {
        headers: {
          'API-Key': userData.api_key,
          'Content-Type': 'application/json'
        }
      });

      if (!tokenResponse.ok) {
        const tokenError = await tokenResponse.text();
        console.log('Token generation error:', tokenError);
        throw new Error(`Token generation failed: ${tokenResponse.status} - ${tokenError}`);
      }

      const tokenData = await tokenResponse.json();
      console.log('Token generated successfully');

      // Store credentials in localStorage
      localStorage.setItem('adminApiKey', userData.api_key);
      localStorage.setItem('adminToken', tokenData.access_token);
      localStorage.setItem('currentUser', JSON.stringify(userData));

      setUser(userData);
      setSuccess('Login successful! Welcome to the Admin Portal.');

    } catch (error) {
      console.error('Login error:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('adminApiKey');
    localStorage.removeItem('adminToken');
    localStorage.removeItem('currentUser');
    setUser(null);
    setSuccess('');
    setError('');
  };

  // Check if already logged in, or auto-login in dev mode
  useEffect(() => {
    const currentUser = localStorage.getItem('currentUser');
    if (currentUser) {
      setUser(JSON.parse(currentUser));
      setLoading(false);
    } else if (IS_DEV_MODE) {
      // Auto-login in development mode
      console.log('Development mode detected - auto-logging in...');
      handleLogin();
    } else {
      setLoading(false);
    }
  }, []);

  // If logged in, show dashboard
  if (user) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Container maxWidth="md" sx={{ mt: 4 }}>
          <Paper elevation={3} sx={{ p: 4 }}>
            <Typography variant="h4" gutterBottom>
              AI API Admin Portal - Dashboard
            </Typography>
            
            <Alert severity="success" sx={{ mb: 3 }}>
              Successfully logged in as admin user!
            </Alert>

            <Box sx={{ mb: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Typography variant="h6" gutterBottom>User Information:</Typography>
              <Typography><strong>Name:</strong> {user.common_name || user.user_name}</Typography>
              <Typography><strong>Email:</strong> {user.user_email}</Typography>
              <Typography><strong>Department:</strong> {user.department || 'N/A'}</Typography>
              <Typography><strong>Company:</strong> {user.company || 'N/A'}</Typography>
              <Typography><strong>Scope:</strong> {user.scope} (Admin)</Typography>
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom>Admin Functions:</Typography>
              <Typography>• User Management</Typography>
              <Typography>• Endpoint Access Control</Typography>
              <Typography>• System Administration</Typography>
            </Box>

            <Button 
              variant="outlined" 
              onClick={handleLogout}
              color="secondary"
            >
              Logout
            </Button>
          </Paper>
        </Container>
      </ThemeProvider>
    );
  }

  // Show loading screen during auto-login or login page
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container component="main" maxWidth="sm">
        <Box sx={{ marginTop: 8, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Paper elevation={3} sx={{ padding: 4, width: '100%' }}>
            <Typography component="h1" variant="h4" align="center" gutterBottom>
              AI API Admin Portal
            </Typography>
            
            {loading ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mt: 3 }}>
                <CircularProgress sx={{ mb: 2 }} />
                <Typography>
                  {IS_DEV_MODE ? 'Authenticating in development mode...' : 'Loading...'}
                </Typography>
              </Box>
            ) : (
              <>
                <Typography component="h2" variant="h6" align="center" color="textSecondary" gutterBottom>
                  {IS_DEV_MODE ? 'Development Mode' : 'Sign in to continue'}
                </Typography>
                
                {IS_DEV_MODE && (
                  <Alert severity="info" sx={{ mb: 2 }}>
                    Development mode is active. Authentication will be bypassed using default test user.
                    <br />
                    <strong>API URL:</strong> {API_BASE_URL}
                    <br />
                    <strong>Test User:</strong> {DEV_USER_EMAIL}
                  </Alert>
                )}

                {error && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                  </Alert>
                )}

                {success && (
                  <Alert severity="success" sx={{ mb: 2 }}>
                    {success}
                  </Alert>
                )}

                <Box sx={{ mt: 2 }}>
                  <Button
                    fullWidth
                    variant="contained"
                    onClick={handleLogin}
                    disabled={loading}
                    sx={{ mt: 3, mb: 2 }}
                  >
                    {IS_DEV_MODE ? 'Continue as Test User' : 'Sign In with Azure AD'}
                  </Button>

                  {!IS_DEV_MODE && (
                    <Typography variant="body2" align="center" sx={{ mt: 2 }}>
                      You will be redirected to Azure Active Directory to authenticate.
                      Only authorized admin users can access this portal.
                    </Typography>
                  )}
                </Box>
              </>
            )}
          </Paper>
        </Box>
      </Container>
    </ThemeProvider>
  );
}

export default App;