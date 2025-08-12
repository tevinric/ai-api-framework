import authService from '../services/authService';

export const isAuthenticated = () => {
  return authService.isAuthenticated();
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
  return authService.isLoginBypassEnabled();
};

export const getCurrentUser = () => {
  return authService.getCurrentUser();
};