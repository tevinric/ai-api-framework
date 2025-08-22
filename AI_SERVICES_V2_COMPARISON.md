# Azure AI Services API v2 - Consolidated Meter Costs

## Overview

The new **AI Services v2 API** consolidates identical meters across all resource groups to provide total spending per meter type across your entire Azure subscription.

## API Endpoints

| Version | Endpoint | Purpose |
|---------|----------|---------|
| **v1** | `/azure/costs/ai-services` | Detailed hierarchical view with resource groups → resources → services → meters |
| **v2** | `/azure/costs/ai-services-v2` | **Consolidated view with total cost per unique meter across all resource groups** |

## Key Differences

### **v1 (Original) - Hierarchical View**
```json
{
  "resource_groups": {
    "rg-prod": {
      "resources": {
        "ai-service-1": {
          "services": {
            "Cognitive Services": {
              "meters": [
                {"meter_name": "gpt-4o 1120 Outp glbl Tokens", "cost_usd": 5.45}
              ]
            }
          }
        }
      }
    },
    "rg-dev": {
      "resources": {
        "ai-service-2": {
          "services": {
            "Cognitive Services": {
              "meters": [
                {"meter_name": "gpt-4o 1120 Outp glbl Tokens", "cost_usd": 10.00}
              ]
            }
          }
        }
      }
    }
  }
}
```

### **v2 (New) - Consolidated View**
```json
{
  "consolidated_meters": {
    "gpt-4o 1120 Outp glbl Tokens_Cognitive Services": {
      "meter_name": "gpt-4o 1120 Outp glbl Tokens",
      "service_name": "Cognitive Services",
      "total_cost_usd": 15.45,  // ← CONSOLIDATED: 5.45 + 10.00
      "instances_aggregated": 2,
      "model": "gpt-4o-1120",
      "usage_type": "output_tokens"
    }
  },
  "meter_usage_summary": [
    {
      "meter_name": "gpt-4o 1120 Outp glbl Tokens",
      "total_cost_usd": 15.45,
      "model": "gpt-4o-1120",
      "usage_type": "output_tokens"
    }
  ]
}
```

## Query Structure Differences

### **v1 Query - Includes ResourceId**
```json
{
  "dataset": {
    "grouping": [
      {"name": "ServiceName"},
      {"name": "MeterCategory"},
      {"name": "MeterSubCategory"},
      {"name": "Meter"},
      {"name": "ResourceId"}  // ← Separates by resource
    ]
  }
}
```

### **v2 Query - No ResourceId**
```json
{
  "dataset": {
    "grouping": [
      {"name": "ServiceName"},
      {"name": "MeterCategory"},
      {"name": "MeterSubCategory"},
      {"name": "Meter"}  // ← No ResourceId = consolidates across resources
    ]
  }
}
```

## Use Cases

### **When to Use v1 (Hierarchical)**
- **Resource-level analysis**: Need to see which specific resources are consuming costs
- **Resource group breakdown**: Need costs organized by resource groups
- **Detailed attribution**: Want to trace costs back to specific Azure resources
- **Budget allocation**: Allocating costs to specific projects/teams by resource group

**Example Questions v1 Answers:**
- "Which resource in rg-prod is using the most GPT-4o tokens?"
- "What's the cost breakdown for ai-service-1 vs ai-service-2?"
- "How much is each resource group spending on different AI services?"

### **When to Use v2 (Consolidated)**
- **Meter-level analysis**: Need to see total spending per meter type subscription-wide
- **Cost optimization**: Identify highest-cost meters regardless of where they're used
- **Model usage analysis**: Understand total usage patterns across all resources
- **Executive reporting**: High-level view of AI spending by service type

**Example Questions v2 Answers:**
- "What's our total spending on GPT-4o output tokens across all resources?"
- "Which AI meters are costing us the most money overall?"
- "How much are we spending on each AI model across the entire subscription?"
- "What's our total Cognitive Services spending by meter type?"

## Response Structure Comparison

### **v1 Response Structure**
```
resource_groups {}
├── [resource_group_name] {}
    ├── resources {}
        ├── [resource_name] {}
            ├── services {}
                ├── [service_name] {}
                    └── meters []
                        └── individual meter records
```

### **v2 Response Structure**
```
consolidated_meters {}        ← Main feature: total cost per unique meter
├── [meter_key] {}
    ├── meter_name
    ├── total_cost_usd         ← Summed across ALL resource groups
    ├── instances_aggregated   ← Count of consolidated instances
    └── model info

service_breakdown {}          ← Costs grouped by service
model_breakdown {}           ← Costs grouped by AI model  
meter_usage_summary []       ← Flat array sorted by cost
```

## Example Scenarios

### **Scenario 1: Multiple Resource Groups Using Same Meter**

**Setup:**
- `rg-prod`: GPT-4o output tokens = $100
- `rg-dev`: GPT-4o output tokens = $50  
- `rg-test`: GPT-4o output tokens = $25

**v1 Result:** Three separate entries showing $100, $50, $25 in different resource groups
**v2 Result:** Single consolidated entry showing $175 total

### **Scenario 2: Same Service Across Different Resources**

**Setup:**
- `ai-service-east`: Cognitive Services meters
- `ai-service-west`: Cognitive Services meters
- `ai-service-central`: Cognitive Services meters

**v1 Result:** Meters organized under each individual service
**v2 Result:** All Cognitive Services meters consolidated regardless of which service generated them

## Benefits of v2

✅ **Simplified Reporting**: One number per meter type across entire subscription  
✅ **Cost Optimization**: Easily identify highest-cost meters for optimization  
✅ **Executive Dashboards**: Clean, high-level view without resource complexity  
✅ **Model Analysis**: Total spending per AI model across all deployments  
✅ **Billing Reconciliation**: Match Azure billing totals per meter  

## Implementation Details

### **Query Optimization**
- **v2 uses fewer grouping dimensions** (4 vs 5) for better performance
- **No ResourceId grouping** enables automatic consolidation at the API level
- **Same aggregation settings** ensure cost accuracy

### **Response Processing**
- **Unique meter keys** prevent duplicate consolidation
- **Instance counting** tracks how many individual meters were consolidated
- **Model parsing** works identically to v1
- **Cost sorting** maintains consistent ordering

### **Fallback Support**
- **Same fallback logic** as v1 when direct Azure API calls fail
- **Client-side consolidation** when needed for edge cases
- **Error handling** maintains API reliability

## Migration Guide

### **For Existing v1 Users**
1. **No breaking changes** - v1 continues to work unchanged
2. **Use v2 for new use cases** requiring meter consolidation
3. **Both APIs can be used together** for different purposes

### **Response Mapping**
```javascript
// v1: Access individual meters
response.resource_groups[rgName].resources[resourceName].services[serviceName].meters[0].cost_usd

// v2: Access consolidated meters
response.consolidated_meters[meterKey].total_cost_usd
response.meter_usage_summary[0].total_cost_usd  // Top meter by cost
```

---

## Summary

**AI Services v2** provides a powerful consolidated view that answers the question: *"How much am I spending on each unique meter type across my entire Azure subscription?"*

This complements the existing detailed hierarchical view in v1, giving you both granular resource-level details and high-level meter consolidation as needed for different use cases.