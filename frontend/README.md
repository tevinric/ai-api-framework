# Admin Portal Frontend

React-based admin portal for the AI API Framework.

## Features

- **Authentication Flow**: Automatically loads admin email from `.env` and validates user access
- **Scope Validation**: Only allows users with scope 0 (admin) to access the portal
- **Token Management**: Generates and manages authentication tokens using API keys
- **User Details Display**: Shows username, department, and user ID in sidebar
- **Debug Information**: Comprehensive logging for troubleshooting
- **Responsive Design**: Clean, professional interface

## Setup

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Configure environment variables in `.env`:
   ```
   REACT_APP_API_BASE_URL=http://gaia.com
   REACT_APP_ADMIN_EMAIL=your-admin@email.com
   ```

3. Start the development server:
   ```bash
   npm start
   ```

## Environment Variables

- `REACT_APP_API_BASE_URL`: Backend API base URL (reads dynamically)
- `REACT_APP_ADMIN_EMAIL`: Admin email address for authentication

## Application Flow

1. **Load Configuration**: Reads API base URL and admin email from environment
2. **User Lookup**: Calls `/admin/user-details` endpoint with admin email
3. **Scope Validation**: Ensures user scope is 0 (admin access)
4. **Token Generation**: Uses user's API key to generate authentication token via `/token` endpoint
5. **Session Management**: Stores token in session state for API calls
6. **UI Display**: Shows user details in sidebar and main dashboard

## Debug Features

- Console logging throughout the application for troubleshooting
- Debug information panel showing user details and session state
- Error handling with detailed error messages
- Network request/response logging

## Components

- `App.js`: Main application component
- `Sidebar.js`: Navigation sidebar with user details
- `MainContent.js`: Main dashboard content
- `LoadingScreen.js`: Loading state display
- `ErrorScreen.js`: Error handling and retry functionality
- `useAuth.js`: Authentication hook managing the complete flow

## API Integration

The frontend integrates with:
- `/admin/user-details` - User lookup and scope validation
- `/token` - Authentication token generation