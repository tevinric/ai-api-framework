# apis/context/context_delete.py
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

def delete_context_route():
    """
    Delete a context file
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
        description: ID of the context to delete
    produces:
      - application/json
    responses:
      200:
        description: Context deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Context deleted successfully"
            context_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
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
              example: "You don't have permission to delete this context"
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
              example: "Error deleting context"
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
    
    try:
        # Delete context
        success, error = ContextService.delete_context(
            context_id=context_id,
            user_id=g.user_id
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
        
        # Return success
        return create_api_response({
            "message": "Context deleted successfully",
            "context_id": context_id
        }, 200)
        
    except Exception as e:
        logger.error(f"Error deleting context: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error deleting context: {str(e)}"
        }, 500)

def register_context_delete_routes(app):
    """Register context deletion route with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    app.route('/context', methods=['DELETE'])(track_usage(api_logger(check_endpoint_access(delete_context_route))))
