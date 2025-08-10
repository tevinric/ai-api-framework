import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Alert
} from '@mui/material';

const UserForm = ({ open, onClose, onSubmit, user = null, loading = false, error = '' }) => {
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

  useEffect(() => {
    if (user) {
      setFormData({
        id: user.id || '',
        user_name: user.user_name || '',
        user_email: user.user_email || '',
        common_name: user.common_name || '',
        company: user.company || '',
        department: user.department || '',
        phone_ext: user.phone_ext || '',
        division: user.division || '',
        sub_department: user.sub_department || '',
        cost_center: user.cost_center || '',
        manager_full_name: user.manager_full_name || '',
        manager_email: user.manager_email || '',
        scope: user.scope || 1,
        active: user.active !== undefined ? user.active : true,
        comment: user.comment || '',
        aic_balance: user.aic_balance || ''
      });
    } else {
      setFormData({
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
    }
  }, [user, open]);

  const handleInputChange = (e) => {
    const { name, value, checked, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    const cleanedData = Object.entries(formData).reduce((acc, [key, value]) => {
      if (value !== '' && value !== null && value !== undefined) {
        acc[key] = value;
      }
      return acc;
    }, {});

    onSubmit(cleanedData);
  };

  const isEditing = !!user;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {isEditing ? 'Edit User' : 'Add New User'}
      </DialogTitle>
      <form onSubmit={handleSubmit}>
        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                required
                fullWidth
                name="user_name"
                label="Username"
                value={formData.user_name}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                required
                fullWidth
                name="user_email"
                label="Email"
                type="email"
                value={formData.user_email}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                name="common_name"
                label="Common Name"
                value={formData.common_name}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                name="company"
                label="Company"
                value={formData.company}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                name="department"
                label="Department"
                value={formData.department}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                name="phone_ext"
                label="Phone Extension"
                value={formData.phone_ext}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                name="division"
                label="Division"
                value={formData.division}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                name="sub_department"
                label="Sub Department"
                value={formData.sub_department}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                name="cost_center"
                label="Cost Center"
                value={formData.cost_center}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                name="manager_full_name"
                label="Manager Full Name"
                value={formData.manager_full_name}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                name="manager_email"
                label="Manager Email"
                type="email"
                value={formData.manager_email}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth margin="dense">
                <InputLabel>Scope</InputLabel>
                <Select
                  name="scope"
                  value={formData.scope}
                  onChange={handleInputChange}
                  label="Scope"
                >
                  <MenuItem value={1}>1 - Basic</MenuItem>
                  <MenuItem value={2}>2 - Standard</MenuItem>
                  <MenuItem value={3}>3 - Advanced</MenuItem>
                  <MenuItem value={4}>4 - Premium</MenuItem>
                  <MenuItem value={5}>5 - Enterprise</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                name="aic_balance"
                label="AIC Balance"
                type="number"
                value={formData.aic_balance}
                onChange={handleInputChange}
                margin="dense"
                inputProps={{ step: "0.01", min: "0" }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.active}
                    onChange={handleInputChange}
                    name="active"
                  />
                }
                label="Active"
                sx={{ mt: 2 }}
              />
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                name="comment"
                label="Comment"
                multiline
                rows={2}
                value={formData.comment}
                onChange={handleInputChange}
                margin="dense"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button type="submit" variant="contained" disabled={loading}>
            {loading ? 'Saving...' : (isEditing ? 'Update User' : 'Create User')}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default UserForm;