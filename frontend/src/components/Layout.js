import React from 'react';
import { 
  AppBar, 
  Toolbar, 
  Typography, 
  Container, 
  Box,
  Button,
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  CssBaseline,
  Chip,
  Avatar,
  Divider
} from '@mui/material';
import { 
  People as PeopleIcon,
  Settings as SettingsIcon,
  ExitToApp as LogoutIcon,
  Dashboard as DashboardIcon,
  DeveloperMode as DevIcon,
  Person as PersonIcon
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { getCurrentUser, isLoginDisabled, clearStoredCredentials } from '../utils/auth';

const drawerWidth = 240;

const Layout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const isDevelopment = isLoginDisabled();
  const currentUser = getCurrentUser();

  const handleLogout = async () => {
    clearStoredCredentials();
    if (!isDevelopment) {
      navigate('/login');
    }
  };

  const menuItems = [
    { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
    { text: 'User Management', icon: <PeopleIcon />, path: '/users' },
    { text: 'Endpoint Access', icon: <SettingsIcon />, path: '/endpoints' },
  ];

  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />
      
      <AppBar
        position="fixed"
        sx={{ 
          width: `calc(100% - ${drawerWidth}px)`, 
          ml: `${drawerWidth}px`,
          bgcolor: 'primary.main'
        }}
      >
        <Toolbar>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            AI API Admin Portal
            {isDevelopment && (
              <Chip 
                icon={<DevIcon />}
                label="DEV MODE" 
                size="small" 
                color="warning" 
                sx={{ ml: 2 }} 
              />
            )}
          </Typography>
          
          {currentUser && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" sx={{ color: 'inherit' }}>
                Welcome, {currentUser.user_name}
              </Typography>
              <Button 
                color="inherit" 
                onClick={handleLogout}
                startIcon={<LogoutIcon />}
                size="small"
              >
                {isDevelopment ? 'Reset' : 'Logout'}
              </Button>
            </Box>
          )}
        </Toolbar>
      </AppBar>

      <Drawer
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
          },
        }}
        variant="permanent"
        anchor="left"
      >
        <Toolbar>
          <Typography variant="h6" noWrap>
            Admin Menu
          </Typography>
        </Toolbar>
        
        {/* User Info Section */}
        {currentUser && (
          <Box sx={{ p: 2, bgcolor: 'grey.50' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Avatar sx={{ bgcolor: 'primary.main', mr: 1, width: 32, height: 32 }}>
                <PersonIcon />
              </Avatar>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="subtitle2" noWrap>
                  {currentUser.common_name || currentUser.user_name}
                </Typography>
                <Typography variant="caption" color="textSecondary" noWrap>
                  {currentUser.department || 'No Department'}
                </Typography>
              </Box>
            </Box>
            <Typography variant="caption" color="textSecondary" display="block">
              {currentUser.user_email}
            </Typography>
            {isDevelopment && (
              <Chip 
                label="DEV USER" 
                size="small" 
                color="warning" 
                sx={{ mt: 1, fontSize: '0.7rem', height: 20 }} 
              />
            )}
          </Box>
        )}
        
        <Divider />
        
        <List>
          {menuItems.map((item) => (
            <ListItem 
              key={item.text}
              button
              selected={location.pathname === item.path}
              onClick={() => navigate(item.path)}
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'primary.light',
                  color: 'primary.contrastText',
                },
              }}
            >
              <ListItemIcon sx={{ color: location.pathname === item.path ? 'primary.main' : 'inherit' }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItem>
          ))}
        </List>
      </Drawer>

      <Box
        component="main"
        sx={{ 
          flexGrow: 1, 
          bgcolor: 'background.default', 
          p: 3,
          width: `calc(100% - ${drawerWidth}px)` 
        }}
      >
        <Toolbar />
        <Container maxWidth="xl">
          {children}
        </Container>
      </Box>
    </Box>
  );
};

export default Layout;