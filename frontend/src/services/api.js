import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://dev-api.tihsa.co.za/ext/api/v1/gaia';

class ApiService {
  constructor() {
    this.api = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
    });

    this.apiKey = localStorage.getItem('adminApiKey') || '';
    this.token = localStorage.getItem('adminToken') || '';

    this.api.interceptors.request.use((config) => {
      // Check if login is disabled
      const disableLogin = process.env.REACT_APP_DISABLE_LOGIN === 'true';
      
      if (!disableLogin) {
        if (this.apiKey) {
          config.headers['API-Key'] = this.apiKey;
        }
        if (this.token) {
          config.headers['X-Token'] = this.token;
        }
      } else {
        // In bypass mode, you might want to set default/mock credentials
        config.headers['API-Key'] = 'dev-bypass-key';
        config.headers['X-Token'] = 'dev-bypass-token';
      }
      
      config.headers['X-Correlation-ID'] = this.generateCorrelationId();
      return config;
    });

    this.api.interceptors.response.use(
      (response) => response,
      (error) => {
        // Only redirect to login if login is not disabled
        const disableLogin = process.env.REACT_APP_DISABLE_LOGIN === 'true';
        
        if (error.response?.status === 401 && !disableLogin) {
          localStorage.removeItem('adminApiKey');
          localStorage.removeItem('adminToken');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  generateCorrelationId() {
    return 'admin-portal-' + Math.random().toString(36).substr(2, 9);
  }

  setCredentials(apiKey, token) {
    this.apiKey = apiKey;
    this.token = token;
    localStorage.setItem('adminApiKey', apiKey);
    localStorage.setItem('adminToken', token);
  }

  clearCredentials() {
    this.apiKey = '';
    this.token = '';
    localStorage.removeItem('adminApiKey');
    localStorage.removeItem('adminToken');
  }

  async createUser(userData) {
    const response = await this.api.post('/admin/user', userData, {
      params: { token: this.token }
    });
    return response.data;
  }

  async updateUser(userData) {
    const response = await this.api.put('/admin/user', userData, {
      params: { token: this.token }
    });
    return response.data;
  }

  async deleteUser(userId) {
    const response = await this.api.post('/admin/delete-user', { id: userId }, {
      params: { token: this.token }
    });
    return response.data;
  }

  async getAllUsers() {
    try {
      const response = await this.api.get('/admin/users', {
        params: { token: this.token }
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching users:', error);
      throw error;
    }
  }

  async getUserById(userId) {
    const response = await this.api.get(`/admin/user/${userId}`, {
      params: { token: this.token }
    });
    return response.data;
  }

  async searchUsersByName(commonName) {
    const response = await this.api.get('/admin/users/search', {
      params: { 
        token: this.token,
        common_name: commonName 
      }
    });
    return response.data;
  }

  async getUserEndpoints(userId) {
    const response = await this.api.get(`/admin/user/${userId}/endpoints`, {
      params: { token: this.token }
    });
    return response.data;
  }

  async getAllEndpoints() {
    const response = await this.api.get('/admin/endpoints', {
      params: { token: this.token }
    });
    return response.data;
  }

  async grantEndpointAccess(userId, endpointId) {
    const response = await this.api.post('/admin/endpoint/access/single', {
      user_id: userId,
      endpoint_id: endpointId
    });
    return response.data;
  }

  async grantMultipleEndpointAccess(userId, endpointIds) {
    const response = await this.api.post('/admin/endpoint/access/multi', {
      user_id: userId,
      endpoint_ids: endpointIds
    });
    return response.data;
  }

  async grantAllEndpointAccess(userId) {
    const response = await this.api.post('/admin/endpoint/access/all', {
      user_id: userId
    });
    return response.data;
  }

  async removeEndpointAccess(userId, endpointId) {
    const response = await this.api.delete('/admin/endpoint/access/single', {
      params: {
        user_id: userId,
        endpoint_id: endpointId
      }
    });
    return response.data;
  }

  async removeMultipleEndpointAccess(userId, endpointIds) {
    const response = await this.api.delete('/admin/endpoint/access/multi', {
      data: {
        user_id: userId,
        endpoint_ids: endpointIds
      }
    });
    return response.data;
  }

  async removeAllEndpointAccess(userId) {
    const response = await this.api.delete('/admin/endpoint/access/all', {
      params: { user_id: userId }
    });
    return response.data;
  }

  async validateCredentials(apiKey, token) {
    // If login is disabled, always return true
    const disableLogin = process.env.REACT_APP_DISABLE_LOGIN === 'true';
    if (disableLogin) {
      return true;
    }

    try {
      const tempApi = axios.create({
        baseURL: API_BASE_URL,
        headers: {
          'API-Key': apiKey,
          'X-Token': token,
          'X-Correlation-ID': this.generateCorrelationId()
        }
      });

      const response = await tempApi.get('/admin/users', {
        params: { token: token }
      });
      
      return response.status === 200;
    } catch (error) {
      return false;
    }
  }
}

const apiService = new ApiService();
export default apiService;