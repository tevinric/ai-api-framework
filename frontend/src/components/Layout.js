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
  Chip
} from '@mui/material';
import { 
  People as PeopleIcon,
  Settings as SettingsIcon,
  ExitToApp as LogoutIcon,
  Dashboard as DashboardIcon,
  DeveloperMode as DevIcon
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import apiService from '../services/api';
import { isLoginDisabled } from '../utils/auth';

const drawerWidth = 240;

const Layout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const loginDisabled = isLoginDisabled();

  const handleLogout = () => {
    if (!loginDisabled) {
      apiService.clearCredentials();
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
            {loginDisabled && (
              <Chip 
                icon={<DevIcon />}
                label="DEV MODE" 
                size="small" 
                color="warning" 
                sx={{ ml: 2 }} 
              />
            )}
          </Typography>
          {!loginDisabled && (
            <Button 
              color="inherit" 
              onClick={handleLogout}
              startIcon={<LogoutIcon />}
            >
              Logout
            </Button>
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