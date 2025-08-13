import axios from 'axios';
import config from '../config/config';

console.log('[API_SERVICE] Initializing API service with base URL:', config.API_BASE_URL);

// Create axios instance with base configuration
const apiClient = axios.create({
  baseURL: config.API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  }
});

// Request interceptor for debugging
apiClient.interceptors.request.use(
  (request) => {
    console.log('[API_SERVICE] Making request:', {
      method: request.method?.toUpperCase(),
      url: request.url,
      headers: request.headers,
      data: request.data
    });
    return request;
  },
  (error) => {
    console.error('[API_SERVICE] Request error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for debugging
apiClient.interceptors.response.use(
  (response) => {
    console.log('[API_SERVICE] Response received:', {
      status: response.status,
      url: response.config.url,
      data: response.data
    });
    return response;
  },
  (error) => {
    console.error('[API_SERVICE] Response error:', {
      status: error.response?.status,
      url: error.config?.url,
      message: error.message,
      data: error.response?.data
    });
    return Promise.reject(error);
  }
);

// Admin API functions
export const adminAPI = {
  // Get user details by email (no authentication required)
  getUserDetails: async (email) => {
    console.log('[API_SERVICE] Getting user details for email:', email);
    try {
      const response = await apiClient.get('/admin/user-details', {
        params: { email }
      });
      console.log('[API_SERVICE] User details retrieved successfully:', response.data);
      return response.data;
    } catch (error) {
      console.error('[API_SERVICE] Failed to get user details:', error.response?.data || error.message);
      throw error;
    }
  },

  // Generate token using API key
  getToken: async (apiKey) => {
    console.log('[API_SERVICE] Requesting token with API key');
    try {
      const response = await apiClient.get('/token', {
        headers: {
          'API-Key': apiKey
        }
      });
      console.log('[API_SERVICE] Token generated successfully');
      return response.data;
    } catch (error) {
      console.error('[API_SERVICE] Failed to generate token:', error.response?.data || error.message);
      throw error;
    }
  },

  // Get all users (admin only)
  getAllUsers: async (apiKey, token) => {
    console.log('[API_SERVICE] Getting all users');
    try {
      const response = await apiClient.get('/admin/users', {
        headers: {
          'API-Key': apiKey
        },
        params: { token }
      });
      console.log('[API_SERVICE] All users retrieved successfully:', response.data.total_count, 'users');
      return response.data;
    } catch (error) {
      console.error('[API_SERVICE] Failed to get all users:', error.response?.data || error.message);
      throw error;
    }
  },

  // Create new user (admin only)
  createUser: async (apiKey, token, userData) => {
    console.log('[API_SERVICE] Creating new user:', userData.user_name);
    try {
      const response = await apiClient.post('/admin/user', userData, {
        headers: {
          'API-Key': apiKey
        },
        params: { token }
      });
      console.log('[API_SERVICE] User created successfully:', response.data.user_id);
      return response.data;
    } catch (error) {
      console.error('[API_SERVICE] Failed to create user:', error.response?.data || error.message);
      throw error;
    }
  },

  // Update user (admin only)
  updateUser: async (apiKey, token, userData) => {
    console.log('[API_SERVICE] Updating user:', userData.id);
    try {
      const response = await apiClient.put('/admin/user', userData, {
        headers: {
          'API-Key': apiKey
        },
        params: { token }
      });
      console.log('[API_SERVICE] User updated successfully:', response.data.updated_fields);
      return response.data;
    } catch (error) {
      console.error('[API_SERVICE] Failed to update user:', error.response?.data || error.message);
      throw error;
    }
  },

  // Delete user (admin only) - Note: This API seems to be commented out in backend
  deleteUser: async (apiKey, token, userId) => {
    console.log('[API_SERVICE] Deleting user:', userId);
    try {
      const response = await apiClient.delete('/admin/user', {
        headers: {
          'API-Key': apiKey
        },
        params: { token },
        data: { id: userId }
      });
      console.log('[API_SERVICE] User deleted successfully');
      return response.data;
    } catch (error) {
      console.error('[API_SERVICE] Failed to delete user:', error.response?.data || error.message);
      throw error;
    }
  }
};

export default apiClient;