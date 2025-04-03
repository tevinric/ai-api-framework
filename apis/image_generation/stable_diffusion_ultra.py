from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
import pytz
from datetime import datetime
import uuid
import io
import json
import requests
import base64
import os
from apis.utils.config import IMAGE_GENERATION_CONTAINER, STORAGE_ACCOUNT
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.utils.fileService import FileService

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Azure Blob Storage container for images
BLOB_CONTAINER_NAME = IMAGE_GENERATION_CONTAINER
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{BLOB_CONTAINER_NAME}"

# Stable Diffusion Ultra API configuration
STABLE_DIFFUSION_API_URL = 'https://StableDiffusion-Image-Ultra.eastus.models.ai.azure.com/images/generations'
STABLE_DIFFUSION_API_KEY = os.environ.get('STABLE_DIFFUSION_API_KEY')

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def stable_diffusion_ultra_route():
    """
    Generate images using Azure Stable Diffusion Ultra
    ---
    tags:
      - Image Generation
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
            - prompt
          properties:
            prompt:
              type: string
              description: Text prompt describing the image to generate
            negative_prompt:
              type: string
              description: Text prompt describing what to avoid in the generated image
              default: ""
            size:
              type: string
              enum: [1024x1024, 768x768, 512x512]
              default: 1024x1024
              description: Output image size
            output_format:
              type: string
              enum: [png, jpeg]
              default: png
              description: Output image format
            seed:
              type: integer
              description: Seed for reproducible generation
              default: -1
    produces:
      - application/json
    consumes:
      - application/json
    security:
      - ApiKeyHeader: []
    responses:
      200:
        description: Successful image generation
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            message:
              type: string
              description: Success message
              example: "Image generated successfully"
            file_id:
              type: string
              description: ID of the file in the upload system
              example: "12345678-1234-5678-1234-567812345678"
            user_id:
              type: integer
              description: ID of the authenticated user
            user_name:
              type: string
              description: Name of the authenticated user
            user_email:
              type: string
              description: Email of the authenticated user
            model:
              type: string
              description: The model used for generation
              example: "stable-diffusion-ultra"
      400:
        description: Bad request
        schema:
          type: object
          properties:
            response:
              type: string
              example: "400"
            message:
              type: string
              description: Error message
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
              description: Authentication error details
      500:
        description: Server error
        schema:
          type: object
          properties:
            response:
              type: string
              example: "500"
            message:
              type: string
              description: Error message from the server or Stable Diffusion API
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
            "response": "400",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    if 'prompt' not in data or not data['prompt']:
        return create_api_response({
            "response": "400",
            "message": "Missing required field: prompt"
        }, 400)
    
    # Extract parameters with defaults
    prompt = data.get('prompt', '')
    negative_prompt = data.get('negative_prompt', '')
    size = data.get('size', '1024x1024')
    output_format = data.get('output_format', 'png')
    seed = data.get('seed', -1)
    
    # Validate size option
    valid_sizes = ['1024x1024', '768x768', '512x512']
    if size not in valid_sizes:
        return create_api_response({
            "response": "400",
            "message": f"Invalid size. Must be one of: {', '.join(valid_sizes)}"
        }, 400)
    
    # Validate output_format option
    valid_formats = ['png', 'jpeg']
    if output_format not in valid_formats:
        return create_api_response({
            "response": "400",
            "message": f"Invalid output_format. Must be one of: {', '.join(valid_formats)}"
        }, 400)
    
    # Check if Stable Diffusion API key is available
    if not STABLE_DIFFUSION_API_KEY:
        logger.error("Stable Diffusion API key not found in environment variables")
        return create_api_response({
            "response": "500",
            "message": "Stable Diffusion API key not configured"
        }, 500)
    
    try:
        # Log API usage
        logger.info(f"Stable Diffusion Ultra API called by user: {user_id}")
        
        # Prepare the request to Stable Diffusion API
        sd_request_data = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "size": size,
            "output_format": output_format,
            "seed": seed
        }
        
        # Make request to Stable Diffusion Ultra API
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {STABLE_DIFFUSION_API_KEY}'
        }
        
        logger.info(f"Sending request to Stable Diffusion API with data: {sd_request_data}")
        sd_response = requests.post(STABLE_DIFFUSION_API_URL, json=sd_request_data, headers=headers)
        
        # Check if the request was successful
        if sd_response.status_code != 200:
            logger.error(f"Stable Diffusion API error: {sd_response.text}")
            return create_api_response({
                "response": str(sd_response.status_code),
                "message": f"Stable Diffusion API error: {sd_response.text}"
            }, sd_response.status_code)
        
        # Parse the response
        sd_result = sd_response.json()
        
        # Log the response for debugging
        logger.info(f"Received Stable Diffusion API response: {sd_result}")
        
        # Extract the image data
        try:
            # The Stable Diffusion Ultra API returns a base64 encoded image in the 'result' field
            if 'result' in sd_result:
                # Decode the base64 string to get the image data
                image_data = base64.b64decode(sd_result['result'])
            # Alternative response structure possibilities
            elif 'images' in sd_result and len(sd_result['images']) > 0:
                image_data = base64.b64decode(sd_result['images'][0])
            elif 'image' in sd_result:
                image_data = base64.b64decode(sd_result['image'])
            elif 'output' in sd_result:
                image_data = base64.b64decode(sd_result['output'])
            elif 'output_url' in sd_result:
                # If the API returns a URL to the generated image
                image_url = sd_result['output_url']
                image_response = requests.get(image_url)
                image_data = image_response.content
            else:
                # If the API returns the entire JSON as a single string containing the base64 image
                # This is a fallback when the response is not in the expected format
                response_text = sd_response.text
                # Try to extract base64 data if it exists in the response
                if "," in response_text:
                    base64_part = response_text.split(",")[1]
                    image_data = base64.b64decode(base64_part)
                else:
                    # Try treating the entire response as base64
                    image_data = base64.b64decode(response_text)
        except Exception as e:
            logger.error(f"Error extracting image data: {str(e)}")
            logger.error(f"Unexpected response format from Stable Diffusion API: {sd_result}")
            return create_api_response({
                "response": "500",
                "message": f"Failed to extract image data from Stable Diffusion API response: {str(e)}"
            }, 500)
        
        # Generate a unique name for the image
        image_name = f"sd-ultra-{uuid.uuid4()}.{output_format}"
        
        # Set the content type for the file
        content_type = f"image/{output_format}"
        
        # Create a custom file-like object that mimics Flask's file object
        class MockFileObj:
            def __init__(self, data, filename, content_type):
                self._io = io.BytesIO(data)
                self.filename = filename
                self.content_type = content_type
            
            def read(self):
                return self._io.getvalue()

        # Create the file object and upload using FileService
        file_obj = MockFileObj(image_data, image_name, content_type)
        file_info, error = FileService.upload_file(file_obj, g.user_id, IMAGE_GENERATION_CONTAINER)

        if error:
            logger.error(f"Failed to upload generated image: {error}")
            return create_api_response({
                "response": "500",
                "message": f"Failed to upload generated image: {error}"
            }, 500)

        file_id = file_info["file_id"]
        
        if not file_id:
            logger.error("Failed to upload generated image")
            return create_api_response({
                "response": "500",
                "message": "Failed to upload generated image"
            }, 500)
        
        # Prepare successful response with user details
        return create_api_response({
            "response": "200",
            "message": "Image generated successfully",
            "file_id": file_id,
            "user_id": user_details["id"],
            "user_name": user_details["user_name"],
            "user_email": user_details["user_email"],
            "model": "stable-diffusion-ultra"
        }, 200)
        
    except Exception as e:
        logger.error(f"Stable Diffusion Ultra API error: {str(e)}")
        status_code = 500 if not str(e).startswith("4") else 400
        return create_api_response({
            "response": str(status_code),
            "message": str(e)
        }, status_code)

def register_stable_diffusion_ultra_routes(app):
    """Register routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    
    app.route('/image-generation/stable-diffusion-ultra', methods=['POST'])(api_logger(check_balance(stable_diffusion_ultra_route)))
