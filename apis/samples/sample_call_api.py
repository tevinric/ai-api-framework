import requests

# TEST THE GET TOKEN ENDPOINT
def get_token(api_key=None):
    """
    Get a token from the token service
    
    Parameters:
    api_key (str): API key for authentication
    
    Returns:
    dict: Token data if successful, None otherwise
    """
    headers = {}
    if api_key:
        headers['X-API-Key'] = api_key
    
    token_response = requests.get("http://localhost:5000/get-token", headers=headers)
    
    if token_response.status_code == 200:
        # Handle successful token request
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        expires_in = token_data.get('expires_in')
        expires_on = token_data.get('expires_on')
        token_type = token_data.get('token_type')
        
        print("Request Status: ", token_response.status_code)
        print("Access Token: ", access_token)
        print("Expires in: ", expires_in)
        print("Expires on: ", expires_on)
        
        return token_data
    else:
        # Handle failed token request
        print("Request Status: ", token_response.status_code)
        print(token_response.json())
        return None

# TEST THE TOKEN VALIDATION PROCESS WITH A SIMPLE API FUNCTION 
def test_endpoints(num1, num2, api_key):
    """
    Test the API endpoints
    
    Parameters:
    num1 (float): First number for multiplication
    num2 (float): Second number for multiplication
    api_key (str): API key for authentication
    
    Returns:
    dict: Result if successful, None otherwise
    """
    # FIRST GET A TOKEN FROM THE TOKEN SERVICE
    token_data = get_token(api_key)
    
    if not token_data:
        print("Failed to get token")
        return None
    
    access_token = token_data.get('access_token')
    
    # CALL THE TEST ENDPOINT TO MULTIPLY TWO NUMBERS
    test_url = "http://localhost:5000/api/multiply"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # CREATE THE REQUEST PAYLOAD
    data = {
        "num1": num1,
        "num2": num2
    }
    
    response = requests.post(test_url, headers=headers, json=data)
    
    print(response.status_code)
    if response.status_code == 200:
        result = response
        print("Result: ", result)
        return result
    else:
        print(f"API call failed: {response.status_code}")
        #print(response.json())
        return None

if __name__ == "__main__":
    # You need to provide a valid API key
    API_KEY = "16ECA9AE-1AB0-46E7-9BF8-56BF9D6D15A7"  # Replace with a valid API key
    
    # Get token
    # print("Testing get_token endpoint:")
    # token = get_token(API_KEY)
    # print("Token generated: ", token)
    # print("\n" + "-"*50 + "\n")
    
    # Test multiplication endpoint
    print("Testing multiplication endpoint:")
    result = test_endpoints(10, 20, API_KEY)
    print("TEST RESULT: ", result)
