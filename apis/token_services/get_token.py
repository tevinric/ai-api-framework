from flask import jsonify, request,  g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
from apis.utils.logMiddleware import api_logger

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

# INITIALIZE THE TOKEN SERVICE
token_service = TokenService()

def create_api_response(data, status_code=200):
  """Helper function to create consistent API responses"""
  response = make_response(jsonify(data))
  response.status_code = status_code
  return response
  

def get_token_route():
    """
    Generate a token for API access using a valid api authentication key.
    ---
    tags:
      - Token Service
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
    responses:
      200:
        description: Token generated successfully
        schema:
          type: object
          properties:
            access_token:
              type: string
              description: generated access token to use with api calls
            expires_in:
              type: integer
              format: seconds
              description: Time in seconds until token expiration
            expires_on:
              type: string
              format: date-time
              description: Token expiration timestamp
            token_type:
              type: string
              description: Type of token generated
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
              example: Error generating token
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
    
    
    try:
        #GET TOKEN WITH USER INFO FOR LOGGING
        response_data, status_code = token_service.get_token(user_info)
        
        # RETURN TEH RESPONSE USING THE HELPER FUNCTION
        return create_api_response(response_data, status_code)
      
    except Exception as e:
        logger.error(f"Error generating token: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": "Error generating token"
        }, 500)
  
    # Get token with user info for logging
    #response, status_code = token_service.get_token(user_info)
    #return jsonify(response), status_code

def register_routes(app):
    """Register routes with the Flask app"""
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    app.route('/token', methods=['GET'])(api_logger(check_endpoint_access(get_token_route)))