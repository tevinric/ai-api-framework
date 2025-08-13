import React from 'react';
import Dashboard from './Dashboard';
import UserManagement from './UserManagement';
import EndpointManagement from './EndpointManagement';
import RBAC from './RBAC';
import './MainContent.css';

const MainContent = ({ user, token, currentView }) => {
  console.log('[MAIN_CONTENT] Rendering main content for user:', user?.user_name, 'view:', currentView);
  
  const renderContent = () => {
    switch (currentView) {
      case 'dashboard':
        return <Dashboard user={user} token={token} />;
      case 'users':
        return <UserManagement user={user} token={token} />;
      case 'endpoints':
        return <EndpointManagement user={user} token={token} />;
      case 'rbac':
        return <RBAC user={user} token={token} />;
      case 'analytics':
        return <div className="coming-soon">📈 Analytics Dashboard - Coming Soon</div>;
      case 'balance':
        return <div className="coming-soon">💰 Balance & Usage Management - Coming Soon</div>;
      case 'logs':
        return <div className="coming-soon">📋 System Logs - Coming Soon</div>;
      case 'settings':
        return <div className="coming-soon">⚙️ System Settings - Coming Soon</div>;
      default:
        return <Dashboard user={user} token={token} />;
    }
  };
  
  return (
    <div className="main-content">
      {renderContent()}
    </div>
  );
};

export default MainContent;