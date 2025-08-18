"""
Test script for Cost Management APIs
"""
import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:5000"  # Update with your server URL
TOKEN = "your-valid-token-here"  # Replace with actual token

# Headers
headers = {
    "X-Token": TOKEN,
    "Content-Type": "application/json"
}

def test_resource_group_costs():
    """Test getting costs for resource groups"""
    print("\n=== Testing Resource Group Costs ===")
    
    # Date range for last 30 days
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    data = {
        "start_date": start_date,
        "end_date": end_date
    }
    
    response = requests.post(
        f"{BASE_URL}/cost_management/resource_group",
        headers=headers,
        json=data
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Total Cost: ${result.get('total_cost', 0):.2f}")
        print(f"Currency: {result.get('currency', 'USD')}")
        print(f"Resource Groups: {len(result.get('costs_by_resource_group', {}))}")
    else:
        print(f"Error: {response.text}")

def test_all_resource_groups():
    """Test getting costs for all resource groups"""
    print("\n=== Testing All Resource Groups Costs ===")
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    data = {
        "start_date": start_date,
        "end_date": end_date
    }
    
    response = requests.post(
        f"{BASE_URL}/cost_management/all_resource_groups",
        headers=headers,
        json=data
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Total Cost: ${result.get('total_cost', 0):.2f}")
        print(f"Total Cost USD: ${result.get('total_cost_usd', 0):.2f}")
        print(f"Resource Group Count: {result.get('resource_group_count', 0)}")
    else:
        print(f"Error: {response.text}")

def test_line_items():
    """Test getting detailed line item costs"""
    print("\n=== Testing Line Item Costs ===")
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    data = {
        "start_date": start_date,
        "end_date": end_date
    }
    
    response = requests.post(
        f"{BASE_URL}/cost_management/line_items",
        headers=headers,
        json=data
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Total Cost: ${result.get('total_cost', 0):.2f}")
        print(f"Item Count: {result.get('item_count', 0)}")
        
        # Show top 5 line items
        line_items = result.get('line_items', [])[:5]
        if line_items:
            print("\nTop 5 Line Items:")
            for item in line_items:
                resource_name = item.get('resource_name', 'Unknown')
                cost = item.get('cost', 0)
                resource_type = item.get('resource_type', 'Unknown')
                service_name = item.get('service_name', 'Unknown')
                print(f"  - {resource_name}: ${cost:.2f} ({resource_type} - {service_name})")
        else:
            print("No line items found")
    else:
        print(f"Error: {response.text}")
        try:
            error_detail = response.json()
            print(f"Error Detail: {error_detail}")
        except:
            pass

def test_user_apportioned_costs():
    """Test getting user apportioned costs"""
    print("\n=== Testing User Apportioned Costs ===")
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    data = {
        "start_date": start_date,
        "end_date": end_date
    }
    
    response = requests.post(
        f"{BASE_URL}/cost_management/user_apportioned",
        headers=headers,
        json=data
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"User ID: {result.get('user_id', 'Unknown')}")
        print(f"Total Apportioned Cost: ${result.get('total_apportioned_cost', 0):.2f}")
        
        usage_summary = result.get('usage_summary', {})
        print(f"Total Tokens Used: {usage_summary.get('total_tokens', 0)}")
        print(f"Total Requests: {usage_summary.get('total_requests', 0)}")
    else:
        print(f"Error: {response.text}")

def main():
    """Run all tests"""
    print("=" * 50)
    print("Cost Management API Tests")
    print("=" * 50)
    
    print("\nNote: Make sure to update the TOKEN variable with a valid token")
    print("and ensure the following environment variables are set:")
    print("  - AZURE_SUBSCRIPTION_ID")
    print("  - ENTRA_COST_CLIENT_ID (or uses ENTRA_APP_CLIENT_ID)")
    print("  - ENTRA_COST_CLIENT_SECRET (or uses ENTRA_APP_CLIENT_SECRET)")
    print("  - ENTRA_APP_TENANT_ID")
    
    # Uncomment the tests you want to run
    # test_resource_group_costs()
    # test_all_resource_groups()
    # test_line_items()
    # test_user_apportioned_costs()

if __name__ == "__main__":
    main()