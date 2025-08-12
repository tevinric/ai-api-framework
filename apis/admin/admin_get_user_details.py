from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

from apis.utils.config import create_api_response

def get_user_details_route():
    """
    Get user details by email address (Used for authentication - no token required)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: email
        in: query
        type: string
        required: true
        description: Email address of the user to retrieve
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
    produces:
      - application/json
    responses:
      200:
        description: User details retrieved successfully
        schema:
          type: object
          properties:
            user_id:
              type: string
              description: Unique identifier for the user
            user_name:
              type: string
              description: Username of the user
            user_email:
              type: string
              description: Email address of the user
            common_name:
              type: string
              description: Common name of the user
            company:
              type: string
              description: Company name
            department:
              type: string
              description: Department name
            scope:
              type: integer
              description: Permission scope (0 = admin)
            active:
              type: boolean
              description: Whether the user is active
            api_key:
              type: string
              description: User's API key (only returned if scope = 0)
            created_at:
              type: string
              format: date-time
              description: User creation timestamp
            modified_at:
              type: string
              format: date-time
              description: Last modification timestamp
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
              example: Missing email parameter
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
              example: User not authorized to access this application
      404:
        description: User not found
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
              example: Error retrieving user details
    """
    
    # Get email from query parameter
    email = request.args.get('email')
    if not email:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing email parameter"
        }, 400)
    
    try:
        # Look up user in the database
        user_details = DatabaseService.get_user_by_email(email)
        
        if not user_details:
            return create_api_response({
                "error": "Not Found",
                "message": "User not found"
            }, 404)
        
        # Check if user has admin privileges (scope = 0)
        if user_details.get("scope") != 0:
            return create_api_response({
                "error": "Authentication Error",
                "message": "User not authorized to access this application"
            }, 401)
        
        # Return user details including API key (since scope = 0)
        response_data = {
            "user_id": user_details.get("id"),
            "user_name": user_details.get("user_name"),
            "user_email": user_details.get("user_email"),
            "common_name": user_details.get("common_name"),
            "company": user_details.get("company"),
            "department": user_details.get("department"),
            "phone_ext": user_details.get("phone_ext"),
            "division": user_details.get("division"),
            "sub_department": user_details.get("sub_department"),
            "cost_center": user_details.get("cost_center"),
            "manager_full_name": user_details.get("manager_full_name"),
            "manager_email": user_details.get("manager_email"),
            "scope": user_details.get("scope"),
            "active": user_details.get("active"),
            "api_key": user_details.get("api_key"),
            "created_at": user_details.get("created_at").isoformat() if user_details.get("created_at") else None,
            "modified_at": user_details.get("modified_at").isoformat() if user_details.get("modified_at") else None,
            "comment": user_details.get("comment"),
            "aic_balance": float(user_details.get("aic_balance")) if user_details.get("aic_balance") else None
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving user details: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": "Error retrieving user details"
        }, 500)

def register_get_user_details_routes(app):
    """Register routes with the Flask app"""
    # Note: This endpoint does NOT require authentication as it's used for initial login validation
    app.route('/admin/user-details', methods=['GET'])(api_logger(get_user_details_route))