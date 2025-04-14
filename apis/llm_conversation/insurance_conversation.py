from flask import request, g
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceService import BalanceService
from apis.utils.llmServices import get_openai_client
# Import references and functions
from apis.llm_conversation.references import (
    GPT4O_DEPLOYMENT, VEHICLE_QUOTE_TOOLS, INSURANCE_BOT_CREDIT_COST, 
    OFF_TOPIC_RESPONSE
)
from apis.llm_conversation.functions import (
    ensure_complete_extraction_data, is_off_topic_query, extract_info_from_message,
    process_tool_calls, format_conversation_for_openai, normalize_extraction_data,
    get_conversation_history, save_conversation_history, delete_conversation_history,
    create_api_response
)
import logging
import pytz
import uuid
from datetime import datetime

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI client
openai_client = get_openai_client()

def insurance_chat_route():
    """
    Vehicle insurance quote bot API endpoint
    ---
    tags:
      - Insurance Bot
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
            - user_message
          properties:
            conversation_id:
              type: string
              description: Existing conversation ID (if continuing a conversation)
            user_message:
              type: string
              description: Message from the user
            temperature:
              type: number
              format: float
              minimum: 0
              maximum: 1
              default: 0.5
              description: Controls randomness (0=focused, 1=creative)
    produces:
      - application/json
    responses:
      200:
        description: Chat response received successfully
        schema:
          type: object
          properties:
            conversation_id:
              type: string
              description: Unique ID for the conversation
            assistant_message:
              type: string
              description: Response from the insurance bot
            extraction_data:
              type: object
              description: Extracted vehicle information
            is_off_topic:
              type: boolean
              description: Whether the user query was off-topic
            is_quote_complete:
              type: boolean
              description: Whether the quote information collection is complete
            prompt_tokens:
              type: integer
              description: Number of prompt tokens used
            completion_tokens:
              type: integer
              description: Number of completion tokens used
            total_tokens:
              type: integer
              description: Total number of tokens used
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
    if 'user_message' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: user_message"
        }, 400)
    
    # Extract parameters
    user_message = data.get('user_message')
    conversation_id = data.get('conversation_id')
    temperature = float(data.get('temperature', 0.5))
    
    # Get endpoint ID for balance tracking
    endpoint_id = DatabaseService.get_endpoint_id_by_path(request.path)
    if not endpoint_id:
        logger.error(f"Endpoint not configured for balance tracking: {request.path}")
        return create_api_response({
            "error": "Configuration Error",
            "message": "Endpoint not configured for balance tracking"
        }, 500)
    
    # Deduct balance based on insurance bot credit cost
    success, result = BalanceService.check_and_deduct_balance(g.user_id, endpoint_id, INSURANCE_BOT_CREDIT_COST)
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
    
    try:
        # Flags for special message handling
        is_off_topic = False
        is_quote_complete = False
        
        # Check if this is a new conversation or continuing an existing one
        if conversation_id:
            # Get existing conversation
            conversation, error = get_conversation_history(conversation_id)
            if not conversation:
                return create_api_response({
                    "error": "Not Found",
                    "message": f"Conversation not found: {error}"
                }, 404)
            
            # Update conversation with new user message
            conversation["messages"].append({"role": "user", "content": user_message})
            
            # Extract information using rules-based approach
            conversation = extract_info_from_message(conversation, user_message)
            
            # Check if this is an off-topic query
            if is_off_topic_query(user_message) and not conversation.get("quote_complete", False):
                is_off_topic = True
                logger.info(f"Detected off-topic query: {user_message}")
                
                # Add response to conversation
                conversation["messages"].append({"role": "assistant", "content": OFF_TOPIC_RESPONSE})
                
                # Save conversation
                success, error = save_conversation_history(conversation_id, conversation)
                if not success:
                    return create_api_response({
                        "error": "Server Error",
                        "message": f"Error saving conversation: {error}"
                    }, 500)
                
                # Return the off-topic response with complete extraction data
                return create_api_response({
                    "conversation_id": conversation_id,
                    "assistant_message": OFF_TOPIC_RESPONSE,
                    "extraction_data": ensure_complete_extraction_data(conversation.get("extraction_data", {})),
                    "is_off_topic": True,
                    "is_quote_complete": conversation.get("quote_complete", False),
                    "prompt_tokens": 0,  # We didn't call the LLM
                    "completion_tokens": 0,
                    "total_tokens": 0
                }, 200)
            
            # Check if quote is already complete
            is_quote_complete = conversation.get("quote_complete", False)
            
        else:
            # Create new conversation
            conversation_id = str(uuid.uuid4())
            
            # Check if this is an off-topic query to start with
            if is_off_topic_query(user_message):
                is_off_topic = True
                logger.info(f"Detected off-topic query for new conversation: {user_message}")
                
                # Initialize conversation
                conversation = {
                    "conversation_id": conversation_id,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "temperature": temperature,
                    "messages": [
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": OFF_TOPIC_RESPONSE}
                    ],
                    "extraction_data": {},
                    "quote_complete": False
                }
                
                # Save conversation
                success, error = save_conversation_history(conversation_id, conversation)
                if not success:
                    return create_api_response({
                        "error": "Server Error",
                        "message": f"Error saving conversation: {error}"
                    }, 500)
                
                # Return the off-topic response
                return create_api_response({
                    "conversation_id": conversation_id,
                    "assistant_message": OFF_TOPIC_RESPONSE,
                    "extraction_data": ensure_complete_extraction_data({}),
                    "is_off_topic": True,
                    "is_quote_complete": False,
                    "prompt_tokens": 0,  # We didn't call the LLM
                    "completion_tokens": 0,
                    "total_tokens": 0
                }, 200)
            
            # Initialize conversation for on-topic query
            conversation = {
                "conversation_id": conversation_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": user_message}
                ],
                "extraction_data": {},
                "quote_complete": False
            }
            
            # Extract initial information
            conversation = extract_info_from_message(conversation, user_message)
        
        # Format conversation for OpenAI API
        messages = format_conversation_for_openai(conversation)
        
        # Call GPT-4o with function calling capabilities
        response = openai_client.chat.completions.create(
            model=GPT4O_DEPLOYMENT,
            messages=messages,
            temperature=temperature,
            tools=VEHICLE_QUOTE_TOOLS,
            tool_choice="auto"
        )
        
        # Extract the response data
        assistant_response = response.choices[0].message
        
        # Process any tool calls from the assistant's response
        if assistant_response.tool_calls:
            # Add the assistant's response with tool calls to the conversation
            conversation["messages"].append({
                "role": "assistant",
                "content": assistant_response.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    } for tc in assistant_response.tool_calls
                ]
            })
            
            # Process the tool calls and update extraction data
            conversation, tool_results = process_tool_calls(conversation, assistant_response.tool_calls)
            
            # Add each tool result to the conversation
            for result in tool_results:
                function_name = result["function_name"]
                result_content = result["result"]
                
                conversation["messages"].append({
                    "role": "function_result",
                    "name": function_name,
                    "content": result_content
                })
                
                # Check if quote is complete based on function call
                if function_name == "process_vehicle_quote":
                    is_quote_complete = True
                    conversation["quote_complete"] = True
            
            # Create a second request to get the final assistant response after tool calls
            messages = format_conversation_for_openai(conversation)
            second_response = openai_client.chat.completions.create(
                model=GPT4O_DEPLOYMENT,
                messages=messages,
                temperature=temperature
            )
            
            # Extract the final assistant message
            assistant_message = second_response.choices[0].message.content
            
            # Calculate total token usage
            prompt_tokens = response.usage.prompt_tokens + second_response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens + second_response.usage.completion_tokens
            total_tokens = response.usage.total_tokens + second_response.usage.total_tokens
            
        else:
            # No tool calls, just use the first response
            assistant_message = assistant_response.content if assistant_response.content else ""
            
            # Get token usage
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
        
        # Add the final assistant message to conversation history
        conversation["messages"].append({"role": "assistant", "content": assistant_message})
        
        # Apply rules-based extraction again to catch any new information
        conversation = extract_info_from_message(conversation, user_message)
        
        # Update timestamp
        conversation["updated_at"] = datetime.now().isoformat()
        
        # Normalize extraction data
        extraction_data = normalize_extraction_data(conversation.get("extraction_data", {}))
        
        # Update extraction data in the conversation
        conversation["extraction_data"] = extraction_data
        
        # Save conversation
        success, error = save_conversation_history(conversation_id, conversation)
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error saving conversation: {error}"
            }, 500)
        
        # Create response with complete extraction data
        response_data = {
            "conversation_id": conversation_id,
            "assistant_message": assistant_message,
            "extraction_data": ensure_complete_extraction_data(extraction_data),
            "is_off_topic": is_off_topic,
            "is_quote_complete": is_quote_complete,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model_used": GPT4O_DEPLOYMENT
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing chat request: {str(e)}"
        }, 500)

def delete_insurance_chat_route():
    """
    Delete a vehicle insurance quote conversation
    ---
    tags:
      - Insurance Bot
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
    
    # Store token ID and user ID in g for logging
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

def register_insurance_bot_routes(app):
    from apis.utils.usageMiddleware import track_usage
    """Register insurance bot routes with the Flask app"""
    app.route('/insurance-bot/chat', methods=['POST'])(track_usage(api_logger(insurance_chat_route)))
    app.route('/insurance-bot/chat', methods=['DELETE'])(api_logger(delete_insurance_chat_route))
