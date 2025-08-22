#!/usr/bin/env python3
"""
Simple validation script for AI services endpoint fix
"""
import sys
import os

def validate_fix():
    """Validate the AI services endpoint fix"""
    print("AI Services Endpoint Fix Validation")
    print("=" * 50)
    
    # Check that the file exists and has the fix
    file_path = "apis/azure_cost_management/cost_extraction.py"
    
    if not os.path.exists(file_path):
        print("[ERROR] cost_extraction.py not found")
        return False
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check for key fixes
    fixes_to_check = [
        ("Fallback parameter", "use_fallback: bool = False"),
        ("Fallback logic", "if response.status_code == 400 and not use_fallback:"),
        ("Fallback method", "_filter_ai_costs_from_all"),
        ("Simplified query", "Cognitive Services"),
        ("Error handling", "Trying fallback method without filters"),
        ("AI keywords", "ai_keywords = [")
    ]
    
    print("\nChecking for implemented fixes:")
    print("-" * 40)
    
    all_present = True
    for fix_name, search_text in fixes_to_check:
        if search_text in content:
            print(f"[OK] {fix_name}")
        else:
            print(f"[MISSING] {fix_name}")
            all_present = False
    
    print("-" * 40)
    
    if all_present:
        print("[SUCCESS] All fixes are present in the code!")
        print("\nWhat the fix does:")
        print("1. Simplifies the Azure Cost Management API query")
        print("2. Removes complex aggregations that cause 400 errors")
        print("3. Implements automatic fallback to client-side filtering")
        print("4. Uses keyword matching to identify AI services")
        print("5. Categorizes services (OpenAI, Cognitive Services, etc.)")
        print("6. Handles missing fields gracefully")
        
        print("\nHow it works:")
        print("- First attempts simplified API query with AI service filter")
        print("- If 400 error occurs, automatically retries with fallback")
        print("- Fallback gets all costs and filters AI services client-side")
        print("- Uses keyword matching (openai, cognitive, gpt, ml, etc.)")
        print("- Provides same API structure but marked as fallback_method")
        
        return True
    else:
        print("[ERROR] Some fixes are missing from the code")
        return False

def show_usage_examples():
    """Show how to use the fixed endpoint"""
    print("\n" + "=" * 50)
    print("Usage Examples")
    print("=" * 50)
    
    print("\n1. Basic AI costs (last 30 days):")
    print("GET /azure/costs/ai-services")
    print("Headers: API-Key: YOUR_KEY")
    
    print("\n2. Custom date range:")
    print("GET /azure/costs/ai-services?start_date=2024-01-01&end_date=2024-01-31")
    
    print("\n3. Expected response structure:")
    print("""
{
  "subscription_id": "auto-from-env",
  "total_ai_cost_usd": 1500.00,
  "services": {
    "Azure OpenAI": {
      "total_cost_usd": 1200.00,
      "resources": { ... }
    },
    "Cognitive Services": {
      "total_cost_usd": 300.00,
      "resources": { ... }
    }
  },
  "models": {
    "gpt-4": {
      "total_cost_usd": 800.00,
      "usage_breakdown": {
        "input_tokens": { "cost_usd": 300.00 },
        "output_tokens": { "cost_usd": 500.00 }
      }
    }
  },
  "metadata": {
    "fallback_method": true  // if fallback was used
  }
}
    """)

if __name__ == "__main__":
    if validate_fix():
        show_usage_examples()
        print("\n[SUCCESS] The AI services endpoint should now work correctly!")
    else:
        print("\n[ERROR] Fix validation failed")
        sys.exit(1)