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
    deepseek_v3_service,
    gpt4o_service,
    gpt4o_mini_service,
    o1_mini_service,
    llama_service,
    gpt41_service,
    gpt41_mini_service,
    o3_mini_service,
    llama_3_2_vision_instruct_service,
    llama_4_maverick_17b_128E_instruct_fp8_service,
    llama_4_scout_17b_16E_instruct_service,
    mistral_medium_2505_service,
    mistral_nemo_service
)

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define container for conversation histories
CONVERSATION_CONTAINER = "llm-conversations"
STORAGE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT")
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{CONVERSATION_CONTAINER}"

# Map LLM types to their service functions
LLM_SERVICES = {
    "gpt-4o": gpt4o_service,
    "gpt-4o-mini": gpt4o_mini_service,
    "gpt-4.1": gpt41_service,
    "gpt-4.1-mini": gpt41_mini_service,
    "o1-mini": o1_mini_service,
    "o3-mini": o3_mini_service,
    "deepseek-r1": deepseek_r1_service,
    "deepseek-v3": deepseek_v3_service,
    "llama-3-1-405b": llama_service,
    "llama-3.2-vision-instruct": llama_3_2_vision_instruct_service,
    "llama-4-maverick-17b-128e": llama_4_maverick_17b_128E_instruct_fp8_service,
    "llama-4-scout-17b-16e": llama_4_scout_17b_16E_instruct_service,
    "mistral-medium-2505": mistral_medium_2505_service,
    "mistral-nemo": mistral_nemo_service
}

# Map LLM types to their credit costs
LLM_CREDIT_COSTS = {
    "gpt-4o": 2,
    "gpt-4o-mini": 0.5,
    "gpt-4.1": 3,
    "gpt-4.1-mini": 1,
    "o1-mini": 5,
    "o3-mini": 3,
    "deepseek-r1": 3,
    "deepseek-v3": 1.5,
    "llama-3-1-405b": 3,
    "llama-3.2-vision-instruct": 2,
    "llama-4-maverick-17b-128e": 4,
    "llama-4-scout-17b-16e": 4,
    "mistral-medium-2505": 2.5,
    "mistral-nemo": 1
}

# Model-specific parameter configurations
MODEL_PARAMETER_CONFIGS = {
    "gpt-4o": {
        "supports_temperature": True,
        "supports_json_output": True,
        "supports_multimodal": True,
        "supports_max_tokens": False,
        "supports_top_p": False,
        "supports_penalties": False,
        "default_temperature": 0.5
    },
    "gpt-4o-mini": {
        "supports_temperature": True,
        "supports_json_output": True,
        "supports_multimodal": True,
        "supports_max_tokens": False,
        "supports_top_p": False,
        "supports_penalties": False,
        "default_temperature": 0.5
    },
    "gpt-4.1": {
        "supports_temperature": True,
        "supports_json_output": True,
        "supports_multimodal": True,
        "supports_max_tokens": False,
        "supports_top_p": False,
        "supports_penalties": False,
        "default_temperature": 0.5
    },
    "gpt-4.1-mini": {
        "supports_temperature": True,
        "supports_json_output": True,
        "supports_multimodal": True,
        "supports_max_tokens": False,
        "supports_top_p": False,
        "supports_penalties": False,
        "default_temperature": 0.5
    },
    "o1-mini": {
        "supports_temperature": True,
        "supports_json_output": True,
        "supports_multimodal": False,
        "supports_max_tokens": False,
        "supports_top_p": False,
        "supports_penalties": False,
        "default_temperature": 0.5
    },
    "o3-mini": {
        "supports_temperature": False,  # O3-mini doesn't support temperature
        "supports_json_output": True,
        "supports_multimodal": False,
        "supports_max_tokens": False,  # Changed from True to False
        "supports_top_p": False,
        "supports_penalties": False,
        "supports_reasoning_effort": True,
        "supports_max_completion_tokens": True,
        "default_max_completion_tokens": 4000,
        "default_reasoning_effort": "medium"
    },
    "deepseek-r1": {
        "supports_temperature": True,
        "supports_json_output": True,
        "supports_multimodal": False,
        "supports_max_tokens": True,
        "supports_top_p": False,
        "supports_penalties": False,
        "default_temperature": 0.5,
        "default_max_tokens": 2048
    },
    "deepseek-v3": {
        "supports_temperature": True,
        "supports_json_output": True,
        "supports_multimodal": False,
        "supports_max_tokens": True,
        "supports_top_p": False,
        "supports_penalties": False,
        "default_temperature": 0.7,
        "default_max_tokens": 1000
    },
    "llama-3-1-405b": {
        "supports_temperature": True,
        "supports_json_output": True,
        "supports_multimodal": False,
        "supports_max_tokens": True,
        "supports_top_p": True,
        "supports_penalties": True,
        "default_temperature": 0.7,
        "default_max_tokens": 2048,
        "default_top_p": 0.1,
        "default_presence_penalty": 0,
        "default_frequency_penalty": 0
    },
    "llama-3.2-vision-instruct": {
        "supports_temperature": True,
        "supports_json_output": False,
        "supports_multimodal": True,
        "supports_max_tokens": True,
        "supports_top_p": False,
        "supports_penalties": False,
        "default_temperature": 0.7,
        "default_max_tokens": 2048
    },
    "llama-4-maverick-17b-128e": {
        "supports_temperature": True,
        "supports_json_output": False,
        "supports_multimodal": True,
        "supports_max_tokens": True,
        "supports_top_p": False,
        "supports_penalties": False,
        "default_temperature": 0.7,
        "default_max_tokens": 2048
    },
    "llama-4-scout-17b-16e": {
        "supports_temperature": True,
        "supports_json_output": False,
        "supports_multimodal": True,
        "supports_max_tokens": True,
        "supports_top_p": False,
        "supports_penalties": False,
        "default_temperature": 0.7,
        "default_max_tokens": 2048
    },
    "mistral-medium-2505": {
        "supports_temperature": True,
        "supports_json_output": True,
        "supports_multimodal": True,
        "supports_max_tokens": True,
        "supports_top_p": True,
        "supports_penalties": False,
        "default_temperature": 0.8,
        "default_max_tokens": 2048,
        "default_top_p": 0.1
    },
    "mistral-nemo": {
        "supports_temperature": True,
        "supports_json_output": False,
        "supports_multimodal": False,
        "supports_max_tokens": True,
        "supports_top_p": True,
        "supports_penalties": True,
        "default_temperature": 0.7,
        "default_max_tokens": 2048,
        "default_top_p": 0.1,
        "default_presence_penalty": 0,
        "default_frequency_penalty": 0
    }
}

# Assistant types and their system messages
ASSISTANT_TYPES = {
    "general": "You are a helpful, friendly AI assistant that provides accurate and concise information.",
    "coding": "You are a coding assistant. Provide helpful, accurate code solutions and explanations.",
    "creative": "You are a creative assistant. Help with writing, storytelling, and creative projects.",
    "research": "You are a research assistant. Provide thorough, well-sourced information and analysis.",
    "business": "You are a business assistant. Help with professional communication, strategy, and analysis."
}

from apis.utils.config import create_api_response

def get_conversation_history(conversation_id):
    """Get conversation history from blob storage"""
    try:
        # Get blob client
        blob_client = get_azure_blob_client()
        
        # Ensure container exists
        ensure_container_exists(CONVERSATION_CONTAINER)
        
        # Get the blob
        blob_name = f"{conversation_id}.json"
        blob_client_instance = blob_client.get_blob_client(
            container=CONVERSATION_CONTAINER, 
            blob=blob_name
        )
        
        # Download and parse the conversation
        blob_data = blob_client_instance.download_blob().readall()
        conversation = json.loads(blob_data.decode('utf-8'))
        
        return conversation, None
        
    except Exception as e:
        logger.error(f"Error retrieving conversation {conversation_id}: {str(e)}")
        return None, str(e)

def save_conversation_history(conversation_id, conversation):
    """Save conversation history to blob storage"""
    try:
        # Get blob client
        blob_client = get_azure_blob_client()
        
        # Ensure container exists
        ensure_container_exists(CONVERSATION_CONTAINER)
        
        # Upload the conversation
        blob_name = f"{conversation_id}.json"
        blob_client_instance = blob_client.get_blob_client(
            container=CONVERSATION_CONTAINER, 
            blob=blob_name
        )
        
        conversation_json = json.dumps(conversation, indent=2)
        blob_client_instance.upload_blob(conversation_json, overwrite=True)
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error saving conversation {conversation_id}: {str(e)}")
        return False, str(e)

def delete_conversation_history(conversation_id):
    """Delete conversation history from blob storage"""
    try:
        # Get blob client
        blob_client = get_azure_blob_client()
        
        # Delete the blob
        blob_name = f"{conversation_id}.json"
        blob_client_instance = blob_client.get_blob_client(
            container=CONVERSATION_CONTAINER, 
            blob=blob_name
        )
        
        blob_client_instance.delete_blob()
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
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
        "model_config": conversation.get("model_config", {})
    }

def apply_context_to_system_prompt_if_provided(system_prompt, context_id, user_id):
    """Apply context to system prompt if context_id is provided"""
    if context_id:
        try:
            from apis.llm.context_integration import apply_context_to_system_prompt
            enhanced_system_prompt, error = apply_context_to_system_prompt(system_prompt, context_id, user_id)
            if error:
                logger.warning(f"Error applying context {context_id}: {error}")
                # Continue with original system prompt but log the issue
                return system_prompt, None
            else:
                logger.info(f"Successfully applied context {context_id}")
                return enhanced_system_prompt, context_id
        except Exception as e:
            logger.error(f"Exception applying context {context_id}: {str(e)}")
            return system_prompt, None
    else:
        return system_prompt, None

def build_service_parameters(llm, enhanced_system_prompt, user_input, file_ids=None, user_id=None):
    """Build service parameters based on model configuration"""
    config = MODEL_PARAMETER_CONFIGS.get(llm, {})
    
    # Base parameters that all models support
    service_params = {
        "system_prompt": enhanced_system_prompt,
        "user_input": user_input
    }
    
    # Add temperature if supported
    if config.get("supports_temperature", False):
        service_params["temperature"] = config.get("default_temperature", 0.7)
    
    # Add JSON output if supported
    if config.get("supports_json_output", False):
        service_params["json_output"] = False  # Default to False for conversations
    
    # Add multimodal support if supported
    if config.get("supports_multimodal", False):
        service_params["file_ids"] = file_ids
        service_params["user_id"] = user_id
    
    # Add max_tokens if supported
    if config.get("supports_max_tokens", False):
        service_params["max_tokens"] = config.get("default_max_tokens", 2048)
    
    # Add top_p if supported
    if config.get("supports_top_p", False):
        service_params["top_p"] = config.get("default_top_p", 0.1)
    
    # Add penalties if supported
    if config.get("supports_penalties", False):
        service_params["presence_penalty"] = config.get("default_presence_penalty", 0)
        service_params["frequency_penalty"] = config.get("default_frequency_penalty", 0)
    
    # Special parameters for O3-mini
    if config.get("supports_reasoning_effort", False):
        service_params["reasoning_effort"] = config.get("default_reasoning_effort", "medium")
    
    if config.get("supports_max_completion_tokens", False):
        service_params["max_completion_tokens"] = config.get("default_max_completion_tokens", 4000)
    
    return service_params

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
            - llm
            - user_message
          properties:
            llm:
              type: string
              enum: [gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, o1-mini, o3-mini, deepseek-r1, deepseek-v3, llama-3-1-405b, llama-3.2-vision-instruct, llama-4-maverick-17b-128e, llama-4-scout-17b-16e, mistral-medium-2505, mistral-nemo]
              description: LLM model to use for conversation
            assistant_type:
              type: string
              enum: [general, coding, creative, research, business]
              default: general
              description: Type of assistant to use
            user_message:
              type: string
              description: Initial message from the user
            context_id:
              type: string
              description: ID of a context file to use as additional knowledge (optional)
            file_ids:
              type: array
              items:
                type: string
              description: Array of file IDs for multimodal models (optional)
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
            prompt_tokens:
              type: integer
              description: Number of prompt tokens used
            completion_tokens:
              type: integer
              description: Number of completion tokens used
            total_tokens:
              type: integer
              description: Total number of tokens used
            cached_tokens:
              type: integer
              description: Number of cached tokens used
            context_used:
              type: string
              description: Context ID that was used (if any)
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Bad Request"
            message:
              type: string
              example: "Missing required fields or Invalid LLM selection"
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
      402:
        description: Payment required
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Insufficient Balance"
            message:
              type: string
              example: "Your API call balance is depleted. Please upgrade your plan for additional calls."
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Server Error"
            message:
              type: string
              example: "Error creating conversation"
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
    context_id = data.get('context_id')  # New parameter for context_id
    file_ids = data.get('file_ids')  # New parameter for multimodal support
    
    # Validate and clean context_id - treat empty strings as None
    if context_id and isinstance(context_id, str):
        context_id = context_id.strip()
        if not context_id:  # Empty string after stripping
            context_id = None
    else:
        context_id = None
    
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
        
        # Apply context if provided
        enhanced_system_message, context_used = apply_context_to_system_prompt_if_provided(
            system_message, context_id, g.user_id
        )
        
        # Deduct balance based on LLM credit cost (simplified without endpoint lookup)
        credit_cost = LLM_CREDIT_COSTS.get(llm, 1)  # Default to 1 if not specified
        
        # Use the appropriate service function with model-specific parameters
        service_function = LLM_SERVICES[llm]
        
        # Build service parameters based on model configuration
        service_params = build_service_parameters(
            llm, enhanced_system_message, user_message, file_ids, g.user_id
        )
        
        # Call the service function
        service_response = service_function(**service_params)
        
        if not service_response["success"]:
            logger.error(f"Error from LLM service: {service_response['error']}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error from LLM service: {service_response['error']}"
            }, 500)
        
        # Extract the response data
        assistant_message = service_response["result"]
        
        # Get model configuration for storage
        model_config = MODEL_PARAMETER_CONFIGS.get(llm, {})
        
        # Create conversation history
        conversation = {
            "conversation_id": conversation_id,
            "model": llm,
            "assistant_type": assistant_type,
            "model_config": model_config,
            "context_id": context_id,  # Store context_id in conversation
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
        prompt_tokens = service_response.get("prompt_tokens", 0)
        completion_tokens = service_response.get("completion_tokens", 0)
        total_tokens = service_response.get("total_tokens", 0)
        cached_tokens = service_response.get("cached_tokens", 0)
        
        # Create response
        response_data = {
            "conversation_id": conversation_id,
            "assistant_message": assistant_message,
            "model_used": llm,
            "assistant_used": assistant_type,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
        # Include context usage info
        if context_used:
            response_data["context_used"] = context_used
        
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
            - conversation_id
            - user_message
          properties:
            conversation_id:
              type: string
              description: ID of the conversation to continue
            user_message:
              type: string
              description: Follow-up message from the user
            file_ids:
              type: array
              items:
                type: string
              description: Array of file IDs for multimodal models (optional)
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
            prompt_tokens:
              type: integer
              description: Number of prompt tokens used
            completion_tokens:
              type: integer
              description: Number of completion tokens used
            total_tokens:
              type: integer
              description: Total number of tokens used
            cached_tokens:
              type: integer
              description: Number of cached tokens used
            context_used:
              type: string
              description: Context ID that was used (if any)
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Bad Request"
            message:
              type: string
              example: "Missing required fields"
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
      404:
        description: Not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Not Found"
            message:
              type: string
              example: "Conversation not found"
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Server Error"
            message:
              type: string
              example: "Error continuing conversation"
    """
    # Authentication and validation (same as create_chat_route)
    token = request.headers.get('X-Token')
    if not token:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing X-Token header"
        }, 401)
    
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token - not found in database"
        }, 401)
    
    g.token_id = token_details["id"]
    g.user_id = token_details["user_id"]
    
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
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
    file_ids = data.get('file_ids')
    
    try:
        conversation, error = get_conversation_history(conversation_id)
        if not conversation:
            return create_api_response({
                "error": "Not Found",
                "message": f"Conversation not found: {error}"
            }, 404)
        
        llm = conversation.get("model")
        assistant_type = conversation.get("assistant_type", "general")
        context_id = conversation.get("context_id")
        
        conversation["messages"].append({"role": "user", "content": user_message})
        
        llm_request_data = format_conversation_for_llm(conversation)
        
        enhanced_system_prompt, context_used = apply_context_to_system_prompt_if_provided(
            llm_request_data["system_prompt"], context_id, g.user_id
        )
        
        if llm not in LLM_SERVICES:
            return create_api_response({
                "error": "Server Error",
                "message": f"Invalid LLM type in conversation: {llm}"
            }, 500)
        
        service_function = LLM_SERVICES[llm]
        
        # Build service parameters using the same function as create_chat
        service_params = build_service_parameters(
            llm, enhanced_system_prompt, llm_request_data["user_input"], file_ids, g.user_id
        )
        
        service_response = service_function(**service_params)
        
        if not service_response["success"]:
            logger.error(f"Error from LLM service: {service_response['error']}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error from LLM service: {service_response['error']}"
            }, 500)
        
        assistant_message = service_response["result"]
        
        conversation["messages"].append({"role": "assistant", "content": assistant_message})
        conversation["updated_at"] = datetime.now().isoformat()
        
        success, error = save_conversation_history(conversation_id, conversation)
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error saving conversation: {error}"
            }, 500)
        
        prompt_tokens = service_response.get("prompt_tokens", 0)
        completion_tokens = service_response.get("completion_tokens", 0)
        total_tokens = service_response.get("total_tokens", 0)
        cached_tokens = service_response.get("cached_tokens", 0)
        
        response_data = {
            "conversation_id": conversation_id,
            "assistant_message": assistant_message,
            "model_used": llm,
            "assistant_used": assistant_type,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
        if context_used:
            response_data["context_used"] = context_used
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error continuing conversation: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error continuing conversation: {str(e)}"
        }, 500)

def delete_conversation_route():
    """
    Delete an existing LLM conversation
    ---
    tags:
      - LLM Conversational
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
              description: Success message
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Bad Request"
            message:
              type: string
              example: "Missing required parameter: conversation_id"
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
      404:
        description: Not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Not Found"
            message:
              type: string
              example: "Conversation not found"
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Server Error"
            message:
              type: string
              example: "Error deleting conversation"
    """
    token = request.headers.get('X-Token')
    if not token:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing X-Token header"
        }, 401)
    
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token - not found in database"
        }, 401)
    
    g.token_id = token_details["id"]
    g.user_id = token_details["user_id"]
    
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get conversation_id from query parameters
    conversation_id = request.args.get('conversation_id')
    
    # Validate conversation_id parameter
    if not conversation_id or not conversation_id.strip():
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing or empty required parameter: conversation_id"
        }, 400)
    
    try:
        success, error = delete_conversation_history(conversation_id)
        if not success:
            if "does not exist" in str(error).lower():
                return create_api_response({
                    "error": "Not Found",
                    "message": "Conversation not found"
                }, 404)
            else:
                return create_api_response({
                    "error": "Server Error",
                    "message": f"Error deleting conversation: {error}"
                }, 500)
        
        return create_api_response({
            "message": "Conversation deleted successfully"
        }, 200)
        
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error deleting conversation: {str(e)}"
        }, 500)

def register_llm_conversation_routes(app):
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    """Register LLM conversation routes with the Flask app"""
    
    app.route('/llm/conversation/chat', methods=['POST'])(track_usage(api_logger(check_endpoint_access(create_chat_route))))
    app.route('/llm/conversation/continue', methods=['POST'])(track_usage(api_logger(check_endpoint_access(continue_conversation_route))))
    app.route('/llm/conversation', methods=['DELETE'])(api_logger(check_endpoint_access(delete_conversation_route)))