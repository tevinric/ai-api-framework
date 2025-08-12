import React from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Typography, Container } from '@mui/material';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
  },
});

function TestApp() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container>
        <Typography variant="h4" component="h1" gutterBottom>
          Test App - Basic Rendering
        </Typography>
        <Typography variant="body1">
          If you can see this, the basic React app is working.
        </Typography>
        <Typography variant="body2" color="textSecondary">
          API Base URL: {process.env.REACT_APP_API_BASE_URL || 'https://dev-api.tihsa.co.za/ext/api/v1/gaia'}
        </Typography>
        <Typography variant="body2" color="textSecondary">
          Environment: {process.env.REACT_APP_ENVIRONMENT || 'Not Set'}
        </Typography>
        <Typography variant="body2" color="textSecondary">
          Disable Login: {process.env.REACT_APP_DISABLE_LOGIN || 'Not Set'}
        </Typography>
      </Container>
    </ThemeProvider>
  );
}

export default TestApp;