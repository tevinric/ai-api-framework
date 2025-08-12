from flask import jsonify, request, g, make_response
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

from apis.utils.config import create_api_response

def get_all_users_route():
    """
    Get all users in the system (Admin only endpoint)
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
    produces:
      - application/json
    responses:
      200:
        description: Users retrieved successfully
        schema:
          type: object
          properties:
            users:
              type: array
              items:
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
                    description: Permission scope
                  active:
                    type: boolean
                    description: Whether the user is active
                  created_at:
                    type: string
                    format: date-time
                    description: User creation timestamp
                  aic_balance:
                    type: number
                    description: Current balance
            total_count:
              type: integer
              description: Total number of users
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
              example: Missing token parameter
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
              example: Invalid API Key
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
              example: Error retrieving users
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
            "message": "Admin privileges required to view all users"
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
    
    try:
        # Get all users from database
        result = DatabaseService.execute_query("""
            SELECT id, user_name, user_email, common_name, company, department, 
                   phone_ext, division, sub_department, cost_center, manager_full_name, 
                   manager_email, scope, active, created_at, modified_at, 
                   comment, aic_balance
            FROM users 
            ORDER BY created_at DESC
        """)
        
        if not result['success']:
            return create_api_response({
                "error": "Server Error",
                "message": "Error retrieving users from database"
            }, 500)
        
        users = []
        for row in result['data']:
            users.append({
                "user_id": str(row[0]),
                "user_name": row[1],
                "user_email": row[2],
                "common_name": row[3],
                "company": row[4],
                "department": row[5],
                "phone_ext": row[6],
                "division": row[7],
                "sub_department": row[8],
                "cost_center": row[9],
                "manager_full_name": row[10],
                "manager_email": row[11],
                "scope": row[12],
                "active": bool(row[13]),
                "created_at": row[14].isoformat() if row[14] else None,
                "modified_at": row[15].isoformat() if row[15] else None,
                "comment": row[16],
                "aic_balance": float(row[17]) if row[17] else None
            })
        
        return create_api_response({
            "users": users,
            "total_count": len(users)
        }, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving all users: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": "Error retrieving users"
        }, 500)

def register_get_all_users_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/users', methods=['GET'])(api_logger(get_all_users_route))