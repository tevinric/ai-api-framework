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

def admin_update_user_route():
    """
Update existing user details (Admin only endpoint)
---
tags:
  - Admin Functions
produces:
  - application/json
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
        - id
      properties:
        id:
          type: string
          description: UUID of the user to update
        user_name:
          type: string
          description: Updated username (optional)
        user_email:
          type: string
          description: Updated email address (optional)
        common_name:
          type: string
          description: Updated common name (optional)
        company:
          type: string
          description: Updated company name (optional)
        department:
          type: string
          description: Updated department name (optional)
        phone_ext:
          type: string
          description: Updated phone extension (optional)
        division:
          type: string
          description: Updated division name (optional)
        sub_department:
          type: string
          description: Updated sub-division name (optional)
        cost_center:
          type: string
          description: Updated cost center (optional)
        manager_full_name:
          type: string
          description: Updated manager's full name (optional)
        manager_email:
          type: string
          description: Updated manager's email address (optional)
        scope:
          type: integer
          description: Updated permission scope (optional, 1-5)
        active:
          type: boolean
          description: Updated active status (optional)
        comment:
          type: string
          description: Updated comment (optional)
        aic_balance:
          type: number
          format: decimal
          description: Custom monthly balance for the user (optional)
responses:
  200:
    description: User updated successfully
    schema:
      type: object
      properties:
        message:
          type: string
          example: User updated successfully
        user_id:
          type: string
          description: ID of the updated user
        updated_fields:
          type: array
          items:
            type: string
          description: List of fields that were updated
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
          example: Email address already in use by another user
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
          example: Error updating user
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
            "message": "Admin privileges required to update users"
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
    
    # Validate required fields in request body
    if 'id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: id"
        }, 400)
    
    # Get user ID to update
    user_id = data.get('id')
    
    # Get current user details
    current_user = DatabaseService.get_user_by_id(user_id)
    if not current_user:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Prepare update data (only include fields that are provided AND different from current values)
    update_data = {}
    valid_fields = ['user_name', 'user_email', 'common_name', 'company', 'department', 
                    'phone_ext', 'division', 'sub_department', 'cost_center', 
                    'manager_full_name', 'manager_email', 
                    'scope', 'active', 'comment', 'aic_balance']
    
    for field in valid_fields:
        if field in data and data[field] is not None:
            # Skip fields where the value hasn't changed
            if field in current_user and data[field] == current_user[field]:
                logger.info(f"Skipping field '{field}' as value hasn't changed")
                continue
                
            # For email, validate format
            if field == 'user_email' and '@' not in data[field]:
                return create_api_response({
                    "error": "Bad Request",
                    "message": "Invalid email format"
                }, 400)
                
            # For scope, validate range
            if field == 'scope' and not (0 <= data[field] <= 5):
                return create_api_response({
                    "error": "Bad Request",
                    "message": "Scope must be between 0 and 5"
                }, 400)

            # Validation for aic_balance
            if field == 'aic_balance':
                try:
                    balance = float(data[field])
                    if balance < 0:
                        return create_api_response({
                            "error": "Bad Request",
                            "message": "Custom balance must be a non-negative number"
                        }, 400)
                    update_data[field] = balance
                except (ValueError, TypeError):
                    return create_api_response({
                        "error": "Bad Request",
                        "message": "Custom balance must be a valid number"
                    }, 400)
            
            update_data[field] = data[field]
    
    # If no fields to update, return early
    if not update_data:
        return create_api_response({
            "message": "No fields to update",
            "user_id": user_id,
            "updated_fields": []
        }, 200)
    
    # Check if trying to update email, make sure it's not already in use by another user
    if 'user_email' in update_data:
        new_email = update_data['user_email']
        
        # Check if this email is already in use by a DIFFERENT user
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT id FROM users 
            WHERE user_email = ? AND id != ?
            """
            
            cursor.execute(query, [new_email, user_id])
            existing_user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if existing_user:
                return create_api_response({
                    "error": "Conflict",
                    "message": f"Email address {new_email} is already in use by another user"
                }, 409)
                
        except Exception as e:
            logger.error(f"Error checking email uniqueness: {str(e)}")
            # Continue with the update, we'll handle any DB constraint errors later
    
    try:
        # Update user in database
        success, updated_fields = DatabaseService.update_user(user_id, update_data)
        
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to update user"
            }, 500)
        
        return create_api_response({
            "message": "User updated successfully",
            "user_id": user_id,
            "updated_fields": updated_fields
        }, 200)
        
    except ValueError as ve:
        # Handle specific validation errors from DatabaseService
        error_message = str(ve)
        if "Email address already exists" in error_message:
            return create_api_response({
                "error": "Conflict",
                "message": error_message
            }, 409)
        else:
            return create_api_response({
                "error": "Bad Request",
                "message": error_message
            }, 400)
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error updating user: {str(e)}"
        }, 500)

def register_admin_update_user_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/user', methods=['PUT'])(api_logger(admin_update_user_route))
