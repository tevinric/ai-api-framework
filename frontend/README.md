# AI API Framework - Admin Portal

A React-based admin portal for managing users and endpoint access in the AI API Framework.

## Features

### User Management
- **Add Users**: Create new users with comprehensive profile information
- **Update Users**: Edit user details, scope levels, and active status
- **Delete Users**: Remove users from the system with confirmation
- **Search Users**: Find users by name, username, or email
- **User Profiles**: Complete user information including:
  - Basic info (name, email, username)
  - Organizational details (company, department, division, cost center)
  - Contact info (phone extension, manager details)
  - System settings (scope, active status, AIC balance)

### Endpoint Access Management
- **Search Users**: Find users by common name to view their current endpoint access
- **View User Endpoints**: See all endpoints a user currently has access to
- **Grant Access**: 
  - **Single**: Add access to one specific endpoint
  - **Multiple**: Select and add access to multiple endpoints at once
  - **All**: Grant access to all available endpoints
- **Remove Access**:
  - **Individual**: Remove access to specific endpoints
  - **All**: Remove access to all endpoints for a user

### Dashboard
- System statistics and overview
- Quick access to main functions
- Real-time status information

## Technical Stack

- **Frontend**: React 18 with Material-UI (MUI)
- **HTTP Client**: Axios for API communication
- **Routing**: React Router v6
- **State Management**: React Hooks (useState, useEffect)
- **Styling**: Material-UI theme system with custom styling

## Setup and Installation

1. **Install Dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Environment Configuration**
   Create a `.env` file in the frontend directory:
   ```
   REACT_APP_API_URL=http://localhost:5000
   ```

3. **Start Development Server**
   ```bash
   npm start
   ```
   
   The application will open at `http://localhost:3000`

## Authentication

The admin portal requires:
- **Admin API Key**: Your admin-level API key from the AI API Framework
- **Admin Token**: A valid authentication token

These credentials are stored in localStorage and used for all API requests.

## API Integration

The portal integrates with the following backend endpoints:

### User Management APIs
- `POST /admin/user` - Create new user
- `PUT /admin/user` - Update existing user  
- `POST /admin/delete-user` - Delete user
- `GET /admin/users` - Get all users
- `GET /admin/users/search` - Search users by name

### Endpoint Access APIs  
- `POST /admin/endpoint/access/single` - Grant single endpoint access
- `POST /admin/endpoint/access/multi` - Grant multiple endpoint access
- `POST /admin/endpoint/access/all` - Grant all endpoint access
- `DELETE /admin/endpoint/access/single` - Remove single endpoint access
- `DELETE /admin/endpoint/access/multi` - Remove multiple endpoint access
- `DELETE /admin/endpoint/access/all` - Remove all endpoint access
- `GET /admin/endpoints` - Get all available endpoints
- `GET /admin/user/{id}/endpoints` - Get user's accessible endpoints

## Security Features

- **Authentication Required**: All routes except login are protected
- **Automatic Token Validation**: Invalid tokens redirect to login
- **Secure Storage**: Credentials stored in localStorage with automatic cleanup
- **CORS Handling**: Proper cross-origin request handling
- **Error Handling**: Comprehensive error handling for API failures

## Database Schema Integration

The portal works with the following database structure:

- **users table**: User profiles and authentication
- **endpoints table**: Available API endpoints  
- **user_endpoint_access table**: Junction table linking users to their accessible endpoints

## Build for Production

```bash
npm run build
```

This creates an optimized production build in the `build` folder.

## Development Notes

- The portal uses a proxy configuration to route API calls to the backend
- All API calls include proper authentication headers (API-Key, X-Token)
- Correlation IDs are automatically generated for request tracking
- The Material-UI theme provides consistent styling across components
- Form validation ensures data integrity before submission

## Browser Support

- Modern browsers supporting ES6+
- Chrome, Firefox, Safari, Edge (latest versions)
- Mobile responsive design