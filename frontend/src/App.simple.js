import React from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Typography, Container, Button, Alert } from '@mui/material';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
  },
});

function App() {
  const [showAlert, setShowAlert] = React.useState(false);
  
  const testEnvironment = () => {
    setShowAlert(true);
    console.log('Environment Variables:');
    console.log('REACT_APP_API_BASE_URL:', process.env.REACT_APP_API_BASE_URL);
    console.log('REACT_APP_ENVIRONMENT:', process.env.REACT_APP_ENVIRONMENT);
    console.log('REACT_APP_DISABLE_LOGIN:', process.env.REACT_APP_DISABLE_LOGIN);
    console.log('REACT_APP_DEV_USER_EMAIL:', process.env.REACT_APP_DEV_USER_EMAIL);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          AI API Admin Portal - Debugging
        </Typography>
        
        <Typography variant="h6" gutterBottom>
          Basic App Rendering Test
        </Typography>
        
        <Typography variant="body1" paragraph>
          If you can see this page, the basic React app is working properly.
        </Typography>

        {showAlert && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Environment variables logged to console. Press F12 to view.
          </Alert>
        )}

        <Button 
          variant="contained" 
          onClick={testEnvironment}
          sx={{ mb: 2 }}
        >
          Test Environment Variables
        </Button>

        <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
          Current Configuration:
        </Typography>
        
        <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 1 }}>
          <strong>API Base URL:</strong> {process.env.REACT_APP_API_BASE_URL || 'https://dev-api.tihsa.co.za/ext/api/v1/gaia'}
        </Typography>
        
        <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 1 }}>
          <strong>Environment:</strong> {process.env.REACT_APP_ENVIRONMENT || 'Not Set'}
        </Typography>
        
        <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 1 }}>
          <strong>Disable Login:</strong> {process.env.REACT_APP_DISABLE_LOGIN || 'Not Set'}
        </Typography>
        
        <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 1 }}>
          <strong>Dev User Email:</strong> {process.env.REACT_APP_DEV_USER_EMAIL || 'Not Set'}
        </Typography>

        <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
          Next Steps:
        </Typography>
        
        <Typography variant="body2" component="div">
          1. Verify the environment variables are correct<br/>
          2. Test API connectivity<br/>
          3. Enable authentication system<br/>
          4. Test full application flow
        </Typography>
      </Container>
    </ThemeProvider>
  );
}

export default App;