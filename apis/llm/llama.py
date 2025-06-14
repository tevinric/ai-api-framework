from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
import pytz
from datetime import datetime
from apis.utils.llmServices import llama_service  # Import the service function

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from apis.utils.config import create_api_response

def llama_route():
    """
    Consumes 3 AI credits per call
    
    Meta Llama 405B parameter LLM model for text generation and general task completion.
    
    ---
    tags:
      - LLM
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
            temperature:
              type: number
              format: float
              minimum: 0
              maximum: 1
              default: 0.8
              description: Controls randomness (0=focused, 1=creative)
            max_tokens:
              type: integer
              default: 2048
              description: Maximum number of tokens to generate
            top_p:
              type: number
              format: float
              minimum: 0.1
              maximum: 1
              default: 0.1
              description: Controls diversity via nucleus sampling
            json_output:
              type: boolean
              default: false
              description: Whether to return the response in JSON format
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
              example: "llama-3-1-405b"
            prompt_tokens:
              type: integer
              example: 125
              description: Number of tokens pass in the prompt
            completion_tokens:
              type: integer
              example: 84
              description: Number of tokens generated by the llm
            total_tokens:
              type: integer
              example: 209
              description: Total number of tokens used
            cached_tokens:
              type: integer
              example: 0
              description: Number of cached tokens (if supported by model)  
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
    temperature = float(data.get('temperature', 0.8))
    json_output = data.get('json_output', False)
    max_tokens = int(data.get('max_tokens', 2048))
    top_p = float(data.get('top_p', 0.1))
    presence_penalty = float(data.get('presence_penalty', 0))
    frequency_penalty = float(data.get('frequency_penalty', 0))
    
    # Validate temperature range
    if not (0 <= temperature <= 1):
        return create_api_response({
            "response": "400",
            "message": "Temperature must be between 0 and 1"
        }, 400)
    
    # Validate top_p range
    if not (0 <= top_p <= 1):
        return create_api_response({
            "response": "400",
            "message": "top_p must be between 0 and 1"
        }, 400)
    
    # Validate presence_penalty range
    if not (-2 <= presence_penalty <= 2):
        return create_api_response({
            "response": "400",
            "message": "presence_penalty must be between -2 and 2"
        }, 400)
    
    # Validate frequency_penalty range
    if not (-2 <= frequency_penalty <= 2):
        return create_api_response({
            "response": "400",
            "message": "frequency_penalty must be between -2 and 2"
        }, 400)
    
    try:
        # Log API usage
        logger.info(f"Llama API called by user: {user_id}")
        
        # Use the service function instead of direct API call
        service_response = llama_service(
            system_prompt=system_prompt,
            user_input=user_input,
            temperature=temperature,
            json_output=json_output,
            max_tokens=max_tokens,
            top_p=top_p,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty
        )
        
        if not service_response["success"]:
            logger.error(f"Llama API error: {service_response['error']}")
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
            "model": "llama-3-1-405b",
            "prompt_tokens": service_response["prompt_tokens"],
            "completion_tokens": service_response["completion_tokens"],
            "total_tokens": service_response["total_tokens"],
            "cached_tokens": service_response.get("cached_tokens", 0)
        }, 200)
        
    except Exception as e:
        logger.error(f"Llama API error: {str(e)}")
        status_code = 500 if not str(e).startswith("4") else 400
        return create_api_response({
            "response": str(status_code),
            "message": str(e)
        }, status_code)

def register_llm_llama(app):
    """Register routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    app.route('/llm/llama', methods=['POST'])(track_usage(api_logger(check_endpoint_access(check_balance(llama_route)))))
