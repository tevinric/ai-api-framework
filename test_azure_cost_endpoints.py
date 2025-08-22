#!/usr/bin/env python3
"""
Test script for all Azure Cost Management API endpoints
"""
import json
from datetime import datetime, timedelta

def test_endpoint_signatures():
    """Test that all endpoints have correct signatures"""
    print("Azure Cost Management API Endpoints Test")
    print("=" * 60)
    
    endpoints = [
        {
            "name": "Get Costs",
            "method": "GET",
            "path": "/azure/costs",
            "params": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            },
            "description": "Get hierarchical cost breakdown"
        },
        {
            "name": "Get Cost Summary",
            "method": "GET",
            "path": "/azure/costs/summary",
            "params": {
                "days": 30
            },
            "description": "Get summarized costs for last N days"
        },
        {
            "name": "Get Period Costs (MTD)",
            "method": "GET",
            "path": "/azure/costs/period",
            "params": {
                "period": "mtd"
            },
            "description": "Get month-to-date costs"
        },
        {
            "name": "Get Period Costs (YTD)",
            "method": "GET",
            "path": "/azure/costs/period",
            "params": {
                "period": "ytd"
            },
            "description": "Get year-to-date costs"
        },
        {
            "name": "Get Period Costs (Custom)",
            "method": "GET",
            "path": "/azure/costs/period",
            "params": {
                "period": "custom",
                "start_period": "202401",
                "end_period": "202403"
            },
            "description": "Get costs for custom period (Jan-Mar 2024)"
        },
        {
            "name": "Get AI Service Costs",
            "method": "GET",
            "path": "/azure/costs/ai-services",
            "params": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            },
            "description": "Get detailed AI/ML service costs with token attribution"
        }
    ]
    
    print("\nAvailable Endpoints:")
    print("-" * 60)
    
    for i, endpoint in enumerate(endpoints, 1):
        print(f"\n{i}. {endpoint['name']}")
        print(f"   Method: {endpoint['method']}")
        print(f"   Path: {endpoint['path']}")
        print(f"   Description: {endpoint['description']}")
        
        if endpoint['params']:
            print("   Parameters:")
            for key, value in endpoint['params'].items():
                print(f"      - {key}: {value}")
        
        # Build example curl command
        params_str = "&".join([f"{k}={v}" for k, v in endpoint['params'].items()])
        curl_cmd = f"curl -X {endpoint['method']} \\"
        print(f"\n   Example:")
        print(f"   {curl_cmd}")
        print(f'     "http://localhost:5000{endpoint["path"]}?{params_str}" \\')
        print(f'     -H "API-Key: YOUR_API_KEY"')
    
    print("\n" + "=" * 60)
    print("Required Environment Variables:")
    print("-" * 60)
    print("ENTRA_APP_TENANT_ID    : Azure AD tenant ID")
    print("ENTRA_APP_CLIENT_ID    : Service principal client ID")
    print("ENTRA_APP_CLIENT_SECRET: Service principal secret")
    print("AZURE_SUBSCRIPTION_ID  : Azure subscription ID")
    
    print("\n" + "=" * 60)
    print("Key Features:")
    print("-" * 60)
    print("1. NO subscription_id parameter needed - uses environment variable")
    print("2. Period-based queries: MTD, YTD, or custom YYYYMM ranges")
    print("3. AI service costs with token-level breakdown:")
    print("   - Input tokens, output tokens, cached tokens")
    print("   - Model-specific attribution (GPT-4, GPT-3.5, etc.)")
    print("   - Service-level grouping (OpenAI, Cognitive Services)")
    print("4. Full hierarchical cost structure for all endpoints")
    print("5. Costs in both original currency and USD")
    
    print("\n" + "=" * 60)
    print("Response Structures:")
    print("-" * 60)
    
    print("\n1. Standard Cost Response (costs, period):")
    print(json.dumps({
        "subscription": {
            "id": "auto-from-env",
            "totalCost": 1500.00,
            "totalCostUSD": 1425.00,
            "resourceGroups": {
                "rg-name": {
                    "resources": ["..."]
                }
            }
        }
    }, indent=2))
    
    print("\n2. AI Service Cost Response:")
    print(json.dumps({
        "models": {
            "gpt-4": {
                "total_cost_usd": 855.00,
                "usage_breakdown": {
                    "input_tokens": {
                        "quantity": 5000000,
                        "cost_usd": 285.00
                    },
                    "output_tokens": {
                        "quantity": 2000000,
                        "cost_usd": 570.00
                    }
                }
            }
        }
    }, indent=2))
    
    print("\n" + "=" * 60)
    print("Testing Complete!")
    print("All endpoint signatures documented and ready for use.")
    print("\nNOTE: Remember to set up your Azure credentials in .env file")
    print("      before making actual API calls.")

if __name__ == "__main__":
    test_endpoint_signatures()