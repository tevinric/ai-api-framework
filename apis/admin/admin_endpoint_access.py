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

def admin_grant_endpoint_access_single_route():
    """
    Grant a user access to a specific endpoint
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
              description: UUID of the user to grant endpoint access to
            endpoint_id:
              type: string
              description: UUID of the endpoint to grant access for
    produces:
      - application/json
    responses:
      201:
        description: Endpoint access successfully granted
        schema:
          type: object
          properties:
            message:
              type: string
              example: Endpoint access successfully granted
            user_id:
              type: string
              description: ID of the user
            endpoint_id:
              type: string
              description: ID of the endpoint
            access_id:
              type: string
              description: ID of the new access record
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
              example: Error granting endpoint access
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
            "message": "Admin privileges required to grant endpoint access"
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
    
    # Get request data from JSON body
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required parameters
    if 'user_id' not in data or 'endpoint_id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required parameters: user_id and endpoint_id are required"
        }, 400)
    
    user_id = data['user_id']
    endpoint_id = data['endpoint_id']
    
    # Check if user exists
    user_exists = DatabaseService.get_user_by_id(user_id)
    if not user_exists:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Get endpoint details
    endpoint = DatabaseService.get_endpoint_by_id(endpoint_id)
    if not endpoint:
        return create_api_response({
            "error": "Not Found",
            "message": f"Endpoint with ID {endpoint_id} not found"
        }, 404)
    
    try:
        # Grant endpoint access to the user
        success, result = DatabaseService.add_user_endpoint_access(user_id, endpoint_id, admin_info["id"])
        
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": f"Failed to grant endpoint access: {result}"
            }, 500)
        
        # If user already has access, return success with appropriate message
        if isinstance(result, str) and "already has access" in result:
            return create_api_response({
                "message": result,
                "user_id": user_id,
                "endpoint_id": endpoint_id
            }, 200)
        
        # Otherwise, return success with the new access ID
        return create_api_response({
            "message": "Endpoint access successfully granted",
            "user_id": user_id,
            "endpoint_id": endpoint_id,
            "access_id": result
        }, 201)
        
    except Exception as e:
        logger.error(f"Error granting endpoint access: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error granting endpoint access: {str(e)}"
        }, 500)

def admin_grant_endpoint_access_all_route():
    """
    Grant a user access to all active endpoints
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
              description: UUID of the user to grant access for all endpoints
    produces:
      - application/json
    responses:
      201:
        description: Access to all endpoints successfully granted
        schema:
          type: object
          properties:
            message:
              type: string
              example: Access to all endpoints successfully granted
            user_id:
              type: string
              description: ID of the user
            endpoints_added:
              type: integer
              description: Number of endpoint access entries added
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
              example: Error granting access to all endpoints
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
            "message": "Admin privileges required to grant endpoint access"
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
    
    # Get request data from JSON body
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required parameters
    if 'user_id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required parameter: user_id is required"
        }, 400)
    
    user_id = data['user_id']
    
    # Check if user exists
    user_exists = DatabaseService.get_user_by_id(user_id)
    if not user_exists:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    try:
        # Grant access to all endpoints for the user
        success, result = DatabaseService.add_all_endpoints_access(user_id, admin_info["id"])
        
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": f"Failed to grant access to all endpoints: {result}"
            }, 500)
        
        return create_api_response({
            "message": "Access to all endpoints successfully granted",
            "user_id": user_id,
            "endpoints_added": result
        }, 201)
        
    except Exception as e:
        logger.error(f"Error granting access to all endpoints: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error granting access to all endpoints: {str(e)}"
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
    # Updated function names and routes
    app.route('/admin/endpoint/access/single', methods=['POST'])(api_logger(admin_grant_endpoint_access_single_route))
    app.route('/admin/endpoint/access/all', methods=['POST'])(api_logger(admin_grant_endpoint_access_all_route))
    app.route('/admin/endpoint/access/single', methods=['DELETE'])(api_logger(admin_delete_endpoint_access_single_route))
    app.route('/admin/endpoint/access/all', methods=['DELETE'])(api_logger(admin_delete_endpoint_access_all_route))
