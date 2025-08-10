import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  TextField,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Chip,
  Alert,
  CircularProgress,
  Autocomplete,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormGroup,
  FormControlLabel,
  Divider
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  Person as PersonIcon,
  Settings as SettingsIcon,
  SelectAll as SelectAllIcon,
  Clear as ClearIcon
} from '@mui/icons-material';
import apiService from '../services/api';

const EndpointAccessPage = () => {
  const [users, setUsers] = useState([]);
  const [endpoints, setEndpoints] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userEndpoints, setUserEndpoints] = useState([]);
  const [loading, setLoading] = useState(false);
  const [endpointsLoading, setEndpointsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const [searchTerm, setSearchTerm] = useState('');
  const [accessDialogOpen, setAccessDialogOpen] = useState(false);
  const [accessMode, setAccessMode] = useState('single'); // 'single', 'multi', 'all'
  const [selectedEndpoints, setSelectedEndpoints] = useState([]);
  const [accessLoading, setAccessLoading] = useState(false);

  useEffect(() => {
    fetchInitialData();
  }, []);

  useEffect(() => {
    if (selectedUser) {
      fetchUserEndpoints();
    } else {
      setUserEndpoints([]);
    }
  }, [selectedUser]);

  const fetchInitialData = async () => {
    try {
      setLoading(true);
      const [usersResponse, endpointsResponse] = await Promise.all([
        apiService.getAllUsers(),
        apiService.getAllEndpoints()
      ]);
      
      setUsers(usersResponse.users || []);
      setEndpoints(endpointsResponse.endpoints || []);
    } catch (error) {
      console.error('Error fetching initial data:', error);
      setError('Failed to load data. Please check your connection and credentials.');
    } finally {
      setLoading(false);
    }
  };

  const fetchUserEndpoints = async () => {
    if (!selectedUser) return;
    
    try {
      setEndpointsLoading(true);
      const response = await apiService.getUserEndpoints(selectedUser.id);
      setUserEndpoints(response.endpoints || []);
    } catch (error) {
      console.error('Error fetching user endpoints:', error);
      setUserEndpoints([]);
    } finally {
      setEndpointsLoading(false);
    }
  };

  const searchUsers = async () => {
    if (!searchTerm.trim()) {
      setError('Please enter a search term');
      return;
    }

    try {
      setLoading(true);
      setError('');
      const response = await apiService.searchUsersByName(searchTerm.trim());
      setUsers(response.users || []);
      
      if (!response.users || response.users.length === 0) {
        setError(`No users found with name containing "${searchTerm}"`);
      }
    } catch (error) {
      console.error('Error searching users:', error);
      setError('Failed to search users');
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  const handleUserSelect = (user) => {
    setSelectedUser(user);
    setError('');
    setSuccess('');
  };

  const openAccessDialog = (mode) => {
    setAccessMode(mode);
    setSelectedEndpoints([]);
    setAccessDialogOpen(true);
  };

  const handleEndpointSelection = (endpointId, checked) => {
    if (checked) {
      setSelectedEndpoints(prev => [...prev, endpointId]);
    } else {
      setSelectedEndpoints(prev => prev.filter(id => id !== endpointId));
    }
  };

  const handleSelectAllEndpoints = (checked) => {
    if (checked) {
      const availableEndpoints = endpoints
        .filter(endpoint => !userEndpoints.some(ue => ue.id === endpoint.id))
        .map(endpoint => endpoint.id);
      setSelectedEndpoints(availableEndpoints);
    } else {
      setSelectedEndpoints([]);
    }
  };

  const grantAccess = async () => {
    if (!selectedUser) return;

    try {
      setAccessLoading(true);
      let response;

      switch (accessMode) {
        case 'single':
          if (selectedEndpoints.length !== 1) {
            setError('Please select exactly one endpoint');
            return;
          }
          response = await apiService.grantEndpointAccess(selectedUser.id, selectedEndpoints[0]);
          break;
        
        case 'multi':
          if (selectedEndpoints.length === 0) {
            setError('Please select at least one endpoint');
            return;
          }
          response = await apiService.grantMultipleEndpointAccess(selectedUser.id, selectedEndpoints);
          break;
        
        case 'all':
          response = await apiService.grantAllEndpointAccess(selectedUser.id);
          break;
        
        default:
          setError('Invalid access mode');
          return;
      }

      setSuccess(`Successfully granted ${accessMode} endpoint access to ${selectedUser.common_name || selectedUser.user_name}`);
      setAccessDialogOpen(false);
      await fetchUserEndpoints();
      
      setTimeout(() => setSuccess(''), 5000);
    } catch (error) {
      console.error('Error granting access:', error);
      setError(error.response?.data?.message || 'Failed to grant access');
    } finally {
      setAccessLoading(false);
    }
  };

  const removeAccess = async (endpointId) => {
    if (!selectedUser) return;

    try {
      await apiService.removeEndpointAccess(selectedUser.id, endpointId);
      setSuccess('Access removed successfully');
      await fetchUserEndpoints();
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      console.error('Error removing access:', error);
      setError('Failed to remove access');
    }
  };

  const removeAllAccess = async () => {
    if (!selectedUser) return;

    try {
      await apiService.removeAllEndpointAccess(selectedUser.id);
      setSuccess('All access removed successfully');
      await fetchUserEndpoints();
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      console.error('Error removing all access:', error);
      setError('Failed to remove all access');
    }
  };

  const availableEndpoints = endpoints.filter(endpoint => 
    !userEndpoints.some(ue => ue.id === endpoint.id)
  );

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Endpoint Access Management
      </Typography>
      
      <Typography variant="body1" color="textSecondary" paragraph>
        Search for users and manage their endpoint access permissions.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* User Search Section */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                <PersonIcon sx={{ mr: 1 }} />
                Search Users
              </Typography>
              
              <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                <TextField
                  fullWidth
                  placeholder="Enter user's common name..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && searchUsers()}
                />
                <Button 
                  variant="contained" 
                  onClick={searchUsers}
                  disabled={loading}
                  startIcon={loading ? <CircularProgress size={20} /> : <SearchIcon />}
                >
                  Search
                </Button>
              </Box>

              {loading ? (
                <Box sx={{ textAlign: 'center', py: 2 }}>
                  <CircularProgress />
                </Box>
              ) : (
                <List sx={{ maxHeight: 300, overflow: 'auto' }}>
                  {users.map((user) => (
                    <ListItem
                      key={user.id}
                      button
                      selected={selectedUser?.id === user.id}
                      onClick={() => handleUserSelect(user)}
                      sx={{
                        border: selectedUser?.id === user.id ? '2px solid' : '1px solid',
                        borderColor: selectedUser?.id === user.id ? 'primary.main' : 'divider',
                        borderRadius: 1,
                        mb: 1,
                      }}
                    >
                      <ListItemText
                        primary={user.common_name || user.user_name}
                        secondary={`${user.user_email} | ${user.company || 'N/A'}`}
                      />
                    </ListItem>
                  ))}
                  {users.length === 0 && !loading && (
                    <ListItem>
                      <ListItemText primary="No users found. Try searching for a user." />
                    </ListItem>
                  )}
                </List>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* User Endpoints Section */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                <SettingsIcon sx={{ mr: 1 }} />
                User Endpoints
                {selectedUser && (
                  <Chip 
                    label={selectedUser.common_name || selectedUser.user_name} 
                    size="small" 
                    sx={{ ml: 2 }} 
                  />
                )}
              </Typography>

              {selectedUser ? (
                <>
                  <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => openAccessDialog('single')}
                      startIcon={<AddIcon />}
                    >
                      Add Single
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => openAccessDialog('multi')}
                      startIcon={<SelectAllIcon />}
                    >
                      Add Multiple
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => openAccessDialog('all')}
                      startIcon={<AddIcon />}
                    >
                      Add All
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      color="error"
                      onClick={removeAllAccess}
                      startIcon={<ClearIcon />}
                      disabled={userEndpoints.length === 0}
                    >
                      Remove All
                    </Button>
                  </Box>

                  {endpointsLoading ? (
                    <Box sx={{ textAlign: 'center', py: 2 }}>
                      <CircularProgress />
                    </Box>
                  ) : (
                    <List sx={{ maxHeight: 300, overflow: 'auto' }}>
                      {userEndpoints.length === 0 ? (
                        <ListItem>
                          <ListItemText primary="No endpoint access assigned" />
                        </ListItem>
                      ) : (
                        userEndpoints.map((endpoint) => (
                          <ListItem key={endpoint.id}>
                            <ListItemText
                              primary={endpoint.endpoint_name}
                              secondary={endpoint.endpoint_path}
                            />
                            <ListItemSecondaryAction>
                              <IconButton 
                                edge="end" 
                                size="small"
                                color="error"
                                onClick={() => removeAccess(endpoint.id)}
                              >
                                <RemoveIcon />
                              </IconButton>
                            </ListItemSecondaryAction>
                          </ListItem>
                        ))
                      )}
                    </List>
                  )}
                </>
              ) : (
                <Typography color="textSecondary" sx={{ textAlign: 'center', py: 4 }}>
                  Select a user to view their endpoint access
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Access Management Dialog */}
      <Dialog open={accessDialogOpen} onClose={() => setAccessDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          Grant Endpoint Access - {accessMode.charAt(0).toUpperCase() + accessMode.slice(1)}
        </DialogTitle>
        <DialogContent>
          {selectedUser && (
            <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
              Granting access to: <strong>{selectedUser.common_name || selectedUser.user_name}</strong>
            </Typography>
          )}

          {accessMode === 'all' ? (
            <Typography>
              This will grant access to all available endpoints ({availableEndpoints.length} endpoints).
            </Typography>
          ) : (
            <>
              {accessMode === 'multi' && (
                <Box sx={{ mb: 2 }}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={selectedEndpoints.length === availableEndpoints.length}
                        indeterminate={selectedEndpoints.length > 0 && selectedEndpoints.length < availableEndpoints.length}
                        onChange={(e) => handleSelectAllEndpoints(e.target.checked)}
                      />
                    }
                    label="Select All Available"
                  />
                  <Divider sx={{ my: 1 }} />
                </Box>
              )}

              <FormGroup sx={{ maxHeight: 400, overflow: 'auto' }}>
                {availableEndpoints.map((endpoint) => (
                  <FormControlLabel
                    key={endpoint.id}
                    control={
                      <Checkbox
                        checked={selectedEndpoints.includes(endpoint.id)}
                        onChange={(e) => handleEndpointSelection(endpoint.id, e.target.checked)}
                      />
                    }
                    label={
                      <Box>
                        <Typography variant="body2">{endpoint.endpoint_name}</Typography>
                        <Typography variant="caption" color="textSecondary">
                          {endpoint.endpoint_path}
                        </Typography>
                      </Box>
                    }
                  />
                ))}
              </FormGroup>

              {availableEndpoints.length === 0 && (
                <Typography color="textSecondary">
                  No additional endpoints available for this user.
                </Typography>
              )}
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAccessDialogOpen(false)} disabled={accessLoading}>
            Cancel
          </Button>
          <Button 
            onClick={grantAccess} 
            variant="contained" 
            disabled={accessLoading || (accessMode !== 'all' && selectedEndpoints.length === 0)}
          >
            {accessLoading ? 'Granting...' : 'Grant Access'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EndpointAccessPage;