from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.context.context_service import ContextService
import logging
import pytz
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

from apis.utils.config import create_api_response

def create_context_route():
    """
    Create a new context file from content and/or files
    ---
    tags:
      - Context
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            content:
              type: string
              description: Text content for the context
            file_ids:
              type: array
              items:
                type: string
              description: List of file IDs to process and include in context
            name:
              type: string
              description: Optional name for the context
            description:
              type: string
              description: Optional description for the context
    produces:
      - application/json
    responses:
      200:
        description: Context created successfully
        schema:
          type: object
          properties:
            context_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
            name:
              type: string
              example: "My Context"
            description:
              type: string
              example: "Context for project X"
            file_size:
              type: integer
              example: 2048
            created_at:
              type: string
              format: date-time
              example: "2023-06-01T10:30:45.123456+02:00"
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Bad Request"
            message:
              type: string
              example: "No content or files provided"
      401:
        description: Authentication error
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Authentication Error"
            message:
              type: string
              example: "Token has expired"
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Server Error"
            message:
              type: string
              example: "Error creating context"
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
    
    # Store token ID and user ID in g for logging and balance check
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
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Extract parameters
    content = data.get('content')
    file_ids = data.get('file_ids', [])
    name = data.get('name')
    description = data.get('description')
    
    # Validate that at least content or files are provided
    if not content and not file_ids:
        return create_api_response({
            "error": "Bad Request",
            "message": "Either content or file_ids must be provided"
        }, 400)
    
    try:
        # Create context
        context_info, error = ContextService.create_context(
            user_id=g.user_id,
            content=content,
            files=file_ids,
            context_name=name,
            description=description
        )
        
        if error:
            return create_api_response({
                "error": "Processing Error",
                "message": error
            }, 400 if "No content" in error else 500)
        
        # Return success with context info
        return create_api_response(context_info, 200)
        
    except Exception as e:
        logger.error(f"Error creating context: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error creating context: {str(e)}"
        }, 500)

def register_context_create_routes(app):
    """Register context creation route with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    app.route('/context', methods=['POST'])(track_usage(api_logger(check_endpoint_access(check_balance(create_context_route)))))
