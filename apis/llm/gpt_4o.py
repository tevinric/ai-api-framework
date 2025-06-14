# apis/llm/gpt_4o.py
from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
import pytz
from datetime import datetime
from apis.utils.llmServices import gpt4o_service, gpt4o_multimodal_service  # Import the multimodal service function
from apis.utils.fileService import FileService
import os
import tempfile
import base64

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Allowed image file extensions and MIME types
ALLOWED_IMAGE_EXTENSIONS = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg'
}

from apis.utils.config import create_api_response
# Remove the balance check decorator from here - we'll apply it in the registration
def gpt4o_route():
    """
    Consumes 2 AI credits per call
    
    OpenAI GPT-4o LLM model for text completion and content generation.
    Supports multimodal input with image file references for enhanced visual analysis.
    
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
              default: 0.5
              description: Controls randomness (0=focused, 1=creative)
            json_output:
              type: boolean
              default: false
              description: When true, the model will return a structured JSON response
            file_ids:
              type: array
              items:
                type: string
              description: Array of image file IDs to process with the model (supports PNG, JPG, JPEG only)
            context_id:
              type: string
              description: ID of a context file to use as an enhanced system prompt (optional)
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
              example: "gpt-4o"
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
            files_processed:
              type: integer
              example: 1
              description: Number of image files processed in the request
            file_processing_details:
              type: object
              properties:
                images_processed:
                  type: integer
                  example: 1
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
    file_ids = data.get('file_ids', [])
    context_id = data.get('context_id')  # New parameter for context_id
    
    # Validate temperature range
    if not (0 <= temperature <= 1):
        return create_api_response({
            "response": "400",
            "message": "Temperature must be between 0 and 1"
        }, 400)
    
    try:
        # Log API usage
        logger.info(f"GPT-4o API called by user: {user_id}")
        
        # Apply context if provided
        if context_id:
            from apis.llm.context_integration import apply_context_to_system_prompt
            enhanced_system_prompt, error = apply_context_to_system_prompt(system_prompt, context_id, g.user_id)
            if error:
                logger.warning(f"Error applying context {context_id}: {error}")
                # Continue with original system prompt but log the issue
                enhanced_system_prompt = system_prompt
        else:
            enhanced_system_prompt = system_prompt
        
        # Check if this is a multimodal request with file_ids
        if file_ids and isinstance(file_ids, list) and len(file_ids) > 0:
            logger.info(f"Multimodal request with {len(file_ids)} files")
            
            # Check for too many files to prevent context overflow
            if len(file_ids) > 20:  # Reasonable limit for GPT-4o
                return create_api_response({
                    "response": "400",
                    "message": "Too many files. GPT-4o can process a maximum of 20 image files per request."
                }, 400)
            
            # Use the multimodal service function with enhanced system prompt
            service_response = gpt4o_multimodal_service(
                system_prompt=enhanced_system_prompt,  # Use enhanced prompt with context
                user_input=user_input,
                temperature=temperature,
                json_output=json_output,
                file_ids=file_ids,
                user_id=user_id
            )
        else:
            # Use the standard service function for text-only requests with enhanced system prompt
            service_response = gpt4o_service(
                system_prompt=enhanced_system_prompt,  # Use enhanced prompt with context
                user_input=user_input,
                temperature=temperature,
                json_output=json_output
            )
        
        if not service_response["success"]:
            logger.error(f"GPT-4o API error: {service_response['error']}")
            status_code = 500 if not str(service_response["error"]).startswith("4") else 400
            return create_api_response({
                "response": str(status_code),
                "message": service_response["error"]
            }, status_code)
        
        # Prepare successful response with user details
        response_data = {
            "response": "200",
            "message": service_response["result"],
            "user_id": user_details["id"],
            "user_name": user_details["user_name"],
            "user_email": user_details["user_email"],
            "model": service_response["model"],
            "prompt_tokens": service_response["prompt_tokens"],
            "completion_tokens": service_response["completion_tokens"],
            "total_tokens": service_response["total_tokens"],
            "cached_tokens": service_response.get("cached_tokens", 0)
        }
        
        # Include file processing details if present
        if "files_processed" in service_response:
            response_data["files_processed"] = service_response["files_processed"]
        
        if "file_processing_details" in service_response:
            response_data["file_processing_details"] = service_response["file_processing_details"]
        
        # Include context usage info if context was used
        if context_id:
            response_data["context_used"] = context_id
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"GPT-4o API error: {str(e)}")
        status_code = 500 if not str(e).startswith("4") else 400
        return create_api_response({
            "response": str(status_code),
            "message": str(e)
        }, status_code)

def register_llm_gpt_4o(app):
    """Register routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    app.route('/llm/gpt-4o', methods=['POST'])(track_usage(api_logger(check_endpoint_access(check_balance(gpt4o_route)))))
