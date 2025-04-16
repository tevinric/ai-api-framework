from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import uuid
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def admin_assign_endpoint_to_user_route():
    """
    Assign a specific endpoint to a user (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: "Admin API Key for authentication"
      - name: token
        in: query
        type: string
        required: true
        description: "A valid token for verification"
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - user_id
            - endpoint_id
          properties:
            user_id:
              type: string
              description: "UUID of the user to grant access"
            endpoint_id:
              type: string
              description: "UUID of the endpoint to grant access to"
    produces:
      - application/json
    responses:
      200:
        description: "Access granted successfully"
      400:
        description: "Bad request"
      401:
        description: "Authentication error"
      403:
        description: "Forbidden - not an admin"
      404:
        description: "User or endpoint not found"
      500:
        description: "Server error"
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to manage endpoint access"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Validate token from query parameter
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
    # Check if token is expired
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['user_id', 'endpoint_id']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    user_id = data.get('user_id')
    endpoint_id = data.get('endpoint_id')
    
    # Verify user exists
    user = DatabaseService.get_user_by_id(user_id)
    if not user:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Verify endpoint exists
    endpoint = DatabaseService.get_endpoint_by_id(endpoint_id)
    if not endpoint:
        return create_api_response({
            "error": "Not Found",
            "message": f"Endpoint with ID {endpoint_id} not found"
        }, 404)
    
    # Grant access
    success, result = DatabaseService.add_user_endpoint_access(user_id, endpoint_id, admin_info["id"])
    
    if not success:
        return create_api_response({
            "error": "Server Error",
            "message": f"Failed to grant endpoint access: {result}"
        }, 500)
    
    return create_api_response({
        "message": "Endpoint access granted successfully",
        "user_id": user_id,
        "endpoint_id": endpoint_id,
        "endpoint_name": endpoint["endpoint_name"],
        "result": result
    }, 200)

def admin_remove_endpoint_from_user_route():
    """
    Remove a specific endpoint access from a user (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: "Admin API Key for authentication"
      - name: token
        in: query
        type: string
        required: true
        description: "A valid token for verification"
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - user_id
            - endpoint_id
          properties:
            user_id:
              type: string
              description: "UUID of the user to remove access from"
            endpoint_id:
              type: string
              description: "UUID of the endpoint to remove access to"
    produces:
      - application/json
    responses:
      200:
        description: "Access removed successfully"
      400:
        description: "Bad request"
      401:
        description: "Authentication error"
      403:
        description: "Forbidden - not an admin"
      404:
        description: "User or endpoint not found"
      500:
        description: "Server error"
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to manage endpoint access"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Validate token from query parameter
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
    # Check if token is expired
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['user_id', 'endpoint_id']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    user_id = data.get('user_id')
    endpoint_id = data.get('endpoint_id')
    
    # Verify user exists
    user = DatabaseService.get_user_by_id(user_id)
    if not user:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Verify endpoint exists
    endpoint = DatabaseService.get_endpoint_by_id(endpoint_id)
    if not endpoint:
        return create_api_response({
            "error": "Not Found",
            "message": f"Endpoint with ID {endpoint_id} not found"
        }, 404)
    
    # Remove access
    success = DatabaseService.remove_user_endpoint_access(user_id, endpoint_id)
    
    if not success:
        return create_api_response({
            "message": "No access found to remove",
            "user_id": user_id,
            "endpoint_id": endpoint_id
        }, 200)
    
    return create_api_response({
        "message": "Endpoint access removed successfully",
        "user_id": user_id,
        "endpoint_id": endpoint_id,
        "endpoint_name": endpoint["endpoint_name"]
    }, 200)

def admin_assign_all_endpoints_to_user_route():
    """
    Assign all active endpoints to a user (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: "Admin API Key for authentication"
      - name: token
        in: query
        type: string
        required: true
        description: "A valid token for verification"
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - user_id
          properties:
            user_id:
              type: string
              description: "UUID of the user to grant access to all endpoints"
    produces:
      - application/json
    responses:
      200:
        description: "Access granted successfully to all endpoints"
      400:
        description: "Bad request"
      401:
        description: "Authentication error"
      403:
        description: "Forbidden - not an admin"
      404:
        description: "User not found"
      500:
        description: "Server error"
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to manage endpoint access"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Validate token from query parameter
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
    # Check if token is expired
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    if 'user_id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: user_id"
        }, 400)
    
    user_id = data.get('user_id')
    
    # Verify user exists
    user = DatabaseService.get_user_by_id(user_id)
    if not user:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Grant access to all endpoints
    success, result = DatabaseService.add_all_endpoints_access(user_id, admin_info["id"])
    
    if not success:
        return create_api_response({
            "error": "Server Error",
            "message": f"Failed to grant endpoint access: {result}"
        }, 500)
    
    return create_api_response({
        "message": "All endpoint access granted successfully",
        "user_id": user_id,
        "endpoints_added": result
    }, 200)

def admin_remove_all_endpoints_from_user_route():
    """
    Remove all endpoint access from a user (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: "Admin API Key for authentication"
      - name: token
        in: query
        type: string
        required: true
        description: "A valid token for verification"
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - user_id
          properties:
            user_id:
              type: string
              description: "UUID of the user to remove all endpoint access from"
    produces:
      - application/json
    responses:
      200:
        description: "All endpoint access removed successfully"
      400:
        description: "Bad request"
      401:
        description: "Authentication error"
      403:
        description: "Forbidden - not an admin"
      404:
        description: "User not found"
      500:
        description: "Server error"
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to manage endpoint access"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Validate token from query parameter
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
    # Check if token is expired
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    if 'user_id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: user_id"
        }, 400)
    
    user_id = data.get('user_id')
    
    # Verify user exists
    user = DatabaseService.get_user_by_id(user_id)
    if not user:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Remove all access
    removed_count = DatabaseService.remove_all_endpoints_access(user_id)
    
    return create_api_response({
        "message": "All endpoint access removed successfully",
        "user_id": user_id,
        "endpoints_removed": removed_count
    }, 200)

def admin_get_user_accessible_endpoints_route():
    """
    Get all endpoints accessible by a user (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: "Admin API Key for authentication"
      - name: token
        in: query
        type: string
        required: true
        description: "A valid token for verification"
      - name: user_id
        in: query
        type: string
        required: true
        description: "UUID of the user to get accessible endpoints for"
    produces:
      - application/json
    responses:
      200:
        description: "Endpoints retrieved successfully"
      400:
        description: "Bad request"
      401:
        description: "Authentication error"
      403:
        description: "Forbidden - not an admin"
      404:
        description: "User not found"
      500:
        description: "Server error"
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to view user endpoint access"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Validate token from query parameter
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
    # Check if token is expired
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get user_id from query parameter
    user_id = request.args.get('user_id')
    if not user_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing user_id parameter"
        }, 400)
    
    # Verify user exists
    user = DatabaseService.get_user_by_id(user_id)
    if not user:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Get accessible endpoints
    endpoints = DatabaseService.get_user_accessible_endpoints(user_id)
    
    return create_api_response({
        "user_id": user_id,
        "endpoints": endpoints,
        "count": len(endpoints),
        "is_admin": user["scope"] == 0
    }, 200)

def user_get_accessible_endpoints_route():
    """
    Get all endpoints accessible by the authenticated user
    ---
    tags:
      - User Endpoints
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: "Authentication token"
    produces:
      - application/json
    responses:
      200:
        description: "Endpoints retrieved successfully"
      401:
        description: "Authentication error"
      500:
        description: "Server error"
    """
    # Get token from X-Token header
    token = request.headers.get('X-Token')
    if not token:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing X-Token header"
        }, 401)
    
    # Validate token from database
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token - not found in database"
        }, 401)
    
    # Store token ID and user ID in g
    g.token_id = token_details["id"]
    g.user_id = token_details["user_id"]
    
    # Check if token is expired
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    
    # Ensure expiration_time is timezone-aware
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get user details
    user_id = token_details["user_id"]
    user_details = DatabaseService.get_user_by_id(user_id)
    if not user_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "User associated with token not found"
        }, 401)
    
    # Get accessible endpoints
    endpoints = DatabaseService.get_user_accessible_endpoints(user_id)
    
    return create_api_response({
        "user_id": user_id,
        "endpoints": endpoints,
        "count": len(endpoints),
        "is_admin": user_details["scope"] == 0
    }, 200)

def register_admin_endpoint_access_routes(app):
    """Register admin endpoint access routes with the Flask app"""
    app.route('/admin/endpoint/access/single', methods=['POST'])(api_logger(admin_assign_endpoint_to_user_route))
    app.route('/admin/endpoint/access/remove_single', methods=['POST'])(api_logger(admin_remove_endpoint_from_user_route))
    app.route('/admin/endpoint/access/all', methods=['POST'])(api_logger(admin_assign_all_endpoints_to_user_route))
    app.route('/admin/endpoint/access/remove_ll', methods=['POST'])(api_logger(admin_remove_all_endpoints_from_user_route))
    app.route('/admin/endpoint/access/', methods=['GET'])(api_logger(admin_get_user_accessible_endpoints_route))
    app.route('/user/allowed_endpoints', methods=['GET'])(api_logger(user_get_accessible_endpoints_route))
