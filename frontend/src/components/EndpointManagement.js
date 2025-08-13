import React, { useState, useEffect, useMemo } from 'react';
import { endpointAPI } from '../services/apiService';
import './EndpointManagement.css';

const EndpointManagement = ({ user, token }) => {
  console.log('[ENDPOINT_MANAGEMENT] Initializing Endpoint Management component');
  
  const [endpoints, setEndpoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedEndpoint, setSelectedEndpoint] = useState(null);
  const [showEndpointModal, setShowEndpointModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Load all endpoints on component mount
  useEffect(() => {
    console.log('[ENDPOINT_MANAGEMENT] Loading endpoints...');
    loadEndpoints();
  }, [refreshTrigger]);

  const loadEndpoints = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('[ENDPOINT_MANAGEMENT] Fetching endpoints from API...');
      
      const response = await endpointAPI.getAllEndpoints(user.api_key, token);
      setEndpoints(response.endpoints || []);
      console.log('[ENDPOINT_MANAGEMENT] Endpoints loaded successfully:', response.endpoints?.length || 0, 'endpoints');
    } catch (err) {
      console.error('[ENDPOINT_MANAGEMENT] Failed to load endpoints:', err);
      setError(err.response?.data?.message || 'Failed to load endpoints');
    } finally {
      setLoading(false);
    }
  };

  // Filter endpoints based on search term
  const filteredEndpoints = useMemo(() => {
    if (!searchTerm) return endpoints;
    
    const term = searchTerm.toLowerCase();
    return endpoints.filter(endpoint => 
      endpoint.endpoint_name?.toLowerCase().includes(term) ||
      endpoint.endpoint_path?.toLowerCase().includes(term) ||
      endpoint.id?.toLowerCase().includes(term) ||
      endpoint.description?.toLowerCase().includes(term)
    );
  }, [endpoints, searchTerm]);

  const handleEndpointClick = (clickedEndpoint) => {
    console.log('[ENDPOINT_MANAGEMENT] Endpoint clicked:', clickedEndpoint.endpoint_name);
    setSelectedEndpoint(clickedEndpoint);
    setShowEndpointModal(true);
  };

  const handleRefresh = () => {
    console.log('[ENDPOINT_MANAGEMENT] Refreshing endpoint list...');
    setRefreshTrigger(prev => prev + 1);
  };

  const getStatusClass = (active) => {
    return active ? 'status-active' : 'status-inactive';
  };

  const getStatusLabel = (active) => {
    return active ? 'Active' : 'Inactive';
  };

  if (loading && endpoints.length === 0) {
    return (
      <div className="endpoint-management">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading endpoints...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="endpoint-management">
      <div className="endpoint-management-header">
        <div className="header-content">
          <h1>Endpoint Management</h1>
          <p>Manage API endpoints, costs, and access control</p>
        </div>
        <div className="header-actions">
          <button 
            className="btn btn-primary" 
            onClick={() => setShowCreateModal(true)}
          >
            <span className="btn-icon">🔗</span>
            Add New Endpoint
          </button>
          <button 
            className="btn btn-secondary" 
            onClick={handleRefresh}
            disabled={loading}
          >
            <span className="btn-icon">🔄</span>
            Refresh
          </button>
        </div>
      </div>

      <div className="endpoint-management-controls">
        <div className="search-section">
          <div className="search-container">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              placeholder="Search by name, path, ID, or description..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
            {searchTerm && (
              <button 
                className="clear-search"
                onClick={() => setSearchTerm('')}
              >
                ✕
              </button>
            )}
          </div>
        </div>

        <div className="stats-bar">
          <div className="stat-item">
            <span className="stat-label">Total Endpoints:</span>
            <span className="stat-value">{endpoints.length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Filtered:</span>
            <span className="stat-value">{filteredEndpoints.length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Active:</span>
            <span className="stat-value">
              {endpoints.filter(e => e.active).length}
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Free Endpoints:</span>
            <span className="stat-value">
              {endpoints.filter(e => e.cost === 0).length}
            </span>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          {error}
          <button onClick={handleRefresh} className="retry-btn">
            Retry
          </button>
        </div>
      )}

      <div className="endpoints-table-container">
        {filteredEndpoints.length === 0 ? (
          <div className="no-endpoints">
            <div className="no-endpoints-icon">🔗</div>
            <h3>{searchTerm ? 'No endpoints found' : 'No endpoints available'}</h3>
            <p>
              {searchTerm 
                ? 'Try adjusting your search criteria' 
                : 'Click "Add New Endpoint" to create the first endpoint'
              }
            </p>
          </div>
        ) : (
          <div className="endpoints-table">
            <div className="table-header">
              <div className="table-cell">Endpoint</div>
              <div className="table-cell">Path</div>
              <div className="table-cell">Status</div>
              <div className="table-cell">Cost</div>
              <div className="table-cell">Created</div>
              <div className="table-cell">Actions</div>
            </div>
            
            {filteredEndpoints.map((endpointData) => (
              <div key={endpointData.id} className="table-row">
                <div className="table-cell endpoint-cell">
                  <div className="endpoint-icon">
                    🔗
                  </div>
                  <div className="endpoint-info">
                    <div className="endpoint-name">{endpointData.endpoint_name}</div>
                    <div className="endpoint-id">{endpointData.id?.substring(0, 8)}...</div>
                  </div>
                </div>
                
                <div className="table-cell path-cell">
                  <code>{endpointData.endpoint_path}</code>
                </div>
                
                <div className="table-cell">
                  <span className={`status-badge ${getStatusClass(endpointData.active)}`}>
                    {getStatusLabel(endpointData.active)}
                  </span>
                </div>
                
                <div className="table-cell cost-cell">
                  <span className={`cost-badge ${endpointData.cost === 0 ? 'free-cost' : ''}`} data-cost={endpointData.cost}>
                    {endpointData.cost === 0 ? 'Free' : `${endpointData.cost} AIC`}
                  </span>
                </div>
                
                <div className="table-cell">
                  {endpointData.created_at 
                    ? new Date(endpointData.created_at).toLocaleDateString()
                    : 'N/A'
                  }
                </div>
                
                <div className="table-cell actions-cell">
                  <button 
                    className="btn btn-small btn-outline"
                    onClick={() => handleEndpointClick(endpointData)}
                  >
                    <span className="btn-icon">👁️</span>
                    View
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Endpoint Detail Modal */}
      {showEndpointModal && selectedEndpoint && (
        <EndpointDetailModal
          endpoint={selectedEndpoint}
          currentUser={user}
          token={token}
          onClose={() => {
            setShowEndpointModal(false);
            setSelectedEndpoint(null);
          }}
          onRefresh={handleRefresh}
        />
      )}

      {/* Create Endpoint Modal */}
      {showCreateModal && (
        <CreateEndpointModal
          currentUser={user}
          token={token}
          onClose={() => setShowCreateModal(false)}
          onRefresh={handleRefresh}
        />
      )}
    </div>
  );
};

// Endpoint Detail Modal Component
const EndpointDetailModal = ({ endpoint: selectedEndpoint, currentUser, token, onClose, onRefresh }) => {
  const [editing, setEditing] = useState(false);
  const [formData, setFormData] = useState({ 
    ...selectedEndpoint, 
    endpoint_id: selectedEndpoint.id // Ensure the endpoint_id field is set for API calls
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Prevent background scrolling when modal is open
  React.useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('[ENDPOINT_DETAIL_MODAL] Updating endpoint:', formData.endpoint_id);
      
      await endpointAPI.updateEndpoint(currentUser.api_key, token, formData);
      console.log('[ENDPOINT_DETAIL_MODAL] Endpoint updated successfully');
      
      setEditing(false);
      onRefresh();
      onClose();
    } catch (err) {
      console.error('[ENDPOINT_DETAIL_MODAL] Failed to update endpoint:', err);
      setError(err.response?.data?.message || 'Failed to update endpoint');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Are you sure you want to delete endpoint "${selectedEndpoint.endpoint_name}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setLoading(true);
      setError(null);
      console.log('[ENDPOINT_DETAIL_MODAL] Deleting endpoint:', selectedEndpoint.id);
      
      await endpointAPI.deleteEndpoint(currentUser.api_key, token, selectedEndpoint.id);
      console.log('[ENDPOINT_DETAIL_MODAL] Endpoint deleted successfully');
      
      onRefresh();
      onClose();
    } catch (err) {
      console.error('[ENDPOINT_DETAIL_MODAL] Failed to delete endpoint:', err);
      setError(err.response?.data?.message || 'Failed to delete endpoint');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{editing ? 'Edit Endpoint' : 'Endpoint Details'}</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            {error}
          </div>
        )}

        <div className="modal-body">
          <div className="endpoint-detail-form">
            <div className="form-row">
              <div className="form-group">
                <label>Endpoint ID</label>
                <input 
                  type="text" 
                  value={selectedEndpoint.id} 
                  disabled 
                  className="form-input disabled"
                />
              </div>
              <div className="form-group">
                <label>Endpoint Name *</label>
                <input 
                  type="text" 
                  value={formData.endpoint_name || ''} 
                  onChange={(e) => handleInputChange('endpoint_name', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
            </div>

            <div className="form-group full-width">
              <label>Endpoint Path *</label>
              <input 
                type="text" 
                value={formData.endpoint_path || ''} 
                onChange={(e) => handleInputChange('endpoint_path', e.target.value)}
                disabled={!editing}
                className={`form-input ${!editing ? 'disabled' : ''}`}
                placeholder="/api/example"
              />
            </div>

            <div className="form-group full-width">
              <label>Description</label>
              <textarea 
                value={formData.description || ''} 
                onChange={(e) => handleInputChange('description', e.target.value)}
                disabled={!editing}
                className={`form-textarea ${!editing ? 'disabled' : ''}`}
                rows={4}
                placeholder="Description of what this endpoint does..."
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Cost (AIC)</label>
                <input 
                  type="number" 
                  step="0.01"
                  min="0"
                  value={formData.cost || 0} 
                  onChange={(e) => handleInputChange('cost', parseFloat(e.target.value) || 0)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
              <div className="form-group">
                <label>Status</label>
                <select 
                  value={formData.active ? 'true' : 'false'} 
                  onChange={(e) => handleInputChange('active', e.target.value === 'true')}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                >
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Created At</label>
                <input 
                  type="text" 
                  value={selectedEndpoint.created_at ? new Date(selectedEndpoint.created_at).toLocaleString() : 'N/A'} 
                  disabled 
                  className="form-input disabled"
                />
              </div>
              <div className="form-group">
                <label>Modified At</label>
                <input 
                  type="text" 
                  value={selectedEndpoint.modified_at ? new Date(selectedEndpoint.modified_at).toLocaleString() : 'N/A'} 
                  disabled 
                  className="form-input disabled"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <div className="footer-left">
            {!editing && (
              <button 
                className="btn btn-danger" 
                onClick={handleDelete}
                disabled={loading}
              >
                <span className="btn-icon">🗑️</span>
                Delete Endpoint
              </button>
            )}
          </div>
          <div className="footer-right">
            {editing ? (
              <>
                <button 
                  className="btn btn-secondary" 
                  onClick={() => {
                    setEditing(false);
                    setFormData({ ...selectedEndpoint, endpoint_id: selectedEndpoint.id });
                    setError(null);
                  }}
                  disabled={loading}
                >
                  Cancel
                </button>
                <button 
                  className="btn btn-primary" 
                  onClick={handleSave}
                  disabled={loading}
                >
                  {loading ? 'Saving...' : 'Save Changes'}
                </button>
              </>
            ) : (
              <>
                <button className="btn btn-secondary" onClick={onClose}>
                  Close
                </button>
                <button 
                  className="btn btn-primary" 
                  onClick={() => setEditing(true)}
                >
                  Edit Endpoint
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Create Endpoint Modal Component
const CreateEndpointModal = ({ currentUser, token, onClose, onRefresh }) => {
  console.log('[CREATE_ENDPOINT_MODAL] Initializing Create Endpoint Modal');

  // Prevent background scrolling when modal is open
  React.useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);
  
  const [formData, setFormData] = useState({
    endpoint_name: '',
    endpoint_path: '',
    description: '',
    active: true,
    cost: 1.0
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleInputChange = (field, value) => {
    console.log('[CREATE_ENDPOINT_MODAL] Field changed:', field, '=', value);
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear any existing errors when user starts typing
    if (error) setError(null);
  };

  const handleSubmit = async (e) => {
    if (e) {
      e.preventDefault();
    }
    
    console.log('[CREATE_ENDPOINT_MODAL] handleSubmit called with form data:', formData);
    
    if (!formData.endpoint_name.trim() || !formData.endpoint_path.trim()) {
      const errorMsg = 'Endpoint name and path are required fields';
      console.error('[CREATE_ENDPOINT_MODAL]', errorMsg);
      setError(errorMsg);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      console.log('[CREATE_ENDPOINT_MODAL] Creating new endpoint:', formData.endpoint_name);
      console.log('[CREATE_ENDPOINT_MODAL] Full form data being sent:', formData);
      
      const response = await endpointAPI.createEndpoint(currentUser.api_key, token, formData);
      console.log('[CREATE_ENDPOINT_MODAL] Endpoint created successfully:', response);
      
      // Show success message briefly
      alert(`Endpoint "${formData.endpoint_name}" created successfully!`);
      
      onRefresh();
      onClose();
    } catch (err) {
      console.error('[CREATE_ENDPOINT_MODAL] Failed to create endpoint:', err);
      setError(err.response?.data?.message || 'Failed to create endpoint');
    } finally {
      setLoading(false);
    }
  };

  const handleButtonClick = (e) => {
    console.log('[CREATE_ENDPOINT_MODAL] Create Endpoint button clicked!');
    e.preventDefault();
    handleSubmit();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add New Endpoint</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="endpoint-detail-form">
              <div className="form-row">
                <div className="form-group">
                  <label>Endpoint Name *</label>
                  <input 
                    type="text" 
                    value={formData.endpoint_name} 
                    onChange={(e) => handleInputChange('endpoint_name', e.target.value)}
                    className="form-input"
                    placeholder="Enter endpoint name"
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Endpoint Path *</label>
                  <input 
                    type="text" 
                    value={formData.endpoint_path} 
                    onChange={(e) => handleInputChange('endpoint_path', e.target.value)}
                    className="form-input"
                    placeholder="/api/example"
                    required
                  />
                </div>
              </div>

              <div className="form-group full-width">
                <label>Description</label>
                <textarea 
                  value={formData.description} 
                  onChange={(e) => handleInputChange('description', e.target.value)}
                  className="form-textarea"
                  rows={4}
                  placeholder="Description of what this endpoint does..."
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Cost (AIC)</label>
                  <input 
                    type="number" 
                    step="0.01"
                    min="0"
                    value={formData.cost} 
                    onChange={(e) => handleInputChange('cost', parseFloat(e.target.value) || 0)}
                    className="form-input"
                    placeholder="1.0"
                  />
                </div>
                <div className="form-group">
                  <label>Status</label>
                  <select 
                    value={formData.active ? 'true' : 'false'} 
                    onChange={(e) => handleInputChange('active', e.target.value === 'true')}
                    className="form-input"
                  >
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <div className="footer-right">
              <button 
                type="button" 
                className="btn btn-secondary" 
                onClick={onClose}
                disabled={loading}
              >
                Cancel
              </button>
              <button 
                type="submit" 
                className="btn btn-primary"
                onClick={handleButtonClick}
                disabled={loading}
                style={{
                  minWidth: '120px',
                  fontWeight: '600',
                  backgroundColor: loading ? '#999' : '',
                  cursor: loading ? 'not-allowed' : 'pointer'
                }}
              >
                {loading ? 'Creating...' : '✓ Create Endpoint'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default EndpointManagement;