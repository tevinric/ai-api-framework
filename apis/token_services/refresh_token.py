from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import pytz
from datetime import datetime, timedelta

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def refresh_token_route():
    """
    Refresh an existing token to extend its expiration time
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
        description: The token to refresh
    produces:
      - application/json
    responses:
      200:
        description: Token refreshed successfully
        schema:
          type: object
          properties:
            access_token:
              type: string
              description: The new refreshed token
            token_type:
              type: string
              description: Type of token generated
            expires_in:
              type: integer
              format: seconds
              description: Time in seconds until token expiration
            expires_on:
              type: string
              format: date-time
              description: Token expiration timestamp
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
              example: Missing token parameter or Invalid token format
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
              example: Error refreshing token
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
        
    g.user_id = user_info["id"]
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Get token details from database
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Bad Request",
            "message": "Invalid token"
        }, 400)
        
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
            "error": "Bad Request",
            "message": "Token has expired and cannot be refreshed"
        }, 400)
    
    # Initialize TokenService
    token_service = TokenService()
    
    try:
        # Call MSAL to get a new token
        response_data, status_code = token_service.get_token(user_info)
        
        if status_code != 200 or "access_token" not in response_data:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to generate a new token"
            }, 500)
            
        # Record token refresh in database
        new_token = response_data["access_token"]
        expires_in = response_data["expires_in"]
        
        # Parse expires_on string to datetime
        expires_on_str = response_data.get("expires_on")
        try:
            # Try to parse the datetime string (format may vary)
            expires_on = datetime.strptime(expires_on_str, "%Y-%m-%d %H:%M:%S %z")
        except (ValueError, TypeError):
            # Fallback: calculate from expires_in
            expires_on = now + timedelta(seconds=expires_in)
        
        # Log the refreshed token
        success = DatabaseService.log_refreshed_token(
            user_id=user_info["id"],
            token_scope=token_details["token_scope"],
            expires_in=expires_in,
            expires_on=expires_on,
            token_value=new_token,
            regenerated_from=token,
            regenerated_by=user_info["id"]
        )
        
        if not success:
            logger.warning("Failed to log refreshed token in database")
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error refreshing token: {str(e)}"
        }, 500)

def register_refresh_token_routes(app):
    """Register refresh token routes with the Flask app"""
    app.route('/refresh-token', methods=['POST'])(api_logger(refresh_token_route))