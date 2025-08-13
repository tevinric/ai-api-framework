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

from apis.utils.config import create_api_response

def admin_delete_user_route():
    """
    Delete a user from the system (Admin only endpoint)
    ---
    tags:
      - Admin Functions
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
            - id
          properties:
            id:
              type: string
              description: UUID of the user to delete
    produces:
      - application/json
    responses:
      200:
        description: User deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: User deleted successfully
            user_id:
              type: string
              description: ID of the deleted user
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
              example: Missing required fields
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
      409:
        description: Conflict
        schema:
          type: object
          properties:
            error:
              type: string
              example: Conflict
            message:
              type: string
              example: Cannot delete user with active tokens
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
              example: Error deleting user
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
            "message": "Admin privileges required to delete users"
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
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    if 'id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: id"
        }, 400)
    
    # Get user ID to delete
    user_id = data.get('id')
    
    # Check if user exists
    user_exists = DatabaseService.get_user_by_id(user_id)
    if not user_exists:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Prevent admins from deleting themselves
    if user_id == admin_info["id"]:
        return create_api_response({
            "error": "Forbidden",
            "message": "Administrators cannot delete their own accounts"
        }, 403)
    
    try:
        # Delete user from database
        success = DatabaseService.delete_user(user_id)
        
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to delete user"
            }, 500)
        
        return create_api_response({
            "message": "User deleted successfully",
            "user_id": user_id
        }, 200)
        
    except Exception as e:
        error_msg = str(e)
        
        # Handle specific error for users with active tokens
        if "foreign key constraint" in error_msg.lower():
            return create_api_response({
                "error": "Conflict",
                "message": "Cannot delete user with active tokens. Revoke all tokens first."
            }, 409
            )
            
        logger.error(f"Error deleting user: {error_msg}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error deleting user: {error_msg}"
        }, 500)

def register_admin_delete_user_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/user', methods=['DELETE'])(api_logger(admin_delete_user_route))