export const isAuthenticated = () => {
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