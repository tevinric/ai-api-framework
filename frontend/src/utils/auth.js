export const isAuthenticated = () => {
  // Check if login is disabled via environment variable
  const disableLogin = process.env.REACT_APP_DISABLE_LOGIN === 'true';
  
  if (disableLogin) {
    return true;
  }
  
  const apiKey = localStorage.getItem('adminApiKey');
  const token = localStorage.getItem('adminToken');
  return !!(apiKey && token);
};

export const getStoredCredentials = () => {
  return {
    apiKey: localStorage.getItem('adminApiKey') || '',
    token: localStorage.getItem('adminToken') || ''
  };
};

export const clearStoredCredentials = () => {
  localStorage.removeItem('adminApiKey');
  localStorage.removeItem('adminToken');
};

export const isLoginDisabled = () => {
  return process.env.REACT_APP_DISABLE_LOGIN === 'true';
};