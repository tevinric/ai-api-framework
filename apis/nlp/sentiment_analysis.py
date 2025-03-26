from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
import pytz
from datetime import datetime
import requests
import json
import re

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

# Define comprehensive emotion list for consistent analysis
EMOTION_LIST = [
    # Primary emotions
    "happiness", "sadness", "anger", "fear", "surprise", "disgust",
    
    # Secondary emotions
    "joy", "excitement", "contentment", "satisfaction", "relief", "pride", "optimism",
    "love", "affection", "compassion", "gratitude", "admiration", 
    "grief", "disappointment", "regret", "shame", "guilt", "remorse",
    "frustration", "irritation", "rage", "contempt", "jealousy", "envy",
    "anxiety", "worry", "nervousness", "dread", "horror", "panic",
    "amazement", "astonishment", "confusion", "bewilderment",
    "boredom", "apathy", "indifference",
    
    # Complex emotional states
    "hope", "anticipation", "curiosity", "interest", "awe", "wonder",
    "trust", "confidence", "doubt", "uncertainty", "skepticism",
    "nostalgia", "longing", "yearning", "desire", "craving",
    "embarrassment", "humiliation", "insecurity", 
    "sympathy", "empathy", "pity",
    "amusement", "enthusiasm", "thrill", "exhilaration",
    "serenity", "calmness", "tranquility", "peace",
    "determination", "motivation", "ambition", "resolve",
    "overwhelm", "stress", "pressure", "burnout",
    "vulnerability", "helplessness", "powerlessness",
    "loneliness", "isolation", "abandonment",
    "resentment", "bitterness", "hostility",
    "defensiveness", "suspicion", "wariness"
]

def sentiment_analysis_route():
    """
    Consumes 0.5 AI credits per call when using gpt-4o-mini, 2 credits for gpt-4o
    
    Classify text sentiment into positive, neutral, or negative categories
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
            - user_input
          properties:
            user_input:
              type: string
              description: Text to analyze for sentiment
            model:
              type: string
              enum: [gpt-4o-mini, gpt-4o]
              default: gpt-4o-mini
              description: LLM model to use for sentiment analysis
    produces:
      - application/json
    responses:
      200:
        description: Sentiment analysis result
        schema:
          type: object
          properties:
            top_sentiment:
              type: string
              enum: [positive, neutral, negative]
              example: "positive"
            all_sentiments:
              type: array
              items:
                type: object
                properties:
                  sentiment:
                    type: string
                    example: "positive"
                  confidence:
                    type: number
                    format: float
                    example: 0.85
              example: [
                {"sentiment": "positive", "confidence": 0.85},
                {"sentiment": "neutral", "confidence": 0.12},
                {"sentiment": "negative", "confidence": 0.03}
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
              example: "Missing required field: user_input"
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
              example: "Error processing sentiment analysis request"
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
    required_fields = ['user_input']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Extract parameters
    user_input = data.get('user_input', '')
    model = data.get('model', 'gpt-4o-mini')
    
    # Validate model selection
    if model not in ['gpt-4o-mini', 'gpt-4o']:
        return create_api_response({
            "error": "Bad Request",
            "message": "Model must be either 'gpt-4o-mini' or 'gpt-4o'"
        }, 400)
    
    try:
        # Create system message for sentiment analysis
        system_prompt = """You are a sentiment analysis system. Your task is to classify the provided text into one of three sentiment categories: positive, neutral, or negative.

Provide a confidence score (0-1) for each sentiment category based on how strongly the text expresses that sentiment.

IMPORTANT: The sum of confidence scores doesn't need to equal 1. Assign each sentiment a score based on its presence in the text.

Respond ONLY in valid JSON format with the following structure:
{
  "sentiments": [
    {"sentiment": "positive", "confidence": 0.75},
    {"sentiment": "neutral", "confidence": 0.20},
    {"sentiment": "negative", "confidence": 0.05}
  ]
}

Only use "positive", "neutral", and "negative" as sentiment values."""
        
        # Create user message with text to analyze
        user_message = f"Text to analyze: {user_input}"
        
        # Determine which LLM endpoint to call based on model selection
        llm_endpoint = f"{request.url_root.rstrip('/')}/llm/{model}"
        
        # Prepare payload for LLM request
        llm_request_data = {
            "system_prompt": system_prompt,
            "user_input": user_message,
            "temperature": 0.0  # Set temperature to 0 for deterministic results
        }
        
        # Call selected LLM API
        logger.info(f"Calling {model} for sentiment analysis")
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
        llm_message = llm_result.get("message", "").strip()
        
        # Parse the JSON response from the LLM
        try:
            # Find JSON content in the LLM's response (it might include other text)
            json_match = re.search(r'({[\s\S]*})', llm_message)
            if json_match:
                sentiment_json = json.loads(json_match.group(1))
            else:
                sentiment_json = json.loads(llm_message)
            
            # Extract sentiments list
            sentiments = sentiment_json.get("sentiments", [])
            
            # Validate sentiments and ensure we have all three categories
            valid_sentiments = ["positive", "neutral", "negative"]
            normalized_sentiments = []
            
            # Create a dictionary to track which sentiments we've seen
            seen_sentiments = {s: False for s in valid_sentiments}
            
            for sentiment in sentiments:
                sentiment_name = sentiment.get("sentiment", "").lower()
                confidence = sentiment.get("confidence", 0)
                
                if sentiment_name in valid_sentiments:
                    normalized_sentiments.append({
                        "sentiment": sentiment_name,
                        "confidence": confidence
                    })
                    seen_sentiments[sentiment_name] = True
            
            # Add any missing sentiments with 0 confidence
            for sentiment_name, seen in seen_sentiments.items():
                if not seen:
                    normalized_sentiments.append({
                        "sentiment": sentiment_name,
                        "confidence": 0.0
                    })
            
            # Sort sentiments by confidence (descending)
            sorted_sentiments = sorted(normalized_sentiments, key=lambda x: x["confidence"], reverse=True)
            
            # Get the top sentiment
            top_sentiment = sorted_sentiments[0]["sentiment"] if sorted_sentiments else "neutral"
            
            # Prepare response with sentiment analysis results and token usage
            response_data = {
                "top_sentiment": top_sentiment,
                "all_sentiments": sorted_sentiments,
                "model_used": model,
                "input_tokens": llm_result.get("input_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "output_tokens": llm_result.get("output_tokens", 0)
            }
            
            return create_api_response(response_data, 200)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing LLM JSON response: {str(e)}, Response: {llm_message}")
            
            # Fallback response if JSON parsing fails
            fallback_sentiments = [
                {"sentiment": "positive", "confidence": 0.0},
                {"sentiment": "neutral", "confidence": 1.0},
                {"sentiment": "negative", "confidence": 0.0}
            ]
            
            response_data = {
                "top_sentiment": "neutral",
                "all_sentiments": fallback_sentiments,
                "model_used": model,
                "input_tokens": llm_result.get("input_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "output_tokens": llm_result.get("output_tokens", 0),
                "parsing_error": f"Could not parse LLM response as JSON. Using fallback sentiment analysis."
            }
            
            return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error in sentiment analysis: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing sentiment analysis request: {str(e)}"
        }, 500)


def advanced_sentiment_analysis_route():
    """
    Consumes 0.5 AI credits per call when using gpt-4o-mini, 2 credits for gpt-4o
    
    Analyze text to identify multiple emotions with confidence scores
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
            - user_input
          properties:
            user_input:
              type: string
              description: Text to analyze for emotions
            model:
              type: string
              enum: [gpt-4o-mini, gpt-4o]
              default: gpt-4o-mini
              description: LLM model to use for advanced emotion analysis
    produces:
      - application/json
    responses:
      200:
        description: Advanced emotion analysis result
        schema:
          type: object
          properties:
            top_emotion:
              type: string
              example: "happiness"
            top_3_emotions:
              type: array
              items:
                type: string
              example: ["happiness", "excitement", "satisfaction"]
            all_emotions:
              type: array
              items:
                type: object
                properties:
                  emotion:
                    type: string
                    example: "happiness"
                  confidence:
                    type: number
                    format: float
                    example: 0.85
              example: [
                {"emotion": "happiness", "confidence": 0.85},
                {"emotion": "excitement", "confidence": 0.65},
                {"emotion": "satisfaction", "confidence": 0.40},
                {"emotion": "sadness", "confidence": 0.05}
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
              example: "Missing required field: user_input"
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
              example: "Error processing advanced emotion analysis request"
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
    required_fields = ['user_input']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Extract parameters
    user_input = data.get('user_input', '')
    model = data.get('model', 'gpt-4o-mini')
    
    # Validate model selection
    if model not in ['gpt-4o-mini', 'gpt-4o']:
        return create_api_response({
            "error": "Bad Request",
            "message": "Model must be either 'gpt-4o-mini' or 'gpt-4o'"
        }, 400)
    
    try:
        # Create system message for advanced emotion analysis
        # Using the comprehensive EMOTION_LIST defined at the top of the file
        emotion_list_str = ", ".join(EMOTION_LIST)
        
        system_prompt = f"""You are an advanced emotion analysis system. Your task is to identify emotions present in the provided text with confidence scores.

Consider ONLY the following emotions: {emotion_list_str}

For the provided text, identify all emotions that are present and assign a confidence score (0-1) for each emotion based on how strongly it is expressed.

IMPORTANT: Only include emotions that are actually present in the text. The sum of confidence scores doesn't need to equal 1. Only use emotions from the provided list.

Respond ONLY in valid JSON format with the following structure:
{{
  "emotions": [
    {{"emotion": "happiness", "confidence": 0.85}},
    {{"emotion": "excitement", "confidence": 0.65}},
    {{"emotion": "satisfaction", "confidence": 0.40}}
  ]
}}

Include ALL emotions detected in the text with appropriate confidence scores."""
        
        # Create user message with text to analyze
        user_message = f"Text to analyze: {user_input}"
        
        # Determine which LLM endpoint to call based on model selection
        llm_endpoint = f"{request.url_root.rstrip('/')}/llm/{model}"
        
        # Prepare payload for LLM request
        llm_request_data = {
            "system_prompt": system_prompt,
            "user_input": user_message,
            "temperature": 0.0  # Set temperature to 0 for deterministic results
        }
        
        # Call selected LLM API
        logger.info(f"Calling {model} for advanced emotion analysis")
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
        llm_message = llm_result.get("message", "").strip()
        
        # Parse the JSON response from the LLM
        try:
            # Find JSON content in the LLM's response (it might include other text)
            json_match = re.search(r'({[\s\S]*})', llm_message)
            if json_match:
                emotions_json = json.loads(json_match.group(1))
            else:
                emotions_json = json.loads(llm_message)
            
            # Extract emotions list
            emotions = emotions_json.get("emotions", [])
            
            # Validate that all emotions are in our predefined list
            valid_emotions = []
            for emotion in emotions:
                emotion_name = emotion.get("emotion", "").lower()
                confidence = emotion.get("confidence", 0)
                
                # Only include emotions that are in our predefined list
                if emotion_name in [e.lower() for e in EMOTION_LIST]:
                    valid_emotions.append({
                        "emotion": emotion_name,
                        "confidence": confidence
                    })
            
            # If no valid emotions were detected, add a neutral emotion
            if not valid_emotions:
                valid_emotions = [{"emotion": "neutral", "confidence": 1.0}]
            
            # Sort emotions by confidence (descending)
            sorted_emotions = sorted(valid_emotions, key=lambda x: x["confidence"], reverse=True)
            
            # Get the top emotion and top 3 emotions
            top_emotion = sorted_emotions[0]["emotion"] if sorted_emotions else "neutral"
            top_3_emotions = [e["emotion"] for e in sorted_emotions[:min(3, len(sorted_emotions))]]
            
            # Prepare response with emotion analysis results and token usage
            response_data = {
                "top_emotion": top_emotion,
                "top_3_emotions": top_3_emotions,
                "all_emotions": sorted_emotions,
                "model_used": model,
                "input_tokens": llm_result.get("input_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "output_tokens": llm_result.get("output_tokens", 0)
            }
            
            return create_api_response(response_data, 200)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing LLM JSON response: {str(e)}, Response: {llm_message}")
            
            # Fallback response if JSON parsing fails
            fallback_emotions = [
                {"emotion": "neutral", "confidence": 1.0}
            ]
            
            response_data = {
                "top_emotion": "neutral",
                "top_3_emotions": ["neutral"],
                "all_emotions": fallback_emotions,
                "model_used": model,
                "input_tokens": llm_result.get("input_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "output_tokens": llm_result.get("output_tokens", 0),
                "parsing_error": f"Could not parse LLM response as JSON. Using fallback emotion analysis."
            }
            
            return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error in advanced emotion analysis: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing advanced emotion analysis request: {str(e)}"
        }, 500)


def register_sentiment_routes(app):
    """Register sentiment analysis routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    
    app.route('/nlp/sentiment', methods=['POST'])(api_logger(check_balance(sentiment_analysis_route)))
    app.route('/nlp/sentiment/advanced', methods=['POST'])(api_logger(check_balance(advanced_sentiment_analysis_route)))
