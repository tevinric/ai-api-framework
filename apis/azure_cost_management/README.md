# Azure Cost Management API

This API provides hierarchical cost breakdown for Azure subscriptions.

## Features

- Hierarchical cost structure: Subscription → Resource Groups → Resources
- Automatic subscription ID from environment variables
- Cost data in both original currency and USD
- Summary endpoint for quick overview
- Sorted results by cost (highest first)

## Setup

### 1. Azure Service Principal

Create a service principal with Cost Management Reader role:

```bash
# Create service principal
az ad sp create-for-rbac --name "cost-management-reader" --role "Cost Management Reader" --scopes /subscriptions/{subscription-id}

# Note the output:
# - appId (use as ENTRA_APP_CLIENT_ID)
# - password (use as ENTRA_APP_CLIENT_SECRET)
# - tenant (use as ENTRA_APP_TENANT_ID)
```

### 2. Environment Variables

Update the `.env` file in the project root with your Azure credentials:

```env
ENTRA_APP_TENANT_ID=your_tenant_id_here
ENTRA_APP_CLIENT_ID=your_client_id_here
ENTRA_APP_CLIENT_SECRET=your_client_secret_here
AZURE_SUBSCRIPTION_ID=your_subscription_id_here
```

### 3. Test Configuration

Run the test script to verify your setup:

```bash
python test_azure_credentials.py
```

## API Endpoints

### Get Detailed Cost Breakdown

```http
GET /azure/costs
```

**Parameters:**
- `subscription_id` (optional): Azure subscription ID. Uses `AZURE_SUBSCRIPTION_ID` from environment if not provided
- `start_date` (optional): Start date in YYYY-MM-DD format (defaults to 30 days ago)
- `end_date` (optional): End date in YYYY-MM-DD format (defaults to today)

**Headers:**
- `API-Key`: Your API key for authentication

**Response:**
```json
{
  "subscription": {
    "id": "subscription-id",
    "totalCost": 1500.00,
    "totalCostUSD": 1425.00,
    "currency": "USD",
    "resourceGroups": {
      "rg-production": {
        "name": "rg-production",
        "totalCost": 800.00,
        "totalCostUSD": 760.00,
        "resources": [
          {
            "resourceId": "/subscriptions/.../virtualMachines/vm1",
            "resourceName": "vm1",
            "resourceType": "Microsoft.Compute/virtualMachines",
            "serviceName": "Virtual Machines",
            "cost": 500.00,
            "costUSD": 475.00,
            "currency": "USD"
          }
        ]
      }
    }
  },
  "dateRange": {
    "from": "2024-01-01",
    "to": "2024-01-31"
  },
  "metadata": {
    "queryTime": "2024-01-31T12:00:00",
    "rowCount": 150
  }
}
```

### Get Cost Summary

```http
GET /azure/costs/summary
```

**Parameters:**
- `subscription_id` (optional): Azure subscription ID. Uses `AZURE_SUBSCRIPTION_ID` from environment if not provided
- `days` (optional): Number of days to look back (default 30)

**Headers:**
- `API-Key`: Your API key for authentication

**Response:**
```json
{
  "subscription_id": "subscription-id",
  "total_cost": 1500.00,
  "total_cost_usd": 1425.00,
  "currency": "USD",
  "period_days": 30,
  "date_range": {
    "from": "2024-01-01",
    "to": "2024-01-31"
  },
  "top_resource_groups": [
    {
      "name": "rg-production",
      "cost": 800.00,
      "percentage": 56.14
    }
  ],
  "top_resources": [
    {
      "name": "vm1",
      "type": "Microsoft.Compute/virtualMachines",
      "service": "Virtual Machines",
      "cost": 500.00,
      "percentage": 35.09
    }
  ],
  "resource_group_count": 5,
  "total_resources": 25
}
```

## Error Handling

The API includes comprehensive error handling:

- **400 Bad Request**: Missing or invalid parameters
- **401 Unauthorized**: Invalid API key or Azure credentials
- **403 Forbidden**: Insufficient permissions for Cost Management API
- **500 Server Error**: Unexpected errors

## Troubleshooting

### 401 Unauthorized Error

If you see: `401 Client Error: Unauthorized for url: https://login.microsoftonline.com/None/oauth2/v2.0/token`

This means the Azure credentials are not set properly. Check:
1. Environment variables are set in `.env` file
2. The `.env` file is in the project root
3. The values are correct (not the placeholder values)

### Missing Environment Variables

Run `python test_azure_credentials.py` to check which variables are missing.

### Permission Errors

Ensure your service principal has the "Cost Management Reader" role at the subscription level.

## Security Notes

- Never commit the `.env` file to version control
- The `.env` file is already added to `.gitignore`
- Use strong, unique passwords for service principals
- Rotate credentials regularly
- Limit service principal permissions to minimum required