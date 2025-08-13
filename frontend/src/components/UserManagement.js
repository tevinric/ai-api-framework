import React, { useState, useEffect, useMemo } from 'react';
import { adminAPI } from '../services/apiService';
import './UserManagement.css';

const UserManagement = ({ user, token }) => {
  console.log('[USER_MANAGEMENT] Initializing User Management component');
  
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [showUserModal, setShowUserModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Load all users on component mount
  useEffect(() => {
    console.log('[USER_MANAGEMENT] Loading users...');
    loadUsers();
  }, [refreshTrigger]);

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('[USER_MANAGEMENT] Fetching users from API...');
      
      const response = await adminAPI.getAllUsers(user.api_key, token);
      setUsers(response.users || []);
      console.log('[USER_MANAGEMENT] Users loaded successfully:', response.users?.length || 0, 'users');
    } catch (err) {
      console.error('[USER_MANAGEMENT] Failed to load users:', err);
      setError(err.response?.data?.message || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  // Filter users based on search term
  const filteredUsers = useMemo(() => {
    if (!searchTerm) return users;
    
    const term = searchTerm.toLowerCase();
    return users.filter(user => 
      user.user_name?.toLowerCase().includes(term) ||
      user.user_email?.toLowerCase().includes(term) ||
      user.user_id?.toLowerCase().includes(term) ||
      user.department?.toLowerCase().includes(term) ||
      user.company?.toLowerCase().includes(term)
    );
  }, [users, searchTerm]);

  const handleUserClick = (clickedUser) => {
    console.log('[USER_MANAGEMENT] User clicked:', clickedUser.user_name);
    setSelectedUser(clickedUser);
    setShowUserModal(true);
  };

  const handleRefresh = () => {
    console.log('[USER_MANAGEMENT] Refreshing user list...');
    setRefreshTrigger(prev => prev + 1);
  };

  const getScopeLabel = (scope) => {
    // Convert to number to handle both string and numeric values
    const numScope = parseInt(scope, 10);
    const scopes = {
      0: 'Admin',
      1: 'User',
      2: 'Limited',
      3: 'Guest',
      4: 'Restricted',
      5: 'Minimal'
    };
    return scopes[numScope] || `Unknown (${scope})`;
  };

  const getScopeClass = (scope) => {
    // Convert to number to handle both string and numeric values
    const numScope = parseInt(scope, 10);
    if (numScope === 0) return 'scope-admin';
    if (numScope <= 2) return 'scope-user';
    return 'scope-limited';
  };

  if (loading && users.length === 0) {
    return (
      <div className="user-management">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading users...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="user-management">
      <div className="user-management-header">
        <div className="header-content">
          <h1>User Management</h1>
          <p>Manage system users, roles, and permissions</p>
        </div>
        <div className="header-actions">
          <button 
            className="btn btn-primary" 
            onClick={() => setShowCreateModal(true)}
          >
            <span className="btn-icon">👤</span>
            Add New User
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

      <div className="user-management-controls">
        <div className="search-section">
          <div className="search-container">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              placeholder="Search by name, email, ID, department, or company..."
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
            <span className="stat-label">Total Users:</span>
            <span className="stat-value">{users.length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Filtered:</span>
            <span className="stat-value">{filteredUsers.length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Active:</span>
            <span className="stat-value">
              {users.filter(u => u.active).length}
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Admins:</span>
            <span className="stat-value">
              {users.filter(u => u.scope === 0).length}
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

      <div className="users-table-container">
        {filteredUsers.length === 0 ? (
          <div className="no-users">
            <div className="no-users-icon">👥</div>
            <h3>{searchTerm ? 'No users found' : 'No users available'}</h3>
            <p>
              {searchTerm 
                ? 'Try adjusting your search criteria' 
                : 'Click "Add New User" to create the first user'
              }
            </p>
          </div>
        ) : (
          <div className="users-table">
            <div className="table-header">
              <div className="table-cell">User</div>
              <div className="table-cell">Email</div>
              <div className="table-cell">Company</div>
              <div className="table-cell">Department</div>
              <div className="table-cell">Role</div>
              <div className="table-cell">Status</div>
              <div className="table-cell">Actions</div>
              <div className="table-cell">Created</div>
            </div>
            
            {filteredUsers.map((userData) => (
              <div key={userData.user_id} className="table-row">
                <div className="table-cell user-cell">
                  <div className="user-avatar">
                    {(userData.common_name || userData.user_name)?.charAt(0)?.toUpperCase()}
                  </div>
                  <div className="user-info">
                    <div className="user-name">{userData.common_name || userData.user_name}</div>
                    <div className="user-id">{userData.user_id?.substring(0, 8)}...</div>
                  </div>
                </div>
                
                <div className="table-cell email-cell">
                  {userData.user_email}
                </div>
                
                <div className="table-cell">
                  {userData.company || 'N/A'}
                </div>
                
                <div className="table-cell">
                  {userData.department || 'N/A'}
                </div>
                
                <div className="table-cell">
                  <span className={`scope-badge ${getScopeClass(userData.scope)}`}>
                    {getScopeLabel(userData.scope)}
                  </span>
                </div>
                
                <div className="table-cell">
                  <span className={`status-badge ${userData.active ? 'active' : 'inactive'}`}>
                    {userData.active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                
                <div className="table-cell actions-cell">
                  <button 
                    className="btn btn-small btn-outline"
                    onClick={() => handleUserClick(userData)}
                  >
                    <span className="btn-icon">👁️</span>
                    View
                  </button>
                </div>
                
                <div className="table-cell">
                  {userData.created_at 
                    ? new Date(userData.created_at).toLocaleDateString()
                    : 'N/A'
                  }
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* User Detail Modal */}
      {showUserModal && selectedUser && (
        <UserDetailModal
          user={selectedUser}
          currentUser={user}
          token={token}
          onClose={() => {
            setShowUserModal(false);
            setSelectedUser(null);
          }}
          onRefresh={handleRefresh}
        />
      )}

      {/* Create User Modal */}
      {showCreateModal && (
        <CreateUserModal
          currentUser={user}
          token={token}
          onClose={() => setShowCreateModal(false)}
          onRefresh={handleRefresh}
        />
      )}
    </div>
  );
};

// User Detail Modal Component
const UserDetailModal = ({ user: selectedUser, currentUser, token, onClose, onRefresh }) => {
  const [editing, setEditing] = useState(false);
  const [formData, setFormData] = useState({ 
    ...selectedUser, 
    id: selectedUser.user_id // Ensure the id field is set for API calls
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
      console.log('[USER_DETAIL_MODAL] Updating user:', formData.id || formData.user_id);
      
      // Ensure we have the correct id field for the API
      const updateData = {
        ...formData,
        id: formData.id || formData.user_id
      };
      
      await adminAPI.updateUser(currentUser.api_key, token, updateData);
      console.log('[USER_DETAIL_MODAL] User updated successfully');
      
      setEditing(false);
      onRefresh();
      onClose();
    } catch (err) {
      console.error('[USER_DETAIL_MODAL] Failed to update user:', err);
      setError(err.response?.data?.message || 'Failed to update user');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Are you sure you want to delete user ${selectedUser.user_name}? This action cannot be undone.`)) {
      return;
    }

    try {
      setLoading(true);
      setError(null);
      console.log('[USER_DETAIL_MODAL] Deleting user:', selectedUser.user_id);
      
      await adminAPI.deleteUser(currentUser.api_key, token, selectedUser.user_id);
      console.log('[USER_DETAIL_MODAL] User deleted successfully');
      
      onRefresh();
      onClose();
    } catch (err) {
      console.error('[USER_DETAIL_MODAL] Failed to delete user:', err);
      setError(err.response?.data?.message || 'Failed to delete user');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{editing ? 'Edit User' : 'User Details'}</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            {error}
          </div>
        )}

        <div className="modal-body">
          <div className="user-detail-form">
            <div className="form-row">
              <div className="form-group">
                <label>User ID</label>
                <input 
                  type="text" 
                  value={selectedUser.user_id} 
                  disabled 
                  className="form-input disabled"
                />
              </div>
              <div className="form-group">
                <label>Username *</label>
                <input 
                  type="text" 
                  value={formData.user_name || ''} 
                  onChange={(e) => handleInputChange('user_name', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Email *</label>
                <input 
                  type="email" 
                  value={formData.user_email || ''} 
                  onChange={(e) => handleInputChange('user_email', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
              <div className="form-group">
                <label>Common Name</label>
                <input 
                  type="text" 
                  value={formData.common_name || ''} 
                  onChange={(e) => handleInputChange('common_name', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Company</label>
                <input 
                  type="text" 
                  value={formData.company || ''} 
                  onChange={(e) => handleInputChange('company', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
              <div className="form-group">
                <label>Department</label>
                <input 
                  type="text" 
                  value={formData.department || ''} 
                  onChange={(e) => handleInputChange('department', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Phone Extension</label>
                <input 
                  type="text" 
                  value={formData.phone_ext || ''} 
                  onChange={(e) => handleInputChange('phone_ext', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
              <div className="form-group">
                <label>Division</label>
                <input 
                  type="text" 
                  value={formData.division || ''} 
                  onChange={(e) => handleInputChange('division', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Sub Department</label>
                <input 
                  type="text" 
                  value={formData.sub_department || ''} 
                  onChange={(e) => handleInputChange('sub_department', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
              <div className="form-group">
                <label>Cost Center</label>
                <input 
                  type="text" 
                  value={formData.cost_center || ''} 
                  onChange={(e) => handleInputChange('cost_center', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Manager Full Name</label>
                <input 
                  type="text" 
                  value={formData.manager_full_name || ''} 
                  onChange={(e) => handleInputChange('manager_full_name', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
              <div className="form-group">
                <label>Manager Email</label>
                <input 
                  type="email" 
                  value={formData.manager_email || ''} 
                  onChange={(e) => handleInputChange('manager_email', e.target.value)}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Scope</label>
                <select 
                  value={parseInt(formData.scope, 10) || 1} 
                  onChange={(e) => handleInputChange('scope', parseInt(e.target.value))}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                >
                  <option value={0}>Admin (0)</option>
                  <option value={1}>User (1)</option>
                  <option value={2}>Limited (2)</option>
                  <option value={3}>Guest (3)</option>
                  <option value={4}>Restricted (4)</option>
                  <option value={5}>Minimal (5)</option>
                </select>
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

            <div className="form-group full-width">
              <label>Comment</label>
              <textarea 
                value={formData.comment || ''} 
                onChange={(e) => handleInputChange('comment', e.target.value)}
                disabled={!editing}
                className={`form-textarea ${!editing ? 'disabled' : ''}`}
                rows={3}
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>API Key</label>
                <input 
                  type="text" 
                  value={selectedUser.api_key || 'N/A'} 
                  disabled 
                  className="form-input disabled"
                  style={{fontFamily: 'Courier New, monospace', fontSize: '12px'}}
                />
              </div>
              <div className="form-group">
                <label>AIC Balance</label>
                <input 
                  type="number" 
                  step="0.01"
                  value={formData.aic_balance || ''} 
                  onChange={(e) => handleInputChange('aic_balance', parseFloat(e.target.value))}
                  disabled={!editing}
                  className={`form-input ${!editing ? 'disabled' : ''}`}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Created At</label>
                <input 
                  type="text" 
                  value={selectedUser.created_at ? new Date(selectedUser.created_at).toLocaleString() : 'N/A'} 
                  disabled 
                  className="form-input disabled"
                />
              </div>
              <div className="form-group">
                <label>Modified At</label>
                <input 
                  type="text" 
                  value={selectedUser.modified_at ? new Date(selectedUser.modified_at).toLocaleString() : 'N/A'} 
                  disabled 
                  className="form-input disabled"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <div className="footer-left">
            {!editing && selectedUser.user_id !== currentUser.user_id && (
              <button 
                className="btn btn-danger" 
                onClick={handleDelete}
                disabled={loading}
              >
                <span className="btn-icon">🗑️</span>
                Delete User
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
                    setFormData({ ...selectedUser, id: selectedUser.user_id });
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
                  Edit User
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Create User Modal Component
const CreateUserModal = ({ currentUser, token, onClose, onRefresh }) => {
  console.log('[CREATE_USER_MODAL] Initializing Create User Modal');

  // Prevent background scrolling when modal is open
  React.useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);
  
  const [formData, setFormData] = useState({
    user_name: '',
    user_email: '',
    common_name: '',
    company: '',
    department: '',
    phone_ext: '',
    division: '',
    sub_department: '',
    cost_center: '',
    manager_full_name: '',
    manager_email: '',
    scope: 1,
    active: true,
    comment: '',
    aic_balance: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleInputChange = (field, value) => {
    console.log('[CREATE_USER_MODAL] Field changed:', field, '=', value);
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear any existing errors when user starts typing
    if (error) setError(null);
  };

  const handleSubmit = async (e) => {
    if (e) {
      e.preventDefault();
    }
    
    console.log('[CREATE_USER_MODAL] handleSubmit called with form data:', formData);
    
    if (!formData.user_name.trim() || !formData.user_email.trim()) {
      const errorMsg = 'Username and email are required fields';
      console.error('[CREATE_USER_MODAL]', errorMsg);
      setError(errorMsg);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      console.log('[CREATE_USER_MODAL] Creating new user:', formData.user_name);
      console.log('[CREATE_USER_MODAL] Full form data being sent:', formData);
      
      const response = await adminAPI.createUser(currentUser.api_key, token, formData);
      console.log('[CREATE_USER_MODAL] User created successfully:', response);
      
      // Show success message briefly
      alert(`User "${formData.user_name}" created successfully!`);
      
      onRefresh();
      onClose();
    } catch (err) {
      console.error('[CREATE_USER_MODAL] Failed to create user:', err);
      setError(err.response?.data?.message || 'Failed to create user');
    } finally {
      setLoading(false);
    }
  };

  const handleButtonClick = (e) => {
    console.log('[CREATE_USER_MODAL] Create User button clicked!');
    e.preventDefault();
    handleSubmit();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add New User</h2>
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
            <div className="user-detail-form">
              <div className="form-row">
                <div className="form-group">
                  <label>Username *</label>
                  <input 
                    type="text" 
                    value={formData.user_name} 
                    onChange={(e) => handleInputChange('user_name', e.target.value)}
                    className="form-input"
                    placeholder="Enter username"
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Email *</label>
                  <input 
                    type="email" 
                    value={formData.user_email} 
                    onChange={(e) => handleInputChange('user_email', e.target.value)}
                    className="form-input"
                    placeholder="Enter email address"
                    required
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Common Name</label>
                  <input 
                    type="text" 
                    value={formData.common_name} 
                    onChange={(e) => handleInputChange('common_name', e.target.value)}
                    className="form-input"
                  />
                </div>
                <div className="form-group">
                  <label>Company</label>
                  <input 
                    type="text" 
                    value={formData.company} 
                    onChange={(e) => handleInputChange('company', e.target.value)}
                    className="form-input"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Department</label>
                  <input 
                    type="text" 
                    value={formData.department} 
                    onChange={(e) => handleInputChange('department', e.target.value)}
                    className="form-input"
                  />
                </div>
                <div className="form-group">
                  <label>Phone Extension</label>
                  <input 
                    type="text" 
                    value={formData.phone_ext} 
                    onChange={(e) => handleInputChange('phone_ext', e.target.value)}
                    className="form-input"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Division</label>
                  <input 
                    type="text" 
                    value={formData.division} 
                    onChange={(e) => handleInputChange('division', e.target.value)}
                    className="form-input"
                  />
                </div>
                <div className="form-group">
                  <label>Sub Department</label>
                  <input 
                    type="text" 
                    value={formData.sub_department} 
                    onChange={(e) => handleInputChange('sub_department', e.target.value)}
                    className="form-input"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Cost Center</label>
                  <input 
                    type="text" 
                    value={formData.cost_center} 
                    onChange={(e) => handleInputChange('cost_center', e.target.value)}
                    className="form-input"
                  />
                </div>
                <div className="form-group">
                  {/* Empty space for alignment */}
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Manager Full Name</label>
                  <input 
                    type="text" 
                    value={formData.manager_full_name} 
                    onChange={(e) => handleInputChange('manager_full_name', e.target.value)}
                    className="form-input"
                  />
                </div>
                <div className="form-group">
                  <label>Manager Email</label>
                  <input 
                    type="email" 
                    value={formData.manager_email} 
                    onChange={(e) => handleInputChange('manager_email', e.target.value)}
                    className="form-input"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Scope</label>
                  <select 
                    value={parseInt(formData.scope, 10)} 
                    onChange={(e) => handleInputChange('scope', parseInt(e.target.value))}
                    className="form-input"
                  >
                    <option value={0}>Admin (0)</option>
                    <option value={1}>User (1)</option>
                    <option value={2}>Limited (2)</option>
                    <option value={3}>Guest (3)</option>
                    <option value={4}>Restricted (4)</option>
                    <option value={5}>Minimal (5)</option>
                  </select>
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

              <div className="form-row">
                <div className="form-group">
                  <label>AIC Balance</label>
                  <input 
                    type="number" 
                    step="0.01"
                    value={formData.aic_balance} 
                    onChange={(e) => handleInputChange('aic_balance', e.target.value)}
                    className="form-input"
                    placeholder="Enter AIC balance (optional)"
                  />
                </div>
                <div className="form-group">
                  {/* Empty space for alignment */}
                </div>
              </div>

              <div className="form-group full-width">
                <label>Comment</label>
                <textarea 
                  value={formData.comment} 
                  onChange={(e) => handleInputChange('comment', e.target.value)}
                  className="form-textarea"
                  rows={3}
                  placeholder="Optional comment about the user..."
                />
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
                {loading ? 'Creating...' : '✓ Create User'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UserManagement;