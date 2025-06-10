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

from apis.utils.config import create_api_response

def create_user_route():
    """
    Create a new user in the system (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
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
            - user_name
            - user_email
          properties:
            user_name:
              type: string
              description: Username for the new user
            user_email:
              type: string
              description: Email address for the new user
            common_name:
              type: string
              description: Common name for the new user (optional)
            company:
              type: string
              description: Company name for the new user (optional)
            department:
              type: string
              description: Department name for the new user (optional)
            phone_ext:
              type: string
              description: Phone extension for the new user (optional)
            division:
              type: string
              description: Division name for the new user (optional)
            sub_department:
              type: string
              description: Sub-division name for the new user (optional)
            cost_center:
              type: string
              description: Cost center for the new user (optional)
            manager_full_name:
              type: string
              description: Manager's full name for the new user (optional)
            manager_email:
              type: string
              description: Manager's email address for the new user (optional)
            scope:
              type: integer
              description: Permission scope for the new user (1-5)
            active:
              type: boolean
              description: Whether the user is active
            comment:
              type: string
              description: Optional comment about the user
    produces:
      - application/json
    responses:
      201:
        description: User created successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: User created successfully
            user_id:
              type: string
              description: ID of the newly created user
            api_key:
              type: string
              description: API key assigned to the new user
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
              example: Missing required fields or invalid data
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
              example: Error creating user
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
            "message": "Admin privileges required to create users"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Verify the token is valid
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
    
    # Validate required fields for user creation
    required_fields = ['user_name', 'user_email']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Validate email format (basic check)
    if '@' not in data['user_email']:
        return create_api_response({
            "error": "Bad Request",
            "message": "Invalid email format"
        }, 400)
    
    # Extract user data from request
    new_user = {
        'user_name': data['user_name'],
        'user_email': data['user_email'],
        'common_name': data.get('common_name', None),
        'scope': data.get('scope', 1),  # Default scope is 1
        'active': data.get('active', True),  # Default active is True
        'comment': data.get('comment', None),
        'company': data.get('company', None),  # Company field
        'department': data.get('department', None),  # Department field
        'phone_ext': data.get('phone_ext', None),  # New fields
        'division': data.get('division', None),
        'sub_department': data.get('sub_department', None),
        'cost_center': data.get('cost_center', None),
        'manager_full_name': data.get('manager_full_name', None),
        'manager_email': data.get('manager_email', None)
    }
    
    # Validate scope is within allowed range (1-5)
    if not (1 <= new_user['scope'] <= 5):
        return create_api_response({
            "error": "Bad Request",
            "message": "Scope must be between 1 and 5"
        }, 400)
    
    try:
        # Create user in the database
        user_id, api_key = DatabaseService.create_user(new_user)
        
        if not user_id:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to create user "
            }, 500)
        
        return create_api_response({
            "message": "User created successfully",
            "user_id": user_id,
            "api_key": api_key
        }, 201)
        
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error creating user: {str(e)}"
        }, 500)

def register_create_user_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/user', methods=['POST'])(api_logger(create_user_route))
