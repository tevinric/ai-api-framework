from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
import pytz
from datetime import datetime
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from apis.utils.config import DEEPSEEK_API_KEY

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fixed deployment endpoint
ENDPOINT = 'https://deepseek-r1-aiapi.eastus.models.ai.azure.com'

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

# Remove the balance check decorator from here - we'll apply it in the registration
def deepseek_r1_route():
    """
    Consumes 3 AI credits per call
    
    DeepSeek-R1 LLM model for text generation on complex tasks that required chain of though and deep reasoning.

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
            temperature:
              type: number
              format: float
              minimum: 0
              maximum: 1
              default: 0.5
              description: Controls randomness (0=focused, 1=creative)

            max_tokens:
              type: integer
              default: 2048
              description: Maximum number of tokens to generate
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
              example: "deepseek-r1-aiapi"
            input_tokens:
              type: integer
              example: 125
            completion_tokens:
              type: integer
              example: 84
            output_tokens:
              type: integer
              example: 209
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
    max_tokens = int(data.get('max_tokens', 2048))
    
    # Validate temperature range
    if not (0 <= temperature <= 1):
        return create_api_response({
            "response": "400",
            "message": "Temperature must be between 0 and 1"
        }, 400)
    
    try:
        # Log API usage
        logger.info(f"DeepSeek-R1 API called by user: {user_id}")
        
        # Get Azure Inference API key
        api_key = DEEPSEEK_API_KEY
        if not api_key:
            raise Exception("Azure Inference API key not found")
        
        # Initialize Azure Inference client exactly as in the sample code
        client = ChatCompletionsClient(
            endpoint=ENDPOINT,
            credential=AzureKeyCredential(api_key)
        )
        
        # Prepare messages for the model
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user message
        messages.append({"role": "user", "content": user_input})
        
        # Prepare payload exactly as in the sample code
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        # Add response format if JSON output is requested
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        
        # Make request to LLM using the client's complete method
        response = client.complete(payload)
        
        # Extract response data from the response object
        result = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        output_tokens = response.usage.total_tokens
        model_name = response.model if hasattr(response, 'model') else "deepseek-r1-aiapi"
        
        # Prepare successful response with user details
        return create_api_response({
            "response": "200",
            "message": result,
            "user_id": user_details["id"],
            "user_name": user_details["user_name"],
            "user_email": user_details["user_email"],
            "model": model_name,
            "input_tokens": input_tokens,
            "completion_tokens": completion_tokens,
            "output_tokens": output_tokens
        }, 200)
        
    except Exception as e:
        logger.error(f"DeepSeek-R1 API error: {str(e)}")
        status_code = 500 if not str(e).startswith("4") else 400
        return create_api_response({
            "response": str(status_code),
            "message": str(e)
        }, status_code)

def register_llm_deepseek_r1(app):
    """Register routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    
    app.route('/llm/deepseek-r1', methods=['POST'])(api_logger(check_balance(deepseek_r1_route)))