import React from 'react';
import './Dashboard.css';

const Dashboard = ({ user, token }) => {
  console.log('[DASHBOARD] Rendering dashboard for user:', user?.user_name);

  const stats = [
    {
      title: 'Active Users',
      value: '1,247',
      change: '+12.5%',
      changeType: 'positive',
      icon: '👥',
      color: '#4CAF50'
    },
    {
      title: 'API Requests',
      value: '89.2K',
      change: '+8.3%',
      changeType: 'positive',
      icon: '🔗',
      color: '#2196F3'
    },
    {
      title: 'Models Active',
      value: '24',
      change: '+2',
      changeType: 'positive',
      icon: '🧠',
      color: '#9C27B0'
    },
    {
      title: 'System Load',
      value: '67%',
      change: '-3.2%',
      changeType: 'negative',
      icon: '📊',
      color: '#FF9800'
    }
  ];

  const recentActivity = [
    {
      id: 1,
      type: 'user_created',
      message: 'New user registered: john.smith@company.com',
      time: '2 minutes ago',
      icon: '👤',
      status: 'success'
    },
    {
      id: 2,
      type: 'model_updated',
      message: 'GPT-4 model configuration updated',
      time: '15 minutes ago',
      icon: '🧠',
      status: 'info'
    },
    {
      id: 3,
      type: 'api_limit',
      message: 'Rate limit exceeded for endpoint /llm/gpt-4o',
      time: '32 minutes ago',
      icon: '⚠️',
      status: 'warning'
    },
    {
      id: 4,
      type: 'system_backup',
      message: 'Automated system backup completed',
      time: '1 hour ago',
      icon: '💾',
      status: 'success'
    },
    {
      id: 5,
      type: 'user_login',
      message: 'Admin login from IP: 192.168.1.100',
      time: '2 hours ago',
      icon: '🔐',
      status: 'info'
    }
  ];

  const quickActions = [
    { title: 'Create User', icon: '👤', color: '#4CAF50', href: '#users/create' },
    { title: 'Deploy Model', icon: '🚀', color: '#2196F3', href: '#models/deploy' },
    { title: 'View Logs', icon: '📋', color: '#9C27B0', href: '#logs' },
    { title: 'System Config', icon: '⚙️', color: '#FF9800', href: '#settings' }
  ];

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>System Overview</h1>
        <p>Monitor and manage your AI API infrastructure</p>
      </div>

      <div className="stats-grid">
        {stats.map((stat, index) => (
          <div key={index} className="stat-card" style={{'--accent-color': stat.color}}>
            <div className="stat-icon" style={{color: stat.color}}>
              {stat.icon}
            </div>
            <div className="stat-content">
              <div className="stat-value">{stat.value}</div>
              <div className="stat-title">{stat.title}</div>
              <div className={`stat-change ${stat.changeType}`}>
                {stat.change}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-section activity-section">
          <div className="section-header">
            <h3>Recent Activity</h3>
            <button className="view-all-btn">View All</button>
          </div>
          <div className="activity-list">
            {recentActivity.map((activity) => (
              <div key={activity.id} className={`activity-item ${activity.status}`}>
                <div className="activity-icon">{activity.icon}</div>
                <div className="activity-content">
                  <p className="activity-message">{activity.message}</p>
                  <span className="activity-time">{activity.time}</span>
                </div>
                <div className={`activity-status ${activity.status}`}></div>
              </div>
            ))}
          </div>
        </div>

        <div className="dashboard-section quick-actions-section">
          <div className="section-header">
            <h3>Quick Actions</h3>
          </div>
          <div className="quick-actions-grid">
            {quickActions.map((action, index) => (
              <a key={index} href={action.href} className="quick-action-card">
                <div className="action-icon" style={{color: action.color}}>
                  {action.icon}
                </div>
                <span>{action.title}</span>
              </a>
            ))}
          </div>
        </div>

        <div className="dashboard-section system-health-section">
          <div className="section-header">
            <h3>System Health</h3>
          </div>
          <div className="health-metrics">
            <div className="health-metric">
              <div className="metric-label">CPU Usage</div>
              <div className="metric-bar">
                <div className="metric-fill" style={{width: '45%', backgroundColor: '#4CAF50'}}></div>
              </div>
              <div className="metric-value">45%</div>
            </div>
            <div className="health-metric">
              <div className="metric-label">Memory</div>
              <div className="metric-bar">
                <div className="metric-fill" style={{width: '62%', backgroundColor: '#FF9800'}}></div>
              </div>
              <div className="metric-value">62%</div>
            </div>
            <div className="health-metric">
              <div className="metric-label">Storage</div>
              <div className="metric-bar">
                <div className="metric-fill" style={{width: '28%', backgroundColor: '#4CAF50'}}></div>
              </div>
              <div className="metric-value">28%</div>
            </div>
            <div className="health-metric">
              <div className="metric-label">Network</div>
              <div className="metric-bar">
                <div className="metric-fill" style={{width: '73%', backgroundColor: '#F44336'}}></div>
              </div>
              <div className="metric-value">73%</div>
            </div>
          </div>
        </div>

        <div className="dashboard-section session-info-section">
          <div className="section-header">
            <h3>Session Information</h3>
          </div>
          <div className="session-details">
            <div className="session-item">
              <span className="session-label">User ID</span>
              <span className="session-value">{user?.user_id?.substring(0, 12)}...</span>
            </div>
            <div className="session-item">
              <span className="session-label">Email</span>
              <span className="session-value">{user?.user_email}</span>
            </div>
            <div className="session-item">
              <span className="session-label">Department</span>
              <span className="session-value">{user?.department || 'N/A'}</span>
            </div>
            <div className="session-item">
              <span className="session-label">Access Level</span>
              <span className="session-value admin-badge">Administrator</span>
            </div>
            <div className="session-item">
              <span className="session-label">Token Status</span>
              <span className="session-value token-active">Active</span>
            </div>
            <div className="session-item">
              <span className="session-label">Last Login</span>
              <span className="session-value">Just now</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;