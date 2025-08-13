import React, { useState, useEffect, useMemo } from 'react';
import { rbacAPI, adminAPI } from '../services/apiService';
import './RBAC.css';

const RBAC = ({ user, token }) => {
  console.log('[RBAC] Initializing RBAC component');
  
  const [userAccess, setUserAccess] = useState([]);
  const [users, setUsers] = useState({});
  const [endpoints, setEndpoints] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [showUserModal, setShowUserModal] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Load all RBAC data on component mount
  useEffect(() => {
    console.log('[RBAC] Loading RBAC data...');
    loadRBACData();
  }, [refreshTrigger]);

  const loadRBACData = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('[RBAC] Fetching user endpoint access from API...');
      
      // Load user endpoint access
      const accessResponse = await rbacAPI.getUserEndpointAccess(user.api_key, token);
      console.log('[RBAC] Access data:', accessResponse);
      
      // Load all users to get names
      const usersResponse = await adminAPI.getAllUsers(user.api_key, token);
      const usersMap = {};
      usersResponse.users?.forEach(u => {
        usersMap[u.user_id] = u;
      });
      
      setUserAccess(accessResponse.user_access || []);
      setUsers(usersMap);
      console.log('[RBAC] RBAC data loaded successfully');
    } catch (err) {
      console.error('[RBAC] Failed to load RBAC data:', err);
      setError(err.response?.data?.message || 'Failed to load RBAC data');
    } finally {
      setLoading(false);
    }
  };

  // Group access data by user
  const userAccessSummary = useMemo(() => {
    const summary = {};
    userAccess.forEach(access => {
      const userId = access.user_id;
      if (!summary[userId]) {
        summary[userId] = {
          user: users[userId],
          endpointCount: 0,
          accesses: []
        };
      }
      summary[userId].endpointCount += 1;
      summary[userId].accesses.push(access);
    });
    return Object.values(summary);
  }, [userAccess, users]);

  // Filter users based on search term
  const filteredUsers = useMemo(() => {
    if (!searchTerm) return userAccessSummary;
    
    const term = searchTerm.toLowerCase();
    return userAccessSummary.filter(summary => 
      summary.user?.common_name?.toLowerCase().includes(term) ||
      summary.user?.user_name?.toLowerCase().includes(term) ||
      summary.user?.user_email?.toLowerCase().includes(term) ||
      summary.user?.user_id?.toLowerCase().includes(term)
    );
  }, [userAccessSummary, searchTerm]);

  const handleUserClick = (userSummary) => {
    console.log('[RBAC] User clicked:', userSummary.user?.user_name);
    setSelectedUser(userSummary);
    setShowUserModal(true);
  };

  const handleRefresh = () => {
    console.log('[RBAC] Refreshing RBAC data...');
    setRefreshTrigger(prev => prev + 1);
  };

  if (loading && userAccess.length === 0) {
    return (
      <div className="rbac">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading RBAC data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rbac">
      <div className="rbac-header">
        <div className="header-content">
          <h1>RBAC - Role-Based Access Control</h1>
          <p>Manage user endpoint access permissions</p>
        </div>
        <div className="header-actions">
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

      <div className="rbac-controls">
        <div className="search-section">
          <div className="search-container">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              placeholder="Search by user name, email, or ID..."
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
            <span className="stat-label">Total Users with Access:</span>
            <span className="stat-value">{userAccessSummary.length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Filtered:</span>
            <span className="stat-value">{filteredUsers.length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Total Access Records:</span>
            <span className="stat-value">{userAccess.length}</span>
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

      <div className="rbac-table-container">
        {filteredUsers.length === 0 ? (
          <div className="no-users">
            <div className="no-users-icon">🔐</div>
            <h3>{searchTerm ? 'No users found' : 'No users with endpoint access'}</h3>
            <p>
              {searchTerm 
                ? 'Try adjusting your search criteria' 
                : 'No users currently have endpoint access assigned'
              }
            </p>
          </div>
        ) : (
          <div className="rbac-table">
            <div className="table-header">
              <div className="table-cell">User</div>
              <div className="table-cell">Email</div>
              <div className="table-cell">Department</div>
              <div className="table-cell">Endpoint Count</div>
              <div className="table-cell">Actions</div>
            </div>
            
            {filteredUsers.map((userSummary) => (
              <div key={userSummary.user?.user_id} className="table-row">
                <div className="table-cell user-cell">
                  <div className="user-avatar">
                    {(userSummary.user?.common_name || userSummary.user?.user_name)?.charAt(0)?.toUpperCase()}
                  </div>
                  <div className="user-info">
                    <div className="user-name">{userSummary.user?.common_name || userSummary.user?.user_name}</div>
                    <div className="user-id">{userSummary.user?.user_id?.substring(0, 8)}...</div>
                  </div>
                </div>
                
                <div className="table-cell email-cell">
                  {userSummary.user?.user_email}
                </div>
                
                <div className="table-cell">
                  {userSummary.user?.department || 'N/A'}
                </div>
                
                <div className="table-cell count-cell">
                  <span className="count-badge">
                    {userSummary.endpointCount} endpoint{userSummary.endpointCount !== 1 ? 's' : ''}
                  </span>
                </div>
                
                <div className="table-cell actions-cell">
                  <button 
                    className="btn btn-small btn-outline"
                    onClick={() => handleUserClick(userSummary)}
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

      {/* User Endpoint Access Modal */}
      {showUserModal && selectedUser && (
        <UserEndpointAccessModal
          userSummary={selectedUser}
          currentUser={user}
          token={token}
          users={users}
          onClose={() => {
            setShowUserModal(false);
            setSelectedUser(null);
          }}
          onRefresh={handleRefresh}
        />
      )}
    </div>
  );
};

// User Endpoint Access Modal Component
const UserEndpointAccessModal = ({ userSummary, currentUser, token, users, onClose, onRefresh }) => {
  const [selectedAccess, setSelectedAccess] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Prevent background scrolling when modal is open
  React.useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  const handleSelectAll = (checked) => {
    if (checked) {
      setSelectedAccess(new Set(userSummary.accesses.map(access => access.id)));
    } else {
      setSelectedAccess(new Set());
    }
  };

  const handleSelectAccess = (accessId, checked) => {
    const newSelected = new Set(selectedAccess);
    if (checked) {
      newSelected.add(accessId);
    } else {
      newSelected.delete(accessId);
    }
    setSelectedAccess(newSelected);
  };

  const handleBulkRemove = async () => {
    if (selectedAccess.size === 0) {
      setError('Please select at least one endpoint to remove');
      return;
    }

    const confirmMessage = `Are you sure you want to remove ${selectedAccess.size} endpoint access${selectedAccess.size !== 1 ? 'es' : ''} from ${userSummary.user?.common_name || userSummary.user?.user_name}? This action cannot be undone.`;
    
    if (!window.confirm(confirmMessage)) {
      return;
    }

    try {
      setLoading(true);
      setError(null);
      console.log('[USER_ENDPOINT_ACCESS_MODAL] Removing selected access:', Array.from(selectedAccess));
      
      // Prepare data for bulk removal
      const removeData = {
        access_ids: Array.from(selectedAccess)
      };
      
      await rbacAPI.removeMultipleEndpointAccess(currentUser.api_key, token, removeData);
      console.log('[USER_ENDPOINT_ACCESS_MODAL] Endpoint access removed successfully');
      
      onRefresh();
      onClose();
    } catch (err) {
      console.error('[USER_ENDPOINT_ACCESS_MODAL] Failed to remove endpoint access:', err);
      setError(err.response?.data?.message || 'Failed to remove endpoint access');
    } finally {
      setLoading(false);
    }
  };

  const allSelected = selectedAccess.size === userSummary.accesses.length;
  const someSelected = selectedAccess.size > 0 && selectedAccess.size < userSummary.accesses.length;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Endpoint Access - {userSummary.user?.common_name || userSummary.user?.user_name}</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            {error}
          </div>
        )}

        <div className="modal-body">
          <div className="access-controls">
            <div className="select-controls">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={input => {
                    if (input) input.indeterminate = someSelected;
                  }}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                />
                <span>Select All ({userSummary.accesses.length} endpoints)</span>
              </label>
              {selectedAccess.size > 0 && (
                <button 
                  className="btn btn-danger btn-small"
                  onClick={handleBulkRemove}
                  disabled={loading}
                >
                  <span className="btn-icon">🗑️</span>
                  Remove Selected ({selectedAccess.size})
                </button>
              )}
            </div>
          </div>

          <div className="access-table">
            <div className="table-header">
              <div className="table-cell">Select</div>
              <div className="table-cell">Endpoint Name</div>
              <div className="table-cell">Endpoint ID</div>
              <div className="table-cell">Assigned Date</div>
              <div className="table-cell">Created By</div>
            </div>
            
            {userSummary.accesses.map((access) => (
              <div key={access.id} className="table-row">
                <div className="table-cell checkbox-cell">
                  <input
                    type="checkbox"
                    checked={selectedAccess.has(access.id)}
                    onChange={(e) => handleSelectAccess(access.id, e.target.checked)}
                  />
                </div>
                
                <div className="table-cell">
                  {access.endpoint_name || 'Unknown Endpoint'}
                </div>
                
                <div className="table-cell endpoint-id-cell">
                  <code>{access.endpoint_id?.substring(0, 8)}...</code>
                </div>
                
                <div className="table-cell">
                  {access.assigned_at 
                    ? new Date(access.assigned_at).toLocaleDateString()
                    : 'N/A'
                  }
                </div>
                
                <div className="table-cell">
                  {users[access.created_by]?.common_name || users[access.created_by]?.user_name || 'Unknown'}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-footer">
          <div className="footer-left">
            <span className="selection-info">
              {selectedAccess.size > 0 ? `${selectedAccess.size} selected` : 'None selected'}
            </span>
          </div>
          <div className="footer-right">
            <button className="btn btn-secondary" onClick={onClose}>
              Close
            </button>
            {selectedAccess.size > 0 && (
              <button 
                className="btn btn-danger" 
                onClick={handleBulkRemove}
                disabled={loading}
              >
                {loading ? 'Removing...' : `Remove Selected (${selectedAccess.size})`}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default RBAC;