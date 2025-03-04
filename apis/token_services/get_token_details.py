from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
from datetime import datetime
import pytz

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def get_token_details_route():
    """
    Retrieve details for a specific token after validating the API key.
    ---
    tags:
      - Token Service
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
      - name: token
        in: query
        type: string
        required: true
        description: The token to validate and get details for
    produces:
      - application/json
    responses:
      200:
        description: Token details retrieved successfully
        schema:
          type: object
          properties:
            token_status:
              type: string
              enum: [valid, invalid, expired]
              description: Current status of the token
              example: valid
            user_id:
              type: string
              description: ID of the user who issued the token
              example: "12345678-1234-1234-1234-123456789012"
            token_scope:
              type: string
              description: Scope of the token
              example: "0,1,2,3,4,5"
            token_expiration_time:
              type: string
              format: date-time
              description: Token expiration timestamp
              example: "yyyy-mm-ddd hh:mm:ss SAST+0200"
          required:
            - token_status
            - user_id
            - token_scope
            - token_expiration_time
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
              example: Missing API Key header (API-Key) or Invalid API Key
      404:
        description: Token not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: Token details not found
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
              example: Error retrieving token details
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key
    user_info = DatabaseService.validate_api_key(api_key)
    if not user_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = user_info['id']
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    try:
        # Get token details from database
        token_details = DatabaseService.get_token_details_by_value(token)
        
        if not token_details:
            return create_api_response({
                "error": "Not Found",
                "message": "Token details not found"
            }, 404)
            
        g.token_id = token_details["id"]
        
        # Determine if token is expired
        now = datetime.now(pytz.UTC)
        expiration_time = token_details["token_expiration_time"]
        
        # Ensure expiration_time is timezone-aware
        if expiration_time.tzinfo is None:
            johannesburg_tz = pytz.timezone('Africa/Johannesburg')
            expiration_time = johannesburg_tz.localize(expiration_time)
            
        if now > expiration_time:
            token_status = "expired"
        else:
            # Validate token with Microsoft Graph
            is_valid = TokenService.validate_token(token)
            token_status = "valid" if is_valid else "invalid"
        
        response_data = {
            "token_status": token_status,
            "user_id": token_details["user_id"],
            "token_scope": token_details["token_scope"],
            "token_expiration_time": token_details["token_expiration_time"].strftime('%Y-%m-%d %H:%M:%S %Z%z')
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving token details: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving token details: {str(e)}"
        }, 500)

def register_token_details_routes(app):
    """Register routes with the Flask app"""
    app.route('/get-token-details', methods=['GET'])(api_logger(get_token_details_route))


