from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
import pytz
from datetime import datetime
import uuid
import io
import requests
from openai import AzureOpenAI
from apis.utils.config import get_openai_client, get_azure_blob_client, IMAGE_GENERATION_CONTAINER, STORAGE_ACCOUNT, create_api_response
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from azure.storage.blob import BlobServiceClient, ContentSettings
from apis.utils.fileService import FileService, FILE_UPLOAD_CONTAINER
from apis.utils.imageServices import dalle3_service

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default deployment model for image generation
DEFAULT_IMAGE_DEPLOYMENT = 'dall-e-3'

# Azure Blob Storage container for images
BLOB_CONTAINER_NAME = IMAGE_GENERATION_CONTAINER
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{BLOB_CONTAINER_NAME}"

def custom_image_generation_route():
    """
    Generate images using Azure OpenAI DALLE-3
    ---
    tags:
      - Image Generation
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
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
            size:
              type: string
              enum: [1024x1024, 1792x1024, 1024x1792]
              default: 1024x1024
              description: Output image size
            quality:
              type: string
              enum: [standard, hd]
              default: standard
              description: Image quality (standard or high definition)
            style:
              type: string
              enum: [vivid, natural]
              default: vivid
              description: Image generation style
    produces:
      - application/json
    consumes:
      - application/json
    security:
      - ApiKeyAuth: []
    x-code-samples:
      - lang: curl
        source: |-
          curl -X POST "https://your-api-domain.com/image/generate" \\
          -H "X-Token: your-api-token-here" \\
          -H "X-Correlation-ID: your-correlation-id" \\
          -H "Content-Type: application/json" \\
          -d '{
            "prompt": "A futuristic city with flying cars and tall glass buildings",
            "size": "1024x1024",
            "quality": "standard",
            "style": "vivid"
          }'
    x-sample-header:
      X-Token: your-api-token-here
      X-Correlation-ID: your-correlation-id
      Content-Type: application/json
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
              description: The model used based on quality
              enum: [dalle3, dalle3-hd]
      400:
        description: Bad request - Missing required fields or invalid parameter values
        schema:
          type: object
          properties:
            response:
              type: string
              example: "400"
            message:
              type: string
              description: Error message
              example: "Missing required field: prompt"
      401:
        description: Authentication error - Invalid or expired token
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Authentication Error"
            message:
              type: string
              description: Authentication error details
              example: "Missing X-Token header"
      500:
        description: Server error or API service unavailable
        schema:
          type: object
          properties:
            response:
              type: string
              example: "500"
            message:
              type: string
              description: Error message from the server, OpenAI API, or Azure Blob Storage
              example: "Failed to generate image"
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
    size = data.get('size', '1024x1024')
    quality = data.get('quality', 'standard')
    style = data.get('style', 'vivid')
    
    # Validate size option
    valid_sizes = ['1024x1024', '1792x1024', '1024x1792']
    if size not in valid_sizes:
        return create_api_response({
            "response": "400",
            "message": f"Invalid size. Must be one of: {', '.join(valid_sizes)}"
        }, 400)
    
    # Validate quality option
    valid_qualities = ['standard', 'hd']
    if quality not in valid_qualities:
        return create_api_response({
            "response": "400",
            "message": f"Invalid quality. Must be one of: {', '.join(valid_qualities)}"
        }, 400)
    
    # Validate style option
    valid_styles = ['vivid', 'natural']
    if style not in valid_styles:
        return create_api_response({
            "response": "400",
            "message": f"Invalid style. Must be one of: {', '.join(valid_styles)}"
        }, 400)
    
    try:
        # Log API usage
        logger.info(f"Image Generation API called by user: {user_id}, quality: {quality}")
        
        # Use the consolidated dalle3_service function
        response = dalle3_service(
            prompt=prompt,
            size=size,
            quality=quality,
            style=style,
            deployment=DEFAULT_IMAGE_DEPLOYMENT
        )
        
        # Check if the service call was successful
        if not response["success"]:
            logger.error(f"Image generation service failed: {response['error']}")
            return create_api_response({
                "response": "500",
                "message": f"Image generation failed: {response['error']}"
            }, 500)
        
        # Extract response data
        b64_image = response["b64_image"]
        client_used = response["client_used"]
        quality_used = response["quality"]
        
        # Determine model name based on quality for usage tracking
        model_for_usage = "dalle3-hd" if quality_used == "hd" else "dalle3"
        
        # Convert base64 to binary
        import base64
        image_data = base64.b64decode(b64_image)
        
        # Generate a unique name for the image
        image_name = f"image-{uuid.uuid4()}.png"
        
        # Create a custom file-like object that mimics Flask's file object
        class MockFileObj:
            def __init__(self, data, filename, content_type):
                self._io = io.BytesIO(data)
                self.filename = filename
                self.content_type = content_type
            
            def read(self):
                return self._io.getvalue()

        # Create the file object and upload using FileService
        file_obj = MockFileObj(image_data, image_name, 'image/png')
        file_info, error = FileService.upload_file(file_obj, g.user_id, FILE_UPLOAD_CONTAINER)

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
            "model": model_for_usage,
            "client_used": client_used,
            "quality": quality_used
        }, 200)
        
    except Exception as e:
        logger.error(f"Image Generation API error: {str(e)}")
        status_code = 500 if not str(e).startswith("4") else 400
        return create_api_response({
            "response": str(status_code),
            "message": str(e)
        }, status_code)

def register_image_generation_routes(app):
    """Register routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access

    # Register the route
    app.route('/image-generation/dalle3', methods=['POST'])(track_usage(api_logger(check_endpoint_access(check_balance(custom_image_generation_route)))))