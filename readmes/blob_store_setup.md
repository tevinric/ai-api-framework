# Azure Blob Storage Setup Guide for File Upload System

This guide covers setting up Azure Blob Storage to work with the file upload API endpoints.

## 1. Create an Azure Storage Account

1. Log in to the Azure Portal (https://portal.azure.com)
2. Click on "Create a resource"
3. Search for "Storage account" and select it
4. Click "Create"
5. Fill in the required details:
   - **Subscription**: Choose your Azure subscription
   - **Resource Group**: Create a new one or use an existing group
   - **Storage account name**: Choose a globally unique name (this will be used in URLs)
   - **Region**: Choose a region close to your application users
   - **Performance**: Standard
   - **Redundancy**: Locally-redundant storage (LRS) for cost savings, or choose higher redundancy as needed

6. Click "Review + create", then click "Create"

## 2. Configure Blob Storage Access

1. Once your storage account is created, navigate to it in the Azure Portal
2. In the left menu, under "Data storage," select "Containers"
3. Click "+ Container" to create a new container:
   - **Name**: Enter `file-uploads` (or your preferred container name matching the environment variable)
   - **Public access level**: Choose based on your requirements:
     - **Private**: No anonymous access (recommended for sensitive files)
     - **Blob**: Anonymous read access for blobs only (good for public downloads)
     - **Container**: Anonymous read access for entire container (use with caution)

4. Click "Create"

## 3. Configure CORS (Cross-Origin Resource Sharing)

If your frontend application will directly access the blob storage:

1. In your storage account, go to "Settings" > "Resource sharing (CORS)"
2. Click "+ Add" and enter the following:
   - **Allowed origins**: Enter your application's domain (e.g., `https://yourappdomain.com`) or `*` for testing
   - **Allowed methods**: Select the methods you need (at minimum: GET, HEAD)
   - **Allowed headers**: Include `*`
   - **Exposed headers**: Include `*`
   - **Max age**: 86400 (or your preferred value)
3. Click "Save"

## 4. Get Storage Account Connection String

1. In your storage account, go to "Settings" > "Access keys"
2. Find the "Connection string" for key1 or key2
3. Click the "Copy to clipboard" button
4. Add this connection string to your application's environment variables as `AZURE_STORAGE_CONNECTION_STRING`

## 5. Configure Additional Environment Variables

Make sure your application has these environment variables set:

```
AZURE_STORAGE_ACCOUNT=yourstorageaccountname
AZURE_STORAGE_UPLOAD_CONTAINER=file-uploads
AZURE_STORAGE_CONNECTION_STRING=your-connection-string-from-step-4
```

## 6. Security Considerations

1. **Shared Access Signatures (SAS)**: For production environments, consider using SAS tokens instead of public access, which provide time-limited access to specific resources.

2. **Access Control**: The API implements user-level access control, ensuring users can only access files they uploaded (unless they're administrators).

3. **Storage Firewall**: In the Azure Portal, go to your storage account > "Settings" > "Networking" to restrict network access to your storage account.

## 7. Testing the File Upload System

1. Use a tool like Postman to test your endpoints:
   - `POST /upload-file` with a file in the request body
   - `GET /get-file-url?file_id={id}` to retrieve a file URL
   - `DELETE /delete-file` with file_id in the request body

2. Remember to include your API-Key in the request headers for authentication

## 8. Monitoring and Management

1. **Azure Monitor**: In the Azure Portal, navigate to your storage account > "Monitoring" to view metrics
2. **Azure Storage Explorer**: Download and install the Azure Storage Explorer application for easier management of your blobs

## Troubleshooting

1. **Permissions Issues**: Ensure your application's managed identity or service principal has the necessary permissions
2. **CORS Issues**: If browser uploads fail, check your CORS configuration
3. **Connection String**: Verify your connection string is correctly formatted and includes the account key
4. **Container Name**: Ensure the container name in your code matches the one in Azure