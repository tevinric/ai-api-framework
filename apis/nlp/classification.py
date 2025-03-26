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
        description: Classification results with confidence scores
        schema:
          type: object
          properties:
            top_result:
              type: object
              properties:
                class:
                  type: string
                  example: "technology"
                confidence:
                  type: number
                  format: float
                  example: 0.85
              description: The most relevant category for the text
            top_categories:
              type: array
              items:
                type: object
                properties:
                  class:
                    type: string
                    example: "technology"
                  confidence:
                    type: number
                    format: float
                    example: 0.85
              description: Top 3 categories most relevant to the text
            all_categories:
              type: array
              items:
                type: object
                properties:
                  class:
                    type: string
                    example: "sports"
                  confidence:
                    type: number
                    format: float
                    example: 0.15
              description: All categories with their confidence scores
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
      401:
        description: Authentication error
      402:
        description: Insufficient balance
      500:
        description: Server error
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
        # Create a system message that includes the categories
        categories_formatted = ", ".join([f'"{category}"' for category in categories])
        system_prompt = f"""You are a text classification system. You must analyze the provided text and assign confidence scores for how strongly it relates to each of these specific categories: {categories_formatted}.

For each category, assign a confidence score from 0.0 to 1.0 based on how relevant the text is to that category:
- A score near 1.0 means the text is highly relevant to the category
- A score near 0.0 means the text has almost no relevance to the category

Important rules:
1. DO NOT assign the same confidence score to all categories
2. If the text clearly relates to one category more than others, that category should receive a substantially higher score
3. Return ONLY a valid JSON array with no explanation or additional text
4. Format: [{{"class": "category_name", "confidence": 0.85}}, {{"class": "another_category", "confidence": 0.25}}]

Your classification must be specific and discriminative, with clear differentiation between relevant and non-relevant categories."""

        # The user message contains only the text to classify
        user_message = f"""Text to classify:
{user_input}"""
        
        # Determine LLM endpoint
        llm_endpoint = f"{request.url_root.rstrip('/')}/llm/{model}"
        
        # Prepare payload for LLM request
        llm_request_data = {
            "system_prompt": system_prompt,
            "user_input": user_message,
            "temperature": 0.2,  # Low but not zero
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
        
        # Extract and process the LLM response
        llm_result = llm_response.json()
        result_message = llm_result.get("message", "[]")
        
        try:
            # Parse the JSON response
            if isinstance(result_message, str):
                classifications = json.loads(result_message)
            elif isinstance(result_message, list):
                # If the API already parsed the JSON for us
                classifications = result_message
            else:
                logger.error(f"Unexpected response format: {type(result_message)}")
                classifications = []
            
            # Validate and process each classification
            processed_classifications = []
            
            for item in classifications:
                if isinstance(item, dict) and 'class' in item and 'confidence' in item:
                    class_name = item['class']
                    
                    # Validate the class name is one of our input categories
                    matched_category = None
                    for category in categories:
                        if category.lower() == class_name.lower():
                            matched_category = category
                            break
                    
                    # Skip if no match found
                    if not matched_category:
                        continue
                        
                    # Process the confidence score
                    try:
                        confidence = float(item['confidence'])
                        confidence = max(0.0, min(1.0, confidence))  # Ensure between 0 and 1
                        confidence = round(confidence, 3)  # Round to 3 decimal places
                        
                        processed_classifications.append({
                            'class': matched_category,
                            'confidence': confidence
                        })
                    except (ValueError, TypeError):
                        continue
            
            # Check if we have a valid classification
            if not processed_classifications:
                logger.warning("No valid classifications returned by LLM")
                # Create a fallback that gives different scores (not equal splits)
                processed_classifications = []
                for i, category in enumerate(categories):
                    # Generate descending scores (0.9, 0.7, 0.5, 0.3...)
                    score = max(0.1, 0.9 - (i * 0.2))
                    processed_classifications.append({
                        'class': category,
                        'confidence': round(score, 3)
                    })
            
            # Add any missing categories with a low confidence score
            classified_categories = {item['class'] for item in processed_classifications}
            for category in categories:
                if category not in classified_categories:
                    processed_classifications.append({
                        'class': category,
                        'confidence': 0.1  # Low default confidence
                    })
            
            # Sort by confidence (descending)
            processed_classifications.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Extract top result and top categories
            top_result = processed_classifications[0]
            top_categories = processed_classifications[:min(3, len(processed_classifications))]
            
            # Prepare the response
            response_data = {
                "top_result": top_result,
                "top_categories": top_categories,
                "all_categories": processed_classifications,
                "model_used": model,
                "input_tokens": llm_result.get("input_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "output_tokens": llm_result.get("output_tokens", 0)
            }
            
            return create_api_response(response_data, 200)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing classification results: {e}, Response: {result_message}")
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
