export const isAuthenticated = () => {
  const isLoginBypassEnabled = process.env.REACT_APP_DISABLE_LOGIN === 'true';
  
  if (isLoginBypassEnabled) {
    const hasUser = localStorage.getItem('currentUser') !== null;
    const hasApiKey = localStorage.getItem('adminApiKey') !== null;
    const hasToken = localStorage.getItem('adminToken') !== null;
    return hasUser && hasApiKey && hasToken;
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
  localStorage.removeItem('currentUser');
};

export const isLoginDisabled = () => {
  return process.env.REACT_APP_DISABLE_LOGIN === 'true';
};

export const getCurrentUser = () => {
  const userString = localStorage.getItem('currentUser');
  return userString ? JSON.parse(userString) : null;
};