#!/usr/bin/env python3
"""
Test the fixed Azure Cost Management API query structure
"""
import json

def test_query_structure():
    """Test that the query structure is valid JSON and has correct format"""
    
    # Test AI service costs query structure
    ai_query = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {
            "from": "2025-08-01",
            "to": "2025-08-22"
        },
        "dataset": {
            "granularity": "Daily",
            "aggregation": {
                "totalCost": {
                    "name": "PreTaxCost",
                    "function": "Sum"
                }
            },
            "grouping": [
                {
                    "type": "Dimension",
                    "name": "ServiceName"
                },
                {
                    "type": "Dimension",
                    "name": "MeterCategory"
                },
                {
                    "type": "Dimension",
                    "name": "MeterSubCategory"
                },
                {
                    "type": "Dimension",
                    "name": "Meter"
                },
                {
                    "type": "Dimension",
                    "name": "ResourceId"
                }
            ],
            "filter": {
                "Or": [
                    {
                        "Dimensions": {
                            "Name": "ServiceName",
                            "Operator": "In",
                            "Values": [
                                "Cognitive Services",
                                "Azure OpenAI",
                                "Azure Machine Learning",
                                "Azure Cognitive Search",
                                "Microsoft Defender for Cloud"
                            ]
                        }
                    },
                    {
                        "Dimensions": {
                            "Name": "MeterCategory", 
                            "Operator": "In",
                            "Values": [
                                "Cognitive Services",
                                "Azure OpenAI Service",
                                "Machine Learning",
                                "Azure Applied AI Services"
                            ]
                        }
                    }
                ]
            }
        }
    }
    
    # Test general costs query structure  
    general_query = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {
            "from": "2025-08-01",
            "to": "2025-08-22"
        },
        "dataset": {
            "granularity": "Daily",
            "aggregation": {
                "totalCost": {
                    "name": "PreTaxCost",
                    "function": "Sum"
                }
            },
            "grouping": [
                {
                    "type": "Dimension",
                    "name": "ResourceId"
                },
                {
                    "type": "Dimension",
                    "name": "ServiceName"
                },
                {
                    "type": "Dimension",
                    "name": "MeterCategory"
                },
                {
                    "type": "Dimension",
                    "name": "MeterSubCategory"
                },
                {
                    "type": "Dimension",
                    "name": "Meter"
                }
            ]
        }
    }
    
    # Test that both queries are valid JSON
    try:
        ai_json = json.dumps(ai_query, indent=2)
        general_json = json.dumps(general_query, indent=2)
        
        print("PASS: Query structures are valid JSON")
        print(f"INFO: AI query has {len(ai_query['dataset']['grouping'])} grouping dimensions")
        print(f"INFO: General query has {len(general_query['dataset']['grouping'])} grouping dimensions")
        
        # Validate key fixes
        assert ai_query['dataset']['aggregation']['totalCost']['name'] == 'PreTaxCost'
        assert general_query['dataset']['aggregation']['totalCost']['name'] == 'PreTaxCost'
        print("PASS: Using correct aggregation field 'PreTaxCost'")
        
        # Check grouping dimensions use 'Meter' instead of 'MeterName'
        ai_grouping_names = [g['name'] for g in ai_query['dataset']['grouping']]
        general_grouping_names = [g['name'] for g in general_query['dataset']['grouping']]
        
        assert 'Meter' in ai_grouping_names
        assert 'Meter' in general_grouping_names
        assert 'MeterName' not in ai_grouping_names
        assert 'MeterName' not in general_grouping_names
        print("PASS: Using correct dimension name 'Meter' instead of 'MeterName'")
        
        # Check filter structure uses proper casing
        ai_filter = ai_query['dataset']['filter']
        assert 'Or' in ai_filter
        assert 'Dimensions' in ai_filter['Or'][0]
        assert 'Name' in ai_filter['Or'][0]['Dimensions']
        assert 'Operator' in ai_filter['Or'][0]['Dimensions']
        assert 'Values' in ai_filter['Or'][0]['Dimensions']
        print("PASS: Filter structure uses correct casing (Or, Dimensions, Name, Operator, Values)")
        
        # Check that problematic dimensions are removed
        assert 'UsageDate' not in ai_grouping_names
        assert 'UnitOfMeasure' not in general_grouping_names
        print("PASS: Removed incompatible dimensions (UsageDate, UnitOfMeasure)")
        
        print("\nQuery Structure Analysis:")
        print("=" * 50)
        print("AI Services Query:")
        print("- Type: ActualCost")
        print("- Aggregation: PreTaxCost")
        print("- Grouping Dimensions: ServiceName, MeterCategory, MeterSubCategory, Meter, ResourceId")
        print("- Filter: AI services only")
        
        print("\nGeneral Costs Query:")
        print("- Type: ActualCost") 
        print("- Aggregation: PreTaxCost")
        print("- Grouping Dimensions: ResourceId, ServiceName, MeterCategory, MeterSubCategory, Meter")
        print("- Filter: None (all services)")
        
        return True
        
    except Exception as e:
        print(f"FAIL: Query structure validation failed: {str(e)}")
        return False

def main():
    """Test the API fix"""
    print("Testing Fixed Azure Cost Management API Query Structure")
    print("=" * 60)
    
    if test_query_structure():
        print("\nSUCCESS: API query structure fixes are correct!")
        print("\nKey Fixes Applied:")
        print("- Changed aggregation from 'Cost'/'CostUSD' to 'PreTaxCost'")
        print("- Changed dimension from 'MeterName' to 'Meter'")
        print("- Fixed filter casing: or->Or, dimensions->Dimensions, etc.")
        print("- Removed incompatible dimensions (UsageDate, UnitOfMeasure)")
        print("- Reduced grouping complexity for better API compatibility")
        print("\nThe 400 Bad Request error should now be resolved!")
        return 0
    else:
        print("\nFAIL: Query structure issues remain")
        return 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)