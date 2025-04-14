from flask import make_response, jsonify
from apis.utils.config import get_azure_blob_client, ensure_container_exists
from apis.llm_conversation.references import (
    CAR_MAKES, CAR_MODELS_BY_MAKE, CAR_COLORS, VEHICLE_USAGE_TYPES,
    COVER_TYPES, INSURED_VALUE_OPTIONS, NIGHT_PARKING_LOCATIONS,
    NIGHT_PARKING_SECURITY_TYPES, VEHICLE_QUOTE_SYSTEM_MESSAGE, 
    INSURANCE_CONVERSATION_CONTAINER
)
import logging
import json
import re
from difflib import get_close_matches

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

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
    
    # Ensure night_parking_security is always a list
    if complete_data["night_parking_security"] is None:
        complete_data["night_parking_security"] = []
    
    # Ensure boolean fields are properly formatted
    if isinstance(complete_data["is_registered_in_sa"], str):
        value = complete_data["is_registered_in_sa"].lower()
        complete_data["is_registered_in_sa"] = value in ["yes", "true", "y", "1"]
    
    if isinstance(complete_data["is_financed"], str):
        value = complete_data["is_financed"].lower()
        complete_data["is_financed"] = value in ["yes", "true", "y", "1"]
    
    return complete_data



def find_best_match(input_text, predefined_list, threshold=0.6):
    """
    Find the best match from a predefined list based on input text
    
    Args:
        input_text (str): The text to match
        predefined_list (list): List of predefined values to match against
        threshold (float): Minimum score required for a match
        
    Returns:
        str or None: The best matching item or None if no match found
    """
    if not input_text:
        return None
    
    # Convert input to lowercase for case-insensitive matching
    input_lower = input_text.lower()
    
    # First try exact match (case-insensitive)
    for item in predefined_list:
        if item.lower() == input_lower:
            return item
    
    # Try using difflib for better fuzzy matching
    predefined_list_lower = [item.lower() for item in predefined_list]
    close_matches = get_close_matches(input_lower, predefined_list_lower, n=1, cutoff=threshold)
    
    if close_matches:
        # Find the original case version of the match
        index = predefined_list_lower.index(close_matches[0])
        return predefined_list[index]
    
    # If difflib doesn't find a match, fall back to a more flexible approach
    best_match = None
    best_match_score = 0
    
    for item in predefined_list:
        item_lower = item.lower()
        # Check if item is contained in input or input is contained in item
        if item_lower in input_lower or input_lower in item_lower:
            # Calculate a simple match score based on length of overlap
            overlap = len(set(input_lower.split()) & set(item_lower.split()))
            if overlap > best_match_score:
                best_match = item
                best_match_score = overlap
    
    # Only return if we have a reasonable match
    if best_match_score > 0:
        return best_match
    
    return None

def get_valid_models_for_make(make):
    """
    Get the valid models for a specific car make
    
    Args:
        make (str): The car make
        
    Returns:
        list: List of valid models for the make, or empty list if make not found
    """
    # First try to find an exact match
    if make in CAR_MODELS_BY_MAKE:
        return CAR_MODELS_BY_MAKE[make]
    
    # Try case-insensitive matching
    for valid_make in CAR_MODELS_BY_MAKE:
        if valid_make.lower() == make.lower():
            return CAR_MODELS_BY_MAKE[valid_make]
    
    # Try to find the closest match using find_best_match
    best_match = find_best_match(make, CAR_MAKES)
    if best_match:
        return CAR_MODELS_BY_MAKE[best_match]
    
    return []

def validate_make(make):
    """
    Validate and correct a car make against the reference list
    
    Args:
        make (str): The car make to validate
        
    Returns:
        tuple: (valid_make, suggestion_list)
            - valid_make: The corrected make or None if no match
            - suggestion_list: List of suggested makes if no exact match
    """
    if not make:
        return None, CAR_MAKES[:5]  # Return first 5 makes as suggestions
    
    # Check if make is already valid
    if make in CAR_MAKES:
        return make, []
    
    # Try to find best match
    best_match = find_best_match(make, CAR_MAKES)
    if best_match:
        return best_match, []
    
    # If no good match, return top 5 suggestions
    return None, CAR_MAKES[:5]

def validate_model(make, model):
    """
    Validate a car model against the reference list for the specified make
    
    Args:
        make (str): The car make
        model (str): The car model to validate
        
    Returns:
        tuple: (valid_model, suggestion_list)
            - valid_model: The corrected model or None if no match
            - suggestion_list: List of suggested models if no exact match
    """
    if not make or not model:
        return None, []
    
    # Get valid models for the make
    valid_models = get_valid_models_for_make(make)
    if not valid_models:
        return None, []
    
    # Check if model is already valid
    if model in valid_models:
        return model, []
    
    # Try to find best match
    best_match = find_best_match(model, valid_models)
    if best_match:
        return best_match, []
    
    # If no good match, return all valid models as suggestions
    return None, valid_models

def validate_color(color):
    """
    Validate a car color against the reference list
    
    Args:
        color (str): The car color to validate
        
    Returns:
        tuple: (valid_color, suggestion_list)
            - valid_color: The corrected color or None if no match
            - suggestion_list: List of suggested colors if no exact match
    """
    if not color:
        return None, []
    
    # Check if color is already valid
    if color in CAR_COLORS:
        return color, []
    
    # Try to find best match
    best_match = find_best_match(color, CAR_COLORS)
    if best_match:
        return best_match, []
    
    # If no good match, return all colors as suggestions
    return None, CAR_COLORS

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
        'security', 'theft', 'value', 'id number', 'name', 'mazda', 
        'volkswagen', 'audi', 'hyundai', 'kia', 'volvo', 'jeep'
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

def extract_info_from_message(conversation, user_message):
    """
    Extract vehicle information from user message using rules-based approach
    
    Args:
        conversation (dict): The conversation object
        user_message (str): The user's message
        
    Returns:
        dict: Updated conversation
    """
    # Import regular expression module
    import re
    
    # Initialize extraction_data if not present
    if "extraction_data" not in conversation:
        conversation["extraction_data"] = {}
    
    # Convert message to lowercase for matching
    message_lower = user_message.lower()
    
    # Extract customer name - look for name patterns
    name_indicators = ["my name is", "name's", "i am", "i'm", "this is"]
    for indicator in name_indicators:
        if indicator in message_lower:
            # Get the part after the indicator
            name_part = message_lower.split(indicator, 1)[1].strip()
            # Extract name (assume name continues until punctuation or end of sentence)
            name_end = min((pos for pos in [
                name_part.find("."), 
                name_part.find(","), 
                name_part.find("and"), 
                len(name_part)
            ] if pos >= 0), default=len(name_part))
            
            potential_name = name_part[:name_end].strip()
            # Only use if it seems like a reasonable name (not too short or too long)
            if 2 <= len(potential_name.split()) <= 5 and len(potential_name) > 3:
                # Capitalize each word in the name
                customer_name = " ".join(word.capitalize() for word in potential_name.split())
                conversation["extraction_data"]["customer_name"] = customer_name
                break
    
    # Extract ID number - look for digit sequences that could be ID numbers
    id_indicators = ["id number", "id is", "identity number", "id no", "id no.", "id #"]
    for indicator in id_indicators:
        if indicator in message_lower:
            # Get the part after the indicator
            id_part = message_lower.split(indicator, 1)[1].strip()
            # Look for a sequence of digits (South African ID is 13 digits)
            id_matches = re.findall(r'\b\d{7,13}\b', id_part)
            if id_matches:
                conversation["extraction_data"]["id_number"] = id_matches[0]
                break
    
    # Extract car make
    for make in CAR_MAKES:
        if make.lower() in message_lower:
            # Validate the make
            valid_make, _ = validate_make(make)
            if valid_make:
                conversation["extraction_data"]["make"] = valid_make
            else:
                conversation["extraction_data"]["make"] = make
            break
    
    # Extract car model if we know the make
    if "make" in conversation["extraction_data"]:
        make = conversation["extraction_data"]["make"]
        valid_models = get_valid_models_for_make(make)
        
        for model in valid_models:
            if model.lower() in message_lower:
                # Validate the model for this make
                valid_model, _ = validate_model(make, model)
                if valid_model:
                    conversation["extraction_data"]["model"] = valid_model
                else:
                    conversation["extraction_data"]["model"] = model
                break
    
    # Extract car color
    for color in CAR_COLORS:
        if color.lower() in message_lower:
            # Validate the color
            valid_color, _ = validate_color(color)
            if valid_color:
                conversation["extraction_data"]["color"] = valid_color
            else:
                conversation["extraction_data"]["color"] = color
            break
    
    # Extract car year - look for 4-digit numbers
    year_matches = re.findall(r'\b(19[7-9]\d|20[0-2]\d)\b', message_lower)
    if year_matches:
        conversation["extraction_data"]["year"] = year_matches[0]
    
    # Extract usage type
    for usage_type in VEHICLE_USAGE_TYPES:
        if usage_type.lower() in message_lower:
            conversation["extraction_data"]["usage"] = usage_type
            break
    
    # Enhanced extraction for registration status
    registration_indicators = [
        "registered in south africa", "registered in sa", 
        "south african registration", "sa registration", 
        "is it registered", "vehicle registration"
    ]
    
    for indicator in registration_indicators:
        if indicator in message_lower:
            # Find affirmative or negative responses
            affirmative = any(word in message_lower for word in 
                             ["yes", "yeah", "yep", "correct", "it is", "that's right", 
                              "affirmative", "indeed", "registered"])
            negative = any(word in message_lower for word in 
                          ["no", "nope", "not", "isn't", "is not", "negative", "unregistered"])
            
            if affirmative and not negative:
                conversation["extraction_data"]["is_registered_in_sa"] = True
            elif negative and not affirmative:
                conversation["extraction_data"]["is_registered_in_sa"] = False
            break
    
    # Enhanced extraction for financing status
    finance_indicators = [
        "financed", "financing", "bank loan", "car loan", "vehicle loan", 
        "paying off", "installment", "finance", "payment plan"
    ]
    
    for indicator in finance_indicators:
        if indicator in message_lower:
            # Find affirmative or negative responses
            affirmative = any(word in message_lower for word in 
                             ["yes", "yeah", "yep", "correct", "it is", "that's right", 
                              "affirmative", "indeed", "financed"])
            negative = any(word in message_lower for word in 
                          ["no", "nope", "not", "isn't", "is not", "negative", "paid off", "fully paid"])
            
            if affirmative and not negative:
                conversation["extraction_data"]["is_financed"] = True
            elif negative and not affirmative:
                conversation["extraction_data"]["is_financed"] = False
            break
    
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
    
    # Extract night parking area
    area_indicators = ["area", "suburb", "neighborhood", "location", "place", "district", "precinct"]
    for indicator in area_indicators:
        if indicator in message_lower:
            # Get the part after the indicator
            area_part = message_lower.split(indicator, 1)[1].strip()
            # Extract area name (assume area continues until punctuation or end of sentence)
            area_end = min((pos for pos in [
                area_part.find("."), 
                area_part.find(","), 
                area_part.find("and"), 
                len(area_part)
            ] if pos >= 0), default=len(area_part))
            
            potential_area = area_part[:area_end].strip()
            # Only use if it seems like a reasonable area name
            if 1 <= len(potential_area.split()) <= 3 and len(potential_area) > 2:
                # Capitalize each word in the area name
                area_name = " ".join(word.capitalize() for word in potential_area.split())
                conversation["extraction_data"]["night_parking_area"] = area_name
                break
    
    # Extract night parking security (multiple selection)
    security_types = []
    for security_type in NIGHT_PARKING_SECURITY_TYPES:
        if security_type.lower() in message_lower:
            security_types.append(security_type)
    
    if security_types:
        conversation["extraction_data"]["night_parking_security"] = security_types
    
    return conversation
    
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
            # Update extraction data with collected information, applying validation
            for key, value in function_args.items():
                if value:  # Only update if value is not None or empty
                    # Apply validation for specific fields
                    if key == "make":
                        valid_make, _ = validate_make(value)
                        conversation["extraction_data"][key] = valid_make or value
                    elif key == "model" and "make" in conversation["extraction_data"]:
                        valid_model, _ = validate_model(conversation["extraction_data"]["make"], value)
                        conversation["extraction_data"][key] = valid_model or value
                    elif key == "color":
                        valid_color, _ = validate_color(value)
                        conversation["extraction_data"][key] = valid_color or value
                    else:
                        conversation["extraction_data"][key] = value
            
            # Prepare response
            result = {
                "success": True,
                "message": "Information collected successfully"
            }
        
        elif function_name == "process_vehicle_quote":
            # Update extraction data from nested objects, applying validation
            # Personal info
            if "customer_name" in function_args:
                conversation["extraction_data"]["customer_name"] = function_args["customer_name"]
            if "id_number" in function_args:
                conversation["extraction_data"]["id_number"] = function_args["id_number"]
            
            # Vehicle details
            if "vehicle_details" in function_args:
                for key, value in function_args["vehicle_details"].items():
                    # Apply validation for specific fields
                    if key == "make":
                        valid_make, _ = validate_make(value)
                        conversation["extraction_data"][key] = valid_make or value
                    elif key == "model":
                        # Get the make from either the nested object or the existing data
                        make = function_args["vehicle_details"].get("make") or conversation["extraction_data"].get("make")
                        if make:
                            valid_model, _ = validate_model(make, value)
                            conversation["extraction_data"][key] = valid_model or value
                        else:
                            conversation["extraction_data"][key] = value
                    elif key == "color":
                        valid_color, _ = validate_color(value)
                        conversation["extraction_data"][key] = valid_color or value
                    else:
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

def format_conversation_for_openai(conversation):
    """
    Format conversation for OpenAI API input
    
    Args:
        conversation (dict): The conversation state
        
    Returns:
        list: Formatted messages for OpenAI API
    """
    messages = []
    
    # Add system message
    messages.append({"role": "system", "content": VEHICLE_QUOTE_SYSTEM_MESSAGE})
    
    # Add conversation history
    for msg in conversation.get("messages", []):
        role = msg.get("role")
        # Skip any initial assistant greeting if it exists
        if role == "assistant" and any(greeting in msg.get("content", "").lower() 
                                      for greeting in ["hi there", "hello", "how can i help"]):
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

def create_api_response(data, status_code=200):
    """
    Helper function to create consistent API responses
    
    Args:
        data (dict): Response data
        status_code (int, optional): HTTP status code. Defaults to 200.
        
    Returns:
        Response: Flask response object
    """
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def get_conversation_history(conversation_id):
    """
    Get conversation history from blob storage
    
    Args:
        conversation_id (str): The conversation ID
        
    Returns:
        tuple: (conversation, error)
    """
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
    """
    Save conversation history to blob storage
    
    Args:
        conversation_id (str): The conversation ID
        conversation (dict): The conversation data
        
    Returns:
        tuple: (success, error)
    """
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
    """
    Delete conversation history from blob storage
    
    Args:
        conversation_id (str): The conversation ID
        
    Returns:
        tuple: (success, error)
    """
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

# This is just the normalize_extraction_data function that needs fixing

def normalize_extraction_data(extraction_data):
    """
    Normalize extraction data by matching values to predefined lists
    
    Args:
        extraction_data (dict): The extraction data to normalize
        
    Returns:
        dict: Normalized extraction data
    """
    # Make a copy to avoid modifying the original
    normalized_data = extraction_data.copy() if extraction_data else {}
    
    # Validate make
    if "make" in normalized_data and normalized_data["make"]:
        valid_make, _ = validate_make(normalized_data["make"])
        if valid_make:
            normalized_data["make"] = valid_make
    
    # Validate model based on make
    if "make" in normalized_data and normalized_data["make"] and "model" in normalized_data and normalized_data["model"]:
        valid_model, _ = validate_model(normalized_data["make"], normalized_data["model"])
        if valid_model:
            normalized_data["model"] = valid_model
    
    # Validate color
    if "color" in normalized_data and normalized_data["color"]:
        valid_color, _ = validate_color(normalized_data["color"])
        if valid_color:
            normalized_data["color"] = valid_color
    
    # Normalize usage type
    if "usage" in normalized_data and normalized_data["usage"]:
        usage = normalized_data["usage"]
        for valid_usage in VEHICLE_USAGE_TYPES:
            if valid_usage.lower() == usage.lower() or usage.lower() in valid_usage.lower():
                normalized_data["usage"] = valid_usage
                break
    
    # Convert yes/no string responses to booleans
    for field in ["is_registered_in_sa", "is_financed"]:
        if field in normalized_data and isinstance(normalized_data[field], str) and normalized_data[field]:
            value = normalized_data[field].lower()
            normalized_data[field] = value in ["yes", "true", "y", "1"]
    
    # Normalize cover type
    if "cover_type" in normalized_data and normalized_data["cover_type"]:
        cover_type = normalized_data["cover_type"]
        for valid_cover in COVER_TYPES:
            if valid_cover.lower() == cover_type.lower() or cover_type.lower() in valid_cover.lower():
                normalized_data["cover_type"] = valid_cover
                break
    
    # Normalize insured value
    if "insured_value" in normalized_data and normalized_data["insured_value"]:
        insured_value = normalized_data["insured_value"]
        for valid_value in INSURED_VALUE_OPTIONS:
            if valid_value.lower() == insured_value.lower() or insured_value.lower() in valid_value.lower():
                normalized_data["insured_value"] = valid_value
                break
    
    # Normalize night parking location
    if "night_parking_location" in normalized_data and normalized_data["night_parking_location"]:
        location = normalized_data["night_parking_location"]
        for valid_location in NIGHT_PARKING_LOCATIONS:
            if valid_location.lower() == location.lower() or location.lower() in valid_location.lower():
                normalized_data["night_parking_location"] = valid_location
                break
    
    # Normalize night parking security
    if "night_parking_security" in normalized_data and normalized_data["night_parking_security"]:
        security_types = normalized_data["night_parking_security"]
        normalized_security = []
        
        for security in security_types:
            if security:  # Add null check here
                for valid_security in NIGHT_PARKING_SECURITY_TYPES:
                    if valid_security.lower() == security.lower() or (security and security.lower() in valid_security.lower()):
                        normalized_security.append(valid_security)
                        break
        
        # Only replace if we found valid matches
        if normalized_security:
            normalized_data["night_parking_security"] = normalized_security
    
    return normalized_data
