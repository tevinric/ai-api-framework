# Set up Proces

This process highlihgts how to create a MS Entra App for token generation

## First, Microsoft Entra ID Setup:

    - Go to Microsoft Entra admin center (https://entra.microsoft.com) 
    - Navigate to "Applications" → "App registrations" 
    - Click "New registration" Name: Enter a name (e.g., "FlaskTokenService") 
    - Supported account types: Select "Accounts in this organizational directory only" Click "Register"

## Configure API Permissions:

    - In your registered app, select "API permissions" Click "Add a permission" Choose "Microsoft Graph" Select "Application permissions" Add these permissions:

        a. User.Read.All 
        b. Application.Read.All 
        c. Directory.Read.All

    - Click "Add permissions" Click "Grant admin consent"

## Create Client Secret:

    - Go to "Certificates & secrets" 
    - Click "New client secret" 
    - Add description (e.g., "Token Service Secret") 
    - Choose expiry (recommend 12 months for testing, 24 months for production) 
    - Save the generated secret immediately

## Note Down Your Values:

    - From "Overview" page, copy:

        - Application (client) ID 
        - Directory (tenant) ID

    - Save the client secret from step 3