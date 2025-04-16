from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def admin_get_endpoint_access_single_route():
    """
    Get endpoint access for a specific user and endpoint
    ---
    tags:
      - Admin Endpoint Access
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: token
        in: query
        type: string
        required: true
        description: A valid token for verification
      - name: user_id
        in: query
        type: string
        required: true
        description: UUID of the user to check endpoint access for
      - name: endpoint_id
        in: query
        type: string
        required: true
        description: UUID of the endpoint to check access for
    produces:
      - application/json
    responses:
      200:
        description: Endpoint access information
        schema:
          type: object
          properties:
            access_granted:
              type: boolean
              description: Whether the user has access to the endpoint
            endpoint_id:
              type: string
              description: ID of the endpoint
            user_id:
              type: string
              description: ID of the user
            endpoint_details:
              type: object
              description: Details about the endpoint
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
              example: Bad Request
            message:
              type: string
              example: Missing required parameters
      401:
        description: Authentication error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Authentication Error
            message:
              type: string
              example: Missing API Key header or Invalid API Key
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: Admin privileges required
      404:
        description: Not Found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: Endpoint or User not found
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Server Error
            message:
              type: string
              example: Error retrieving endpoint access
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key
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
            "message": "Admin privileges required to view endpoint access"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Validate token
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
    
    # Ensure expiration_time is timezone-aware
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get required parameters
    user_id = request.args.get('user_id')
    endpoint_id = request.args.get('endpoint_id')
    
    # Validate required parameters
    if not user_id or not endpoint_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required parameters: user_id and endpoint_id are required"
        }, 400)
    
    # Check if user exists
    user_exists = DatabaseService.get_user_by_id(user_id)
    if not user_exists:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Fixed: Changed from get_endpoint_by_ud to get_endpoint_by_id
    endpoint = DatabaseService.get_endpoint_by_id(endpoint_id)
    if not endpoint:
        return create_api_response({
            "error": "Not Found",
            "message": f"Endpoint with ID {endpoint_id} not found"
        }, 404)
    
    try:
        # Get endpoint access info
        access_info = DatabaseService.get_user_endpoint_access(user_id, endpoint_id)
        
        return create_api_response({
            "access_granted": access_info.get("access_granted", False) if access_info else False,
            "endpoint_id": endpoint_id,
            "user_id": user_id,
            "endpoint_details": endpoint
        }, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving endpoint access: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving endpoint access: {str(e)}"
        }, 500)

def admin_get_endpoint_access_all_route():
    """
    Get all endpoint access for a specific user
    ---
    tags:
      - Admin Endpoint Access
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: token
        in: query
        type: string
        required: true
        description: A valid token for verification
      - name: user_id
        in: query
        type: string
        required: true
        description: UUID of the user to check endpoint access for
    produces:
      - application/json
    responses:
      200:
        description: List of endpoint access information
        schema:
          type: object
          properties:
            user_id:
              type: string
              description: ID of the user
            endpoint_access:
              type: array
              items:
                type: object
                properties:
                  endpoint_id:
                    type: string
                  endpoint_path:
                    type: string
                  endpoint_name:
                    type: string
                  access_granted:
                    type: boolean
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
              example: Bad Request
            message:
              type: string
              example: Missing required parameters
      401:
        description: Authentication error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Authentication Error
            message:
              type: string
              example: Missing API Key header or Invalid API Key
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: Admin privileges required
      404:
        description: Not Found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: User not found
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Server Error
            message:
              type: string
              example: Error retrieving endpoint access
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key
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
            "message": "Admin privileges required to view endpoint access"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Validate token
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
    
    # Ensure expiration_time is timezone-aware
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get required parameters
    user_id = request.args.get('user_id')
    
    # Validate required parameters
    if not user_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required parameter: user_id is required"
        }, 400)
    
    # Check if user exists
    user_exists = DatabaseService.get_user_by_id(user_id)
    if not user_exists:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    try:
        # Get all endpoint access for the user
        access_list = DatabaseService.get_all_user_endpoint_access(user_id)
        
        return create_api_response({
            "user_id": user_id,
            "endpoint_access": access_list
        }, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving all endpoint access: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving all endpoint access: {str(e)}"
        }, 500)

def admin_delete_endpoint_access_single_route():
    """
    Delete endpoint access for a specific user and endpoint
    ---
    tags:
      - Admin Endpoint Access
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: token
        in: query
        type: string
        required: true
        description: A valid token for verification
      - name: user_id
        in: query
        type: string
        required: true
        description: UUID of the user to remove endpoint access for
      - name: endpoint_id
        in: query
        type: string
        required: true
        description: UUID of the endpoint to remove access for
    produces:
      - application/json
    responses:
      200:
        description: Endpoint access successfully removed
        schema:
          type: object
          properties:
            message:
              type: string
              example: Endpoint access successfully removed
            user_id:
              type: string
              description: ID of the user
            endpoint_id:
              type: string
              description: ID of the endpoint
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
              example: Bad Request
            message:
              type: string
              example: Missing required parameters
      401:
        description: Authentication error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Authentication Error
            message:
              type: string
              example: Missing API Key header or Invalid API Key
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: Admin privileges required
      404:
        description: Not Found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: Endpoint or User not found
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Server Error
            message:
              type: string
              example: Error removing endpoint access
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key
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
            "message": "Admin privileges required to remove endpoint access"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Validate token
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
    
    # Ensure expiration_time is timezone-aware
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get required parameters
    user_id = request.args.get('user_id')
    endpoint_id = request.args.get('endpoint_id')
    
    # Validate required parameters
    if not user_id or not endpoint_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required parameters: user_id and endpoint_id are required"
        }, 400)
    
    # Check if user exists
    user_exists = DatabaseService.get_user_by_id(user_id)
    if not user_exists:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Check if endpoint exists
    endpoint = DatabaseService.get_endpoint_by_id(endpoint_id)
    if not endpoint:
        return create_api_response({
            "error": "Not Found",
            "message": f"Endpoint with ID {endpoint_id} not found"
        }, 404)
    
    try:
        # Remove endpoint access
        success = DatabaseService.remove_user_endpoint_access(user_id, endpoint_id)
        
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to remove endpoint access"
            }, 500)
        
        return create_api_response({
            "message": "Endpoint access successfully removed",
            "user_id": user_id,
            "endpoint_id": endpoint_id
        }, 200)
        
    except Exception as e:
        logger.error(f"Error removing endpoint access: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error removing endpoint access: {str(e)}"
        }, 500)

def admin_delete_endpoint_access_all_route():
    """
    Delete all endpoint access for a specific user
    ---
    tags:
      - Admin Endpoint Access
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: token
        in: query
        type: string
        required: true
        description: A valid token for verification
      - name: user_id
        in: query
        type: string
        required: true
        description: UUID of the user to remove all endpoint access for
    produces:
      - application/json
    responses:
      200:
        description: All endpoint access successfully removed
        schema:
          type: object
          properties:
            message:
              type: string
              example: All endpoint access successfully removed
            user_id:
              type: string
              description: ID of the user
            endpoints_removed:
              type: integer
              description: Number of endpoint access entries removed
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
              example: Bad Request
            message:
              type: string
              example: Missing required parameters
      401:
        description: Authentication error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Authentication Error
            message:
              type: string
              example: Missing API Key header or Invalid API Key
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: Admin privileges required
      404:
        description: Not Found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: User not found
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Server Error
            message:
              type: string
              example: Error removing all endpoint access
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key
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
            "message": "Admin privileges required to remove all endpoint access"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Validate token
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
    
    # Ensure expiration_time is timezone-aware
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get required parameters
    user_id = request.args.get('user_id')
    
    # Validate required parameters
    if not user_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required parameter: user_id is required"
        }, 400)
    
    # Check if user exists
    user_exists = DatabaseService.get_user_by_id(user_id)
    if not user_exists:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    try:
        # Remove all endpoint access for the user
        count_removed = DatabaseService.remove_all_user_endpoint_access(user_id)
        
        return create_api_response({
            "message": "All endpoint access successfully removed",
            "user_id": user_id,
            "endpoints_removed": count_removed
        }, 200)
        
    except Exception as e:
        logger.error(f"Error removing all endpoint access: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error removing all endpoint access: {str(e)}"
        }, 500)

def register_admin_endpoint_access_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/endpoint/access/single', methods=['GET'])(api_logger(admin_get_endpoint_access_single_route))
    app.route('/admin/endpoint/access/all', methods=['GET'])(api_logger(admin_get_endpoint_access_all_route))
    app.route('/admin/endpoint/access/single', methods=['DELETE'])(api_logger(admin_delete_endpoint_access_single_route))
    app.route('/admin/endpoint/access/all', methods=['DELETE'])(api_logger(admin_delete_endpoint_access_all_route))
