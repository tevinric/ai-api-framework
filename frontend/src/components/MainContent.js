import React from 'react';
import Dashboard from './Dashboard';
import './MainContent.css';

const MainContent = ({ user, token }) => {
  console.log('[MAIN_CONTENT] Rendering main content for user:', user?.user_name);
  
  return (
    <div className="main-content">
      <Dashboard user={user} token={token} />
    </div>
  );
};

export default MainContent;