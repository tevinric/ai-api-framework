# Admin Portal Authentication Flow - Corrected Implementation

## Overview

This document explains the corrected authentication flow for the admin portal, clarifying when each API is used and how the authentication process works.

## Authentication Flow Diagram

```
[User Login Attempt]
        ↓
[Email from Entra AD (PROD) or Dev Email (DEV)]
        ↓
[Call /admin/user-details?email=xxx (NO TOKEN REQUIRED)]
        ↓
[Check if user.scope === 0]
        ↓
   [YES] → [Get user.api_key] → [Generate Token via /token API] → [Store credentials] → [Login Success]
        ↓
   [NO] → [Return "Not Authorized" error] → [Login Failed]
```

## API Usage Breakdown

### 1. `/admin/user-details` (admin_get_user_details.py)

**Purpose**: Initial authentication validation - checks if user exists and has admin privileges

**When Used**: During login process (BEFORE token generation)

**Authentication Required**: **NO** - This is the authentication endpoint itself

**Request**: `GET /admin/user-details?email=user@example.com`

**Response** (if user has scope=0):
```json
{
  "user_id": "uuid",
  "user_name": "John Doe",
  "user_email": "user@example.com",
  "common_name": "John Doe", 
  "department": "IT",
  "scope": 0,
  "api_key": "user-api-key-uuid",
  "active": true
}
```

**Response** (if user doesn't have scope=0):
```json
{
  "error": "Authentication Error",
  "message": "User not authorized to access this application"
}
```

### 2. `/token` (get_token.py)

**Purpose**: Generate access token using the user's API key

**When Used**: After successful user validation, before accessing other admin APIs

**Authentication Required**: **YES** - Requires API-Key header

**Request**: 
```
GET /token
Headers: API-Key: {user.api_key from step 1}
```

**Response**:
```json
{
  "access_token": "generated-token",
  "expires_in": 3600,
  "expires_on": "2024-01-01T12:00:00Z",
  "token_type": "Bearer"
}
```

### 3. `/admin/users` (admin_get_all_users.py)

**Purpose**: Get list of all users for display in admin portal

**When Used**: **AFTER** successful authentication to populate user management page

**Authentication Required**: **YES** - Requires both API-Key header and valid token parameter

**Request**: 
```
GET /admin/users?token={access_token}
Headers: API-Key: {user.api_key}
```

**Response**:
```json
{
  "users": [
    {
      "user_id": "uuid",
      "user_name": "User 1",
      "user_email": "user1@example.com",
      "scope": 1,
      "active": true,
      "department": "Finance"
    }
  ],
  "total_count": 50
}
```

## Step-by-Step Authentication Process

### Development Mode (REACT_APP_DISABLE_LOGIN=true)

1. **User Action**: Clicks "Continue as Test User"
2. **Email Source**: Uses `REACT_APP_DEV_USER_EMAIL` (default: gaiatester@test.com)
3. **User Lookup**: Call `/admin/user-details?email=gaiatester@test.com` (no token needed)
4. **Scope Check**: Verify `response.scope === 0`
5. **Token Generation**: Call `/token` with `API-Key: response.api_key`
6. **Store Credentials**: Save `api_key` and `access_token` to localStorage
7. **Store User Info**: Save user details to localStorage for sidebar display
8. **Redirect**: Navigate to dashboard

### Production Mode (REACT_APP_DISABLE_LOGIN=false)

1. **User Action**: Clicks "Sign In with Azure AD"
2. **Azure AD Auth**: MSAL handles popup authentication
3. **Email Source**: Extract from `loginResponse.account.username`
4. **User Lookup**: Call `/admin/user-details?email={azure_email}` (no token needed)
5. **Scope Check**: Verify `response.scope === 0`
6. **Token Generation**: Call `/token` with `API-Key: response.api_key`
7. **Store Credentials**: Save `api_key` and `access_token` to localStorage
8. **Store User Info**: Save user details to localStorage for sidebar display
9. **Redirect**: Navigate to dashboard
10. **Error Handling**: If user not admin, logout from Azure AD and show error

## UI Components and User Information Display

### Sidebar User Information
The corrected implementation now displays:
- **User Avatar**: Profile icon
- **Display Name**: `common_name` or fallback to `user_name`
- **Department**: `department` field from user details
- **Email**: `user_email`
- **Dev Indicator**: "DEV USER" chip in development mode

### Header Information
- **Welcome Message**: Shows user name in top bar
- **Environment Indicator**: "DEV MODE" chip in development
- **Logout/Reset Button**: Context-aware text

## Token Management

### Automatic Refresh
- **Timer**: Checks token validity every 4 minutes
- **Refresh Endpoint**: Uses `/refresh-token` API
- **Refresh Trigger**: When token expires in less than 5 minutes
- **Session State**: Updates expiration times in sessionStorage

### Security Features
- **Scope Validation**: Only scope=0 users can access
- **Token Validation**: All subsequent APIs require valid token
- **Automatic Cleanup**: Credentials cleared on logout

## Database Requirements

For the authentication flow to work:

### Development Mode
```sql
-- Ensure test user exists with admin privileges
INSERT INTO users (user_name, user_email, common_name, department, scope, active)
VALUES ('Test Admin', 'gaiatester@test.com', 'Test Admin User', 'IT Development', 0, 1);
```

### Production Mode
```sql
-- Ensure production admin users have scope = 0
UPDATE users SET scope = 0 WHERE user_email IN (
  'admin1@company.com',
  'admin2@company.com'
);
```

## Environment Configuration

### .env for Development
```bash
REACT_APP_ENVIRONMENT=DEV
REACT_APP_DISABLE_LOGIN=true
REACT_APP_API_BASE_URL=https://gaia.com
REACT_APP_DEV_USER_EMAIL=gaiatester@test.com
```

### .env for Production
```bash
REACT_APP_ENVIRONMENT=PROD
REACT_APP_DISABLE_LOGIN=false
REACT_APP_API_BASE_URL=https://gaia.com
REACT_APP_AZURE_CLIENT_ID=your-client-id
REACT_APP_AZURE_TENANT_ID=your-tenant-id
REACT_APP_AZURE_REDIRECT_URI=https://your-domain.com
```

## Testing the Flow

### Manual Testing Steps

1. **Verify Database Setup**:
   - Ensure test user exists with scope=0 in development
   - Ensure your Azure AD email exists with scope=0 in production

2. **Test Development Mode**:
   - Set `REACT_APP_DISABLE_LOGIN=true`
   - Start application: `npm start`
   - Click "Continue as Test User"
   - Verify redirect to dashboard
   - Check sidebar shows user name and department
   - Check browser localStorage contains `adminApiKey` and `adminToken`

3. **Test Production Mode**:
   - Set `REACT_APP_DISABLE_LOGIN=false`
   - Configure Azure AD settings
   - Click "Sign In with Azure AD"
   - Complete Azure authentication
   - Verify admin validation and redirect

4. **Test Error Cases**:
   - Try with user that has scope ≠ 0
   - Verify proper error message
   - Verify no credentials stored

## Troubleshooting

### Common Issues

1. **"User not authorized" in dev mode**:
   - Check if `gaiatester@test.com` exists in database
   - Verify user has `scope = 0`

2. **Token generation fails**:
   - Verify user has valid `api_key` in database
   - Check `/token` endpoint is accessible

3. **Azure AD login works but admin access denied**:
   - Verify your Azure AD email exists in users table
   - Verify your user record has `scope = 0`

4. **Sidebar not showing user info**:
   - Check localStorage contains `currentUser` after login
   - Verify user details were properly stored during authentication

This corrected implementation ensures the authentication flow works exactly as intended, with clear separation between authentication APIs and administrative APIs.