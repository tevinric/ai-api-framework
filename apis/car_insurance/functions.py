from flask import make_response, jsonify
from apis.utils.config import get_azure_blob_client, ensure_container_exists
from apis.car_insurance.references import (
    CAR_MAKES, CAR_MODELS_BY_MAKE, MODEL_TYPES_BY_MODEL, CAR_COLORS, 
    VEHICLE_USAGE_TYPES, VEHICLE_USAGE_DESCRIPTIONS, COVER_TYPES, 
    COVER_TYPE_DESCRIPTIONS, INSURED_VALUE_OPTIONS, INSURED_VALUE_DESCRIPTIONS,
    PARKING_LOCATIONS, PARKING_SECURITY_TYPES, MARITAL_STATUS_OPTIONS,
    EMPLOYMENT_STATUS_OPTIONS, CAR_INSURANCE_SYSTEM_MESSAGE,
    CAR_INSURANCE_CONVERSATION_CONTAINER, QUESTION_FLOW
)
import logging
import json
import re
from difflib import get_close_matches
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def ensure_complete_data(extraction_data):
    """
    Ensure all possible extraction fields are included in the data structure
    
    Args:
        extraction_data (dict): The current extraction data
        
    Returns:
        dict: A complete extraction data structure with all possible fields
    """
    # Create a complete structure with default values
    complete_data = {field: extraction_data.get(field, None) for field in QUESTION_FLOW}
    
    # Ensure array fields are always arrays
    for field in ["night_parking_security", "day_parking_security"]:
        if complete_data[field] is None:
            complete_data[field] = []
        elif not isinstance(complete_data[field], list):
            complete_data[field] = [complete_data[field]]
    
    # Ensure boolean fields are properly formatted
    for field in ["is_registered_in_sa", "is_financed", "has_tracking_device", "is_regular_driver"]:
        if isinstance(complete_data[field], str):
            value = complete_data[field].lower()
            complete_data[field] = value in ["yes", "true", "y", "1"]
    
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

def get_valid_types_for_model(model):
    """
    Get the valid types for a specific car model
    
    Args:
        model (str): The car model
        
    Returns:
        list: List of valid types for the model, or default list if model not found
    """
    # First try to find an exact match
    if model in MODEL_TYPES_BY_MODEL:
        return MODEL_TYPES_BY_MODEL[model]
    
    # Try case-insensitive matching
    for valid_model in MODEL_TYPES_BY_MODEL:
        if valid_model.lower() == model.lower():
            return MODEL_TYPES_BY_MODEL[valid_model]
    
    # Return default types if no match found
    return MODEL_TYPES_BY_MODEL["DEFAULT"]

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
    
    # Check for exact match (case-insensitive)
    model_lower = model.lower()
    for valid_model in valid_models:
        if valid_model.lower() == model_lower:
            return valid_model, []
    
    # Check for a partial match where the model is a substring of a valid model
    partial_matches = []
    for valid_model in valid_models:
        if model_lower in valid_model.lower():
            partial_matches.append(valid_model)
    
    if len(partial_matches) == 1:
        # If exactly one partial match, return it
        return partial_matches[0], []
    elif len(partial_matches) > 1:
        # If multiple partial matches, return None and the list of matching models
        return None, partial_matches
    
    # Try to find best match using fuzzy matching
    best_match = find_best_match(model, valid_models, threshold=0.8)  # Increased threshold for stricter matching
    if best_match:
        return best_match, []
    
    # If no good match, return all valid models as suggestions
    return None, valid_models

def validate_model_type(model, model_type):
    """
    Validate a car model type against the reference list for the specified model
    
    Args:
        model (str): The car model
        model_type (str): The model type to validate
        
    Returns:
        tuple: (valid_type, suggestion_list)
            - valid_type: The corrected type or None if no match
            - suggestion_list: List of suggested types if no exact match
    """
    if not model or not model_type:
        return None, []
    
    # Get valid types for the model
    valid_types = get_valid_types_for_model(model)
    if not valid_types:
        return None, MODEL_TYPES_BY_MODEL["DEFAULT"]
    
    # Check for exact match (case-insensitive)
    type_lower = model_type.lower()
    for valid_type in valid_types:
        if valid_type.lower() == type_lower:
            return valid_type, []
    
    # Try to find best match using fuzzy matching
    best_match = find_best_match(model_type, valid_types, threshold=0.7)
    if best_match:
        return best_match, []
    
    # If no good match, return all valid types as suggestions
    return None, valid_types

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

def validate_year(year):
    """
    Validate a car year is reasonable
    
    Args:
        year (str): The car year to validate
        
    Returns:
        tuple: (valid_year, error_message)
            - valid_year: The year as a string if valid, None if invalid
            - error_message: Error message if invalid, None if valid
    """
    if not year:
        return None, "Year is required"
    
    try:
        year_int = int(year)
        current_year = datetime.now().year
        
        # Check if year is reasonable (between 1950 and current year + 1)
        if year_int < 1950:
            return None, f"Year {year} seems too old. Please provide a year between 1950 and {current_year + 1}"
        
        if year_int > current_year + 1:
            return None, f"Year {year} is in the future. Please provide a year between 1950 and {current_year + 1}"
        
        return str(year_int), None
    except ValueError:
        return None, f"'{year}' is not a valid year. Please provide a numeric year (e.g., 2020)"

def validate_id_number(id_number):
    """
    Validate a South African ID number
    
    Args:
        id_number (str): The ID number to validate
        
    Returns:
        tuple: (valid_id, error_message)
            - valid_id: The formatted ID if valid, None if invalid
            - error_message: Error message if invalid, None if valid
    """
    if not id_number:
        return None, "ID number is required"
    
    # Remove any spaces or hyphens
    id_clean = re.sub(r'[\s-]', '', id_number)
    
    # Check if it's a 13-digit number
    if not re.match(r'^\d{13}$', id_clean):
        return None, "South African ID number must be 13 digits"
    
    # Additional validation could be added here (checksum, date validation)
    
    return id_clean, None

def validate_email(email):
    """
    Validate an email address
    
    Args:
        email (str): The email address to validate
        
    Returns:
        tuple: (valid_email, error_message)
            - valid_email: The normalized email if valid, None if invalid
            - error_message: Error message if invalid, None if valid
    """
    if not email:
        return None, "Email address is required"
    
    # Simple regex pattern for email validation
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        return None, "Invalid email format"
    
    # Check for common mistakes
    if '..' in email or email.startswith('.') or email.endswith('.'):
        return None, "Email contains consecutive dots or starts/ends with a dot"
    
    # Check domain
    domain = email.split('@')[1]
    if len(domain) > 255:
        return None, "Email domain is too long"
    
    # Simple normalization - lowercase the domain part
    local_part, domain = email.split('@')
    normalized_email = f"{local_part}@{domain.lower()}"
    
    return normalized_email, None

def validate_phone_number(phone):
    """
    Validate a South African phone number
    
    Args:
        phone (str): The phone number to validate
        
    Returns:
        tuple: (valid_phone, error_message)
            - valid_phone: The formatted phone if valid, None if invalid
            - error_message: Error message if invalid, None if valid
    """
    if not phone:
        return None, "Phone number is required"
    
    # Remove any spaces, hyphens, or brackets
    phone_clean = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check if it starts with +27 and convert to 0
    if phone_clean.startswith('+27'):
        phone_clean = '0' + phone_clean[3:]
    
    # Check if it's a valid SA number format
    if not re.match(r'^0\d{9}$', phone_clean):
        return None, "South African phone number must be 10 digits starting with 0"
    
    return phone_clean, None

def validate_name(name):
    """
    Validate a name input
    
    Args:
        name (str): The name to validate
        
    Returns:
        tuple: (valid_name, error_message)
            - valid_name: The formatted name if valid, None if invalid
            - error_message: Error message if invalid, None if valid
    """
    if not name:
        return None, "Name is required"
    
    # Trim whitespace
    name = name.strip()
    
    # Check if it contains at least a first and last name
    parts = name.split()
    if len(parts) < 2:
        return None, "Please provide both your first and last name"
    
    # Check for test or profanity indicators (simplified check)
    test_terms = ["test", "tester", "testing", "abc", "xyz", "123", "fuck", "shit", "dummy"]
    for part in parts:
        if part.lower() in test_terms:
            return None, "Please provide your actual name"
    
    # Format: Capitalize each part
    formatted_name = " ".join(part.capitalize() for part in parts)
    
    return formatted_name, None

def is_off_topic_query(query):
    """
    Detects if a user query is not related to car insurance quotes
    
    Args:
        query (str): The user message to analyze
        
    Returns:
        bool: True if the query is off-topic, False if it's car insurance-related
    """
    # Convert to lowercase for easier matching
    query_lower = query.lower()
    
    # Car insurance-related keywords
    insurance_keywords = [
        'insurance', 'policy', 'premium', 'coverage', 'accident', 
        'damage', 'quote', 'vehicle', 'car', 'auto', 'liability', 
        'excess', 'deductible', 'insure', 'underwriting', 'risk', 
        'cover', 'third-party', 'third party', 'comprehensive', 
        'registration', 'financed', 'toyota', 'bmw', 'ford', 'vehicle', 
        'honda', 'color', 'model', 'make', 'year', 'parking',
        'security', 'theft', 'value', 'id number', 'name', 'mazda', 
        'volkswagen', 'audi', 'hyundai', 'kia', 'volvo', 'jeep',
        'tracking', 'device', 'driver', 'regular', 'marital', 'employment'
    ]
    
    # Check if the query contains any car insurance-related keywords
    for keyword in insurance_keywords:
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
    
    # For short queries (1-3 words) without insurance keywords, we'll be lenient
    if len(query_lower.split()) <= 3:
        return False
    
    # For longer queries without insurance keywords, likely off-topic
    if len(query_lower.split()) > 5:
        return True
    
    # If we can't determine clearly, default to on-topic to avoid false positives
    return False

def generate_quote_summary(extraction_data):
    """
    Generate a summary of collected information for the car insurance quote
    
    Args:
        extraction_data (dict): The collected vehicle information
        
    Returns:
        str: A summary string for the car insurance quote
    """
    # Ensure all fields are present with proper formatting
    data = ensure_complete_data(extraction_data)
    
    # Personal information
    customer_name = data.get("customer_name", "Not provided")
    id_number = data.get("id_number", "Not provided")
    gender = data.get("gender", "Not provided")
    cellphone_number = data.get("cellphone_number", "Not provided")
    email_address = data.get("email_address", "Not provided")
    marital_status = data.get("marital_status", "Not provided")
    employment_status = data.get("employment_status", "Not provided")
    is_regular_driver = "Yes" if data.get("is_regular_driver") else "No"
    
    # Vehicle details
    make = data.get("make", "Not provided")
    model = data.get("model", "Not provided")
    model_type = data.get("model_type", "Not provided")
    year = data.get("year", "Not provided")
    color = data.get("color", "Not provided")
    usage = data.get("usage", "Not provided")
    
    # Format Boolean values nicely
    is_registered_in_sa = "Yes" if data.get("is_registered_in_sa") else "No"
    is_financed = "Yes" if data.get("is_financed") else "No"
    has_tracking_device = "Yes" if data.get("has_tracking_device") else "No"
    
    # Coverage details
    cover_type = data.get("cover_type", "Not provided")
    insured_value = data.get("insured_value", "Not provided")
    
    # Risk details - Night
    night_parking_area = data.get("night_parking_area", "Not provided")
    night_parking_location = data.get("night_parking_location", "Not provided")
    night_parking_security = data.get("night_parking_security", [])
    
    # Risk details - Day
    day_parking_area = data.get("day_parking_area", "Not provided")
    day_parking_location = data.get("day_parking_location", "Not provided")
    day_parking_security = data.get("day_parking_security", [])
    
    # Format security as comma-separated lists
    night_security_str = ", ".join(night_parking_security) if night_parking_security else "None"
    day_security_str = ", ".join(day_parking_security) if day_parking_security else "None"
    
    # Build summary
    summary = "Here's a summary of your car insurance quote information:\n\n"
    
    summary += "Personal Information:\n"
    summary += f"- Name: {customer_name}\n"
    summary += f"- ID Number: {id_number}\n"
    summary += f"- Gender: {gender}\n"
    summary += f"- Cellphone: {cellphone_number}\n"
    summary += f"- Email: {email_address}\n"
    summary += f"- Marital Status: {marital_status}\n"
    summary += f"- Employment Status: {employment_status}\n"
    summary += f"- Regular Driver: {is_regular_driver}\n\n"
    
    summary += "Vehicle Details:\n"
    summary += f"- Make: {make}\n"
    summary += f"- Model: {model}\n"
    summary += f"- Type: {model_type}\n"
    summary += f"- Year: {year}\n"
    summary += f"- Color: {color}\n"
    summary += f"- Usage: {usage}\n"
    summary += f"- Registered in South Africa: {is_registered_in_sa}\n"
    summary += f"- Vehicle Financed: {is_financed}\n"
    summary += f"- Tracking Device Installed: {has_tracking_device}\n\n"
    
    summary += "Coverage Preferences:\n"
    summary += f"- Cover Type: {cover_type}\n"
    summary += f"- Insured Value: {insured_value}\n\n"
    
    summary += "Risk Information - Night:\n"
    summary += f"- Night Parking Area: {night_parking_area}\n"
    summary += f"- Night Parking Location: {night_parking_location}\n"
    summary += f"- Night Parking Security: {night_security_str}\n\n"
    
    summary += "Risk Information - Day:\n"
    summary += f"- Day Parking Area: {day_parking_area}\n"
    summary += f"- Day Parking Location: {day_parking_location}\n"
    summary += f"- Day Parking Security: {day_security_str}\n\n"
    
    summary += "Your quote information has been received. A representative will contact you shortly with your premium details and next steps."
    
    return summary

def check_if_quote_complete(extraction_data):
    """
    Check if all required information has been collected for a car insurance quote
    
    Args:
        extraction_data (dict): The extraction data
        
    Returns:
        bool: True if complete, False otherwise
    """
    # Check if all required fields are present and have values
    for field in QUESTION_FLOW:
        if field not in extraction_data or extraction_data[field] is None:
            # Special case for array fields
            if field in ["night_parking_security", "day_parking_security"]:
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
    # Initialize extraction_data if not present
    if "extraction_data" not in conversation:
        conversation["extraction_data"] = {}
    
    # Convert message to lowercase for matching
    message_lower = user_message.lower()
    
    # Extract car make
    for make in CAR_MAKES:
        if make.lower() in message_lower:
            valid_make, _ = validate_make(make)
            if valid_make:
                conversation["extraction_data"]["make"] = valid_make
            break
    
    # Extract car model if we know the make
    if "make" in conversation["extraction_data"]:
        make = conversation["extraction_data"]["make"]
        valid_models = get_valid_models_for_make(make)
        
        for model in valid_models:
            if model.lower() in message_lower:
                conversation["extraction_data"]["model"] = model
                break
    
    # Extract model type if we know the model
    if "model" in conversation["extraction_data"]:
        model = conversation["extraction_data"]["model"]
        valid_types = get_valid_types_for_model(model)
        
        for model_type in valid_types:
            if model_type.lower() in message_lower:
                conversation["extraction_data"]["model_type"] = model_type
                break
    
    # Extract car color
    for color in CAR_COLORS:
        if color.lower() in message_lower:
            valid_color, _ = validate_color(color)
            if valid_color:
                conversation["extraction_data"]["color"] = valid_color
            break
    
    # Extract car year - look for 4-digit numbers
    year_matches = re.findall(r'\b(19[5-9]\d|20[0-2]\d)\b', message_lower)
    if year_matches:
        valid_year, _ = validate_year(year_matches[0])
        if valid_year:
            conversation["extraction_data"]["year"] = valid_year
    
    # Extract usage type
    for usage_type in VEHICLE_USAGE_TYPES:
        if usage_type.lower() in message_lower:
            conversation["extraction_data"]["usage"] = usage_type
            break
    
    # Extract registration status
    if "registered" in message_lower:
        affirmative = any(word in message_lower for word in 
                         ["yes", "yeah", "yep", "correct", "it is", "that's right", 
                          "affirmative", "indeed", "registered"])
        negative = any(word in message_lower for word in 
                      ["no", "nope", "not", "isn't", "is not", "negative", "unregistered"])
        
        if affirmative and not negative:
            conversation["extraction_data"]["is_registered_in_sa"] = True
        elif negative and not affirmative:
            conversation["extraction_data"]["is_registered_in_sa"] = False
    
    # Extract financing status
    if "financed" in message_lower or "finance" in message_lower:
        affirmative = any(word in message_lower for word in 
                         ["yes", "yeah", "yep", "correct", "it is", "that's right", 
                          "affirmative", "indeed", "financed"])
        negative = any(word in message_lower for word in 
                      ["no", "nope", "not", "isn't", "is not", "negative", "paid off", "fully paid"])
        
        if affirmative and not negative:
            conversation["extraction_data"]["is_financed"] = True
        elif negative and not affirmative:
            conversation["extraction_data"]["is_financed"] = False
    
    # Extract tracking device status
    if "tracking" in message_lower or "device" in message_lower:
        affirmative = any(word in message_lower for word in 
                         ["yes", "yeah", "yep", "correct", "it is", "that's right", 
                          "affirmative", "indeed", "installed", "have"])
        negative = any(word in message_lower for word in 
                      ["no", "nope", "not", "isn't", "is not", "negative", "don't have"])
        
        if affirmative and not negative:
            conversation["extraction_data"]["has_tracking_device"] = True
        elif negative and not affirmative:
            conversation["extraction_data"]["has_tracking_device"] = False
    
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
    
    # Extract parking locations
    for location in PARKING_LOCATIONS:
        if location.lower() in message_lower:
            # Determine if it's night or day parking based on context
            if "night" in message_lower or "evening" in message_lower:
                conversation["extraction_data"]["night_parking_location"] = location
            elif "day" in message_lower or "daytime" in message_lower:
                conversation["extraction_data"]["day_parking_location"] = location
            # Default to night if not specified
            else:
                conversation["extraction_data"]["night_parking_location"] = location
            break
    
    # Extract parking security (multiple selection)
    security_types = []
    for security_type in PARKING_SECURITY_TYPES:
        if security_type.lower() in message_lower:
            security_types.append(security_type)
    
    if security_types:
        # Determine if it's night or day security based on context
        if "night" in message_lower or "evening" in message_lower:
            conversation["extraction_data"]["night_parking_security"] = security_types
        elif "day" in message_lower or "daytime" in message_lower:
            conversation["extraction_data"]["day_parking_security"] = security_types
        # Default to night if not specified
        else:
            conversation["extraction_data"]["night_parking_security"] = security_types
    
    # Extract ID number - look for digit sequences that could be ID numbers
    id_matches = re.findall(r'\b\d{13}\b', message_lower)
    if id_matches:
        valid_id, _ = validate_id_number(id_matches[0])
        if valid_id:
            conversation["extraction_data"]["id_number"] = valid_id
    
    # Extract gender
    if "male" in message_lower and "female" not in message_lower:
        conversation["extraction_data"]["gender"] = "Male"
    elif "female" in message_lower:
        conversation["extraction_data"]["gender"] = "Female"
    
    # Extract employment status
    for status in EMPLOYMENT_STATUS_OPTIONS:
        if status.lower() in message_lower:
            conversation["extraction_data"]["employment_status"] = status
            break
    
    # Extract marital status
    for status in MARITAL_STATUS_OPTIONS:
        if status.lower() in message_lower:
            conversation["extraction_data"]["marital_status"] = status
            break
    
    # Extract regular driver status
    if "regular driver" in message_lower:
        affirmative = any(word in message_lower for word in 
                         ["yes", "yeah", "yep", "correct", "i am", "i will", "that's right", 
                          "affirmative", "indeed"])
        negative = any(word in message_lower for word in 
                      ["no", "nope", "not", "isn't", "is not", "negative", "won't be"])
        
        if affirmative and not negative:
            conversation["extraction_data"]["is_regular_driver"] = True
        elif negative and not affirmative:
            conversation["extraction_data"]["is_regular_driver"] = False
    
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
        
        if function_name == "collect_car_info":
            # Update extraction data with collected information, applying validation
            for key, value in function_args.items():
                if value:  # Only update if value is not None or empty
                    # Apply validation for specific fields
                    if key == "make":
                        valid_make, _ = validate_make(value)
                        if valid_make:  # Only set if it's a valid make
                            conversation["extraction_data"][key] = valid_make
                    elif key == "model" and "make" in conversation["extraction_data"]:
                        valid_model, _ = validate_model(conversation["extraction_data"]["make"], value)
                        if valid_model:
                            conversation["extraction_data"][key] = valid_model
                    elif key == "model_type" and "model" in conversation["extraction_data"]:
                        valid_type, _ = validate_model_type(conversation["extraction_data"]["model"], value)
                        if valid_type:
                            conversation["extraction_data"][key] = valid_type
                    elif key == "color":
                        valid_color, _ = validate_color(value)
                        if valid_color:  # Only set if it's a valid color
                            conversation["extraction_data"][key] = valid_color
                    elif key == "year":
                        valid_year, _ = validate_year(value)
                        if valid_year:
                            conversation["extraction_data"][key] = valid_year
                    elif key == "id_number":
                        valid_id, _ = validate_id_number(value)
                        if valid_id:
                            conversation["extraction_data"][key] = valid_id
                    elif key == "email_address":
                        valid_email, _ = validate_email(value)
                        if valid_email:
                            conversation["extraction_data"][key] = valid_email
                    elif key == "cellphone_number":
                        valid_phone, _ = validate_phone_number(value)
                        if valid_phone:
                            conversation["extraction_data"][key] = valid_phone
                    elif key == "customer_name":
                        valid_name, _ = validate_name(value)
                        if valid_name:
                            conversation["extraction_data"][key] = valid_name
                    elif key in ["night_parking_security", "day_parking_security"]:
                        if isinstance(value, list):
                            valid_securities = []
                            for security in value:
                                if security in PARKING_SECURITY_TYPES:
                                    valid_securities.append(security)
                            if valid_securities:
                                conversation["extraction_data"][key] = valid_securities
                        elif value in PARKING_SECURITY_TYPES:
                            conversation["extraction_data"][key] = [value]
                    else:
                        # For other fields, set directly
                        conversation["extraction_data"][key] = value
            
            # Prepare response
            result = {
                "success": True,
                "message": "Information collected successfully"
            }
        
        elif function_name == "process_quote":
            # Update extraction data from nested objects, applying validation
            
            # Customer details
            if "customer_details" in function_args:
                for key, value in function_args["customer_details"].items():
                    if key == "id_number":
                        valid_id, _ = validate_id_number(value)
                        if valid_id:
                            conversation["extraction_data"][key] = valid_id
                    elif key == "email_address":
                        valid_email, _ = validate_email(value)
                        if valid_email:
                            conversation["extraction_data"][key] = valid_email
                    elif key == "cellphone_number":
                        valid_phone, _ = validate_phone_number(value)
                        if valid_phone:
                            conversation["extraction_data"][key] = valid_phone
                    elif key == "customer_name":
                        valid_name, _ = validate_name(value)
                        if valid_name:
                            conversation["extraction_data"][key] = valid_name
                    else:
                        # For other fields, set directly
                        conversation["extraction_data"][key] = value
            
            # Vehicle details
            if "vehicle_details" in function_args:
                for key, value in function_args["vehicle_details"].items():
                    if key == "make":
                        valid_make, _ = validate_make(value)
                        if valid_make:
                            conversation["extraction_data"][key] = valid_make
                    elif key == "model":
                        make = function_args["vehicle_details"].get("make") or conversation["extraction_data"].get("make")
                        if make:
                            valid_model, _ = validate_model(make, value)
                            if valid_model:
                                conversation["extraction_data"][key] = valid_model
                    elif key == "model_type":
                        model = function_args["vehicle_details"].get("model") or conversation["extraction_data"].get("model")
                        if model:
                            valid_type, _ = validate_model_type(model, value)
                            if valid_type:
                                conversation["extraction_data"][key] = valid_type
                    elif key == "color":
                        valid_color, _ = validate_color(value)
                        if valid_color:
                            conversation["extraction_data"][key] = valid_color
                    elif key == "year":
                        valid_year, _ = validate_year(value)
                        if valid_year:
                            conversation["extraction_data"][key] = valid_year
                    else:
                        # For other fields, set directly
                        conversation["extraction_data"][key] = value
            
            # Coverage details
            if "coverage_details" in function_args:
                for key, value in function_args["coverage_details"].items():
                    conversation["extraction_data"][key] = value
            
            # Risk details
            if "risk_details" in function_args:
                for key, value in function_args["risk_details"].items():
                    if key in ["night_parking_security", "day_parking_security"]:
                        if isinstance(value, list):
                            valid_securities = []
                            for security in value:
                                if security in PARKING_SECURITY_TYPES:
                                    valid_securities.append(security)
                            if valid_securities:
                                conversation["extraction_data"][key] = valid_securities
                        elif value in PARKING_SECURITY_TYPES:
                            conversation["extraction_data"][key] = [value]
                    else:
                        # For other fields, set directly
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
    messages.append({"role": "system", "content": CAR_INSURANCE_SYSTEM_MESSAGE})
    
    # Add conversation history
    for msg in conversation.get("messages", []):
        role = msg.get("role")
            
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
        
        # Check if container exists
        try:
            container_client = blob_service_client.get_container_client(CAR_INSURANCE_CONVERSATION_CONTAINER)
            container_client.get_container_properties()  # Will raise if container doesn't exist
        except Exception as e:
            if "ContainerNotFound" in str(e):
                logger.warning(f"Container {CAR_INSURANCE_CONVERSATION_CONTAINER} not found - conversation cannot exist yet")
                return None, f"Conversation container not found: {CAR_INSURANCE_CONVERSATION_CONTAINER}"
            else:
                raise
        
        # Get blob client
        blob_client = container_client.get_blob_client(f"{conversation_id}.json")
        
        # Download blob
        try:
            blob_data = blob_client.download_blob().readall().decode('utf-8')
        except Exception as e:
            if "BlobNotFound" in str(e):
                return None, f"Conversation not found with ID: {conversation_id}"
            else:
                raise
        
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
        # Ensure container exists - create it if it doesn't
        try:
            ensure_container_exists(CAR_INSURANCE_CONVERSATION_CONTAINER)
        except Exception as container_error:
            logger.warning(f"Error ensuring container exists, will attempt to create directly: {str(container_error)}")
            # Direct container creation as fallback
            blob_service_client = get_azure_blob_client()
            try:
                container_client = blob_service_client.create_container(CAR_INSURANCE_CONVERSATION_CONTAINER)
                logger.info(f"Container {CAR_INSURANCE_CONVERSATION_CONTAINER} created directly")
            except Exception as direct_create_error:
                if "ContainerAlreadyExists" in str(direct_create_error):
                    logger.info(f"Container {CAR_INSURANCE_CONVERSATION_CONTAINER} already exists")
                else:
                    logger.error(f"Failed to create container directly: {str(direct_create_error)}")
                    raise
        
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(CAR_INSURANCE_CONVERSATION_CONTAINER)
        
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
        
        # Check if container exists
        try:
            container_client = blob_service_client.get_container_client(CAR_INSURANCE_CONVERSATION_CONTAINER)
            container_client.get_container_properties()  # Will raise if container doesn't exist
        except Exception as e:
            if "ContainerNotFound" in str(e):
                logger.warning(f"Container {CAR_INSURANCE_CONVERSATION_CONTAINER} not found - nothing to delete")
                return True, None  # Consider it a success since there's nothing to delete
            else:
                raise
        
        # Get blob client
        blob_client = container_client.get_blob_client(f"{conversation_id}.json")
        
        # Delete blob
        try:
            blob_client.delete_blob()
        except Exception as e:
            if "BlobNotFound" in str(e):
                logger.warning(f"Conversation not found with ID: {conversation_id} - nothing to delete")
                return True, None  # Consider it a success since there's nothing to delete
            else:
                raise
        
        return True, None
    except Exception as e:
        logger.error(f"Error deleting conversation history: {str(e)}")
        return False, str(e)

def get_next_question_options(conversation):
    """
    Get options for the next question to ask based on conversation state
    
    Args:
        conversation (dict): The conversation object
        
    Returns:
        dict: Options for the next question
    """
    extracted_data = conversation.get("extraction_data", {})
    
    # Determine which question to ask next based on what's already been collected
    for field in QUESTION_FLOW:
        if field not in extracted_data or extracted_data[field] is None:
            # Found the next question to ask
            options = {}
            
            if field == "make":
                options = {"make": CAR_MAKES}
            elif field == "model" and "make" in extracted_data:
                options = {"model": get_valid_models_for_make(extracted_data["make"])}
            elif field == "model_type" and "model" in extracted_data:
                options = {"model_type": get_valid_types_for_model(extracted_data["model"])}
            elif field == "color":
                options = {"color": CAR_COLORS}
            elif field == "usage":
                options = {"usage": VEHICLE_USAGE_TYPES, "descriptions": VEHICLE_USAGE_DESCRIPTIONS}
            elif field == "is_registered_in_sa":
                options = {"is_registered_in_sa": ["Yes", "No"]}
            elif field == "is_financed":
                options = {"is_financed": ["Yes", "No"]}
            elif field == "cover_type":
                options = {"cover_type": COVER_TYPES, "descriptions": COVER_TYPE_DESCRIPTIONS}
            elif field == "insured_value":
                options = {"insured_value": INSURED_VALUE_OPTIONS, "descriptions": INSURED_VALUE_DESCRIPTIONS}
            elif field == "night_parking_location":
                options = {"night_parking_location": PARKING_LOCATIONS}
            elif field == "night_parking_security":
                options = {"night_parking_security": PARKING_SECURITY_TYPES, "multiselect": True}
            elif field == "day_parking_location":
                options = {"day_parking_location": PARKING_LOCATIONS}
            elif field == "day_parking_security":
                options = {"day_parking_security": PARKING_SECURITY_TYPES, "multiselect": True}
            elif field == "has_tracking_device":
                options = {"has_tracking_device": ["Yes", "No"]}
            elif field == "gender":
                options = {"gender": ["Male", "Female"]}
            elif field == "marital_status":
                options = {"marital_status": MARITAL_STATUS_OPTIONS}
            elif field == "employment_status":
                options = {"employment_status": EMPLOYMENT_STATUS_OPTIONS}
            elif field == "is_regular_driver":
                options = {"is_regular_driver": ["Yes", "No"]}
                
            return options
    
    # If all fields are filled, no more options needed
    return {}
