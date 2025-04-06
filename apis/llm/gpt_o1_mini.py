from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
import pytz
from datetime import datetime
from apis.utils.llmServices import o1_mini_service  # Import the service function

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def o1_mini_route():
    """
    Consumes 5 AI credits per call
    
    OpenAI LLM model for text generation on complex tasks that required chain of though and deep reasoning.
    ---
    tags:
      - LLM
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
            - user_input
          properties:
            system_prompt:
              type: string
              description: System prompt to control model behavior
              default: "You are a helpful AI assistant"
            user_input:
              type: string
              description: Text for the model to process
    produces:
      - application/json
    responses:
      200:
        description: Successful model response
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            message:
              type: string
              example: "I'll help you with that question. Based on the information provided..."
            user_id:
              type: string
              example: "user123"
            user_name:
              type: string
              example: "John Doe"
            user_email:
              type: string
              example: "john.doe@example.com"
            model:
              type: string
              example: "o1-mini"
            input_tokens:
              type: integer
              example: 125
            completion_tokens:
              type: integer
              example: 84
            output_tokens:
              type: integer
              example: 209
            cached_tokens:
              type: integer
              example: 0
      400:
        description: Bad request
        schema:
          type: object
          properties:
            response:
              type: string
              example: "400"
            message:
              type: string
              example: "Missing required fields: user_input"
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
            response:
              type: string
              example: "500"
            message:
              type: string
              example: "Internal server error occurred during API request"
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
    g.user_id = token_details["user_id"]  # This is critical for the balance middleware
    
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
    
    # Validate token with Microsoft Graph
    is_valid = TokenService.validate_token(token)
    if not is_valid:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token is no longer valid with provider"
        }, 401)
        
    # Get user details
    user_id = token_details["user_id"]
    user_details = DatabaseService.get_user_by_id(user_id)
    if not user_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "User associated with token not found"
        }, 401)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "response": "400",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['user_input']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "response": "400",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Extract parameters with defaults
    system_prompt = data.get('system_prompt', 'You are a helpful AI assistant')
    user_input = data.get('user_input', '')
    temperature = float(data.get('temperature', 0.5))
    json_output = data.get('json_output', False)
    
    # Validate temperature range
    if not (0 <= temperature <= 1):
        return create_api_response({
            "response": "400",
            "message": "Temperature must be between 0 and 1"
        }, 400)
    
    try:
        # Log API usage
        logger.info(f"O1-mini API called by user: {user_id}")
        
        # Use the service function instead of direct API call
        service_response = o1_mini_service(
            system_prompt=system_prompt,
            user_input=user_input,
            temperature=temperature,
            json_output=json_output
        )
        
        if not service_response["success"]:
            logger.error(f"O1-mini API error: {service_response['error']}")
            status_code = 500 if not str(service_response["error"]).startswith("4") else 400
            return create_api_response({
                "response": str(status_code),
                "message": service_response["error"]
            }, status_code)
        
        # Prepare successful response with user details
        return create_api_response({
            "response": "200",
            "message": service_response["result"],
            "user_id": user_details["id"],
            "user_name": user_details["user_name"],
            "user_email": user_details["user_email"],
            "model": service_response["model"],
            "input_tokens": service_response["input_tokens"],
            "completion_tokens": service_response["completion_tokens"],
            "output_tokens": service_response["output_tokens"],
            "cached_tokens": service_response.get("cached_tokens")
        }, 200)
        
    except Exception as e:
        logger.error(f"O1-mini API error: {str(e)}")
        status_code = 500 if not str(e).startswith("4") else 400
        return create_api_response({
            "response": str(status_code),
            "message": str(e)
        }, status_code)

def register_llm_o1_mini(app):
    """Register routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    
    app.route('/llm/o1-mini', methods=['POST'])(api_logger(check_balance(o1_mini_route)))
