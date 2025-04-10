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
- Ask what they want to insure (vehicle, home, contents)
- Collect personal details (name, ID number)
- Collect relevant asset information (for vehicles: make, model, year)
- Collect address information
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

You'll respond conversationally while making appropriate use of tools when needed.
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
                    "details": {
                        "type": "object",
                        "description": "Details specific to the insurance type",
                        "properties": {
                            "vehicle_make": {
                                "type": "string",
                                "description": "Make of the vehicle (for vehicle insurance)"
                            },
                            "vehicle_model": {
                                "type": "string",
                                "description": "Model of the vehicle (for vehicle insurance)"
                            },
                            "vehicle_year": {
                                "type": "string",
                                "description": "Year of the vehicle (for vehicle insurance)"
                            },
                            "home_type": {
                                "type": "string",
                                "description": "Type of home (for home insurance)"
                            },
                            "contents_value": {
                                "type": "string",
                                "description": "Estimated value of contents (for contents insurance)"
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

def get_quote(customer_name, id_number, insurance_type, address, details=None):
    """Generate an insurance quote"""
    # This would be replaced with an actual API call
    quote_id = f"Q-{uuid.uuid4().hex[:8].upper()}"
    
    # Calculate mock premium based on insurance type
    if insurance_type == "vehicle":
        if details and 'vehicle_year' in details:
            year = int(details['vehicle_year'])
            if year > 2020:
                premium = "R1,400.00"
            elif year > 2015:
                premium = "R950.00"
            else:
                premium = "R750.00"
        else:
            premium = "R950.00"
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
            "valid_until": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
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
                function_args.get("details")
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
            
        else:
            # Create new conversation
            conversation_id = str(uuid.uuid4())
            
            # Initialize conversation
            conversation = {
                "conversation_id": conversation_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "temperature": temperature,
                "state": CONVERSATION_STATE["NEW"],
                "messages": [
                    {"role": "assistant", "content": "Hi there, how can I help you today?"},
                    {"role": "user", "content": user_message}
                ]
            }
        
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
        
        # Determine conversation state based on content
        conversation_state = determine_conversation_state(conversation, assistant_message, user_message)
        
        # Update conversation state
        conversation["state"] = conversation_state
        
        # Update timestamp
        conversation["updated_at"] = datetime.now().isoformat()
        
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
