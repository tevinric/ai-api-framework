// Configuration file for the admin portal
console.log('[CONFIG] Loading application configuration...');

export const config = {
  API_BASE_URL: process.env.REACT_APP_API_BASE_URL || 'http://gaia.com',
  ADMIN_EMAIL: process.env.REACT_APP_ADMIN_EMAIL || 'admin@example.com',
};

console.log('[CONFIG] Configuration loaded:', {
  API_BASE_URL: config.API_BASE_URL,
  ADMIN_EMAIL: config.ADMIN_EMAIL
});

export default config;