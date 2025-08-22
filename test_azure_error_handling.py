#!/usr/bin/env python3
"""
Test script to verify Azure Cost Management API error handling
"""
import sys
import os

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_missing_credentials_error():
    """Test that the service properly handles missing credentials"""
    print("Testing error handling for missing credentials...")
    print("-" * 50)
    
    try:
        from apis.azure_cost_management.cost_extraction import AzureCostManagementService
        
        # This should raise a ValueError with details about missing env vars
        service = AzureCostManagementService()
        print("[ERROR] Service initialized without proper credentials - this shouldn't happen!")
        return False
        
    except ValueError as e:
        error_msg = str(e)
        print(f"[SUCCESS] Caught expected error: {error_msg}")
        
        # Check that the error message mentions the missing variables
        if "Missing required environment variables" in error_msg:
            print("[SUCCESS] Error message correctly identifies missing variables")
            
            # Check for specific variable names
            expected_vars = ['ENTRA_APP_TENANT_ID', 'ENTRA_APP_CLIENT_ID', 
                           'ENTRA_APP_CLIENT_SECRET', 'AZURE_SUBSCRIPTION_ID']
            
            missing_count = sum(1 for var in expected_vars if var in error_msg)
            print(f"[INFO] Error message mentions {missing_count}/{len(expected_vars)} expected variables")
            
            return True
        else:
            print("[ERROR] Error message doesn't mention missing variables")
            return False
            
    except ImportError as e:
        print(f"[ERROR] Import error: {str(e)}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {str(e)}")
        return False

def test_partial_credentials():
    """Test with partial credentials set"""
    print("\nTesting with partial credentials...")
    print("-" * 50)
    
    # Set only subscription ID
    os.environ['AZURE_SUBSCRIPTION_ID'] = 'test-subscription-id'
    
    try:
        from apis.azure_cost_management.cost_extraction import AzureCostManagementService
        
        # Force reimport to pick up new env vars
        import importlib
        import apis.azure_cost_management.cost_extraction
        importlib.reload(apis.azure_cost_management.cost_extraction)
        from apis.azure_cost_management.cost_extraction import AzureCostManagementService
        
        service = AzureCostManagementService()
        print("[ERROR] Service initialized with partial credentials - this shouldn't happen!")
        return False
        
    except ValueError as e:
        error_msg = str(e)
        print(f"[SUCCESS] Caught expected error with partial credentials")
        
        # Should still mention ENTRA_APP variables but not AZURE_SUBSCRIPTION_ID
        if "ENTRA_APP_TENANT_ID" in error_msg and "AZURE_SUBSCRIPTION_ID" not in error_msg:
            print("[SUCCESS] Error correctly identifies only missing ENTRA_APP variables")
            return True
        else:
            print(f"[INFO] Error message: {error_msg}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Unexpected error: {str(e)}")
        return False
    finally:
        # Clean up
        if 'AZURE_SUBSCRIPTION_ID' in os.environ:
            del os.environ['AZURE_SUBSCRIPTION_ID']

def main():
    """Run all error handling tests"""
    print("=" * 60)
    print("Azure Cost Management API Error Handling Test")
    print("=" * 60)
    
    tests_passed = []
    
    # Test 1: Missing all credentials
    tests_passed.append(test_missing_credentials_error())
    
    # Test 2: Partial credentials
    tests_passed.append(test_partial_credentials())
    
    # Summary
    print("\n" + "=" * 60)
    passed = sum(tests_passed)
    total = len(tests_passed)
    
    if all(tests_passed):
        print(f"[SUCCESS] All {total} error handling tests passed!")
        print("\nThe Azure Cost Management API correctly:")
        print("  - Validates all required environment variables on initialization")
        print("  - Provides clear error messages about missing credentials")
        print("  - Prevents initialization with incomplete configuration")
    else:
        print(f"[WARNING] {passed}/{total} tests passed")
        print("\nSome error handling tests failed. Check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()