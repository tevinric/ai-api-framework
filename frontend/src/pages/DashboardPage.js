import React, { useState, useEffect } from 'react';
import { 
  Grid, 
  Card, 
  CardContent, 
  Typography, 
  Box,
  Alert,
  CircularProgress
} from '@mui/material';
import { 
  People as PeopleIcon,
  Settings as SettingsIcon,
  Assessment as AssessmentIcon
} from '@mui/icons-material';
import apiService from '../services/api';

const DashboardPage = () => {
  const [stats, setStats] = useState({
    totalUsers: 0,
    totalEndpoints: 0,
    loading: true
  });
  const [error, setError] = useState('');

  useEffect(() => {
    fetchDashboardStats();
  }, []);

  const fetchDashboardStats = async () => {
    try {
      setError('');
      const [usersResponse, endpointsResponse] = await Promise.allSettled([
        apiService.getAllUsers(),
        apiService.getAllEndpoints()
      ]);

      let totalUsers = 0;
      let totalEndpoints = 0;

      if (usersResponse.status === 'fulfilled' && usersResponse.value?.users) {
        totalUsers = usersResponse.value.users.length;
      }

      if (endpointsResponse.status === 'fulfilled' && endpointsResponse.value?.endpoints) {
        totalEndpoints = endpointsResponse.value.endpoints.length;
      }

      setStats({
        totalUsers,
        totalEndpoints,
        loading: false
      });
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
      setError('Failed to load dashboard statistics');
      setStats(prev => ({ ...prev, loading: false }));
    }
  };

  const StatCard = ({ title, value, icon, color = 'primary' }) => (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Box sx={{ 
            bgcolor: `${color}.light`, 
            borderRadius: '50%', 
            p: 1, 
            mr: 2,
            color: `${color}.main`
          }}>
            {icon}
          </Box>
          <Typography variant="h6" component="h2">
            {title}
          </Typography>
        </Box>
        <Typography variant="h3" component="div" color={`${color}.main`}>
          {stats.loading ? <CircularProgress size={30} /> : value}
        </Typography>
      </CardContent>
    </Card>
  );

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Dashboard
      </Typography>
      
      <Typography variant="body1" color="textSecondary" paragraph>
        Welcome to the AI API Admin Portal. Manage users and endpoint access from here.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard
            title="Total Users"
            value={stats.totalUsers}
            icon={<PeopleIcon />}
            color="primary"
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={4}>
          <StatCard
            title="Total Endpoints"
            value={stats.totalEndpoints}
            icon={<SettingsIcon />}
            color="secondary"
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={4}>
          <StatCard
            title="Active Sessions"
            value="--"
            icon={<AssessmentIcon />}
            color="success"
          />
        </Grid>
      </Grid>

      <Grid container spacing={3} sx={{ mt: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" component="h2" gutterBottom>
                Quick Actions
              </Typography>
              <Typography variant="body2" color="textSecondary">
                • Add new users to the system<br />
                • Manage endpoint access permissions<br />
                • Search users by name<br />
                • Update user information
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" component="h2" gutterBottom>
                System Status
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Admin portal is operational.<br />
                All API endpoints are accessible.<br />
                Database connection is stable.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardPage;