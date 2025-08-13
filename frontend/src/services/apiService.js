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

  // Delete user (admin only)
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

// Endpoint Management API
export const endpointAPI = {
  // Get all endpoints (admin only)
  getAllEndpoints: async (apiKey, token) => {
    console.log('[ENDPOINT_API] Getting all endpoints');
    try {
      const response = await apiClient.get('/admin/endpoints', {
        headers: {
          'API-Key': apiKey
        },
        params: { token }
      });
      console.log('[ENDPOINT_API] All endpoints retrieved successfully:', response.data.count, 'endpoints');
      return response.data;
    } catch (error) {
      console.error('[ENDPOINT_API] Failed to get all endpoints:', error.response?.data || error.message);
      throw error;
    }
  },

  // Create endpoint (admin only)
  createEndpoint: async (apiKey, token, endpointData) => {
    console.log('[ENDPOINT_API] Creating endpoint:', endpointData.endpoint_name);
    try {
      const response = await apiClient.post('/admin/endpoint', endpointData, {
        headers: {
          'API-Key': apiKey
        },
        params: { token }
      });
      console.log('[ENDPOINT_API] Endpoint created successfully');
      return response.data;
    } catch (error) {
      console.error('[ENDPOINT_API] Failed to create endpoint:', error.response?.data || error.message);
      throw error;
    }
  },

  // Update endpoint (admin only)
  updateEndpoint: async (apiKey, token, endpointData) => {
    console.log('[ENDPOINT_API] Updating endpoint:', endpointData.endpoint_id);
    try {
      const response = await apiClient.put('/admin/endpoint', endpointData, {
        headers: {
          'API-Key': apiKey
        },
        params: { token }
      });
      console.log('[ENDPOINT_API] Endpoint updated successfully');
      return response.data;
    } catch (error) {
      console.error('[ENDPOINT_API] Failed to update endpoint:', error.response?.data || error.message);
      throw error;
    }
  },

  // Delete endpoint (admin only)
  deleteEndpoint: async (apiKey, token, endpointId) => {
    console.log('[ENDPOINT_API] Deleting endpoint:', endpointId);
    try {
      const response = await apiClient.delete('/admin/endpoint', {
        headers: {
          'API-Key': apiKey
        },
        params: { token },
        data: { endpoint_id: endpointId }
      });
      console.log('[ENDPOINT_API] Endpoint deleted successfully');
      return response.data;
    } catch (error) {
      console.error('[ENDPOINT_API] Failed to delete endpoint:', error.response?.data || error.message);
      throw error;
    }
  }
};

// RBAC API
export const rbacAPI = {
  // Get all user endpoint access (admin only)
  getUserEndpointAccess: async (apiKey, token) => {
    console.log('[RBAC_API] Getting all user endpoint access');
    try {
      const response = await apiClient.get('/admin/endpoint/access', {
        headers: {
          'API-Key': apiKey
        },
        params: { token }
      });
      console.log('[RBAC_API] User endpoint access retrieved successfully');
      return response.data;
    } catch (error) {
      console.error('[RBAC_API] Failed to get user endpoint access:', error.response?.data || error.message);
      throw error;
    }
  },

  // Remove multiple endpoint access for users (admin only)
  removeMultipleEndpointAccess: async (apiKey, token, accessData) => {
    console.log('[RBAC_API] Removing multiple endpoint access:', accessData);
    try {
      const response = await apiClient.delete('/admin/endpoint/access/multi', {
        headers: {
          'API-Key': apiKey
        },
        params: { token },
        data: accessData
      });
      console.log('[RBAC_API] Multiple endpoint access removed successfully');
      return response.data;
    } catch (error) {
      console.error('[RBAC_API] Failed to remove multiple endpoint access:', error.response?.data || error.message);
      throw error;
    }
  }
};

export default apiClient;