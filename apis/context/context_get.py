# apis/context/context_get.py
from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.context.context_service import ContextService
import logging
import pytz
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

from apis.utils.config import create_api_response

def get_context_route():
    """
    Get a context file by ID
    ---
    tags:
      - Context
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
      - name: context_id
        in: query
        type: string
        required: true
        description: ID of the context to retrieve
      - name: metadata_only
        in: query
        type: boolean
        required: false
        default: false
        description: Only return metadata without content
    produces:
      - application/json
    responses:
      200:
        description: Context retrieved successfully
        schema:
          type: object
          properties:
            context_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
            owner_id:
              type: string
              example: "98765432-9876-9876-9876-987654321098"
            owner_name:
              type: string
              example: "John Doe"
            name:
              type: string
              example: "My Context"
            description:
              type: string
              example: "Context for project X"
            created_at:
              type: string
              format: date-time
              example: "2023-06-01T10:30:45.123456+02:00"
            modified_at:
              type: string
              format: date-time
              example: "2023-06-02T14:22:33.123456+02:00"
            file_size:
              type: integer
              example: 2048
            content:
              type: string
              description: The context content (only included if metadata_only=false)
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
              example: "Missing required parameter: context_id"
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
              example: "You don't have permission to access this context"
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
              example: "Error retrieving context"
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
    
    # Get context_id from query parameter
    context_id = request.args.get('context_id')
    if not context_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required parameter: context_id"
        }, 400)
    
    # Check if metadata_only parameter is provided
    metadata_only = request.args.get('metadata_only', 'false').lower() == 'true'
    
    try:
        # Get context
        context_data, error = ContextService.get_context(
            context_id=context_id,
            user_id=g.user_id,
            metadata_only=metadata_only
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
        
        # Return success with context data
        return create_api_response(context_data, 200)
        
    except Exception as e:
        logger.error(f"Error getting context: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving context: {str(e)}"
        }, 500)

def list_contexts_route():
    """
    List contexts available to the user
    ---
    tags:
      - Context
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
      - name: name_filter
        in: query
        type: string
        required: false
        description: Filter contexts by name (partial match)
      - name: limit
        in: query
        type: integer
        required: false
        default: 50
        description: Maximum number of contexts to return
      - name: offset
        in: query
        type: integer
        required: false
        default: 0
        description: Pagination offset
    produces:
      - application/json
    responses:
      200:
        description: Contexts retrieved successfully
        schema:
          type: object
          properties:
            contexts:
              type: array
              items:
                type: object
                properties:
                  context_id:
                    type: string
                    example: "12345678-1234-1234-1234-123456789012"
                  owner_id:
                    type: string
                    example: "98765432-9876-9876-9876-987654321098"
                  owner_name:
                    type: string
                    example: "John Doe"
                  name:
                    type: string
                    example: "My Context"
                  description:
                    type: string
                    example: "Context for project X"
                  created_at:
                    type: string
                    format: date-time
                    example: "2023-06-01T10:30:45.123456+02:00"
                  modified_at:
                    type: string
                    format: date-time
                    example: "2023-06-02T14:22:33.123456+02:00"
                  file_size:
                    type: integer
                    example: 2048
            count:
              type: integer
              example: 5
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
              example: "Error listing contexts"
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
    
    # Get query parameters
    name_filter = request.args.get('name_filter')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    try:
        # List contexts
        contexts, error = ContextService.list_contexts(
            user_id=g.user_id,
            filter_name=name_filter,
            limit=limit,
            offset=offset
        )
        
        if error:
            return create_api_response({
                "error": "Server Error",
                "message": error
            }, 500)
        
        # Return success with contexts list
        return create_api_response({
            "contexts": contexts,
            "count": len(contexts)
        }, 200)
        
    except Exception as e:
        logger.error(f"Error listing contexts: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error listing contexts: {str(e)}"
        }, 500)

def register_context_get_routes(app):
    """Register context retrieval routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    app.route('/context', methods=['GET'])(track_usage(api_logger(check_endpoint_access(check_balance(get_context_route)))))
    app.route('/context/list', methods=['GET'])(track_usage(api_logger(check_endpoint_access(check_balance(list_contexts_route)))))
