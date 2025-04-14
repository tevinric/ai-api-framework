from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceService import BalanceService
from apis.utils.config import get_azure_blob_client, ensure_container_exists
# Import static references from references.py
from apis.llm_conversation.references import (
    CAR_MAKES, CAR_MODELS_BY_MAKE, CAR_COLORS, VEHICLE_USAGE_TYPES,
    COVER_TYPES, INSURED_VALUE_OPTIONS, NIGHT_PARKING_LOCATIONS,
    NIGHT_PARKING_SECURITY_TYPES, INSURANCE_BOT_CREDIT_COST,
    GPT4O_DEPLOYMENT, CONVERSATION_STATE, VEHICLE_QUOTE_SYSTEM_MESSAGE,
    VEHICLE_QUOTE_TOOLS, INSURANCE_CONVERSATION_CONTAINER, OFF_TOPIC_RESPONSE
)
import logging
import pytz
import os
import uuid
import json
from datetime import datetime
from apis.utils.llmServices import get_openai_client

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI client
openai_client = get_openai_client()

# Define storage account details
STORAGE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT")
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{INSURANCE_CONVERSATION_CONTAINER}"

def ensure_complete_extraction_data(extraction_data):
    """
    Ensure all possible extraction fields are included in the data structure
    
    Args:
        extraction_data (dict): The current extraction data
        
    Returns:
        dict: A complete extraction data structure with all possible fields
    """
    # Create a complete structure with default values for vehicle insurance
    complete_data = {
        "customer_name": extraction_data.get("customer_name", None),
        "id_number": extraction_data.get("id_number", None),
        "make": extraction_data.get("make", None),
        "model": extraction_data.get("model", None),
        "year": extraction_data.get("year", None),
        "color": extraction_data.get("color", None),
        "usage": extraction_data.get("usage", None),
        "is_registered_in_sa": extraction_data.get("is_registered_in_sa", None),
        "is_financed": extraction_data.get("is_financed", None),
        "cover_type": extraction_data.get("cover_type", None),
        "insured_value": extraction_data.get("insured_value", None),
        "night_parking_area": extraction_data.get("night_parking_area", None),
        "night_parking_location": extraction_data.get("night_parking_location", None),
        "night_parking_security": extraction_data.get("night_parking_security", [])
    }
    
    return complete_data

# Function to find best match in predefined lists
def find_best_match(input_text, predefined_list):
    """Find the best match from a predefined list based on input text"""
    if not input_text:
        return None
    
    # Convert input to lowercase for case-insensitive matching
    input_lower = input_text.lower()
    
    # First try exact match (case-insensitive)
    for item in predefined_list:
        if item.lower() == input_lower:
            return item
    
    # If no exact match, try to find a partial match
    best_match = None
    best_match_score = 0
    
    for item in predefined_list:
        # Check if item is contained in input or input is contained in item
        if item.lower() in input_lower or input_lower in item.lower():
            # Calculate a simple match score based on length of overlap
            overlap = len(set(input_lower.split()) & set(item.lower().split()))
            if overlap > best_match_score:
                best_match = item
                best_match_score = overlap
    
    return best_match

# Function to detect off-topic queries
def is_off_topic_query(query):
    """
    Detects if a user query is not related to vehicle insurance quotes
    
    Args:
        query (str): The user message to analyze
        
    Returns:
        bool: True if the query is off-topic, False if it's vehicle insurance-related
    """
    # Convert to lowercase for easier matching
    query_lower = query.lower()
    
    # Vehicle insurance-related keywords
    vehicle_insurance_keywords = [
        'insurance', 'policy', 'premium', 'coverage', 'accident', 
        'damage', 'quote', 'vehicle', 'car', 'auto', 'liability', 
        'excess', 'deductible', 'insure', 'underwriting', 'risk', 
        'cover', 'third-party', 'third party', 'comprehensive', 
        'registration', 'financed', 'toyota', 'bmw', 'vehicle', 
        'ford', 'honda', 'color', 'model', 'make', 'year', 'parking',
        'security', 'theft', 'value'
    ]
    
    # Check if the query contains any vehicle insurance-related keywords
    for keyword in vehicle_insurance_keywords:
        if keyword in query_lower:
            return False
    
    # Common off-topic themes that might indicate a non-insurance query
    off_topic_themes = [
        # General knowledge
        'what is', 'who is', 'when did', 'where is', 'tell me about', 'facts about',
        # Current events and news
        'news', 'latest', 'president', 'election', 'covid', 'pandemic', 'war', 'politics',
        # Entertainment
        'movie', 'tv show', 'netflix', 'actor', 'film', 'music', 'song', 'celebrity',
        # Other types of insurance that are not in scope
        'home insurance', 'content', 'property', 'health', 'life insurance', 'medical',
        # Irrelevant financial topics
        'bank', 'loan', 'mortgage', 'investment', 'stock', 'share', 'bond', 'crypto',
        # Technology (unrelated to insurance)
        'computer', 'phone', 'iphone', 'android', 'app', 'software', 'programming',
        # Sports
        'football', 'soccer', 'basketball', 'baseball', 'player', 'team', 'game', 'sport',
        # Weather
        'weather', 'forecast', 'temperature', 'rain', 'sunny', 'cold', 'hot',
        # Food and recipes
        'recipe', 'cook', 'bake', 'food', 'restaurant', 'meal', 'diet',
        # Math and calculations (unless related to premiums)
        'calculate', 'solve', 'equation', 'math problem'
    ]
    
    # Check for common greeting patterns (which are acceptable)
    greeting_patterns = ['hello', 'hi', 'hey', 'greetings', 'good morning', 'good afternoon', 'good evening']
    
    # If the query is just a greeting, it's not off-topic
    if any(greeting in query_lower for greeting in greeting_patterns) and len(query_lower.split()) < 4:
        return False
    
    # If we find any off-topic themes, consider it off-topic
    for theme in off_topic_themes:
        if theme in query_lower:
            return True
    
    # For short queries (1-3 words) without vehicle insurance keywords, we'll be lenient
    if len(query_lower.split()) <= 3:
        return False
    
    # For longer queries without vehicle insurance keywords, likely off-topic
    if len(query_lower.split()) > 5:
        return True
    
    # If we can't determine clearly, default to on-topic to avoid false positives
    return False

def generate_quote_summary(extraction_data):
    """
    Generate a summary of collected information for the vehicle quote
    
    Args:
        extraction_data (dict): The collected vehicle information
        
    Returns:
        str: A summary string for the vehicle quote
    """
    # Ensure all fields are present with proper formatting
    customer_name = extraction_data.get("customer_name", "Not provided")
    id_number = extraction_data.get("id_number", "Not provided")
    make = extraction_data.get("make", "Not provided")
    model = extraction_data.get("model", "Not provided")
    year = extraction_data.get("year", "Not provided")
    color = extraction_data.get("color", "Not provided")
    usage = extraction_data.get("usage", "Not provided")
    
    # Format Boolean values nicely
    is_registered_in_sa = "Yes" if extraction_data.get("is_registered_in_sa") else "No"
    is_financed = "Yes" if extraction_data.get("is_financed") else "No"
    
    # Coverage details
    cover_type = extraction_data.get("cover_type", "Not provided")
    insured_value = extraction_data.get("insured_value", "Not provided")
    
    # Risk details
    night_parking_area = extraction_data.get("night_parking_area", "Not provided")
    night_parking_location = extraction_data.get("night_parking_location", "Not provided")
    night_parking_security = extraction_data.get("night_parking_security", [])
    
    # Format night_parking_security as a comma-separated list
    night_parking_security_str = ", ".join(night_parking_security) if night_parking_security else "None"
    
    # Build summary
    summary = "Here's a summary of your vehicle insurance quote information:\n\n"
    summary += "Personal Information:\n"
    summary += f"- Name: {customer_name}\n"
    summary += f"- ID Number: {id_number}\n\n"
    
    summary += "Vehicle Details:\n"
    summary += f"- Make: {make}\n"
    summary += f"- Model: {model}\n"
    summary += f"- Year: {year}\n"
    summary += f"- Color: {color}\n"
    summary += f"- Usage: {usage}\n"
    summary += f"- Registered in South Africa: {is_registered_in_sa}\n"
    summary += f"- Vehicle Financed: {is_financed}\n\n"
    
    summary += "Coverage Preferences:\n"
    summary += f"- Cover Type: {cover_type}\n"
    summary += f"- Insured Value: {insured_value}\n\n"
    
    summary += "Risk Information:\n"
    summary += f"- Night Parking Area: {night_parking_area}\n"
    summary += f"- Night Parking Location: {night_parking_location}\n"
    summary += f"- Night Parking Security: {night_parking_security_str}\n\n"
    
    summary += "Your quote information has been received. A representative will contact you shortly with your premium details."
    
    return summary

def check_if_quote_complete(extraction_data):
    """
    Check if all required information has been collected for a vehicle quote
    
    Args:
        extraction_data (dict): The extraction data
        
    Returns:
        bool: True if complete, False otherwise
    """
    # Required fields for a complete vehicle quote
    required_fields = [
        "customer_name", "id_number", "make", "model", "year", "color",
        "usage", "is_registered_in_sa", "is_financed", "cover_type",
        "insured_value", "night_parking_area", "night_parking_location",
        "night_parking_security"
    ]
    
    # Check if all required fields are present and have values
    for field in required_fields:
        if field not in extraction_data or extraction_data[field] is None:
            # Special case for night_parking_security which is a list
            if field == "night_parking_security":
                if field not in extraction_data or not extraction_data[field]:
                    return False
            else:
                return False
    
    return True

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
        container_client = blob_service_client.get_container_client(INSURANCE_CONVERSATION_CONTAINER)
        
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
        ensure_container_exists(INSURANCE_CONVERSATION_CONTAINER)
        
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(INSURANCE_CONVERSATION_CONTAINER)
        
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
        container_client = blob_service_client.get_container_client(INSURANCE_CONVERSATION_CONTAINER)
        
        # Get blob client
        blob_client = container_client.get_blob_client(f"{conversation_id}.json")
        
        # Delete blob
        blob_client.delete_blob()
        
        return True, None
    except Exception as e:
        logger.error(f"Error deleting conversation history: {str(e)}")
        return False, str(e)

def format_conversation_for_openai(conversation):
    """Format conversation for OpenAI API input"""
    messages = []
    
    # Add system message
    messages.append({"role": "system", "content": VEHICLE_QUOTE_SYSTEM_MESSAGE})
    
    # Add conversation history
    for msg in conversation.get("messages", []):
        role = msg.get("role")
        # Skip the initial assistant greeting if it exists
        if role == "assistant" and msg.get("content") == "Hi there, how can I help you today?":
            continue
            
        # Convert to OpenAI message format
        if role in ["user", "assistant"]:
            messages.append({
                "role": role,
                "content": msg.get("content", "")
            })
        elif role == "function":
            messages.append({
                "role": "assistant",
                "content": "",
                "function_call": {
                    "name": msg.get("name"),
                    "arguments": msg.get("arguments", "{}")
                }
            })
        elif role == "function_result":
            messages.append({
                "role": "function",
                "name": msg.get("name"),
                "content": msg.get("content", "")
            })
    
    return messages

def process_tool_calls(conversation, tool_calls):
    """
    Process tool calls from the assistant and update extraction data
    
    Args:
        conversation (dict): The conversation object
        tool_calls (list): List of tool call objects from OpenAI
        
    Returns:
        tuple: (updated_conversation, tool_results)
    """
    tool_results = []
    
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        if function_name == "collect_vehicle_info":
            # Update extraction data with collected information
            for key, value in function_args.items():
                if value:  # Only update if value is not None or empty
                    conversation["extraction_data"][key] = value
            
            # Prepare response
            result = {
                "success": True,
                "message": "Information collected successfully"
            }
        
        elif function_name == "process_vehicle_quote":
            # Update extraction data from nested objects
            # Personal info
            if "customer_name" in function_args:
                conversation["extraction_data"]["customer_name"] = function_args["customer_name"]
            if "id_number" in function_args:
                conversation["extraction_data"]["id_number"] = function_args["id_number"]
            
            # Vehicle details
            if "vehicle_details" in function_args:
                for key, value in function_args["vehicle_details"].items():
                    conversation["extraction_data"][key] = value
            
            # Coverage details
            if "coverage_details" in function_args:
                for key, value in function_args["coverage_details"].items():
                    conversation["extraction_data"][key] = value
            
            # Risk details
            if "risk_details" in function_args:
                for key, value in function_args["risk_details"].items():
                    conversation["extraction_data"][key] = value
            
            # Generate summary
            summary = generate_quote_summary(conversation["extraction_data"])
            
            # Mark conversation as complete
            conversation["quote_complete"] = True
            
            # Prepare response
            result = {
                "success": True,
                "message": "Quote processed successfully",
                "summary": summary
            }
        
        # Add to tool results
        tool_results.append({
            "tool_call_id": tool_call.id,
            "function_name": function_name,
            "result": json.dumps(result)
        })
    
    return conversation, tool_results

def extract_info_from_message(conversation, user_message):
    """
    Extract vehicle information from user message using rules-based approach
    
    Args:
        conversation (dict): The conversation object
        user_message (str): The user's message
        
    Returns:
        dict: Updated conversation
    """
    # Initialize extraction_data if not present
    if "extraction_data" not in conversation:
        conversation["extraction_data"] = {}
    
    # Convert message to lowercase for matching
    message_lower = user_message.lower()
    
    # Extract car make
    for make in CAR_MAKES:
        if make.lower() in message_lower:
            conversation["extraction_data"]["make"] = make
            break
    
    # Extract car model if we know the make
    if "make" in conversation["extraction_data"]:
        make = conversation["extraction_data"]["make"]
        if make in CAR_MODELS_BY_MAKE:
            for model in CAR_MODELS_BY_MAKE[make]:
                if model.lower() in message_lower:
                    conversation["extraction_data"]["model"] = model
                    break
    
    # Extract car color
    for color in CAR_COLORS:
        if color.lower() in message_lower:
            conversation["extraction_data"]["color"] = color
            break
    
    # Extract car year - look for 4-digit numbers
    import re
    year_matches = re.findall(r'\b(19[7-9]\d|20[0-2]\d)\b', message_lower)
    if year_matches:
        conversation["extraction_data"]["year"] = year_matches[0]
    
    # Extract usage type
    for usage_type in VEHICLE_USAGE_TYPES:
        if usage_type.lower() in message_lower:
            conversation["extraction_data"]["usage"] = usage_type
            break
    
    # Extract yes/no answers for registration and financing
    if "registered in south africa" in message_lower or "registered in sa" in message_lower:
        is_registered = "yes" in message_lower or "yeah" in message_lower or "correct" in message_lower
        conversation["extraction_data"]["is_registered_in_sa"] = is_registered
    
    if "financed" in message_lower:
        is_financed = "yes" in message_lower or "yeah" in message_lower or "correct" in message_lower
        conversation["extraction_data"]["is_financed"] = is_financed
    
    # Extract cover type
    for cover_type in COVER_TYPES:
        if cover_type.lower() in message_lower:
            conversation["extraction_data"]["cover_type"] = cover_type
            break
    
    # Extract insured value
    for value_option in INSURED_VALUE_OPTIONS:
        if value_option.lower() in message_lower:
            conversation["extraction_data"]["insured_value"] = value_option
            break
    
    # Extract night parking location
    for location in NIGHT_PARKING_LOCATIONS:
        if location.lower() in message_lower:
            conversation["extraction_data"]["night_parking_location"] = location
            break
    
    # Extract night parking security (multiple selection)
    security_types = []
    for security_type in NIGHT_PARKING_SECURITY_TYPES:
        if security_type.lower() in message_lower:
            security_types.append(security_type)
    
    if security_types:
        conversation["extraction_data"]["night_parking_security"] = security_types
    
    return conversation

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
                    "state": CONVERSATION_STATE,
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
                "state": CONVERSATION_STATE,
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
            
            # Check if the quote is complete based on extraction data
            if check_if_quote_complete(conversation.get("extraction_data", {})):
                is_quote_complete = True
                conversation["quote_complete"] = True
            
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
        
        # Process vehicle details to find best matches from predefined lists
        extraction_data = conversation.get("extraction_data", {})
        
        # Match car make against predefined list
        if "make" in extraction_data:
            best_make_match = find_best_match(extraction_data["make"], CAR_MAKES)
            if best_make_match:
                extraction_data["make"] = best_make_match
        
        # Match car model against models for the selected make
        if "make" in extraction_data and "model" in extraction_data:
            make = extraction_data["make"]
            if make in CAR_MODELS_BY_MAKE:
                best_model_match = find_best_match(extraction_data["model"], CAR_MODELS_BY_MAKE[make])
                if best_model_match:
                    extraction_data["model"] = best_model_match
        
        # Match color against predefined list
        if "color" in extraction_data:
            best_color_match = find_best_match(extraction_data["color"], CAR_COLORS)
            if best_color_match:
                extraction_data["color"] = best_color_match
        
        # Match usage type against predefined list
        if "usage" in extraction_data:
            best_usage_match = find_best_match(extraction_data["usage"], VEHICLE_USAGE_TYPES)
            if best_usage_match:
                extraction_data["usage"] = best_usage_match
        
        # Convert yes/no string responses to booleans
        for field in ["is_registered_in_sa", "is_financed"]:
            if field in extraction_data and isinstance(extraction_data[field], str):
                value = extraction_data[field].lower()
                extraction_data[field] = value in ["yes", "true", "y", "1"]
        
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
