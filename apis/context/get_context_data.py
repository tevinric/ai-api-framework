from flask import jsonify, request, g
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.config import create_api_response
from apis.context.context_service import ContextService
import logging
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def get_context_data_route():
    """
    Retrieve the text content of a context file by context ID
    ---
    tags:
      - Context
    summary: Get context file text content
    description: Retrieves the text content of a context file to allow users to see what the context file contains before making updates. Returns the full text content along with metadata.
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
      - name: context_id
        in: query
        type: string
        required: true
        description: Unique context identifier
    produces:
      - application/json
    responses:
      200:
        description: Context data retrieved successfully
        schema:
          type: object
          properties:
            context_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
            context_name:
              type: string
              example: "Project Documentation Context"
            context_description:
              type: string
              example: "Context containing project documentation and guidelines"
            context_text:
              type: string
              example: "This is the full text content of the context file..."
            created_date:
              type: string
              format: date-time
              example: "2024-03-16T10:30:45+02:00"
            updated_date:
              type: string
              format: date-time
              example: "2024-03-16T15:45:30+02:00"
            file_size:
              type: integer
              example: 2048
              description: Size of the context file in bytes
            owner_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
              description: ID of the user who owns this context
            owner_name:
              type: string
              example: "John Doe"
              description: Name of the user who owns this context
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
              example: context_id is required as a query parameter
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
              enum:
                - Missing X-Token header
                - Invalid token
                - Token has expired
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
              example: You don't have permission to access this context
      404:
        description: Context not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: Context with ID 12345678-1234-1234-1234-123456789012 not found
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
              example: Error retrieving context data
    """
    # Get token from X-Token header
    token = request.headers.get('X-Token')
    if not token:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing X-Token header"
        }, 401)
    
    # Validate token and get token details
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token"
        }, 401)
        
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
        
    g.user_id = token_details["user_id"]
    g.token_id = token_details["id"]
    
    # Get context_id from query parameter
    context_id = request.args.get('context_id')
    if not context_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "context_id is required as a query parameter"
        }, 400)
    
    try:
        # Get context data using ContextService (includes content)
        context_data, error = ContextService.get_context(
            context_id=context_id,
            user_id=g.user_id,
            metadata_only=False  # We want the full content
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
                    "error": "Server Error",
                    "message": error
                }, 500)
        
        # Prepare response data with the content
        response_data = {
            "context_id": context_data.get('context_id'),
            "context_name": context_data.get('name', ''),
            "context_description": context_data.get('description', ''),
            "context_text": context_data.get('content', ''),
            "created_date": context_data.get('created_at'),
            "updated_date": context_data.get('modified_at'),
            "file_size": context_data.get('file_size', 0),
            "owner_id": context_data.get('owner_id'),
            "owner_name": context_data.get('owner_name', 'Unknown')
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving context data: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving context data: {str(e)}"
        }, 500)

def register_get_context_data_routes(app):
    """Register context data retrieval routes with the Flask app"""
    from apis.utils.rbacMiddleware import check_endpoint_access
    app.route('/context/data', methods=['GET'])(api_logger(check_endpoint_access(get_context_data_route)))