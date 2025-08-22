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

### 1. Get Detailed Cost Breakdown

```http
GET /azure/costs
```

**Parameters:**
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

### 2. Get Cost Summary

```http
GET /azure/costs/summary
```

**Parameters:**
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

### 3. Get Period-Based Costs

```http
GET /azure/costs/period
```

**Parameters:**
- `period` (optional): Period type - 'mtd' (month-to-date), 'ytd' (year-to-date), or 'custom' (default 'mtd')
- `start_period` (optional): For custom period, start in YYYYMM format (e.g., 202401)
- `end_period` (optional): For custom period, end in YYYYMM format (e.g., 202412)

**Headers:**
- `API-Key`: Your API key for authentication

**Examples:**

Month-to-date:
```http
GET /azure/costs/period?period=mtd
```

Year-to-date:
```http
GET /azure/costs/period?period=ytd
```

Custom period (Jan-Mar 2024):
```http
GET /azure/costs/period?period=custom&start_period=202401&end_period=202403
```

**Response:** Returns the same hierarchical structure as `/azure/costs` with additional period information.

### 4. Get AI/ML/Cognitive Services Costs

```http
GET /azure/costs/ai-services
```

**Parameters:**
- `start_date` (optional): Start date in YYYY-MM-DD format (defaults to 30 days ago)
- `end_date` (optional): End date in YYYY-MM-DD format (defaults to today)

**Headers:**
- `API-Key`: Your API key for authentication

**Response:**
```json
{
  "subscription_id": "subscription-id",
  "period": {
    "from": "2024-01-01",
    "to": "2024-01-31"
  },
  "total_ai_cost": 2500.00,
  "total_ai_cost_usd": 2375.00,
  "services": {
    "Azure OpenAI": {
      "name": "Azure OpenAI",
      "total_cost": 1800.00,
      "total_cost_usd": 1710.00,
      "resources": {
        "openai-prod": {
          "name": "openai-prod",
          "resource_id": "/subscriptions/.../openai-prod",
          "total_cost": 1800.00,
          "total_cost_usd": 1710.00,
          "meters": [
            {
              "meter_name": "GPT-4 Input Tokens",
              "meter_category": "Azure OpenAI Service",
              "usage_quantity": 5000000,
              "unit_of_measure": "1K Tokens",
              "cost": 300.00,
              "cost_usd": 285.00,
              "model": "gpt-4",
              "usage_type": "input_tokens"
            },
            {
              "meter_name": "GPT-4 Output Tokens",
              "usage_quantity": 2000000,
              "cost": 600.00,
              "cost_usd": 570.00,
              "model": "gpt-4",
              "usage_type": "output_tokens"
            }
          ]
        }
      }
    }
  },
  "models": {
    "gpt-4": {
      "model": "gpt-4",
      "total_cost": 900.00,
      "total_cost_usd": 855.00,
      "usage_breakdown": {
        "input_tokens": {
          "quantity": 5000000,
          "cost": 300.00,
          "cost_usd": 285.00,
          "unit": "1K Tokens"
        },
        "output_tokens": {
          "quantity": 2000000,
          "cost": 600.00,
          "cost_usd": 570.00,
          "unit": "1K Tokens"
        }
      }
    },
    "gpt-3.5-turbo": {
      "model": "gpt-3.5-turbo",
      "total_cost": 450.00,
      "total_cost_usd": 427.50,
      "usage_breakdown": {
        "input_tokens": {
          "quantity": 20000000,
          "cost": 200.00,
          "cost_usd": 190.00,
          "unit": "1K Tokens"
        },
        "output_tokens": {
          "quantity": 15000000,
          "cost": 250.00,
          "cost_usd": 237.50,
          "unit": "1K Tokens"
        }
      }
    },
    "text-embedding-ada-002": {
      "model": "text-embedding-ada-002",
      "total_cost": 50.00,
      "total_cost_usd": 47.50,
      "usage_breakdown": {
        "embeddings": {
          "quantity": 10000000,
          "cost": 50.00,
          "cost_usd": 47.50,
          "unit": "1K Tokens"
        }
      }
    }
  }
}
```

The AI services endpoint provides **meter-level detail matching Azure portal**:

### 🎯 **Exact Portal Match Structure**
- **Resource Group → Resource → Service → Meters** (same hierarchy as portal)
- **Every individual meter** with specific costs (e.g., "gpt-4o 1120 Outp glbl Tokens": $2.17)
- **Enhanced model detection** (gpt-4o-1120, gpt-4o-mini-0718, kontext-pro, etc.)
- **Token type parsing** (Inp/Outp/cached from meter names)
- **Regional detection** (glbl = global)

### 📊 **Comprehensive Cost Attribution**
- **Meter-level granularity** - every charge line item
- **Perfect for chargeback** and cost attribution
- **Model summary** with input/output/cached token breakdown
- **Service categorization** (Cognitive Services, Defender, etc.)
- **Sorted by cost** (highest first, matching portal)

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