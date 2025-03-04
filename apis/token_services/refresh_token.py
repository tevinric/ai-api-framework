from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
from datetime import datetime, timedelta
import pytz
import uuid

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

# INITIALIZE THE TOKEN SERVICE
token_service = TokenService()

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def refresh_token_route():
    """
    Refresh an existing token using a valid API key.
    ---
    tags:
      - Token Service
    parameters:
      - name: X-API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - token
          properties:
            token:
              type: string
              description: The existing token to refresh
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
              description: Newly generated access token
            token_type:
              type: string
              description: Type of token generated
            expires_in:
              type: integer
              format: int32
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
              example: Missing token in request body
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
              example: Missing API Key header (X-API-Key) or Invalid API Key
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
              example: Token not found in database
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
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (X-API-Key)"
        }, 401)
        
    # Validate API key
    user_info = DatabaseService.validate_api_key(api_key)
    if not user_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = user_info['id']
    
    # Get token from request body
    data = request.get_json()
    if not data or 'token' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token in request body"
        }, 400)
    
    existing_token = data['token']
    
    try:
        # Get token details from database for the old token
        old_token_details = DatabaseService.get_token_details_by_value(existing_token)
        
        if not old_token_details:
            return create_api_response({
                "error": "Not Found",
                "message": "Token not found in database"
            }, 404)
        
        g.token_id = old_token_details["id"]
        
        # Store the original token ID
        original_token_id = old_token_details["id"]
        
        # Generate new token
        new_token_response, status_code = token_service.get_token(user_info)
        if status_code != 200:
            return jsonify(new_token_response), status_code
        
        # Parse the expiration date for the new token
        try:
            # Get the raw expires_on date string
            expires_on_str = new_token_response['expires_on']
            
            # Try to parse with timezone info
            johannesburg_tz = pytz.timezone('Africa/Johannesburg')
            
            # Split the string to separate date/time from timezone info
            datetime_part = expires_on_str.split(' ')[0] + ' ' + expires_on_str.split(' ')[1]
            
            # Parse the datetime part
            expires_on_dt = datetime.strptime(datetime_part, '%Y-%m-%d %H:%M:%S')
            
            # Localize it to Johannesburg timezone
            expires_on = johannesburg_tz.localize(expires_on_dt)
            
        except Exception as date_error:
            logger.error(f"Error parsing expiration date: {str(date_error)}")
            # Fallback: use current time plus expires_in seconds
            expires_on = datetime.now(johannesburg_tz) + timedelta(seconds=new_token_response['expires_in'])
        
        # Get token details for the new token that was just created
        new_token_value = new_token_response['access_token']
        new_token_details = DatabaseService.get_token_details_by_value(new_token_value)
        
        if not new_token_details:
            logger.error("New token not found in database after creation")
            return create_api_response({
                "error": "Server Error",
                "message": "New token not found in database after creation"
            }, 500)
        
        # Get the ID of the new token
        new_token_id = new_token_details["id"]
        
        # Update the old token with the new token's values
        updated = DatabaseService.update_token(
            existing_token=existing_token,
            new_token_value=new_token_value,
            expires_in=new_token_response['expires_in'],
            expires_on=expires_on,
            token_scope=user_info['scope'],
            regenerated_by=user_info['id'],
            regenerated_from=new_token_id  # Old token's regenerated_from points to new token's ID
        )
        
        if not updated:
            logger.error("Failed to update old token in database")
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to update old token in database"
            }, 500)
        
        # Now update the new token to point to the old token ID
        updated_new = DatabaseService.update_token(
            existing_token=new_token_value,
            new_token_value=new_token_value,  # Keep the same token value
            expires_in=new_token_response['expires_in'],
            expires_on=expires_on,
            token_scope=user_info['scope'],
            regenerated_by=user_info['id'],
            regenerated_from=original_token_id  # New token's regenerated_from points to old token's ID
        )
        
        if not updated_new:
            logger.warning("Failed to update new token's regenerated_from field")
        
        return create_api_response(new_token_response, 200)
        
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error refreshing token: {str(e)}"
        }, 500)


def register_refresh_token_routes(app):
    """Register routes with the Flask app"""
    app.route('/refresh-token', methods=['POST'])(api_logger(refresh_token_route))