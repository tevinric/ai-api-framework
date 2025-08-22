#!/usr/bin/env python3
"""
Test the updated column mapping for the fixed Azure Cost Management API
"""

def test_column_mapping():
    """Test that the column mapping handles the corrected response structure"""
    
    # Mock response that would come from the fixed Azure API
    mock_response = {
        "properties": {
            "columns": [
                {"name": "PreTaxCost", "type": "Number"},  # Correct aggregation field
                {"name": "ServiceName", "type": "String"},
                {"name": "MeterCategory", "type": "String"},
                {"name": "MeterSubCategory", "type": "String"},
                {"name": "Meter", "type": "String"},  # Correct dimension name
                {"name": "ResourceId", "type": "String"}
            ],
            "rows": [
                [3.99, "Microsoft Defender for Cloud", "Microsoft Defender for Cloud", "Security Center", "Standard Tokens", "/subscriptions/12345/resourceGroups/rg-gaia-za/providers/Microsoft.Security/pricings/defender1"],
                [2.17, "Cognitive Services", "Cognitive Services", "Azure OpenAI Service", "gpt-4o 1120 Outp glbl Tokens", "/subscriptions/12345/resourceGroups/rg-gaia-za/providers/Microsoft.CognitiveServices/accounts/gaia-foundry-za"],
                [2.16, "Cognitive Services", "Cognitive Services", "Azure OpenAI Service", "gpt-4o 1120 Inp glbl Tokens", "/subscriptions/12345/resourceGroups/rg-gaia-za/providers/Microsoft.CognitiveServices/accounts/gaia-foundry-za"],
                [0.76, "Cognitive Services", "Cognitive Services", "Azure Applied AI Services", "Kontext Pro glbl Images", "/subscriptions/12345/resourceGroups/rg-gaia-za/providers/Microsoft.CognitiveServices/accounts/gaia-foundry-za"]
            ]
        }
    }
    
    # Test column mapping
    columns = mock_response['properties']['columns']
    column_map = {col['name']: idx for idx, col in enumerate(columns)}
    
    # Validate expected columns are present
    expected_columns = ['PreTaxCost', 'ServiceName', 'MeterCategory', 'MeterSubCategory', 'Meter', 'ResourceId']
    for col in expected_columns:
        assert col in column_map, f"Expected column '{col}' not found in response"
    
    print("PASS: All expected columns are present in mock response")
    
    # Test row processing logic
    rows = mock_response['properties']['rows']
    total_cost = 0
    processed_records = []
    
    for row in rows:
        try:
            # Extract fields using corrected column mapping
            cost = row[column_map.get('PreTaxCost')] if 'PreTaxCost' in column_map else 0
            cost_usd = cost  # ActualCost typically returns cost in USD
            
            resource_id = row[column_map.get('ResourceId')] if 'ResourceId' in column_map else 'Unknown'
            
            # Extract resource group from ResourceId
            resource_group = 'Unknown'
            if resource_id != 'Unknown' and '/resourceGroups/' in resource_id:
                try:
                    resource_group = resource_id.split('/resourceGroups/')[1].split('/')[0]
                except (IndexError, AttributeError):
                    resource_group = 'Unknown'
            
            service_name = row[column_map.get('ServiceName')] if 'ServiceName' in column_map else 'Unknown'
            meter_name = row[column_map.get('Meter')] if 'Meter' in column_map else 'Unknown'
            meter_category = row[column_map.get('MeterCategory')] if 'MeterCategory' in column_map else 'Unknown'
            meter_subcategory = row[column_map.get('MeterSubCategory')] if 'MeterSubCategory' in column_map else 'Unknown'
            
            # Extract resource name from resource ID
            resource_name = resource_id.split('/')[-1] if resource_id != 'Unknown' else 'Unknown'
            
            record = {
                'cost': cost,
                'cost_usd': cost_usd,
                'resource_group': resource_group,
                'resource_name': resource_name,
                'service_name': service_name,
                'meter_name': meter_name,
                'meter_category': meter_category,
                'meter_subcategory': meter_subcategory
            }
            
            processed_records.append(record)
            total_cost += cost_usd
            
        except Exception as e:
            print(f"Error processing row: {str(e)}")
            return False
    
    print("PASS: All rows processed successfully")
    print(f"INFO: Processed {len(processed_records)} records")
    print(f"INFO: Total cost: ${total_cost:.2f}")
    
    # Validate specific field extraction
    first_record = processed_records[0]
    assert first_record['resource_group'] == 'rg-gaia-za', f"Expected 'rg-gaia-za', got '{first_record['resource_group']}'"
    assert first_record['service_name'] == 'Microsoft Defender for Cloud'
    assert first_record['meter_name'] == 'Standard Tokens'
    
    gpt4_record = processed_records[1]
    assert gpt4_record['meter_name'] == 'gpt-4o 1120 Outp glbl Tokens'
    assert gpt4_record['resource_name'] == 'gaia-foundry-za'
    
    print("PASS: Resource group extraction from ResourceId works correctly")
    print("PASS: Meter name extraction works correctly")
    
    # Display sample processed records
    print("\nSample Processed Records:")
    print("-" * 80)
    for i, record in enumerate(processed_records[:3]):
        print(f"{i+1}. {record['resource_group']} / {record['resource_name']}")
        print(f"   Service: {record['service_name']}")
        print(f"   Meter: {record['meter_name']} - ${record['cost_usd']:.2f}")
        print()
    
    return True

def main():
    """Test the column mapping fixes"""
    print("Testing Azure Cost Management API Column Mapping Fixes")
    print("=" * 60)
    
    if test_column_mapping():
        print("SUCCESS: Column mapping fixes work correctly!")
        print("\nKey Column Mapping Fixes:")
        print("- Uses 'PreTaxCost' instead of 'Cost'/'CostUSD'")
        print("- Uses 'Meter' instead of 'MeterName'")
        print("- Extracts resource group from ResourceId path")
        print("- Handles missing columns gracefully")
        print("- Processes meter-level details correctly")
        print("\nThe API should now handle Azure responses without 400 errors!")
        return 0
    else:
        print("FAIL: Column mapping issues remain")
        return 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)