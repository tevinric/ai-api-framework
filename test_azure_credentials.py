#!/usr/bin/env python3
"""
Test script to verify Azure Cost Management API configuration
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_environment_variables():
    """Test that all required Azure environment variables are set"""
    print("Checking Azure environment variables...")
    print("-" * 50)
    
    required_vars = {
        'AZURE_TENANT_ID': 'Azure AD tenant ID',
        'AZURE_CLIENT_ID': 'Service principal client ID',
        'AZURE_CLIENT_SECRET': 'Service principal secret',
        'AZURE_SUBSCRIPTION_ID': 'Azure subscription ID'
    }
    
    all_set = True
    for var_name, description in required_vars.items():
        value = os.getenv(var_name)
        if value and value != f"your_{var_name.lower().replace('azure_', '').replace('_', '_')}_here":
            # Mask the secret for display
            if 'SECRET' in var_name:
                display_value = '*' * 8 + value[-4:] if len(value) > 4 else '*' * len(value)
            else:
                display_value = value[:8] + '...' if len(value) > 20 else value
            print(f"[OK] {var_name}: {display_value} ({description})")
        else:
            print(f"[MISSING] {var_name}: NOT SET - {description}")
            all_set = False
    
    print("-" * 50)
    
    if all_set:
        print("[SUCCESS] All required environment variables are set!")
        return True
    else:
        print("[WARNING] Some environment variables are missing.")
        print("\nPlease update the .env file with your Azure credentials:")
        print("   1. Open .env file in the project root")
        print("   2. Replace placeholder values with your actual Azure credentials")
        print("   3. Save the file and run this test again")
        return False

def test_service_initialization():
    """Test that the Azure Cost Management Service can be initialized"""
    print("\nTesting Azure Cost Management Service initialization...")
    print("-" * 50)
    
    try:
        # Add the apis directory to Python path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from apis.azure_cost_management.cost_extraction import AzureCostManagementService
        
        service = AzureCostManagementService()
        print("[SUCCESS] AzureCostManagementService initialized successfully!")
        print(f"   - Subscription ID: {service.subscription_id[:8]}..." if service.subscription_id else "   - Subscription ID: NOT SET")
        print(f"   - API Version: {service.api_version}")
        print(f"   - Base URL: {service.base_url}")
        return True
        
    except ValueError as e:
        print(f"[ERROR] Configuration error: {str(e)}")
        return False
    except ImportError as e:
        print(f"[ERROR] Import error: {str(e)}")
        print("   Make sure you're running this from the project root directory")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Azure Cost Management API Configuration Test")
    print("=" * 60)
    
    tests_passed = []
    
    # Test 1: Environment variables
    tests_passed.append(test_environment_variables())
    
    # Test 2: Service initialization (only if env vars are set)
    if tests_passed[0]:
        tests_passed.append(test_service_initialization())
    else:
        print("\n[SKIP] Skipping service initialization test until environment variables are set")
    
    # Summary
    print("\n" + "=" * 60)
    if all(tests_passed):
        print("[SUCCESS] All tests passed! Your Azure Cost Management API is configured correctly.")
        print("\nNext steps:")
        print("   1. Start your Flask application")
        print("   2. Test the API endpoints:")
        print("      - GET /azure/costs (no subscription_id needed)")
        print("      - GET /azure/costs/summary (no subscription_id needed)")
    else:
        print("[WARNING] Configuration incomplete. Please fix the issues above.")
        print("\nTip: Make sure you have:")
        print("   1. Created an Azure service principal with Cost Management Reader role")
        print("   2. Updated the .env file with your credentials")
        print("   3. Installed required Python packages (python-dotenv, requests)")
        sys.exit(1)

if __name__ == "__main__":
    main()