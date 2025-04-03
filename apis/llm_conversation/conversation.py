from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.utils.balanceService import BalanceService
from apis.utils.config import get_azure_blob_client, ensure_container_exists
import logging
import pytz
import os
import uuid
import json
from datetime import datetime
from apis.utils.llmServices import (
    deepseek_r1_service,
    gpt4o_service,
    gpt4o_mini_service,
    o1_mini_service,
    llama_service
)

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define container for conversation histories
CONVERSATION_CONTAINER = "llm-conversations"
STORAGE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT")
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{CONVERSATION_CONTAINER}"

# Available LLMs and their endpoints (kept for reference)
LLM_ENDPOINTS = {
    "gpt-4o": "/llm/gpt-4o",
    "gpt-4o-mini": "/llm/gpt-4o-mini",
    "o1-mini": "/llm/o1-mini",
    "deepseek-r1": "/llm/deepseek-r1",
    "llama": "/llm/llama"
}

# Map LLM types to their service functions
LLM_SERVICES = {
    "gpt-4o": gpt4o_service,
    "gpt-4o-mini": gpt4o_mini_service,
    "gpt-o1-mini": o1_mini_service,
    "deepseek-r1": deepseek_r1_service,
    "llama": llama_service
}

# Map LLM types to their credit costs
LLM_CREDIT_COSTS = {
    "gpt-4o": 2,
    "gpt-4o-mini": 0.5,
    "gpt-o1-mini": 5,
    "deepseek-r1": 3,
    "llama": 3
}

# Map LLM types to their endpoint IDs for logging
LLM_ENDPOINT_IDS = {}

# Assistant types and their system messages
ASSISTANT_TYPES = {
    "general": "You are a helpful, friendly AI assistant that provides accurate and concise information.",
    "coding": "You are a coding assistant. Provide helpful, accurate code solutions and explanations.",
    "creative": "You are a creative assistant. Help with writing, storytelling, and creative projects.",
    "research": "You are a research assistant. Provide thorough, well-sourced information and analysis.",
    "business": "You are a business assistant. Help with professional communication, strategy, and analysis."
}

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def get_conversation_history(conversation_id):
    """Get conversation history from blob storage"""
    try:
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(CONVERSATION_CONTAINER)
        
        # Get blob client
        blob_client = container_client.get_blob_client(f"{conversation_id}.json")
        
        # Download blob
        blob_data = blob_client.download_blob().readall().decode('utf-8')
        
        # Parse JSON
        conversation = json.loads(blob_data)
        
        return conversation, None
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        return None, str(e)

def save_conversation_history(conversation_id, conversation):
    """Save conversation history to blob storage"""
    try:
        # Ensure container exists
        ensure_container_exists(CONVERSATION_CONTAINER)
        
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(CONVERSATION_CONTAINER)
        
        # Convert conversation to JSON
        conversation_json = json.dumps(conversation, indent=2)
        
        # Upload blob
        blob_client = container_client.get_blob_client(f"{conversation_id}.json")
        blob_client.upload_blob(conversation_json, overwrite=True)
        
        return True, None
    except Exception as e:
        logger.error(f"Error saving conversation history: {str(e)}")
        return False, str(e)

def delete_conversation_history(conversation_id):
    """Delete conversation history from blob storage"""
    try:
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(CONVERSATION_CONTAINER)
        
        # Get blob client
        blob_client = container_client.get_blob_client(f"{conversation_id}.json")
        
        # Delete blob
        blob_client.delete_blob()
        
        return True, None
    except Exception as e:
        logger.error(f"Error deleting conversation history: {str(e)}")
        return False, str(e)

def format_conversation_for_llm(conversation, include_last_n=6):
    """Format conversation history for LLM input"""
    # Get the system message based on assistant type
    assistant_type = conversation.get("assistant_type", "general")
    system_message = ASSISTANT_TYPES.get(assistant_type, ASSISTANT_TYPES["general"])
    
    # Get messages (limited to the last include_last_n)
    messages = conversation.get("messages", [])
    if len(messages) > include_last_n:
        messages = messages[-include_last_n:]
    
    # Format conversation history as text
    chat_history = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        chat_history += f"{role.capitalize()}: {content}\n\n"
    
    # Remove the trailing newlines
    chat_history = chat_history.rstrip()
    
    return {
        "system_prompt": system_message,
        "user_input": chat_history,
        "temperature": conversation.get("temperature", 0.7)
    }

def create_chat_route():
    """
    Create a new LLM conversation
    ---
    tags:
      - LLM Conversational
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
            - llm
            - user_message
          properties:
            llm:
              type: string
              enum: [gpt-4o, gpt-4o-mini, gpt-o1-mini, deepseek-r1, llama]
              description: LLM model to use for conversation
            assistant_type:
              type: string
              enum: [general, coding, creative, research, business]
              default: general
              description: Type of assistant to use
            user_message:
              type: string
              description: Initial message from the user
            temperature:
              type: number
              format: float
              minimum: 0
              maximum: 1
              default: 0.7
              description: Controls randomness (0=focused, 1=creative)
    produces:
      - application/json
    responses:
      200:
        description: Conversation created successfully
        schema:
          type: object
          properties:
            conversation_id:
              type: string
              description: Unique ID for the conversation
            assistant_message:
              type: string
              description: Response from the LLM
            model_used:
              type: string
              description: The LLM model used
            assistant_used:
              type: string
              description: The assistant type used
            input_tokens:
              type: integer
              description: Number of input tokens used
            completion_tokens:
              type: integer
              description: Number of completion tokens used
            output_tokens:
              type: integer
              description: Number of output tokens used
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
              example: Missing required fields or Invalid LLM selection
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
              example: Token has expired
      402:
        description: Payment required
        schema:
          type: object
          properties:
            error:
              type: string
              example: Insufficient Balance
            message:
              type: string
              example: Your API call balance is depleted. Please upgrade your plan for additional calls.
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
              example: Error creating conversation
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
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    if 'llm' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: llm"
        }, 400)
        
    if 'user_message' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: user_message"
        }, 400)
    
    # Extract parameters
    llm = data.get('llm')
    assistant_type = data.get('assistant_type', 'general')
    user_message = data.get('user_message')
    temperature = float(data.get('temperature', 0.7))
    
    # Validate LLM selection
    if llm not in LLM_SERVICES:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Invalid LLM selection. Must be one of: {', '.join(LLM_SERVICES.keys())}"
        }, 400)
    
    # Validate assistant type
    if assistant_type not in ASSISTANT_TYPES:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Invalid assistant type. Must be one of: {', '.join(ASSISTANT_TYPES.keys())}"
        }, 400)
    
    # Create conversation ID
    conversation_id = str(uuid.uuid4())
    
    try:
        # Get system message based on assistant type
        system_message = ASSISTANT_TYPES.get(assistant_type, ASSISTANT_TYPES["general"])
        
        # Get the endpoint ID for the LLM type, cache it if not already cached
        if llm not in LLM_ENDPOINT_IDS:
            endpoint_path = LLM_ENDPOINTS[llm]
            endpoint_id = DatabaseService.get_endpoint_id_by_path(endpoint_path)
            if not endpoint_id:
                logger.error(f"Endpoint not found for {llm} at path {endpoint_path}")
                return create_api_response({
                    "error": "Configuration Error",
                    "message": "Endpoint not configured for balance tracking"
                }, 500)
            LLM_ENDPOINT_IDS[llm] = endpoint_id
        
        # Deduct balance based on LLM credit cost
        endpoint_id = LLM_ENDPOINT_IDS[llm]
        credit_cost = LLM_CREDIT_COSTS.get(llm, 1)  # Default to 1 if not specified
        
        # Check and deduct user balance
        success, result = BalanceService.check_and_deduct_balance(g.user_id, endpoint_id, credit_cost)
        if not success:
            if result == "Insufficient balance":
                logger.warning(f"Insufficient balance for user {g.user_id}")
                return create_api_response({
                    "error": "Insufficient Balance",
                    "message": "Your API call balance is depleted. Please upgrade your plan for additional calls."
                }, 402)  # 402 Payment Required
            
            logger.error(f"Balance error for user {g.user_id}: {result}")
            return create_api_response({
                "error": "Balance Error",
                "message": f"Error processing balance: {result}"
            }, 500)
        
        # Log successful balance deduction
        logger.info(f"Balance successfully deducted for user {g.user_id}, endpoint {endpoint_id}, cost {credit_cost}")
        
        # Use the appropriate service function directly instead of making an API call
        service_function = LLM_SERVICES[llm]
        service_response = service_function(
            system_prompt=system_message,
            user_input=user_message,
            temperature=temperature
        )
        
        if not service_response["success"]:
            logger.error(f"Error from LLM service: {service_response['error']}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error from LLM service: {service_response['error']}"
            }, 500)
        
        # Extract the response data
        assistant_message = service_response["result"]
        
        # Create conversation history
        conversation = {
            "conversation_id": conversation_id,
            "model": llm,
            "assistant_type": assistant_type,
            "temperature": temperature,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message}
            ]
        }
        
        # Save conversation to blob storage
        success, error = save_conversation_history(conversation_id, conversation)
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error saving conversation: {error}"
            }, 500)
        
        # Extract token usage
        input_tokens = service_response.get("input_tokens", 0)
        completion_tokens = service_response.get("completion_tokens", 0)
        output_tokens = service_response.get("output_tokens", 0)
        
        # Create response
        response_data = {
            "conversation_id": conversation_id,
            "assistant_message": assistant_message,
            "model_used": llm,
            "assistant_used": assistant_type,
            "input_tokens": input_tokens,
            "completion_tokens": completion_tokens,
            "output_tokens": output_tokens
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error creating conversation: {str(e)}"
        }, 500)

def continue_conversation_route():
    """
    Continue an existing LLM conversation
    ---
    tags:
      - LLM Conversational
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
            - conversation_id
            - user_message
          properties:
            conversation_id:
              type: string
              description: ID of the conversation to continue
            user_message:
              type: string
              description: Follow-up message from the user
    produces:
      - application/json
    responses:
      200:
        description: Conversation continued successfully
        schema:
          type: object
          properties:
            conversation_id:
              type: string
              description: Unique ID for the conversation
            assistant_message:
              type: string
              description: Response from the LLM
            model_used:
              type: string
              description: The LLM model used
            assistant_used:
              type: string
              description: The assistant type used
            input_tokens:
              type: integer
              description: Number of input tokens used
            completion_tokens:
              type: integer
              description: Number of completion tokens used
            output_tokens:
              type: integer
              description: Number of output tokens used
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
              example: Missing required fields
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
              example: Token has expired
      402:
        description: Payment required
        schema:
          type: object
          properties:
            error:
              type: string
              example: Insufficient Balance
            message:
              type: string
              example: Your API call balance is depleted. Please upgrade your plan for additional calls.
      404:
        description: Not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: Conversation not found
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
              example: Error continuing conversation
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
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    if 'conversation_id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: conversation_id"
        }, 400)
        
    if 'user_message' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: user_message"
        }, 400)
    
    conversation_id = data.get('conversation_id')
    user_message = data.get('user_message')
    
    try:
        # Get conversation history
        conversation, error = get_conversation_history(conversation_id)
        if not conversation:
            return create_api_response({
                "error": "Not Found",
                "message": f"Conversation not found: {error}"
            }, 404)
        
        # Extract model and assistant type
        llm = conversation.get("model")
        assistant_type = conversation.get("assistant_type", "general")
        temperature = conversation.get("temperature", 0.7)
        
        # Add user message to conversation
        conversation["messages"].append({"role": "user", "content": user_message})
        
        # Format conversation for LLM
        llm_request_data = format_conversation_for_llm(conversation)
        
        # Use the appropriate service function directly instead of making an API call
        if llm not in LLM_SERVICES:
            return create_api_response({
                "error": "Server Error",
                "message": f"Invalid LLM type in conversation: {llm}"
            }, 500)
            
        service_function = LLM_SERVICES[llm]
        service_response = service_function(
            system_prompt=llm_request_data["system_prompt"],
            user_input=llm_request_data["user_input"],
            temperature=temperature
        )
        
        if not service_response["success"]:
            logger.error(f"Error from LLM service: {service_response['error']}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error from LLM service: {service_response['error']}"
            }, 500)
        
        # Extract the response data
        assistant_message = service_response["result"]
        
        # Add assistant message to conversation
        conversation["messages"].append({"role": "assistant", "content": assistant_message})
        
        # Update timestamp
        conversation["updated_at"] = datetime.now().isoformat()
        
        # Save updated conversation
        success, error = save_conversation_history(conversation_id, conversation)
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error saving conversation: {error}"
            }, 500)
        
        # Extract token usage
        input_tokens = service_response.get("input_tokens", 0)
        completion_tokens = service_response.get("completion_tokens", 0)
        output_tokens = service_response.get("output_tokens", 0)
        
        # Create response
        response_data = {
            "conversation_id": conversation_id,
            "assistant_message": assistant_message,
            "model_used": llm,
            "assistant_used": assistant_type,
            "input_tokens": input_tokens,
            "completion_tokens": completion_tokens,
            "output_tokens": output_tokens
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error continuing conversation: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error continuing conversation: {str(e)}"
        }, 500)

def delete_conversation_route():
    """
    Delete an LLM conversation
    ---
    tags:
      - LLM Conversational
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: conversation_id
        in: query
        type: string
        required: true
        description: ID of the conversation to delete
    produces:
      - application/json
    responses:
      200:
        description: Conversation deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Conversation deleted successfully
            conversation_id:
              type: string
              description: ID of the deleted conversation
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
              example: Missing conversation_id parameter
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
              example: Token has expired
      404:
        description: Not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: Conversation not found
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
              example: Error deleting conversation
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
    
    # Get conversation ID from query parameter
    conversation_id = request.args.get('conversation_id')
    if not conversation_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required parameter: conversation_id"
        }, 400)
    
    try:
        # Delete conversation
        success, error = delete_conversation_history(conversation_id)
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error deleting conversation: {error}"
            }, 500)
        
        return create_api_response({
            "message": "Conversation deleted successfully",
            "conversation_id": conversation_id
        }, 200)
        
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error deleting conversation: {str(e)}"
        }, 500)

def register_llm_conversation_routes(app):
    """Register LLM conversation routes with the Flask app"""
    # We handle balance checking inside the route functions now, but keep the api_logger
    app.route('/llm/conversation/chat', methods=['POST'])(api_logger(create_chat_route))
    app.route('/llm/conversation/continue', methods=['POST'])(api_logger(continue_conversation_route))
    app.route('/llm/conversation', methods=['DELETE'])(api_logger(delete_conversation_route))
