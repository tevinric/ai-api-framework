# Cost Management APIs Documentation

## Overview
The Cost Management APIs provide comprehensive Azure subscription cost analysis and user-based cost apportionment. These APIs integrate with Azure Cost Management to retrieve detailed cost information and apportion costs based on individual user usage.

## Prerequisites

### Environment Variables
The following environment variables must be configured:

- `AZURE_SUBSCRIPTION_ID`: Your Azure subscription ID
- `ENTRA_APP_TENANT_ID`: Azure AD tenant ID
- `ENTRA_COST_CLIENT_ID`: Client ID for the service principal with Cost Management Reader access (falls back to `ENTRA_APP_CLIENT_ID`)
- `ENTRA_COST_CLIENT_SECRET`: Client secret for the service principal (falls back to `ENTRA_APP_CLIENT_SECRET`)

### Azure Permissions
The service principal must have the following permissions:
- **Cost Management Reader** role at the subscription level
- Access to read cost data for all resource groups

### Setting up the Service Principal
1. Create a service principal in Azure AD
2. Assign the "Cost Management Reader" role at the subscription level
3. Note the client ID, client secret, and tenant ID
4. Configure the environment variables

## API Endpoints

### 1. Get Cost by Resource Group
**Endpoint:** `POST /cost_management/resource_group`

Retrieves costs for specific or all resource groups with service-level breakdown.

**Request Body:**
```json
{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "resource_group": "optional-rg-name"
}
```

**Response:**
```json
{
    "message": "Resource group costs retrieved successfully",
    "costs_by_resource_group": {
        "rg-name": {
            "total_cost": 1234.56,
            "total_cost_usd": 1234.56,
            "services": {
                "Cognitive Services": {
                    "cost": 500.00,
                    "cost_usd": 500.00
                }
            }
        }
    },
    "total_cost": 1234.56,
    "total_cost_usd": 1234.56,
    "currency": "USD"
}
```

### 2. Get Total Cost for All Resource Groups
**Endpoint:** `POST /cost_management/all_resource_groups`

Retrieves aggregated costs for all resource groups in the subscription.

**Request Body:**
```json
{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
}
```

**Response:**
```json
{
    "message": "Total costs retrieved successfully",
    "costs_by_resource_group": {...},
    "total_cost": 5678.90,
    "total_cost_usd": 5678.90,
    "resource_group_count": 5,
    "currency": "USD"
}
```

### 3. Get Detailed Line Item Costs
**Endpoint:** `POST /cost_management/line_items`

Retrieves detailed line-item costs for individual resources.

**Request Body:**
```json
{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "resource_group": "optional-rg-name"
}
```

**Response:**
```json
{
    "message": "Line item costs retrieved successfully",
    "line_items": [
        {
            "resource_id": "/subscriptions/.../resourceGroups/.../providers/...",
            "resource_name": "resource-name",
            "resource_type": "Microsoft.CognitiveServices/accounts",
            "meter_category": "Cognitive Services",
            "meter_subcategory": "Language",
            "meter_name": "Text Analytics",
            "cost": 123.45,
            "quantity": 1000
        }
    ],
    "total_cost": 1234.56,
    "item_count": 50,
    "currency": "USD"
}
```

### 4. Get User Apportioned Costs
**Endpoint:** `POST /cost_management/user_apportioned`

Calculates user-specific costs based on their usage proportion.

**Request Body:**
```json
{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
}
```

**Response:**
```json
{
    "message": "User apportioned costs retrieved successfully",
    "user_id": "user_123",
    "user_cost_breakdown": {
        "rg-name": {
            "services": {
                "Cognitive Services": {
                    "cost": 50.00,
                    "cost_usd": 50.00,
                    "usage_proportion": 0.1,
                    "matched_models": ["gpt-4", "gpt-4o"]
                }
            },
            "total_cost": 50.00,
            "total_cost_usd": 50.00
        }
    },
    "usage_summary": {
        "total_tokens": 100000,
        "total_requests": 500
    },
    "total_apportioned_cost": 123.45
}
```

## Cost Apportionment Logic

The system apportions costs based on:

1. **Token Usage**: For LLM services, costs are distributed based on the proportion of tokens consumed
2. **Request Count**: For APIs charged per request
3. **Storage Usage**: For blob storage and file services
4. **Audio Processing**: For speech services based on audio seconds processed
5. **Image Generation**: Based on number of images generated

### Service Mapping
The system maps Azure services to specific models:
- **Cognitive Services** → GPT models, DALL-E, Whisper, TTS
- **Storage** → File uploads, image storage
- **Document Intelligence** → OCR and document processing

## Authentication

All endpoints require authentication via the `X-Token` header:

```bash
curl -X POST https://api.example.com/cost_management/resource_group \
  -H "X-Token: your-token-here" \
  -H "Content-Type: application/json" \
  -d '{"start_date":"2024-01-01","end_date":"2024-01-31"}'
```

## Error Handling

Common error responses:

- **401 Unauthorized**: Invalid or missing token
- **400 Bad Request**: Invalid date format or missing required fields
- **500 Internal Server Error**: Azure API errors or configuration issues

## Testing

Use the provided `test_cost_management.py` script to test the endpoints:

```python
python test_cost_management.py
```

Update the script with:
1. Valid authentication token
2. Correct server URL
3. Appropriate date ranges

## Integration with Usage Analytics

The cost management APIs integrate seamlessly with the existing usage analytics endpoints to provide:
- Accurate cost allocation per user
- Model-specific cost breakdown
- Service-level cost tracking
- Historical cost trends

## Performance Considerations

- Cost queries can take 5-10 seconds for large date ranges
- Cache results when possible for frequently accessed data
- Use smaller date ranges for real-time dashboards
- Consider implementing background jobs for heavy reports

## Troubleshooting

### Common Issues

1. **"Client not found" error**
   - Verify service principal exists in Azure AD
   - Check CLIENT_ID environment variable

2. **"Insufficient permissions" error**
   - Ensure Cost Management Reader role is assigned
   - Verify subscription ID is correct

3. **No cost data returned**
   - Check if costs are available for the date range
   - Verify resource groups exist in the subscription
   - Allow 24-48 hours for cost data to be available

## Future Enhancements

- [ ] Budget alerts and notifications
- [ ] Cost forecasting based on usage trends
- [ ] Departmental cost allocation
- [ ] Export to CSV/Excel functionality
- [ ] Real-time cost monitoring dashboard
- [ ] Cost optimization recommendations