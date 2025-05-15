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

def update_context_route():
    """
    Update an existing context file
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
          required:
            - context_id
          properties:
            context_id:
              type: string
              description: ID of the context to update
            content:
              type: string
              description: New text content to add or replace
            file_ids:
              type: array
              items:
                type: string
              description: File IDs to process and add to context
            append:
              type: boolean
              default: true
              description: Whether to append to existing content (true) or replace it (false)
            name:
              type: string
              description: New name for the context
            description:
              type: string
              description: New description for the context
    produces:
      - application/json
    responses:
      200:
        description: Context updated successfully
        schema:
          type: object
          properties:
            context_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
            name:
              type: string
              example: "My Updated Context"
            description:
              type: string
              example: "Updated context for project X"
            file_size:
              type: integer
              example: 3072
            created_at:
              type: string
              format: date-time
              example: "2023-06-01T10:30:45.123456+02:00"
            modified_at:
              type: string
              format: date-time
              example: "2023-06-03T15:40:22.123456+02:00"
            updated_content:
              type: boolean
              example: true
            updated_metadata:
              type: boolean
              example: true
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
              example: "Missing required field: context_id"
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
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Forbidden"
            message:
              type: string
              example: "You don't have permission to update this context"
      404:
        description: Not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Not Found"
            message:
              type: string
              example: "Context not found"
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
              example: "Error updating context"
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
    
    # Check required field
    if 'context_id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: context_id"
        }, 400)
    
    # Extract parameters
    context_id = data.get('context_id')
    content = data.get('content')
    file_ids = data.get('file_ids')
    append = data.get('append', True)
    name = data.get('name')
    description = data.get('description')
    
    # Check if any update parameters provided
    if not content and not file_ids and name is None and description is None:
        return create_api_response({
            "error": "Bad Request",
            "message": "At least one update field (content, file_ids, name, or description) must be provided"
        }, 400)
    
    try:
        # Update context
        updated_context, error = ContextService.update_context(
            context_id=context_id,
            user_id=g.user_id,
            content=content,
            files=file_ids,
            append=append,
            context_name=name,
            description=description
        )
        
        if error:
            if "not found" in error:
                return create_api_response({
                    "error": "Not Found",
                    "message": error
                }, 404)
            elif "permission" in error:
                return create_api_response({
                    "error": "Forbidden",
                    "message": error
                }, 403)
            else:
                return create_api_response({
                    "error": "Processing Error",
                    "message": error
                }, 400 if "No content" in error else 500)
        
        # Return success with updated context info
        return create_api_response(updated_context, 200)
        
    except Exception as e:
        logger.error(f"Error updating context: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error updating context: {str(e)}"
        }, 500)

def register_context_update_routes(app):
    """Register context update route with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    app.route('/context', methods=['PUT'])(track_usage(api_logger(check_endpoint_access(check_balance(update_context_route)))))
