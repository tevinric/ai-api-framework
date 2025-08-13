import React, { useState } from 'react';
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [user, setUser] = useState(null);

  const handleLogin = React.useCallback(async () => {
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      console.log('Starting login process...');
      console.log('API Base URL:', API_BASE_URL);
      console.log('Dev User Email:', DEV_USER_EMAIL);

      // Step 1: Get user details - Try different endpoint paths
      const possibleEndpoints = [
        '/admin/user-details'
      ];
      
      let userResponse = null;
      let workingUrl = '';
      
      for (const endpoint of possibleEndpoints) {
        const testUrl = `${API_BASE_URL}${endpoint}?email=${encodeURIComponent(DEV_USER_EMAIL)}`;
        console.log(`Trying URL: ${testUrl}`);
        
        try {
          const response = await fetch(testUrl, {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
            }
          });
          
          console.log(`Response status for ${endpoint}:`, response.status);
          
          if (response.ok) {
            userResponse = response;
            workingUrl = testUrl;
            console.log(`✅ Success! Working endpoint: ${endpoint}`);
            break;
          } else if (response.status !== 404) {
            // If it's not 404, it might be the right endpoint but with different error (e.g., 401, 500)
            const errorText = await response.text();
            console.log(`❓ Non-404 error for ${endpoint}:`, response.status, errorText);
            userResponse = response;
            workingUrl = testUrl;
            break;
          }
        } catch (error) {
          console.log(`❌ Network error for ${endpoint}:`, error.message);
        }
      }
      
      if (!userResponse) {
        throw new Error('Unable to find working admin endpoint. All endpoints returned 404 or network errors.');
      }
      
      console.log('Using URL:', workingUrl);
      console.log('Response status:', userResponse.status);
      console.log('Response headers:', Object.fromEntries(userResponse.headers.entries()));
      
      if (!userResponse.ok) {
        const errorText = await userResponse.text();
        console.log('Error response body:', errorText);
        console.log('Response status text:', userResponse.statusText);
        throw new Error(`User lookup failed: ${userResponse.status} (${userResponse.statusText}) - ${errorText}`);
      }

      const userData = await userResponse.json();
      console.log('User data received:', userData);

      if (userData.scope !== 0) {
        throw new Error('User does not have admin privileges (scope must be 0)');
      }

      // Step 2: Generate token
      const tokenResponse = await fetch(`${API_BASE_URL}/token`, {
        headers: {
          'API-Key': userData.api_key,
          'Content-Type': 'application/json'
        }
      });

      if (!tokenResponse.ok) {
        throw new Error(`Token generation failed: ${tokenResponse.status}`);
      }

      const tokenData = await tokenResponse.json();
      console.log('Token generated successfully');

      // Step 3: Store credentials
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
  }, []);

  // Check if already logged in or auto-login in dev mode
  React.useEffect(() => {
    const currentUser = localStorage.getItem('currentUser');
    if (currentUser) {
      setUser(JSON.parse(currentUser));
    } else if (IS_DEV_MODE) {
      // Auto-login in development mode
      console.log('Development mode detected - auto-logging in...');
      handleLogin();
    }
  }, [handleLogin]);

  const handleLogout = () => {
    localStorage.removeItem('adminApiKey');
    localStorage.removeItem('adminToken');
    localStorage.removeItem('currentUser');
    setUser(null);
    setSuccess('');
    setError('');
  };

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

  // Show login page
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container component="main" maxWidth="sm">
        <Box sx={{ marginTop: 8, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Paper elevation={3} sx={{ padding: 4, width: '100%' }}>
            <Typography component="h1" variant="h4" align="center" gutterBottom>
              AI API Admin Portal
            </Typography>
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
                {loading ? (
                  <CircularProgress size={24} />
                ) : (
                  IS_DEV_MODE ? 'Continue as Test User' : 'Sign In with Azure AD'
                )}
              </Button>

              {!IS_DEV_MODE && (
                <Typography variant="body2" align="center" sx={{ mt: 2 }}>
                  You will be redirected to Azure Active Directory to authenticate.
                  Only authorized admin users can access this portal.
                </Typography>
              )}
            </Box>
          </Paper>
        </Box>
      </Container>
    </ThemeProvider>
  );
}

export default App;