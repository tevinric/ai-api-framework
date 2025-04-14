# apis/image_processing.py
from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.fileService import FileService
import logging
import pytz
from datetime import datetime
import os
import base64
import requests
import json
from apis.utils.config import get_openai_client

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = get_openai_client()

# Reference image path
REFERENCE_IMAGE_PATH = "static/resources/romeo/vehicle-reference-views.jpg"

# Fixed deployment model - using GPT-4o
DEPLOYMENT = 'gpt-4o'

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def vehicle_damage_assessment_route():
    """
    Consumes 2 AI credits per call
    
    Vehicle damage assessment using GPT-4o to compare the provided image with reference images
    and determine the vehicle view.
    ---
    tags:
      - Image Processing
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
            - file_id
          properties:
            file_id:
              type: string
              description: ID of the uploaded image file to analyze
    produces:
      - application/json
    responses:
      200:
        description: Successful image analysis
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            vehicle_view:
              type: string
              enum: ["front", "left-side", "right-side", "rear", "top-view"]
              example: "front"
            message:
              type: string
              example: "The image shows a front view of the vehicle with damage to the bumper and headlight."
            user_id:
              type: string
              example: "user123"
            user_name:
              type: string
              example: "John Doe"
            user_email:
              type: string
              example: "john.doe@example.com"
            model:
              type: string
              example: "gpt-4o"
            prompt_tokens:
              type: integer
              example: 125
            completion_tokens:
              type: integer
              example: 84
            total_tokens:
              type: integer
              example: 209
            cached_tokens:
              type: integer
              example: 0
      400:
        description: Bad request
      401:
        description: Authentication error
      404:
        description: File not found
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
            "response": "400",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['file_id']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "response": "400",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Get the file_id from request
    file_id = data.get('file_id')
    
    try:
        # Get the uploaded file using FileService
        file_info, error = FileService.get_file_url(file_id, user_id)
        
        if error:
            if "not found" in error:
                return create_api_response({
                    "error": "Not Found",
                    "message": error
                }, 404)
            elif "permission" in error:
                return create_api_response({
                    "error": "Forbidden",
                    "message": error
                }, 403)
            else:
                return create_api_response({
                    "error": "Server Error",
                    "message": error
                }, 500)
        
        # Load the uploaded image
        try:
            uploaded_image_url = file_info["file_url"]
            response = requests.get(uploaded_image_url)
            if response.status_code != 200:
                return create_api_response({
                    "error": "Server Error",
                    "message": f"Failed to download image file: HTTP {response.status_code}"
                }, 500)
            uploaded_image_data = response.content
        except Exception as e:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error loading uploaded image: {str(e)}"
            }, 500)
        
        # Load the reference image
        try:
            with open(REFERENCE_IMAGE_PATH, 'rb') as f:
                reference_image_data = f.read()
        except Exception as e:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error loading reference image: {str(e)}"
            }, 500)
        
        # Encode both images as base64
        uploaded_image_base64 = base64.b64encode(uploaded_image_data).decode('utf-8')
        reference_image_base64 = base64.b64encode(reference_image_data).decode('utf-8')
        
        # Determine MIME type for uploaded image
        uploaded_mime_type = file_info["content_type"]
        
        # Create system prompt
        system_prompt = """
        You are an expert vehicle damage assessor. Your task is to analyze the uploaded vehicle image and compare it to the reference image containing standard vehicle views.
        
        The reference image shows different views of a vehicle: front, left-side, right-side, rear, and top-view.
        
        Based on the uploaded image, determine which of these standard views the uploaded image most closely matches, ignoring any damage present.
        
        Your output must include ONLY ONE of these exact view names: "front", "left-side", "right-side", "rear", or "top-view".
        
        Additionally, provide a brief assessment of any damage visible in the uploaded image.
        
        Format your response as a JSON object with two fields:
        1. "vehicle_view" - MUST be exactly one of: "front", "left-side", "right-side", "rear", or "top-view"
        2. "damage_assessment" - A brief description of visible damage, if any
        """
        
        # Create the message structure
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {
                    "type": "text",
                    "text": "I need to identify which standard vehicle view this image represents, using the reference image provided."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{uploaded_mime_type};base64,{uploaded_image_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": "Here is the reference image showing the standard vehicle views:"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{reference_image_base64}"
                    }
                }
            ]}
        ]
        
        # Make the API call to GPT-4o
        response = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1000
        )
        
        # Extract response data
        result = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        output_tokens = response.usage.total_tokens
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        # Parse the JSON result
        try:
            result_dict = json.loads(result)
            vehicle_view = result_dict.get("vehicle_view", "")
            damage_assessment = result_dict.get("damage_assessment", "")
            
            # Validate that vehicle_view is one of the allowed values
            valid_views = ["front", "left-side", "right-side", "rear", "top-view"]
            if vehicle_view not in valid_views:
                logger.warning(f"LLM returned invalid vehicle view: {vehicle_view}. Defaulting to 'front'.")
                vehicle_view = "front"
            
        except Exception as e:
            logger.error(f"Error parsing LLM result: {str(e)}")
            return create_api_response({
                "response": "500",
                "message": f"Error parsing analysis result: {str(e)}"
            }, 500)
        
        # Prepare successful response with user details
        return create_api_response({
            "response": "200",
            "vehicle_view": vehicle_view,
            "message": damage_assessment,
            "user_id": user_details["id"],
            "user_name": user_details["user_name"],
            "user_email": user_details["user_email"],
            "model": DEPLOYMENT,
            "prompt_tokens": input_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": output_tokens,
            "cached_tokens": cached_tokens
        }, 200)
        
    except Exception as e:
        logger.error(f"Vehicle damage assessment error: {str(e)}")
        return create_api_response({
            "response": "500",
            "message": f"Error processing image: {str(e)}"
        }, 500)

def register_image_processing_routes(app):
    """Register image processing routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    from apis.utils.usageMiddleware import track_usage
    
    app.route('/image-processing/vehicle-damage-assessment', methods=['POST'])(track_usage(api_logger(check_balance(vehicle_damage_assessment_route))))
