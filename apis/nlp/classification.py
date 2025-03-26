from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
import pytz
from datetime import datetime
import requests
import json

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
        # Create system message for classification
        system_prompt = """You are a text classification system. Your task is to classify the provided text into exactly one of the given categories.
Respond ONLY with the category name that best matches the text. Do not include any explanations, punctuation, or additional text.
Use the format: category_name"""
        
        # Create user message with category list and text to classify
        categories_list = ', '.join(categories)
        user_message = f"Categories: {categories_list}\n\nText to classify: {user_input}"
        
        # Determine which LLM endpoint to call based on model selection
        llm_endpoint = f"{request.url_root.rstrip('/')}/llm/{model}"
        
        # Prepare payload for LLM request
        llm_request_data = {
            "system_prompt": system_prompt,
            "user_input": user_message,
            "temperature": 0.0  # Set temperature to 0 for deterministic results
        }
        
        # Call selected LLM API
        logger.info(f"Calling {model} for simple classification")
        headers = {"X-Token": token, "Content-Type": "application/json"}
        llm_response = requests.post(
            llm_endpoint,
            headers=headers,
            json=llm_request_data
        )
        
        if llm_response.status_code != 200:
            logger.error(f"Error from LLM API: {llm_response.text}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error from LLM API: {llm_response.text[:200]}"
            }, 500)
        
        # Extract response and token usage
        llm_result = llm_response.json()
        result_class = llm_result.get("message", "").strip()
        
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
    
    Classify text into multiple categories with probability scores
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
        description: Classification results with probabilities
        schema:
          type: object
          properties:
            classifications:
              type: array
              items:
                type: object
                properties:
                  class:
                    type: string
                    example: "sports"
                  probability:
                    type: number
                    format: float
                    example: 0.75
            top_classifications:
              type: array
              items:
                type: object
                properties:
                  class:
                    type: string
                    example: "sports"
                  probability:
                    type: number
                    format: float
                    example: 0.75
              description: Top 3 classifications by probability
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
        # Simple prompt for the model to provide classification probabilities
        system_prompt = """Classify the given text into the provided categories and assign a probability to each category.

Carefully analyze the text and determine how relevant it is to each category. Assign higher probabilities to more relevant categories and lower probabilities to less relevant ones.

Important rules:
1. The probabilities MUST sum to exactly 1.0 (100%)
2. If a category is clearly the best match, give it a much higher probability (0.7-0.9)
3. Provide only the required JSON output with no explanation or additional text
4. Format: [{"class": "category_name", "probability": 0.7}, {"class": "another_category", "probability": 0.3}]

If a text is strongly related to one category, it should have a high probability for that category and very low for others."""
        
        # Format categories for the user message
        categories_list = ', '.join(categories)
        user_message = f"""Categories: {categories_list}

Text to classify: {user_input}

Classify the above text into the provided categories with probabilities that sum to 1.0."""
        
        # Determine which LLM endpoint to call
        llm_endpoint = f"{request.url_root.rstrip('/')}/llm/{model}"
        
        # Prepare payload for LLM request
        llm_request_data = {
            "system_prompt": system_prompt,
            "user_input": user_message,
            "temperature": 0.1,  # Slight randomness to avoid uniform distributions
            "json_output": True  # Request JSON output format
        }
        
        # Call LLM API
        logger.info(f"Calling {model} for multiclass classification")
        headers = {"X-Token": token, "Content-Type": "application/json"}
        llm_response = requests.post(
            llm_endpoint,
            headers=headers,
            json=llm_request_data
        )
        
        if llm_response.status_code != 200:
            logger.error(f"Error from LLM API: {llm_response.text}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error from LLM API: {llm_response.text[:200]}"
            }, 500)
        
        # Extract response
        llm_result = llm_response.json()
        result_text = llm_result.get("message", "[]")
        
        # Parse and validate the classification results
        try:
            classifications = json.loads(result_text)
            
            # Validate and clean up results
            valid_classifications = []
            total_probability = 0.0
            
            for item in classifications:
                if isinstance(item, dict) and 'class' in item and 'probability' in item:
                    # Try to match the class name to one of our categories
                    class_name = item['class']
                    if class_name not in categories:
                        # Try to find a close match
                        for category in categories:
                            if category.lower() == class_name.lower() or category.lower() in class_name.lower() or class_name.lower() in category.lower():
                                class_name = category
                                break
                    
                    # Skip if we still don't have a valid category
                    if class_name not in categories:
                        continue
                    
                    # Add valid classification
                    try:
                        prob = float(item['probability'])
                        prob = max(0, min(1, prob))  # Ensure probability is between 0 and 1
                        
                        valid_classifications.append({
                            'class': class_name,
                            'probability': prob
                        })
                        total_probability += prob
                    except (ValueError, TypeError):
                        continue
            
            # Handle case where we have no valid classifications
            if not valid_classifications:
                # Create default with 100% for first category
                valid_classifications = [{'class': categories[0], 'probability': 1.0}]
                total_probability = 1.0
            
            # Normalize probabilities to ensure they sum to 1.0
            if abs(total_probability - 1.0) > 0.01:  # Allow small rounding errors
                for item in valid_classifications:
                    item['probability'] = item['probability'] / total_probability
            
            # Handle missing categories
            category_dict = {item['class']: item for item in valid_classifications}
            for category in categories:
                if category not in category_dict:
                    valid_classifications.append({'class': category, 'probability': 0.0})
            
            # Sort by probability (descending)
            valid_classifications.sort(key=lambda x: x['probability'], reverse=True)
            
            # Round to 4 decimal places
            for item in valid_classifications:
                item['probability'] = round(item['probability'], 4)
            
            # Get top 3 classifications
            top_classifications = valid_classifications[:min(3, len(valid_classifications))]
            
            # Prepare response with classifications and token usage
            response_data = {
                "classifications": valid_classifications,
                "top_classifications": top_classifications,
                "model_used": model,
                "input_tokens": llm_result.get("input_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "output_tokens": llm_result.get("output_tokens", 0)
            }
            
            return create_api_response(response_data, 200)
            
        except json.JSONDecodeError:
            logger.error(f"Error parsing classification results as JSON: {result_text}")
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to parse classification results as JSON"
            }, 500)
            
    except Exception as e:
        logger.error(f"Error in multiclass classification: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing classification request: {str(e)}"
        }, 500)

def register_nlp_routes(app):
    """Register NLP routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    
    app.route('/nlp/classify', methods=['POST'])(api_logger(check_balance(simple_classification_route)))
    app.route('/nlp/classify/multi', methods=['POST'])(api_logger(check_balance(multiclass_classification_route)))
