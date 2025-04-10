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
from datetime import datetime, timedelta
from apis.utils.llmServices import get_openai_client

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI client
openai_client = get_openai_client()

# Define container for insurance conversation histories
INSURANCE_CONVERSATION_CONTAINER = "insurance-bot-conversations"
STORAGE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT")
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{INSURANCE_CONVERSATION_CONTAINER}"

# Define cost in credits for using the insurance bot
INSURANCE_BOT_CREDIT_COST = 1

# Define GPT-4o deployment model
GPT4O_DEPLOYMENT = "gpt-4o"

# Predefined lists for vehicle data validation
CAR_MAKES = [
    "Toyota", "Honda", "Ford", "Volkswagen", "BMW", "Mercedes-Benz", "Audi", 
    "Nissan", "Hyundai", "Kia", "Mazda", "Subaru", "Lexus", "Chevrolet", 
    "Jeep", "Volvo", "Land Rover", "Porsche", "Ferrari", "Tesla"
]

# Dictionary mapping makes to their models
CAR_MODELS_BY_MAKE = {
    "Toyota": ["Corolla", "Camry", "RAV4", "Fortuner", "Hilux", "Land Cruiser", "Avanza", "Yaris"],
    "Honda": ["Civic", "Accord", "CR-V", "Pilot", "Fit", "HR-V", "Odyssey"],
    "Ford": ["Mustang", "F-150", "Ranger", "Explorer", "Escape", "Focus", "Fiesta"],
    "Volkswagen": ["Golf", "Polo", "Tiguan", "Passat", "Jetta", "Touareg", "Amarok"],
    "BMW": ["3 Series", "5 Series", "7 Series", "X3", "X5", "X7", "i3", "i8"],
    "Mercedes-Benz": ["C-Class", "E-Class", "S-Class", "GLA", "GLC", "GLE", "G-Class"],
    "Audi": ["A3", "A4", "A6", "Q3", "Q5", "Q7", "TT", "R8"],
    "Nissan": ["Micra", "Almera", "Sentra", "Altima", "X-Trail", "Qashqai", "Navara", "GTR"],
    "Hyundai": ["i10", "i20", "i30", "Tucson", "Santa Fe", "Creta", "Venue", "Kona"],
    "Kia": ["Picanto", "Rio", "Cerato", "Sportage", "Sorento", "Seltos", "Soul"],
    "Mazda": ["Mazda2", "Mazda3", "Mazda6", "CX-3", "CX-5", "CX-9", "MX-5"],
    "Subaru": ["Impreza", "Legacy", "Outback", "Forester", "XV", "WRX", "BRZ"],
    "Lexus": ["IS", "ES", "LS", "UX", "NX", "RX", "LX", "RC", "LC"],
    "Chevrolet": ["Spark", "Cruze", "Malibu", "Trailblazer", "Captiva", "Silverado"],
    "Jeep": ["Renegade", "Compass", "Cherokee", "Grand Cherokee", "Wrangler", "Gladiator"],
    "Volvo": ["S60", "S90", "V60", "V90", "XC40", "XC60", "XC90"],
    "Land Rover": ["Discovery", "Discovery Sport", "Range Rover", "Range Rover Sport", "Range Rover Evoque", "Defender"],
    "Porsche": ["911", "Boxster", "Cayman", "Panamera", "Cayenne", "Macan", "Taycan"],
    "Ferrari": ["488", "F8 Tributo", "812", "Roma", "SF90", "Portofino"],
    "Tesla": ["Model 3", "Model S", "Model X", "Model Y", "Cybertruck"]
}

# Car colors
CAR_COLORS = [
    "Black", "White", "Silver", "Gray", "Red", "Blue", "Green", 
    "Yellow", "Brown", "Orange", "Purple", "Gold", "Bronze", "Beige"
]

# Vehicle usage types
VEHICLE_USAGE_TYPES = [
    "Private and/or travelling to work",
    "Private and occasional business",
    "Private and full business"
]

# Define system message for insurance bot - This guides GPT-4o on how to behave
INSURANCE_BOT_SYSTEM_MESSAGE = """
You are InsuranceBot, a helpful insurance customer service assistant. Your job is to help customers with various insurance-related needs:

1. Getting insurance quotes
2. Managing existing policies 
3. Submitting claims
4. Checking coverage details
5. Requesting callbacks

You maintain a friendly, professional tone and follow conversation flows for each scenario. When specific customer information is needed, you collect it step by step.

Important rules:
- Speak in clear, simple language avoiding insurance jargon
- Confirm you understand the customer's request before proceeding
- If a user asks about topics unrelated to insurance services, politely redirect them
- Never make up policy or customer information
- Maintain customer privacy and handle personal information securely

Use the available tools when appropriate:
- Use get_policy_details when you need to look up a customer's policy information
- Use update_policy_address when a customer wants to change their address
- Use get_quote when a customer has provided all information needed for a quote
- Use submit_claim when a customer has provided all information for a claim

Follow these conversation flows based on customer needs:

FOR INSURANCE QUOTES:
- First ask what they want to insure (vehicle, home, contents)

FOR VEHICLE INSURANCE QUOTES:
- Collect personal details (name, ID number)
- Ask what make of car they want to insure (e.g., Toyota, BMW, Ford)
  * Match their response to our predefined list of car makes
  * If no match is found, suggest close alternatives
- Ask for the year of the vehicle (e.g., 2018, 2022)
- Ask for the model of the vehicle (e.g., Corolla, 5 Series, Ranger)
  * Models should match the previously selected make
  * If no match is found, suggest models available for that make
- Ask for the color of the car (e.g., Red, White, Black)
  * Match their response to our predefined list of colors
- Ask what the car will be used for, with these specific options:
  1. Private and/or travelling to work
  2. Private and occasional business
  3. Private and full business
  * If the user's response doesn't match one of these options, ask them to select a valid option
- Ask if the car is registered in South Africa (Yes or No)
- Ask if the car is financed (Yes or No)
- Once you have all required information, use the get_quote tool

FOR HOME INSURANCE QUOTES:
- Collect personal details (name, ID number)
- Collect relevant property information (address, type of home)
- Once you have all required information, use the get_quote tool

FOR CONTENTS INSURANCE QUOTES:
- Collect personal details (name, ID number)
- Collect address information
- Ask for estimated value of contents
- Once you have all required information, use the get_quote tool

FOR POLICY MANAGEMENT:
- Request policy number or ID number for verification
- Call get_policy_details to retrieve current information
- Ask what they want to change
- For address changes: confirm current address, then collect new address and use update_policy_address
- For other changes: collect relevant information and inform the user you'll process the change

FOR CLAIM SUBMISSIONS:
- Request policy number
- Call get_policy_details to verify the policy exists
- Ask for incident details (date, time, what happened)
- Ask for supporting information
- Once you have all the required information, use the submit_claim tool

You'll respond conversationally while making appropriate use of tools when needed. Always keep track of where you are in the conversation flow and what information you still need to collect.

As you collect information, you should extract and store the relevant details for later use in the quote process. Be especially careful to match vehicle makes, models, and colors to our predefined lists.
"""

# Conversation state codes
CONVERSATION_STATE = {
    "NEW": "new_conversation",
    "QUOTE_FLOW": "insurance_quote",
    "POLICY_MANAGEMENT": "policy_management",
    "CLAIM_SUBMISSION": "claim_submission",
    "COVER_DETAILS": "cover_details",
    "CALLBACK_REQUEST": "callback_request",
    "GENERAL_QUERY": "general_query"
}

# Define tools for GPT-4o function calling
INSURANCE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_policy_details",
            "description": "Get details of a customer's insurance policy using their policy number",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_number": {
                        "type": "string",
                        "description": "The customer's policy number"
                    }
                },
                "required": ["policy_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_policy_address",
            "description": "Update the address on a customer's insurance policy",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_number": {
                        "type": "string",
                        "description": "The customer's policy number"
                    },
                    "new_address": {
                        "type": "string",
                        "description": "The customer's new address"
                    }
                },
                "required": ["policy_number", "new_address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_quote",
            "description": "Generate an insurance quote based on customer information",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The customer's full name"
                    },
                    "id_number": {
                        "type": "string",
                        "description": "The customer's ID number"
                    },
                    "insurance_type": {
                        "type": "string",
                        "description": "Type of insurance (vehicle, home, contents)",
                        "enum": ["vehicle", "home", "contents"]
                    },
                    "address": {
                        "type": "string",
                        "description": "The customer's address"
                    },
                    "vehicle_details": {
                        "type": "object",
                        "description": "Details specific to vehicle insurance",
                        "properties": {
                            "make": {
                                "type": "string",
                                "description": "Make of the vehicle (e.g., Toyota, BMW)"
                            },
                            "model": {
                                "type": "string",
                                "description": "Model of the vehicle (e.g., Corolla, X5)"
                            },
                            "year": {
                                "type": "string",
                                "description": "Year of the vehicle (e.g., 2020)"
                            },
                            "color": {
                                "type": "string",
                                "description": "Color of the vehicle"
                            },
                            "usage": {
                                "type": "string",
                                "description": "How the vehicle will be used",
                                "enum": [
                                    "Private and/or travelling to work",
                                    "Private and occasional business",
                                    "Private and full business"
                                ]
                            },
                            "is_registered_in_sa": {
                                "type": "boolean",
                                "description": "Whether the vehicle is registered in South Africa"
                            },
                            "is_financed": {
                                "type": "boolean",
                                "description": "Whether the vehicle is financed"
                            }
                        },
                        "required": ["make", "model", "year", "color", "usage", "is_registered_in_sa", "is_financed"]
                    },
                    "home_details": {
                        "type": "object",
                        "description": "Details specific to home insurance",
                        "properties": {
                            "home_type": {
                                "type": "string",
                                "description": "Type of home (e.g., apartment, house)"
                            }
                        }
                    },
                    "contents_details": {
                        "type": "object",
                        "description": "Details specific to contents insurance",
                        "properties": {
                            "contents_value": {
                                "type": "string",
                                "description": "Estimated value of contents"
                            }
                        }
                    }
                },
                "required": ["customer_name", "id_number", "insurance_type", "address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_claim",
            "description": "Submit an insurance claim",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_number": {
                        "type": "string",
                        "description": "The customer's policy number"
                    },
                    "incident_date": {
                        "type": "string",
                        "description": "Date when the incident occurred (YYYY-MM-DD)"
                    },
                    "incident_description": {
                        "type": "string",
                        "description": "Description of what happened"
                    },
                    "claim_type": {
                        "type": "string",
                        "description": "Type of claim (vehicle, home, contents)",
                        "enum": ["vehicle", "home", "contents"]
                    }
                },
                "required": ["policy_number", "incident_date", "incident_description", "claim_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_callback",
            "description": "Schedule a callback from a customer service representative",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The customer's name"
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "Customer's phone number"
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "Preferred time for callback (morning, afternoon, evening)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the callback request"
                    }
                },
                "required": ["customer_name", "phone_number"]
            }
        }
    }
]

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

# Functions for handling extraction data
def update_extraction_data(conversation, field, value):
    """Add or update extraction data in the conversation"""
    if "extraction_data" not in conversation:
        conversation["extraction_data"] = {}
    
    # For vehicle details, store in a nested structure
    if field.startswith("vehicle_"):
        if "vehicle" not in conversation["extraction_data"]:
            conversation["extraction_data"]["vehicle"] = {}
        # Remove the "vehicle_" prefix and store in the vehicle object
        actual_key = field[8:]  # Remove "vehicle_" prefix
        conversation["extraction_data"]["vehicle"][actual_key] = value
    elif field.startswith("home_"):
        if "home" not in conversation["extraction_data"]:
            conversation["extraction_data"]["home"] = {}
        # Remove the "home_" prefix
        actual_key = field[5:]
        conversation["extraction_data"]["home"][actual_key] = value
    elif field.startswith("contents_"):
        if "contents" not in conversation["extraction_data"]:
            conversation["extraction_data"]["contents"] = {}
        # Remove the "contents_" prefix
        actual_key = field[9:]
        conversation["extraction_data"]["contents"][actual_key] = value
    else:
        # Store directly in the extraction data
        conversation["extraction_data"][field] = value
    
    return conversation

def extract_info_from_messages(conversation):
    """
    Extract information from conversation messages using rules-based approaches.
    This supplements the AI's own extraction capabilities.
    """
    if "extraction_data" not in conversation:
        conversation["extraction_data"] = {}
    
    # Get the messages from the conversation
    messages = conversation.get("messages", [])
    
    # Track what type of insurance the user is interested in
    insurance_type = conversation["extraction_data"].get("insurance_type")
    
    for i, message in enumerate(messages):
        if message.get("role") == "user":
            user_message = message.get("content", "").lower()
            
            # Try to identify insurance type if not already set
            if not insurance_type:
                if "vehicle" in user_message or "car" in user_message or "auto" in user_message:
                    insurance_type = "vehicle"
                    conversation["extraction_data"]["insurance_type"] = "vehicle"
                elif "home" in user_message or "house" in user_message or "property" in user_message:
                    insurance_type = "home"
                    conversation["extraction_data"]["insurance_type"] = "home"
                elif "content" in user_message or "belonging" in user_message:
                    insurance_type = "contents"
                    conversation["extraction_data"]["insurance_type"] = "contents"
            
            # If we're dealing with vehicle insurance, look for car details
            if insurance_type == "vehicle":
                # Extract car make
                for make in CAR_MAKES:
                    if make.lower() in user_message:
                        update_extraction_data(conversation, "vehicle_make", make)
                        break
                
                # Extract car model if we know the make
                if "vehicle" in conversation["extraction_data"] and "make" in conversation["extraction_data"]["vehicle"]:
                    make = conversation["extraction_data"]["vehicle"]["make"]
                    if make in CAR_MODELS_BY_MAKE:
                        for model in CAR_MODELS_BY_MAKE[make]:
                            if model.lower() in user_message:
                                update_extraction_data(conversation, "vehicle_model", model)
                                break
                
                # Extract car color
                for color in CAR_COLORS:
                    if color.lower() in user_message:
                        update_extraction_data(conversation, "vehicle_color", color)
                        break
                
                # Extract car year - look for 4-digit numbers
                import re
                year_matches = re.findall(r'\b(19[7-9]\d|20[0-2]\d)\b', user_message)
                if year_matches:
                    update_extraction_data(conversation, "vehicle_year", year_matches[0])
                
                # Extract usage type
                for usage_type in VEHICLE_USAGE_TYPES:
                    if usage_type.lower() in user_message:
                        update_extraction_data(conversation, "vehicle_usage", usage_type)
                        break
                
                # Extract yes/no answers for registration and financing
                if "registered in south africa" in user_message or "registered in sa" in user_message:
                    is_registered = "yes" in user_message or "yeah" in user_message
                    update_extraction_data(conversation, "vehicle_is_registered_in_sa", is_registered)
                
                if "financed" in user_message:
                    is_financed = "yes" in user_message or "yeah" in user_message
                    update_extraction_data(conversation, "vehicle_is_financed", is_financed)
    
    return conversation

def process_tool_calls_for_extraction(conversation, tool_calls):
    """Process tool calls to extract information into the extraction data structure"""
    if "extraction_data" not in conversation:
        conversation["extraction_data"] = {}
    
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        if function_name == "get_quote":
            # Extract insurance type
            if "insurance_type" in function_args:
                conversation["extraction_data"]["insurance_type"] = function_args["insurance_type"]
            
            # Extract customer information
            if "customer_name" in function_args:
                conversation["extraction_data"]["customer_name"] = function_args["customer_name"]
            
            if "id_number" in function_args:
                conversation["extraction_data"]["id_number"] = function_args["id_number"]
            
            if "address" in function_args:
                conversation["extraction_data"]["address"] = function_args["address"]
            
            # Extract vehicle details
            if "vehicle_details" in function_args and function_args["vehicle_details"]:
                vehicle_details = function_args["vehicle_details"]
                for key, value in vehicle_details.items():
                    update_extraction_data(conversation, f"vehicle_{key}", value)
            
            # Extract home details
            if "home_details" in function_args and function_args["home_details"]:
                home_details = function_args["home_details"]
                for key, value in home_details.items():
                    update_extraction_data(conversation, f"home_{key}", value)
            
            # Extract contents details
            if "contents_details" in function_args and function_args["contents_details"]:
                contents_details = function_args["contents_details"]
                for key, value in contents_details.items():
                    update_extraction_data(conversation, f"contents_{key}", value)
    
    return conversation

# Mock functions that would be replaced with actual API calls in production
def get_policy_details(policy_number):
    """Get details of a customer's insurance policy"""
    # This would be replaced with an actual API call
    mock_policies = {
        "11122234": {
            "policy_holder": "John Smith",
            "policy_number": "11122234",
            "address": "123 First street, Durban, 1234",
            "coverage_type": "Vehicle",
            "vehicle_details": "2018 BMW 320i",
            "monthly_premium": "R1,250.00",
            "start_date": "2023-01-15"
        },
        "22233445": {
            "policy_holder": "Sarah Johnson",
            "policy_number": "22233445",
            "address": "456 Main Road, Cape Town, 8001",
            "coverage_type": "Home",
            "property_details": "3 bedroom house",
            "monthly_premium": "R850.00",
            "start_date": "2022-08-10"
        }
    }
    
    if policy_number in mock_policies:
        return {
            "success": True,
            "message": "Policy details retrieved successfully",
            "data": mock_policies[policy_number]
        }
    else:
        return {
            "success": False,
            "message": f"Policy number {policy_number} not found in our system."
        }

def update_policy_address(policy_number, new_address):
    """Update the address on a customer's insurance policy"""
    # This would be replaced with an actual API call
    mock_policies = {
        "11122234": True,
        "22233445": True
    }
    
    if policy_number in mock_policies:
        return {
            "success": True,
            "message": f"Address for policy {policy_number} updated to '{new_address}' successfully."
        }
    else:
        return {
            "success": False,
            "message": f"Policy number {policy_number} not found in our system."
        }

def get_quote(customer_name, id_number, insurance_type, address, vehicle_details=None, home_details=None, contents_details=None):
    """Generate an insurance quote"""
    # This would be replaced with an actual API call
    quote_id = f"Q-{uuid.uuid4().hex[:8].upper()}"
    
    # Calculate mock premium based on insurance type
    if insurance_type == "vehicle":
        if vehicle_details:
            # Base premium calculation using vehicle details
            base_premium = 1000.0
            
            # Adjust for vehicle year
            if 'year' in vehicle_details:
                try:
                    year = int(vehicle_details['year'])
                    if year > 2022:
                        base_premium *= 1.5  # Very new cars cost more to insure
                    elif year > 2019:
                        base_premium *= 1.3
                    elif year > 2015:
                        base_premium *= 1.1
                    elif year > 2010:
                        base_premium *= 0.9
                    else:
                        base_premium *= 0.7  # Older cars are cheaper to insure
                except (ValueError, TypeError):
                    # If year is not a valid number, use default premium
                    pass
            
            # Adjust for vehicle make
            if 'make' in vehicle_details:
                make = vehicle_details['make']
                premium_multipliers = {
                    "BMW": 1.4,
                    "Mercedes-Benz": 1.4,
                    "Audi": 1.3,
                    "Volkswagen": 1.1,
                    "Toyota": 0.9,
                    "Honda": 0.9,
                    "Hyundai": 0.85,
                    "Kia": 0.85,
                    "Ford": 1.0
                }
                base_premium *= premium_multipliers.get(make, 1.0)
            
            # Adjust for usage type
            if 'usage' in vehicle_details:
                usage = vehicle_details['usage']
                if usage == "Private and occasional business":
                    base_premium *= 1.2  # 20% increase for occasional business use
                elif usage == "Private and full business":
                    base_premium *= 1.5  # 50% increase for full business use
            
            # Adjust for financing
            if 'is_financed' in vehicle_details and vehicle_details['is_financed']:
                base_premium *= 1.15  # 15% increase if financed
            
            # Adjust for SA registration
            if 'is_registered_in_sa' in vehicle_details and not vehicle_details['is_registered_in_sa']:
                base_premium *= 1.25  # 25% increase for non-SA registration
            
            # Round to 2 decimal places and convert to string with R prefix
            premium = f"R{base_premium:.2f}"
        else:
            # Default premium if no vehicle details
            premium = "R1,200.00"
    elif insurance_type == "home":
        premium = "R850.00"
    else:  # contents
        premium = "R350.00"
    
    return {
        "success": True,
        "message": "Quote generated successfully",
        "data": {
            "quote_id": quote_id,
            "customer_name": customer_name,
            "insurance_type": insurance_type,
            "monthly_premium": premium,
            "excess": "R2,500.00",
            "coverage_details": "Standard coverage including theft, damage, and liability",
            "valid_until": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
            # Include the extracted details for reference
            "extracted_details": {
                "insurance_type": insurance_type,
                "customer_name": customer_name,
                "id_number": id_number,
                "address": address,
                "vehicle_details": vehicle_details,
                "home_details": home_details,
                "contents_details": contents_details
            }
        }
    }

def submit_claim(policy_number, incident_date, incident_description, claim_type):
    """Submit an insurance claim"""
    # This would be replaced with an actual API call
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
    
    mock_policies = {
        "11122234": "Vehicle",
        "22233445": "Home"
    }
    
    if policy_number not in mock_policies:
        return {
            "success": False,
            "message": f"Policy number {policy_number} not found in our system."
        }
    
    expected_claim_type = mock_policies[policy_number].lower()
    if claim_type != expected_claim_type and expected_claim_type != "home" and claim_type != "contents":
        return {
            "success": False,
            "message": f"Claim type '{claim_type}' does not match policy type '{expected_claim_type}'."
        }
    
    return {
        "success": True,
        "message": "Claim submitted successfully",
        "data": {
            "claim_id": claim_id,
            "policy_number": policy_number,
            "status": "Submitted",
            "next_steps": "Your claim has been received and a claims assessor will contact you within 24 hours.",
            "submission_date": datetime.now().strftime("%Y-%m-%d")
        }
    }

def request_callback(customer_name, phone_number, preferred_time=None, reason=None):
    """Schedule a callback from a customer service representative"""
    # This would be replaced with an actual API call
    reference_number = f"CB-{uuid.uuid4().hex[:8].upper()}"
    
    preferred_time_msg = f" during the {preferred_time}" if preferred_time else ""
    
    return {
        "success": True,
        "message": f"Callback scheduled successfully",
        "data": {
            "reference_number": reference_number,
            "customer_name": customer_name,
            "phone_number": phone_number,
            "callback_details": f"A representative will call you{preferred_time_msg} within the next business day.",
            "scheduled_on": datetime.now().strftime("%Y-%m-%d")
        }
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
    messages.append({"role": "system", "content": INSURANCE_BOT_SYSTEM_MESSAGE})
    
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
                "content": None,
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

def determine_conversation_state(conversation, assistant_message, user_message):
    """Determine the current state of the conversation based on content"""
    # Get the current state
    current_state = conversation.get("state", CONVERSATION_STATE["NEW"])
    
    # Check if we're already in a flow and should stay there
    if current_state != CONVERSATION_STATE["NEW"] and current_state != CONVERSATION_STATE["GENERAL_QUERY"]:
        return current_state
    
    # Check for quote-related keywords
    quote_keywords = ["quote", "insure", "coverage", "cover", "price", "cost", "premium"]
    if any(keyword in user_message.lower() for keyword in quote_keywords):
        return CONVERSATION_STATE["QUOTE_FLOW"]
    
    # Check for policy management keywords
    policy_keywords = ["policy", "update", "change", "modify", "amend", "update", "manage"]
    if any(keyword in user_message.lower() for keyword in policy_keywords):
        return CONVERSATION_STATE["POLICY_MANAGEMENT"]
    
    # Check for claim submission keywords
    claim_keywords = ["claim", "accident", "damage", "incident", "file", "submit"]
    if any(keyword in user_message.lower() for keyword in claim_keywords):
        return CONVERSATION_STATE["CLAIM_SUBMISSION"]
    
    # Check for cover details keywords
    cover_keywords = ["details", "coverage", "benefits", "limit", "what's covered", "whats covered"]
    if any(keyword in user_message.lower() for keyword in cover_keywords):
        return CONVERSATION_STATE["COVER_DETAILS"]
    
    # Check for callback request keywords
    callback_keywords = ["call back", "callback", "contact me", "call me", "speak", "agent", "representative"]
    if any(keyword in user_message.lower() for keyword in callback_keywords):
        return CONVERSATION_STATE["CALLBACK_REQUEST"]
    
    # Default to general query
    return CONVERSATION_STATE["GENERAL_QUERY"]

def handle_tool_calls(tool_calls):
    """Process tool calls from the assistant"""
    results = []
    
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        result = None
        if function_name == "get_policy_details":
            result = get_policy_details(function_args.get("policy_number"))
        elif function_name == "update_policy_address":
            result = update_policy_address(
                function_args.get("policy_number"),
                function_args.get("new_address")
            )
        elif function_name == "get_quote":
            result = get_quote(
                function_args.get("customer_name"),
                function_args.get("id_number"),
                function_args.get("insurance_type"),
                function_args.get("address"),
                function_args.get("vehicle_details"),
                function_args.get("home_details"),
                function_args.get("contents_details")
            )
        elif function_name == "submit_claim":
            result = submit_claim(
                function_args.get("policy_number"),
                function_args.get("incident_date"),
                function_args.get("incident_description"),
                function_args.get("claim_type")
            )
        elif function_name == "request_callback":
            result = request_callback(
                function_args.get("customer_name"),
                function_args.get("phone_number"),
                function_args.get("preferred_time"),
                function_args.get("reason")
            )
        
        results.append({
            "tool_call_id": tool_call.id,
            "function_name": function_name,
            "result": json.dumps(result)
        })
    
    return results

def insurance_chat_route():
    """
    Create or continue an insurance bot conversation
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
            conversation_state:
              type: string
              description: Current state of the conversation flow
            extraction_data:
              type: object
              description: Extracted data from the conversation
            prompt_tokens:
              type: integer
              description: Number of prompt tokens used
            completion_tokens:
              type: integer
              description: Number of completion tokens used
            total_tokens:
              type: integer
              description: Total number of tokens used
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
              example: Error processing chat request
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
            
            # Apply rules-based extraction to the conversation
            conversation = extract_info_from_messages(conversation)
            
        else:
            # Create new conversation
            conversation_id = str(uuid.uuid4())
            
            # Initialize conversation with extraction_data
            conversation = {
                "conversation_id": conversation_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "temperature": temperature,
                "state": CONVERSATION_STATE["NEW"],
                "messages": [
                    {"role": "assistant", "content": "Hi there, how can I help you today?"},
                    {"role": "user", "content": user_message}
                ],
                "extraction_data": {}  # Initialize empty extraction data
            }
            
            # Apply rules-based extraction to the initial message
            conversation = extract_info_from_messages(conversation)
        
        # Format conversation for OpenAI API
        messages = format_conversation_for_openai(conversation)
        
        # Call GPT-4o with tool capabilities
        response = openai_client.chat.completions.create(
            model=GPT4O_DEPLOYMENT,
            messages=messages,
            temperature=temperature,
            tools=INSURANCE_TOOLS,
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
            
            # Process the tool calls for extraction
            conversation = process_tool_calls_for_extraction(conversation, assistant_response.tool_calls)
            
            # Process the tool calls
            tool_results = handle_tool_calls(assistant_response.tool_calls)
            
            # Add each tool result to the conversation
            for result in tool_results:
                conversation["messages"].append({
                    "role": "function_result",
                    "name": result["function_name"],
                    "content": result["result"]
                })
            
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
        conversation = extract_info_from_messages(conversation)
        
        # Determine conversation state based on content
        conversation_state = determine_conversation_state(conversation, assistant_message, user_message)
        
        # Update conversation state
        conversation["state"] = conversation_state
        
        # Update timestamp
        conversation["updated_at"] = datetime.now().isoformat()
        
        # Process vehicle details to find best matches from predefined lists
        if "extraction_data" in conversation and "vehicle" in conversation["extraction_data"]:
            vehicle_data = conversation["extraction_data"]["vehicle"]
            
            # Match car make against predefined list
            if "make" in vehicle_data:
                best_make_match = find_best_match(vehicle_data["make"], CAR_MAKES)
                if best_make_match:
                    vehicle_data["make"] = best_make_match
            
            # Match car model against models for the selected make
            if "make" in vehicle_data and "model" in vehicle_data:
                make = vehicle_data["make"]
                if make in CAR_MODELS_BY_MAKE:
                    best_model_match = find_best_match(vehicle_data["model"], CAR_MODELS_BY_MAKE[make])
                    if best_model_match:
                        vehicle_data["model"] = best_model_match
            
            # Match color against predefined list
            if "color" in vehicle_data:
                best_color_match = find_best_match(vehicle_data["color"], CAR_COLORS)
                if best_color_match:
                    vehicle_data["color"] = best_color_match
            
            # Match usage type against predefined list
            if "usage" in vehicle_data:
                best_usage_match = find_best_match(vehicle_data["usage"], VEHICLE_USAGE_TYPES)
                if best_usage_match:
                    vehicle_data["usage"] = best_usage_match
            
            # Convert yes/no string responses to booleans
            for field in ["is_registered_in_sa", "is_financed"]:
                if field in vehicle_data and isinstance(vehicle_data[field], str):
                    value = vehicle_data[field].lower()
                    vehicle_data[field] = value in ["yes", "true", "y", "1"]
        
        # Save conversation
        success, error = save_conversation_history(conversation_id, conversation)
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error saving conversation: {error}"
            }, 500)
        
        # Create response
        response_data = {
            "conversation_id": conversation_id,
            "assistant_message": assistant_message,
            "conversation_state": conversation_state,
            "extraction_data": conversation.get("extraction_data", {}),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
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
    Delete an insurance bot conversation
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
    """Register insurance bot routes with the Flask app"""
    app.route('/insurance-bot/chat', methods=['POST'])(api_logger(insurance_chat_route))
    app.route('/insurance-bot/chat', methods=['DELETE'])(api_logger(delete_insurance_chat_route))
