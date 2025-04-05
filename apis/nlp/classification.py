from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.balanceService import BalanceService
from apis.utils.llmServices import gpt4o_service, gpt4o_mini_service
import logging
import pytz
from datetime import datetime
import json
import uuid

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def simple_classification_route():
    """
    Consumes 0.5 AI credits per call when using gpt-4o-mini, 2 credits for gpt-4o
    
    Classify text into one of the provided categories using NLP
    ---
    tags:
      - Natural Language Processing
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
            - categories
            - user_input
          properties:
            categories:
              type: array
              items:
                type: string
              description: List of categories to classify into
              example: ["sports", "politics", "technology", "entertainment"]
            user_input:
              type: string
              description: Text to classify
            model:
              type: string
              enum: [gpt-4o-mini, gpt-4o]
              default: gpt-4o-mini
              description: LLM model to use for classification
    produces:
      - application/json
    responses:
      200:
        description: Classification result
        schema:
          type: object
          properties:
            result_class:
              type: string
              example: "sports"
            model_used:
              type: string
              example: "gpt-4o-mini"
            input_tokens:
              type: integer
              example: 125
            completion_tokens:
              type: integer
              example: 42
            output_tokens:
              type: integer
              example: 167
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
              example: "Missing required fields: categories, user_input"
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
        description: Insufficient balance
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
              example: "Error processing classification request"
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
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['categories', 'user_input']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Extract parameters
    categories = data.get('categories', [])
    user_input = data.get('user_input', '')
    model = data.get('model', 'gpt-4o-mini')
    
    # Validate categories is a non-empty list
    if not isinstance(categories, list) or len(categories) == 0:
        return create_api_response({
            "error": "Bad Request",
            "message": "Categories must be a non-empty list of strings"
        }, 400)
    
    # Validate model selection
    if model not in ['gpt-4o-mini', 'gpt-4o']:
        return create_api_response({
            "error": "Bad Request",
            "message": "Model must be either 'gpt-4o-mini' or 'gpt-4o'"
        }, 400)
    
    try:
        # Deduct AI credits based on model
        # Get endpoint ID for this request
        endpoint_id = DatabaseService.get_endpoint_id_by_path(request.path)
        if not endpoint_id:
            endpoint_id = str(uuid.uuid4())  # Use a placeholder if endpoint not found
            
        # Determine credit cost based on model
        if model == 'gpt-4o-mini':
            credit_cost = 0.5
        else:  # model == 'gpt-4o'
            credit_cost = 2.0
            
        # Check and deduct balance
        success, result = BalanceService.check_and_deduct_balance(user_id, endpoint_id, credit_cost)
        if not success:
            if result == "Insufficient balance":
                return create_api_response({
                    "error": "Insufficient Balance",
                    "message": "Your API call balance is depleted. Please upgrade your plan for additional calls."
                }, 402)
            return create_api_response({
                "error": "Balance Error",
                "message": f"Error processing balance: {result}"
            }, 500)
        
        # Create system message for classification
        system_prompt = """You are a text classification system. Your task is to classify the provided text into exactly one of the given categories.
Respond ONLY with the category name that best matches the text. Do not include any explanations, punctuation, or additional text.
Use the format: category_name"""
        
        # Create user message with category list and text to classify
        categories_list = ', '.join(categories)
        user_message = f"Categories: {categories_list}\n\nText to classify: {user_input}"
        
        # Use appropriate LLM service from llmServices based on model parameter
        if model == 'gpt-4o-mini':
            llm_result = gpt4o_mini_service(system_prompt, user_message, temperature=0.0)
        else:  # model == 'gpt-4o'
            llm_result = gpt4o_service(system_prompt, user_message, temperature=0.0)
        
        if not llm_result.get("success", False):
            logger.error(f"Error from LLM service: {llm_result.get('error', 'Unknown error')}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error from LLM service: {llm_result.get('error', 'Unknown error')[:200]}"
            }, 500)
        
        # Extract response and token usage
        result_class = llm_result.get("result", "").strip()
        
        # Validate that the result is one of the provided categories
        # The LLM might occasionally return something not in the list despite our prompt
        if result_class not in categories:
            # Find the closest match if exact match not found
            for category in categories:
                if category.lower() in result_class.lower():
                    result_class = category
                    break
            # If still no match, use the first category as fallback
            if result_class not in categories:
                logger.warning(f"LLM returned '{result_class}' which is not in the provided categories. Using fallback.")
                result_class = categories[0]
        
        # Prepare response with classification result and token usage
        response_data = {
            "result_class": result_class,
            "model_used": model,
            "input_tokens": llm_result.get("input_tokens", 0),
            "completion_tokens": llm_result.get("completion_tokens", 0),
            "output_tokens": llm_result.get("output_tokens", 0)
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error in simple classification: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing classification request: {str(e)}"
        }, 500)


def multiclass_classification_route():
    """
    Consumes 0.5 AI credits per call when using gpt-4o-mini, 2 credits for gpt-4o
    
    Classify text into multiple categories with confidence scores
    ---
    tags:
      - Natural Language Processing
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
            - categories
            - user_input
          properties:
            categories:
              type: array
              items:
                type: string
              description: List of categories to classify into
              example: ["sports", "politics", "technology", "entertainment"]
            user_input:
              type: string
              description: Text to classify
            model:
              type: string
              enum: [gpt-4o-mini, gpt-4o]
              default: gpt-4o-mini
              description: LLM model to use for classification
    produces:
      - application/json
    responses:
      200:
        description: Multiclass classification results
        schema:
          type: object
          properties:
            top_result:
              type: string
              example: "sports"
            top_3_classes:
              type: array
              items:
                type: string
              example: ["sports", "entertainment", "technology"]
            all_classes:
              type: array
              items:
                type: object
                properties:
                  category:
                    type: string
                    example: "sports"
                  confidence:
                    type: number
                    format: float
                    example: 0.85
              example: [
                {"category": "sports", "confidence": 0.85},
                {"category": "entertainment", "confidence": 0.65},
                {"category": "technology", "confidence": 0.40},
                {"category": "politics", "confidence": 0.15}
              ]
            model_used:
              type: string
              example: "gpt-4o-mini"
            input_tokens:
              type: integer
              example: 125
            completion_tokens:
              type: integer
              example: 42
            output_tokens:
              type: integer
              example: 167
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
              example: "Missing required fields: categories, user_input"
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
        description: Insufficient balance
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
              example: "Error processing classification request"
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
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['categories', 'user_input']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Extract parameters
    categories = data.get('categories', [])
    user_input = data.get('user_input', '')
    model = data.get('model', 'gpt-4o-mini')
    
    # Validate categories is a non-empty list
    if not isinstance(categories, list) or len(categories) == 0:
        return create_api_response({
            "error": "Bad Request",
            "message": "Categories must be a non-empty list of strings"
        }, 400)
    
    # Validate model selection
    if model not in ['gpt-4o-mini', 'gpt-4o']:
        return create_api_response({
            "error": "Bad Request",
            "message": "Model must be either 'gpt-4o-mini' or 'gpt-4o'"
        }, 400)
    
    try:
        # Deduct AI credits based on model
        # Get endpoint ID for this request
        endpoint_id = DatabaseService.get_endpoint_id_by_path(request.path)
        if not endpoint_id:
            endpoint_id = str(uuid.uuid4())  # Use a placeholder if endpoint not found
            
        # Determine credit cost based on model
        if model == 'gpt-4o-mini':
            credit_cost = 0.5
        else:  # model == 'gpt-4o'
            credit_cost = 2.0
            
        # Check and deduct balance
        success, result = BalanceService.check_and_deduct_balance(user_id, endpoint_id, credit_cost)
        if not success:
            if result == "Insufficient balance":
                return create_api_response({
                    "error": "Insufficient Balance",
                    "message": "Your API call balance is depleted. Please upgrade your plan for additional calls."
                }, 402)
            return create_api_response({
                "error": "Balance Error",
                "message": f"Error processing balance: {result}"
            }, 500)
        
        # Create system message for multiclass classification
        system_prompt = """You are a text classification system. Your task is to classify the provided text into the given categories, with confidence scores for each category.

Rank ALL categories based on how well they fit the text, providing a confidence score (0-1) for each category.

IMPORTANT: Only use the categories provided in the list. Do not add any new categories.

Respond ONLY in valid JSON format with the following structure:
{
  "classifications": [
    {"category": "category_name", "confidence": 0.95},
    {"category": "category_name", "confidence": 0.75},
    ...
  ]
}

Include ALL provided categories in your response with appropriate confidence scores.
The sum of confidence scores does not need to equal 1. Assign each category a score based on how well it matches the text."""
        
        # Create user message with category list and text to classify
        categories_list = ', '.join(categories)
        user_message = f"Categories: {categories_list}\n\nText to classify: {user_input}"
        
        # Use appropriate LLM service from llmServices based on model parameter
        if model == 'gpt-4o-mini':
            llm_result = gpt4o_mini_service(system_prompt, user_message, temperature=0.0, json_output=True)
        else:  # model == 'gpt-4o'
            llm_result = gpt4o_service(system_prompt, user_message, temperature=0.0, json_output=True)
        
        if not llm_result.get("success", False):
            logger.error(f"Error from LLM service: {llm_result.get('error', 'Unknown error')}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error from LLM service: {llm_result.get('error', 'Unknown error')[:200]}"
            }, 500)
        
        # Extract response and token usage
        llm_message = llm_result.get("result", "").strip()
        
        # Parse the JSON response from the LLM
        try:
            # Parse the JSON response
            classifications_json = json.loads(llm_message)
            
            # Extract classifications list
            classifications = classifications_json.get("classifications", [])
            
            # Validate that classifications only include the provided categories
            valid_classifications = []
            for cls in classifications:
                category = cls.get("category", "")
                confidence = cls.get("confidence", 0)
                
                # Check if the category is in the provided list
                if category in categories:
                    valid_classifications.append({
                        "category": category,
                        "confidence": confidence
                    })
                else:
                    # Check for close matches
                    for cat in categories:
                        if cat.lower() in category.lower() or category.lower() in cat.lower():
                            valid_classifications.append({
                                "category": cat,  # Use the exact category name from the list
                                "confidence": confidence
                            })
                            break
            
            # If we don't have classifications for all categories, add missing ones with low confidence
            category_set = set(c["category"] for c in valid_classifications)
            for cat in categories:
                if cat not in category_set:
                    valid_classifications.append({
                        "category": cat,
                        "confidence": 0.01  # Very low confidence for missing categories
                    })
            
            # Sort classifications by confidence (descending)
            sorted_classifications = sorted(valid_classifications, key=lambda x: x["confidence"], reverse=True)
            
            # Extract top result and top 3 classes
            top_result = sorted_classifications[0]["category"] if sorted_classifications else categories[0]
            top_3_classes = [c["category"] for c in sorted_classifications[:min(3, len(sorted_classifications))]]
            
            # Ensure we have at least 3 classes in top_3_classes if available
            if len(top_3_classes) < 3 and len(categories) >= 3:
                for cat in categories:
                    if cat not in top_3_classes and len(top_3_classes) < 3:
                        top_3_classes.append(cat)
            
            # Prepare response with classification results and token usage
            response_data = {
                "top_result": top_result,
                "top_3_classes": top_3_classes,
                "all_classes": sorted_classifications,
                "model_used": model,
                "input_tokens": llm_result.get("input_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "output_tokens": llm_result.get("output_tokens", 0)
            }
            
            return create_api_response(response_data, 200)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing LLM JSON response: {str(e)}, Response: {llm_message}")
            
            # Fallback response if JSON parsing fails
            fallback_classifications = []
            for category in categories:
                fallback_classifications.append({
                    "category": category,
                    "confidence": 1.0 if category == categories[0] else 0.1
                })
            
            response_data = {
                "top_result": categories[0],
                "top_3_classes": categories[:min(3, len(categories))],
                "all_classes": fallback_classifications,
                "model_used": model,
                "input_tokens": llm_result.get("input_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "output_tokens": llm_result.get("output_tokens", 0),
                "parsing_error": f"Could not parse LLM response as JSON. Using fallback classification."
            }
            
            return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error in multiclass classification: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing multiclass classification request: {str(e)}"
        }, 500)
        
def register_nlp_routes(app):
    """Register NLP routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    
    # No longer using balanceMiddleware's check_balance since we're handling billing directly in the route
    app.route('/nlp/classify', methods=['POST'])(api_logger(simple_classification_route))
    app.route('/nlp/classify/multi', methods=['POST'])(api_logger(multiclass_classification_route))
