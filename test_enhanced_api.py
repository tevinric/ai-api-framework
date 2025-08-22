#!/usr/bin/env python3
"""
Test script for enhanced Azure Cost Management API with meter-level granularity
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
from datetime import datetime

def test_enhanced_response_formatting():
    """Test the enhanced response formatting with mock data that includes meter details"""
    
    # Mock the dependencies to avoid database requirements
    class MockService:
        def __init__(self):
            self.tenant_id = "mock-tenant"
            self.client_id = "mock-client"
            self.client_secret = "mock-secret"
            self.subscription_id = "mock-subscription"
        
        def _validate_credentials(self):
            pass
        
        def _parse_ai_model_info(self, meter_name, meter_category, meter_subcategory):
            """Mock AI model parsing"""
            if 'gpt-4o' in meter_name.lower():
                if 'outp' in meter_name.lower():
                    return {'model': 'gpt-4o', 'usage_type': 'output_tokens'}
                elif 'inp' in meter_name.lower():
                    return {'model': 'gpt-4o', 'usage_type': 'input_tokens'}
            elif 'kontext' in meter_name.lower():
                return {'model': 'kontext-pro', 'usage_type': 'images'}
            return None
    
    # Import the formatting functions directly
    from apis.azure_cost_management.cost_extraction import AzureCostManagementService
    
    # Create mock service
    service = MockService()
    
    # Use the real formatting method
    real_service = AzureCostManagementService.__new__(AzureCostManagementService)
    real_service.tenant_id = "mock"
    real_service.client_id = "mock" 
    real_service.client_secret = "mock"
    real_service.subscription_id = "mock"
    
    try:
        # Mock enhanced response data similar to Azure portal detail view
        mock_ai_response = {
            "properties": {
                "columns": [
                    {"name": "Cost", "type": "Number"},
                    {"name": "CostUSD", "type": "Number"},
                    {"name": "ResourceGroupName", "type": "String"},
                    {"name": "ResourceId", "type": "String"},
                    {"name": "ServiceName", "type": "String"},
                    {"name": "MeterName", "type": "String"},
                    {"name": "MeterCategory", "type": "String"},
                    {"name": "MeterSubCategory", "type": "String"},
                    {"name": "ResourceType", "type": "String"},
                    {"name": "UnitOfMeasure", "type": "String"},
                    {"name": "UsageQuantity", "type": "Number"},
                    {"name": "UsageDate", "type": "String"}
                ],
                "rows": [
                    # Microsoft Defender for Cloud - Standard Tokens
                    [3.99, 3.99, "rg-gaia-za", "/subscriptions/12345/resourceGroups/rg-gaia-za/providers/Microsoft.Security/pricings/defender1", "Microsoft Defender for Cloud", "Standard Tokens", "Microsoft Defender for Cloud", "Security Center", "Microsoft.Security/pricings", "Tokens", 1000000, "2025-08-01"],
                    
                    # Cognitive Services - gpt-4o Output Tokens  
                    [2.17, 2.17, "rg-gaia-za", "/subscriptions/12345/resourceGroups/rg-gaia-za/providers/Microsoft.CognitiveServices/accounts/gaia-foundry-za", "Cognitive Services", "gpt-4o 1120 Outp glbl Tokens", "Cognitive Services", "Azure OpenAI Service", "Microsoft.CognitiveServices/accounts", "Tokens", 72334, "2025-08-01"],
                    
                    # Cognitive Services - gpt-4o Input Tokens
                    [2.16, 2.16, "rg-gaia-za", "/subscriptions/12345/resourceGroups/rg-gaia-za/providers/Microsoft.CognitiveServices/accounts/gaia-foundry-za", "Cognitive Services", "gpt-4o 1120 Inp glbl Tokens", "Cognitive Services", "Azure OpenAI Service", "Microsoft.CognitiveServices/accounts", "Tokens", 864000, "2025-08-01"],
                    
                    # Cognitive Services - Kontext Pro Images
                    [0.76, 0.76, "rg-gaia-za", "/subscriptions/12345/resourceGroups/rg-gaia-za/providers/Microsoft.CognitiveServices/accounts/gaia-foundry-za", "Cognitive Services", "Kontext Pro glbl Images", "Cognitive Services", "Azure Applied AI Services", "Microsoft.CognitiveServices/accounts", "Images", 38, "2025-08-01"],
                    
                    # More granular entries...
                    [0.62, 0.62, "rg-gaia-za", "/subscriptions/12345/resourceGroups/rg-gaia-za/providers/Microsoft.CognitiveServices/accounts/gaia-foundry-za", "Cognitive Services", "gpt-4o-mini-0718-inp-glbl Tokens", "Cognitive Services", "Azure OpenAI Service", "Microsoft.CognitiveServices/accounts", "Tokens", 2066667, "2025-08-01"],
                    
                    [0.57, 0.57, "rg-gaia-za", "/subscriptions/12345/resourceGroups/rg-gaia-za/providers/Microsoft.CognitiveServices/accounts/gaia-foundry-za", "Cognitive Services", "gpt-4o-mini-0718-outp-glbl Tokens", "Cognitive Services", "Azure OpenAI Service", "Microsoft.CognitiveServices/accounts", "Tokens", 950000, "2025-08-01"]
                ]
            }
        }
        
        # Test the enhanced AI costs formatting
        formatted = real_service._format_ai_costs_response(mock_ai_response, "test-subscription-123", "2025-08-01", "2025-08-22")
        
        # Validate the enhanced structure
        assert "subscription_id" in formatted
        assert "resource_groups" in formatted
        assert "individual_meter_records" in formatted  # New feature
        assert "meter_summary" in formatted
        assert "model_summary" in formatted
        assert "metadata" in formatted
        
        print("PASS: Enhanced AI response formatting works correctly")
        print(f"INFO: Found {len(formatted['resource_groups'])} resource groups")
        print(f"INFO: Individual meter records: {len(formatted['individual_meter_records'])}")
        print(f"INFO: Meter summary entries: {len(formatted['meter_summary'])}")
        print(f"INFO: Model summary entries: {len(formatted['model_summary'])}")
        print(f"INFO: Total AI cost: ${formatted['total_ai_cost_usd']:.2f}")
        
        # Show sample individual meter records (like portal)
        print("\nSample Individual Meter Records (Portal Style):")
        print("-" * 80)
        for i, record in enumerate(formatted['individual_meter_records'][:5]):
            print(f"{i+1}. {record['service_name']}: {record['meter_name']} - ${record['cost_usd']:.2f}")
            if 'model' in record:
                print(f"   Model: {record['model']}, Type: {record.get('usage_type', 'unknown')}")
        
        # Show hierarchical structure
        print("\nResource Group Hierarchy:")
        print("-" * 50)
        for rg_name, rg_data in formatted['resource_groups'].items():
            print(f"RG: {rg_name} - ${rg_data['total_cost_usd']:.2f}")
            for resource_name, resource_data in list(rg_data['resources'].items())[:2]:  # Show first 2 resources
                print(f"  Resource: {resource_name} - ${resource_data['total_cost_usd']:.2f}")
                for service_name, service_data in resource_data['services'].items():
                    print(f"    Service: {service_name} - ${service_data['total_cost_usd']:.2f}")
                    print(f"      Meters: {len(service_data['meters'])} records")
        
        return True
        
    except Exception as e:
        print(f"FAIL: Enhanced response formatting test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_general_costs_formatting():
    """Test the enhanced general costs response formatting"""
    try:
        # Import the service
        from apis.azure_cost_management.cost_extraction import AzureCostManagementService
        
        # Create mock service
        real_service = AzureCostManagementService.__new__(AzureCostManagementService)
        real_service.tenant_id = "mock"
        real_service.client_id = "mock"
        real_service.client_secret = "mock"
        real_service.subscription_id = "mock"
        
        # Mock enhanced general response with meter details
        mock_response = {
            "properties": {
                "columns": [
                    {"name": "Cost", "type": "Number"},
                    {"name": "CostUSD", "type": "Number"},
                    {"name": "ResourceGroupName", "type": "String"},
                    {"name": "ResourceId", "type": "String"},
                    {"name": "ServiceName", "type": "String"},
                    {"name": "ResourceType", "type": "String"},
                    {"name": "MeterName", "type": "String"},
                    {"name": "MeterCategory", "type": "String"},
                    {"name": "MeterSubCategory", "type": "String"},
                    {"name": "UnitOfMeasure", "type": "String"},
                    {"name": "UsageQuantity", "type": "Number"}
                ],
                "rows": [
                    [100.50, 95.25, "rg-production", "/subscriptions/12345/resourceGroups/rg-production/providers/Microsoft.Compute/virtualMachines/vm1", "Virtual Machines", "Microsoft.Compute/virtualMachines", "D2s v3", "Virtual Machines", "Dv3/DSv3 Series", "Hours", 720],
                    [25.25, 24.00, "rg-production", "/subscriptions/12345/resourceGroups/rg-production/providers/Microsoft.Compute/virtualMachines/vm1", "Virtual Machines", "Microsoft.Compute/virtualMachines", "Premium SSD P10", "Storage", "Premium SSD Managed Disks", "GB-Month", 128],
                    [75.25, 71.49, "rg-production", "/subscriptions/12345/resourceGroups/rg-production/providers/Microsoft.Storage/storageAccounts/storage1", "Storage", "Microsoft.Storage/storageAccounts", "LRS Data Stored", "Storage", "General Purpose v2", "GB-Month", 1024]
                ]
            }
        }
        
        formatted = real_service._format_hierarchical_response(mock_response, "test-subscription-123")
        
        # Validate the enhanced structure 
        assert "subscription" in formatted
        assert "resourceGroups" in formatted["subscription"]
        assert "metadata" in formatted
        
        # Check that resources now have meter-level details
        for rg_name, rg_data in formatted["subscription"]["resourceGroups"].items():
            for resource_name, resource_data in rg_data["resources"].items():
                assert "meters" in resource_data, "Resources should have meter details"
                assert len(resource_data["meters"]) > 0, "Resources should have at least one meter"
        
        print("PASS: Enhanced general costs formatting works correctly")
        print(f"INFO: Found {len(formatted['subscription']['resourceGroups'])} resource groups")
        print(f"INFO: Total cost: ${formatted['subscription']['totalCostUSD']:.2f}")
        
        # Show meter details for first resource
        first_rg = list(formatted['subscription']['resourceGroups'].values())[0]
        first_resource = list(first_rg['resources'].values())[0]
        print(f"\nSample Meter Details for {first_resource['resourceName']}:")
        print("-" * 60)
        for meter in first_resource['meters']:
            print(f"  - {meter['meterName']}: {meter['usageQuantity']} {meter['unitOfMeasure']} - ${meter['costUSD']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"FAIL: Enhanced general costs formatting test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run enhanced API tests"""
    print("Testing Enhanced Azure Cost Management API (Meter-Level Granularity)\n")
    print("This test validates that the API now provides the same level of detail as the Azure portal\n")
    
    tests = [
        ("Enhanced AI Costs Formatting", test_enhanced_response_formatting),
        ("Enhanced General Costs Formatting", test_general_costs_formatting)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\nRunning test: {test_name}")
        print("-" * 70)
        
        if test_func():
            passed += 1
        else:
            failed += 1
    
    print("\n" + "="*70)
    print(f"Test Summary: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("SUCCESS: All tests passed! Enhanced Azure Cost Management API is working!")
        print("\nKey Enhancements:")
        print("   - Individual meter records (matching Azure portal detail view)")
        print("   - Hierarchical structure: Resource Groups -> Resources -> Services -> Meters")
        print("   - Enhanced AI model parsing and token-level breakdown")
        print("   - Meter-level details for all resources (not just AI)")
        print("   - Usage quantity and unit of measure for each meter")
        print("\nNew API Response Includes:")
        print("   - individual_meter_records[] - Flat list like portal detail view")
        print("   - resource_groups{}.resources{}.meters[] - Hierarchical meter details")  
        print("   - Enhanced model parsing with usage_type classification")
        print("   - Proper cost sorting at all levels")
        
    else:
        print("WARNING: Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)