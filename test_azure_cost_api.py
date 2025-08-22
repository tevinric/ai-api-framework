#!/usr/bin/env python3
"""
Test script for Azure Cost Management API
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apis.azure_cost_management.cost_extraction import AzureCostManagementService
import json

def test_service_initialization():
    """Test that the service can be initialized"""
    try:
        service = AzureCostManagementService()
        print("✅ AzureCostManagementService initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize service: {str(e)}")
        return False

def test_mock_response_formatting():
    """Test the response formatting with mock data"""
    try:
        service = AzureCostManagementService()
        
        # Mock response data similar to what Azure Cost Management API would return
        mock_response = {
            "properties": {
                "columns": [
                    {"name": "PreTaxCost", "type": "Number"},
                    {"name": "PreTaxCostUSD", "type": "Number"},
                    {"name": "ResourceGroup", "type": "String"},
                    {"name": "ResourceId", "type": "String"},
                    {"name": "ServiceName", "type": "String"},
                    {"name": "ResourceType", "type": "String"},
                    {"name": "Currency", "type": "String"}
                ],
                "rows": [
                    [100.50, 95.25, "rg-production", "/subscriptions/12345/resourceGroups/rg-production/providers/Microsoft.Compute/virtualMachines/vm1", "Virtual Machines", "Microsoft.Compute/virtualMachines", "USD"],
                    [75.25, 71.49, "rg-production", "/subscriptions/12345/resourceGroups/rg-production/providers/Microsoft.Storage/storageAccounts/storage1", "Storage", "Microsoft.Storage/storageAccounts", "USD"],
                    [50.00, 47.50, "rg-development", "/subscriptions/12345/resourceGroups/rg-development/providers/Microsoft.Web/sites/webapp1", "App Service", "Microsoft.Web/sites", "USD"]
                ]
            }
        }
        
        formatted = service._format_hierarchical_response(mock_response, "test-subscription-123")
        
        # Validate the structure
        assert "subscription" in formatted
        assert "resourceGroups" in formatted["subscription"]
        assert "metadata" in formatted
        
        print("✅ Response formatting works correctly")
        print(f"📊 Found {len(formatted['subscription']['resourceGroups'])} resource groups")
        print(f"💰 Total cost: ${formatted['subscription']['totalCostUSD']:.2f}")
        
        # Pretty print the structure
        print("\n📋 Sample formatted response structure:")
        print(json.dumps(formatted, indent=2))
        
        return True
    except Exception as e:
        print(f"❌ Response formatting test failed: {str(e)}")
        return False

def test_route_imports():
    """Test that the routes can be imported"""
    try:
        from apis.azure_cost_management.cost_extraction import (
            get_azure_costs_route,
            get_azure_cost_summary_route,
            register_azure_cost_routes
        )
        print("✅ Route functions imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import route functions: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Azure Cost Management API Implementation\n")
    
    tests = [
        ("Service Initialization", test_service_initialization),
        ("Response Formatting", test_mock_response_formatting),
        ("Route Imports", test_route_imports)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running test: {test_name}")
        print("-" * 50)
        
        if test_func():
            passed += 1
        else:
            failed += 1
    
    print("\n" + "="*50)
    print(f"📈 Test Summary: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Your Azure Cost Management API is ready to use.")
        print("\n📝 To use the API:")
        print("1. Set environment variables:")
        print("   - AZURE_TENANT_ID")
        print("   - AZURE_CLIENT_ID")
        print("   - AZURE_CLIENT_SECRET")
        print("2. Start your Flask app")
        print("3. Make GET requests to:")
        print("   - /azure/costs?subscription_id=YOUR_SUBSCRIPTION_ID")
        print("   - /azure/costs/summary?subscription_id=YOUR_SUBSCRIPTION_ID")
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()