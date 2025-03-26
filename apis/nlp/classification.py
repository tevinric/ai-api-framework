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
        # Create a two-step approach for more accurate probability distributions
        # Step 1: First we'll ask the model to rank and score each category separately
        system_prompt_step1 = """You are an expert text classifier. Analyze the provided text and score each category on a scale of 0-100 based on how well the text fits that category.

Rules:
1. Score MUST be between 0-100 where:
   - 0: No relation whatsoever
   - 1-20: Minimal relation
   - 21-50: Moderate relation
   - 51-80: Strong relation
   - 81-100: Perfect match
2. You MUST give very different scores when categories clearly differ in relevance
3. Provide brief reasoning for each score
4. Respond in valid JSON with this format:
   [{"category": "name", "score": number, "reasoning": "text"}, {...}]

IMPORTANT: Do not distribute scores evenly! If one category is clearly the best match, give it a much higher score than the others."""
        
        # Create detailed user message with category list and text to classify
        categories_list = '\n'.join([f"- {cat}" for cat in categories])
        user_message_step1 = f"""CATEGORIES TO SCORE:
{categories_list}

TEXT TO ANALYZE:
{user_input}

For each category, provide a score (0-100) indicating how well the text matches that category. Use your expert judgment to provide a wide range of scores that accurately reflects the text's relationship to each category."""

        # Prepare payload for first LLM request
        llm_request_data_step1 = {
            "system_prompt": system_prompt_step1,
            "user_input": user_message_step1,
            "temperature": 0.0,
            "json_output": True
        }
        
        # Determine which LLM endpoint to call based on model selection
        llm_endpoint = f"{request.url_root.rstrip('/')}/llm/{model}"
        
        # Call LLM API for step 1 - scoring
        logger.info(f"Calling {model} for step 1: category scoring")
        headers = {"X-Token": token, "Content-Type": "application/json"}
        llm_response_step1 = requests.post(
            f"{request.url_root.rstrip('/')}/llm/{model}",
            headers=headers,
            json=llm_request_data_step1
        )
        
        if llm_response_step1.status_code != 200:
            logger.error(f"Error from LLM API in step 1: {llm_response_step1.text}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error from LLM API: {llm_response_step1.text[:200]}"
            }, 500)
        
        # Extract response and token usage
        llm_result_step1 = llm_response_step1.json()
        result_text_step1 = llm_result_step1.get("message", "[]")
        
        try:
            # Parse the scores
            scores_result = json.loads(result_text_step1)
            
            # Validate and extract scores
            category_scores = {}
            category_reasonings = {}
            
            for item in scores_result:
                if isinstance(item, dict) and 'category' in item and 'score' in item:
                    cat_name = item['category']
                    # Find matching category from our list (case-insensitive)
                    matching_cat = next((c for c in categories if c.lower() == cat_name.lower()), None)
                    if not matching_cat and 'reasoning' in item:
                        # Try to find in original categories list
                        for c in categories:
                            if c.lower() in cat_name.lower() or cat_name.lower() in c.lower():
                                matching_cat = c
                                break
                    
                    # If we found a match or it's already in our categories
                    if matching_cat or cat_name in categories:
                        use_cat = matching_cat if matching_cat else cat_name
                        try:
                            score = float(item['score'])
                            # Ensure score is between 0-100
                            score = max(0.1, min(100.0, score))  # Minimum 0.1 to avoid division by zero
                            category_scores[use_cat] = score
                            if 'reasoning' in item:
                                category_reasonings[use_cat] = item['reasoning']
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid score value: {item['score']}")
            
            # Make sure we have scores for all categories
            for cat in categories:
                if cat not in category_scores:
                    # Assign minimum score for missing categories
                    category_scores[cat] = 0.1
            
            # Handle the case where all scores are the same
            all_same = len(set(category_scores.values())) == 1
            if all_same:
                # Apply a curve - 1st category gets highest score, then linear decrease
                sorted_cats = sorted(categories)
                for i, cat in enumerate(sorted_cats):
                    # Simple linear decay from 100 to 10
                    category_scores[cat] = 100 - (i * (90 / max(1, len(categories) - 1)))
            
            # Convert scores to probabilities
            total_score = sum(category_scores.values())
            probabilities = {cat: score/total_score for cat, score in category_scores.items()}
            
            # Create sorted results array
            results = [{"class": cat, "probability": prob} for cat, prob in probabilities.items()]
            results.sort(key=lambda x: x["probability"], reverse=True)
            
            # Apply exponential skewing to make distribution more extreme
            # This will make high probabilities higher and low probabilities lower
            if len(results) > 1 and results[0]["probability"] < 0.8:
                # Square the probabilities and renormalize
                for result in results:
                    result["probability"] = result["probability"] ** 2
                
                # Renormalize to ensure sum is 1.0
                total_prob = sum(r["probability"] for r in results)
                for result in results:
                    result["probability"] = result["probability"] / total_prob
            
            # Round to 4 decimal places
            for result in results:
                result["probability"] = round(result["probability"], 4)
            
            # Get top 3 classifications
            top_classifications = results[:min(3, len(results))]
            
            # Calculate total token usage
            input_tokens = llm_result_step1.get("input_tokens", 0)
            completion_tokens = llm_result_step1.get("completion_tokens", 0)
            output_tokens = llm_result_step1.get("output_tokens", 0)
            
            # Prepare the response
            response_data = {
                "classifications": results,
                "top_classifications": top_classifications,
                "model_used": model,
                "input_tokens": input_tokens,
                "completion_tokens": completion_tokens,
                "output_tokens": output_tokens
            }
        
        # Parse the JSON result, handling potential JSON parsing errors
        try:
            classification_results = json.loads(result_text)
            
            # Ensure all categories have probabilities and format is correct
            valid_results = []
            total_probability = 0.0
            
            for result in classification_results:
                if isinstance(result, dict) and 'class' in result and 'probability' in result:
                    # Ensure class is in the provided categories
                    class_name = result['class']
                    if class_name not in categories:
                        # Try to find closest match
                        for category in categories:
                            if category.lower() in class_name.lower():
                                class_name = category
                                break
                        
                        # If still no match, skip this result
                        if class_name not in categories:
                            continue
                    
                    # Add valid result with matched class name
                    prob = float(result['probability'])
                    valid_results.append({
                        'class': class_name,
                        'probability': prob
                    })
                    total_probability += prob
            
            # If no valid results, create default with uniform distribution
            if not valid_results:
                prob_per_category = 1.0 / len(categories)
                valid_results = [{'class': cat, 'probability': prob_per_category} for cat in categories]
                total_probability = 1.0
            
            # Normalize probabilities if they don't sum to 1.0
            if abs(total_probability - 1.0) > 0.01:  # Allow small rounding errors
                logger.warning(f"Probabilities sum to {total_probability}, normalizing to 1.0")
                for result in valid_results:
                    result['probability'] = result['probability'] / total_probability
            
            # Sort by probability (descending)
            valid_results.sort(key=lambda x: x['probability'], reverse=True)
            
            # Get top 3 classifications (or all if fewer than 3)
            top_classifications = valid_results[:min(3, len(valid_results))]
            
            # Prepare response with classifications and token usage
            response_data = {
                "classifications": valid_results,
                "top_classifications": top_classifications,
                "model_used": model,
                "input_tokens": llm_result.get("input_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "output_tokens": llm_result.get("output_tokens", 0)
            }
            
            return create_api_response(response_data, 200)
            
        except json.JSONDecodeError as je:
            logger.error(f"Error parsing LLM response as JSON: {str(je)}")
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
