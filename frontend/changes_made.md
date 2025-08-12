# Admin Portal Changes Made

This document outlines all the changes made to implement the admin portal according to the requirements in CLAUDE.md.

## Overview

Implemented a comprehensive admin portal with React frontend and Python backend APIs that supports:
- Environment-based authentication (DEV bypass vs PROD Azure AD)
- User management with CRUD operations
- Token generation and automatic refresh
- Admin-only access control

## Backend API Changes

### 1. New Admin API Endpoints

#### **apis/admin/admin_get_user_details.py** (NEW)
- **Route**: `GET /admin/user-details`
- **Purpose**: Get user details by email address (Admin only)
- **Authentication**: Requires scope=0 (admin) user
- **Response**: Returns user details including API key if scope=0, otherwise returns unauthorized error
- **Key Features**:
  - Email-based user lookup
  - Admin scope validation
  - Returns full user profile with API key for valid admin users

#### **apis/admin/admin_get_all_users.py** (NEW)
- **Route**: `GET /admin/users`
- **Purpose**: Get all users in the system (Admin only)
- **Authentication**: Requires admin API key and valid token
- **Response**: Returns paginated list of all users with metadata
- **Key Features**:
  - Admin-only access control
  - Comprehensive user data including balance information
  - Sorted by creation date

### 2. Database Service Updates

#### **apis/utils/databaseService.py** (MODIFIED)
- **Added**: `get_user_by_email(email)` method
- **Purpose**: Database lookup for user by email address
- **Returns**: Complete user record including all profile fields and API key
- **Usage**: Used by both dev and prod authentication flows

### 3. App Registration

#### **app.py** (MODIFIED)
- **Added**: Registration of new admin endpoints
- **Lines**: 194-199 for user details and get all users endpoints
- **Integration**: Properly integrated with existing middleware and logging

## Frontend Changes

### 1. Authentication System

#### **src/services/authService.js** (NEW)
- **Dual Authentication**: Supports both Azure AD (PROD) and bypass (DEV)
- **Environment Detection**: Automatically switches based on `REACT_APP_ENVIRONMENT` and `REACT_APP_DISABLE_LOGIN`
- **Token Management**: Handles token generation, validation, and automatic refresh
- **User Validation**: Validates admin access through `/admin/user-details` endpoint
- **Key Features**:
  - MSAL integration for Azure AD
  - Development mode with test user (gaiatester@test.com)
  - Automatic token refresh every 4 minutes
  - Session state management
  - Proper logout handling

#### **src/utils/auth.js** (MODIFIED)
- **Updated**: To use new authService instead of simple localStorage checks
- **Added**: `getCurrentUser()` function
- **Integration**: Seamless integration with existing components

### 2. Login System

#### **src/pages/LoginPage.js** (MODIFIED)
- **Environment-Aware UI**: Different UI for DEV vs PROD modes
- **DEV Mode**: Shows "Continue as Test User" button with info banner
- **PROD Mode**: Shows "Sign In with Azure AD" button
- **Integration**: Uses authService for all authentication operations
- **User Experience**: Clear messaging about authentication mode

#### **src/App.js** (MODIFIED)
- **MSAL Provider**: Conditionally wraps app with MsalProvider only in PROD mode
- **Route Protection**: Enhanced integration with authentication service
- **Performance**: Avoids MSAL overhead in development mode

### 3. Enhanced Components

#### **src/components/Layout.js** (MODIFIED)
- **User Display**: Shows current user name in header
- **Environment Indicator**: DEV MODE chip when in development
- **Logout Functionality**: Environment-aware logout (Reset in DEV, Logout in PROD)
- **User Context**: Displays welcome message with current user info

#### **src/components/ProtectedRoute.js** (MODIFIED)
- **Token Refresh**: Automatically starts token refresh timer for authenticated users
- **Smart Protection**: Only starts token management in production mode
- **Performance**: Efficient authentication checking

### 4. API Integration

#### **src/services/api.js** (MODIFIED)
- **Base URL**: Updated to use `REACT_APP_API_BASE_URL` referencing https://gaia.com
- **New Endpoints**: Added `getUserDetailsByEmail()` method
- **Environment Handling**: Proper header management for both DEV and PROD modes
- **Token Integration**: Works seamlessly with new authentication flow

### 5. Configuration

#### **frontend/.env.example** (NEW)
- **Environment Variables**: Complete example of required configuration
- **DEV/PROD Settings**: Clear separation of development and production config
- **Azure AD Config**: Template for production Azure AD integration
- **Default Values**: Sensible defaults for development

#### **frontend/package.json** (MODIFIED)
- **MSAL Packages**: Added @azure/msal-react and @azure/msal-browser
- **Dependencies**: All required packages for Azure AD integration

## Key Implementation Details

### Environment-Based Authentication Flow

#### Development Mode (REACT_APP_DISABLE_LOGIN=true)
1. User clicks "Continue as Test User"
2. System calls `/admin/user-details?email=gaiatester@test.com`
3. If user exists with scope=0, generates token using their API key
4. Stores credentials and user details in localStorage
5. Redirects to dashboard

#### Production Mode (REACT_APP_DISABLE_LOGIN=false)
1. User clicks "Sign In with Azure AD"
2. MSAL handles Azure AD popup authentication
3. Extracts user email from Azure AD response
4. Calls `/admin/user-details?email={user_email}`
5. If user exists with scope=0, generates token using their API key
6. Stores credentials and user details
7. If user not authorized, logs out from Azure AD and shows error

### Token Management

#### Automatic Refresh
- **Timer**: Checks token validity every 4 minutes
- **Threshold**: Refreshes token if less than 5 minutes until expiration
- **API Call**: Uses `/refresh-token` endpoint with current token
- **Session State**: Updates session storage with new expiration times
- **Error Handling**: Gracefully handles refresh failures

#### Security Features
- **Scope Validation**: Only users with scope=0 can access admin portal
- **Token Validation**: All admin APIs require valid API key and token
- **Session Management**: Proper cleanup on logout
- **Error Boundaries**: Comprehensive error handling for auth failures

## Database Schema Requirements

The implementation assumes the following user table structure (as defined in sql_init/users.sql):

```sql
CREATE TABLE users (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_name NVARCHAR(100) NOT NULL,
    user_email NVARCHAR(255) NOT NULL UNIQUE,
    api_key UNIQUEIDENTIFIER NOT NULL UNIQUE DEFAULT NEWID(),
    scope INT CHECK (scope IN (0,1,2,3,4,5)) DEFAULT 1,
    -- Additional fields as defined in schema
);
```

**Critical Requirements**:
- Admin users must have `scope = 0`
- The test user `gaiatester@test.com` must exist with scope=0 for development mode
- All admin users need valid `api_key` for token generation

## Environment Configuration

### Development Setup
```bash
# .env file
REACT_APP_ENVIRONMENT=DEV
REACT_APP_DISABLE_LOGIN=true
REACT_APP_API_BASE_URL=https://gaia.com
REACT_APP_DEV_USER_EMAIL=gaiatester@test.com
```

### Production Setup  
```bash
# .env file
REACT_APP_ENVIRONMENT=PROD
REACT_APP_DISABLE_LOGIN=false
REACT_APP_API_BASE_URL=https://gaia.com
REACT_APP_AZURE_CLIENT_ID=your-client-id
REACT_APP_AZURE_TENANT_ID=your-tenant-id
REACT_APP_AZURE_REDIRECT_URI=https://your-domain.com
```

## Usage

### Development Mode
1. Set environment variables for DEV mode
2. Ensure `gaiatester@test.com` exists in database with scope=0
3. Run `npm start`
4. Click "Continue as Test User" on login page
5. System automatically authenticates and redirects to dashboard

### Production Mode  
1. Configure Azure AD app registration
2. Set environment variables for PROD mode
3. Deploy application
4. Users authenticate through Azure AD
5. Only users in database with scope=0 can access admin portal

## Testing

### Dev Mode Testing
- Verify test user authentication works
- Test token generation and refresh
- Verify admin API access with test user credentials
- Test logout/reset functionality

### Prod Mode Testing
- Configure test Azure AD tenant
- Test Azure AD authentication flow
- Verify admin user validation
- Test unauthorized user rejection
- Test token management in production

## Security Considerations

1. **Admin Scope**: Only scope=0 users can access admin portal
2. **Token Security**: Tokens are validated and automatically refreshed
3. **Environment Separation**: Clear separation between dev and prod authentication
4. **API Key Protection**: API keys are only exposed to authorized admin users
5. **Session Management**: Proper credential cleanup on logout
6. **Error Handling**: Secure error messages that don't expose system details

## Files Modified/Created

### Backend Files
- **NEW**: `apis/admin/admin_get_user_details.py`
- **NEW**: `apis/admin/admin_get_all_users.py`
- **MODIFIED**: `apis/utils/databaseService.py`
- **MODIFIED**: `app.py`

### Frontend Files
- **NEW**: `src/services/authService.js`
- **NEW**: `.env.example`
- **MODIFIED**: `src/utils/auth.js`
- **MODIFIED**: `src/pages/LoginPage.js`
- **MODIFIED**: `src/App.js`
- **MODIFIED**: `src/components/Layout.js`
- **MODIFIED**: `src/components/ProtectedRoute.js`
- **MODIFIED**: `src/services/api.js`
- **MODIFIED**: `package.json`

All requirements from CLAUDE.md have been successfully implemented with a production-ready admin portal that supports both development and production authentication flows.