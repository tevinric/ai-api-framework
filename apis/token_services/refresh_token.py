from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import pytz
import uuid
from datetime import datetime, timedelta

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

from apis.utils.config import create_api_response


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
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
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
        # Get a new token directly from the token service
        # This bypasses the log_token_transaction call in the get_token method
        import requests
        import os
        from apis.utils.config import Config
        
        # Define the token endpoint
        token_endpoint = f"https://login.microsoftonline.com/{Config.TENANT_ID}/oauth2/token/"
        
        # Prepare the request body
        data = {
            "client_id": Config.CLIENT_ID,
            "client_secret": Config.CLIENT_SECRET,
            "resource": 'https://graph.microsoft.com',
            "grant_type": "client_credentials"
        }
        
        # Make the POST request
        response = requests.post(token_endpoint, data=data)
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        
        if "access_token" not in result:
            logger.error(f"Token acquisition failed: {result.get('error_description', 'Unknown error')}")
            return create_api_response({
                "error": "Failed to acquire token",
                "details": result.get("error_description", "Unknown error")
            }, 500)
        
        # Extract token information
        new_token = result.get("access_token")
        expires_in = result.get("expires_in")
        
        # Calculate expiration time
        expires_on_timestamp = int(result.get("expires_on"))
        utc_time = datetime.fromtimestamp(expires_on_timestamp, pytz.UTC)
        gmt_plus_2 = pytz.timezone('Africa/Johannesburg')
        expires_on = utc_time.astimezone(gmt_plus_2)
        
        # Format for response
        formatted_expiry = expires_on.strftime('%Y-%m-%d %H:%M:%S %z')
        
        # Create the refreshed token record with regenerated_from field
        transaction_id = DatabaseService.log_refreshed_token(
            user_id=user_info["id"],
            token_scope=token_details["token_scope"],
            expires_in=expires_in,
            expires_on=expires_on,
            token_value=new_token,
            regenerated_from=token_details["id"],  # ID of the original token
            regenerated_by=user_info["id"]
        )
        
        if not transaction_id:
            logger.warning("Failed to log refreshed token in database")
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to store refreshed token"
            }, 500)
        
        # Prepare response data
        response_data = {
            "access_token": new_token,
            "token_type": result.get("token_type", "Bearer"),
            "expires_in": expires_in,
            "expires_on": formatted_expiry
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error refreshing token: {str(e)}"
        }, 500)

def register_refresh_token_routes(app):
    """Register refresh token routes with the Flask app"""
    
    from apis.utils.rbacMiddleware import check_endpoint_access

    app.route('/token/refresh', methods=['GET'])(api_logger(check_endpoint_access(refresh_token_route)))