from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
import pytz
from datetime import datetime
import uuid
import io
import requests
import base64
from apis.utils.config import create_api_response
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.utils.fileService import FileService, FILE_UPLOAD_CONTAINER
import os

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FLUX.1-Kontext-pro API Configuration - Azure Cognitive Services
AZURE_ENDPOINT = "https://gaia-foundry-za.cognitiveservices.azure.com/"
DEPLOYMENT_NAME = "FLUX.1-Kontext-pro"
MODEL_NAME = "FLUX.1-Kontext-pro"  # Azure OpenAI requires explicit model parameter
API_VERSION = "2025-04-01-preview"

def is_valid_file_id(file_id):
    """
    Check if file_id is valid and not empty/null/none
    """
    if not file_id:
        return False
    
    # Convert to string and check for common empty values
    file_id_str = str(file_id).lower().strip()
    
    # Check for empty, null, none, or whitespace
    if file_id_str in ['', 'null', 'none', 'undefined']:
        return False
    
    # Check if it's a valid UUID format (basic check)
    try:
        uuid.UUID(file_id_str)
        return True
    except ValueError:
        return False

def download_file_content(file_id, user_id):
    """
    Download file content using the correct FileService pattern
    """
    try:
        # Get file info and URL using FileService
        file_info, error = FileService.get_file_url(file_id, user_id)
        if error:
            logger.error(f"Error retrieving file info for {file_id}: {error}")
            return None, f"Error retrieving file: {error}"
        
        # Get file URL and validate it's an image
        file_url = file_info.get('file_url')
        file_name = file_info.get('file_name', '')
        content_type = file_info.get('content_type', '')
        
        if not file_url:
            return None, "File URL not found"
        
        # Validate that it's an image file
        if not content_type.startswith('image/'):
            return None, f"File must be an image. Found content type: {content_type}"
        
        logger.info(f"Downloading image file - Name: {file_name}, Type: {content_type}")
        
        # Download the file content
        response = requests.get(file_url, timeout=30)
        response.raise_for_status()
        
        return response.content, None
        
    except requests.RequestException as e:
        logger.error(f"Error downloading file {file_id}: {str(e)}")
        return None, f"Error downloading file: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error downloading file {file_id}: {str(e)}")
        return None, f"Unexpected error: {str(e)}"

def flux_1_kontext_pro_service(prompt, output_format="png", n=1, size="1024x1024", image_data=None, operation="generation"):
    """
    Service function to call FLUX.1-Kontext-pro API via Azure Cognitive Services
    Supports both image generation and editing
    """
    try:
        # Get API key from environment (using OPENAI_API_KEY as subscription key)
        subscription_key = os.environ.get("OPENAI_API_KEY")
        if not subscription_key:
            return {
                "success": False,
                "error": "Azure API key not configured"
            }

        # Build the correct Azure endpoint URL based on operation
        base_path = f'openai/deployments/{DEPLOYMENT_NAME}/images'
        endpoint_suffix = "generations" if operation == "generation" else "edits"
        params = f'?api-version={API_VERSION}'
        url = f"{AZURE_ENDPOINT}{base_path}/{endpoint_suffix}{params}"

        if operation == "generation":
            # Standard generation request
            headers = {
                "Api-Key": subscription_key,
                "Content-Type": "application/json"
            }

            payload = {
                "model": MODEL_NAME,  # Required by Azure OpenAI API
                "prompt": prompt,
                "n": n,
                "size": size,
                "output_format": output_format
            }
            
            logger.info(f"Calling FLUX.1-Kontext-pro API (generation) at {url} with model: {MODEL_NAME}")
            logger.info(f"Request payload: {payload}")
            response = requests.post(url, json=payload, headers=headers)

        else:
            # Image editing request - requires multipart form data
            headers = {
                "Api-Key": subscription_key
            }

            # For multipart requests, the model parameter goes in the data section
            data = {
                "model": MODEL_NAME,  # Required by Azure OpenAI API
                "prompt": prompt,
                "n": n,
                "size": size
            }

            files = {
                "image": ("input_image.png", image_data, "image/png")
            }
            
            logger.info(f"Calling FLUX.1-Kontext-pro API (editing) at {url} with model: {MODEL_NAME}")
            logger.info(f"Request data: {data}")
            response = requests.post(url, headers=headers, data=data, files=files)
        
        if response.status_code != 200:
            logger.error(f"FLUX.1-Kontext-pro API error: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": f"FLUX.1-Kontext-pro API error: {response.status_code} - {response.text}"
            }

        response_data = response.json()
        
        if "data" not in response_data or not response_data["data"]:
            return {
                "success": False,
                "error": "No image data received from FLUX.1-Kontext-pro API"
            }

        # Extract the base64 image data
        b64_image = response_data["data"][0]["b64_json"]
        
        return {
            "success": True,
            "b64_image": b64_image,
            "output_format": output_format,
            "size": size,
            "operation": operation
        }

    except Exception as e:
        logger.error(f"FLUX.1-Kontext-pro service error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def custom_flux_kontext_image_generation_route():
    """
    Generate images using FLUX.1-Kontext-pro (multimodal)
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
            file_id:
              type: string
              description: Optional file ID of an existing image to use as input (for multimodal generation). Leave empty, null, or "none" for text-only generation.
            output_format:
              type: string
              enum: [png, jpeg]
              default: png
              description: Output image format
            n:
              type: integer
              minimum: 1
              maximum: 1
              default: 1
              description: Number of images to generate (currently limited to 1)
            size:
              type: string
              enum: [1024x1024, 1792x1024, 1024x1792]
              default: 1024x1024
              description: Output image size
    produces:
      - application/json
    consumes:
      - application/json
    security:
      - ApiKeyAuth: []
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
              description: The model used
              example: "flux-1-kontext-pro"
            output_format:
              type: string
              description: The output format used
            size:
              type: string
              description: The image size used
            operation:
              type: string
              description: The operation performed (generation or editing)
      400:
        description: Bad request - Missing required fields or invalid parameter values
      401:
        description: Authentication error - Invalid or expired token
      500:
        description: Server error or API service unavailable
    """
    try:
        # Get request data first
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
        file_id = data.get('file_id', None)
        output_format = data.get('output_format', 'png')
        n = data.get('n', 1)
        size = data.get('size', '1024x1024')
        
        # Validate output_format option
        valid_formats = ['png', 'jpeg']
        if output_format not in valid_formats:
            return create_api_response({
                "response": "400",
                "message": f"Invalid output_format. Must be one of: {', '.join(valid_formats)}"
            }, 400)
        
        # Validate n parameter
        if not isinstance(n, int) or n < 1 or n > 1:
            return create_api_response({
                "response": "400",
                "message": "Invalid n. Must be 1 (currently only 1 image generation is supported)"
            }, 400)
        
        # Validate size option
        valid_sizes = ['1024x1024', '1792x1024', '1024x1792']
        if size not in valid_sizes:
            return create_api_response({
                "response": "400",
                "message": f"Invalid size. Must be one of: {', '.join(valid_sizes)}"
            }, 400)

        # Get user ID from g object (set by middleware)
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            logger.error("User ID not found in g object")
            return create_api_response({
                "response": "401",
                "message": "Authentication required"
            }, 401)

        # Get user details from database
        user_details = DatabaseService.get_user_by_id(user_id)
        if not user_details:
            logger.error(f"User details not found for user_id: {user_id}")
            return create_api_response({
                "response": "401",
                "message": "User not found"
            }, 401)

        # Handle image input if file_id is provided and valid
        image_data = None
        operation = "generation"
        
        # Check if file_id is provided and valid
        if is_valid_file_id(file_id):
            logger.info(f"Processing file_id: {file_id} for multimodal input")
            
            # Download file content using the correct FileService pattern
            file_content, download_error = download_file_content(file_id, user_id)
            
            if download_error:
                logger.error(f"Error downloading file {file_id}: {download_error}")
                return create_api_response({
                    "response": "400",
                    "message": f"Unable to access file: {download_error}"
                }, 400)
            
            if not file_content:
                logger.error(f"Empty file content for file_id {file_id}")
                return create_api_response({
                    "response": "400",
                    "message": f"File not found or empty: {file_id}"
                }, 400)
            
            # Set operation to editing since we have an image
            image_data = file_content
            operation = "editing"
            logger.info(f"Successfully loaded image file ID: {file_id} for multimodal editing")
                
        else:
            # No valid file_id provided - proceed with text-only generation
            if file_id is not None:
                logger.info(f"file_id provided but invalid or empty ('{file_id}') - proceeding with text-only generation")
            else:
                logger.info("No file_id provided - proceeding with text-only generation")
            operation = "generation"
        
        # Log API usage
        logger.info(f"FLUX.1-Kontext-pro Image {operation} API called by user: {user_id}, format: {output_format}, size: {size}")
        
        # Use the FLUX.1-Kontext-pro service function
        response = flux_1_kontext_pro_service(
            prompt=prompt,
            output_format=output_format,
            n=n,
            size=size,
            image_data=image_data,
            operation=operation
        )
        
        # Check if the service call was successful
        if not response["success"]:
            logger.error(f"FLUX.1-Kontext-pro image {operation} service failed: {response['error']}")
            return create_api_response({
                "response": "500",
                "message": f"Image {operation} failed: {response['error']}"
            }, 500)
        
        # Extract response data
        b64_image = response["b64_image"]
        output_format_used = response["output_format"]
        size_used = response["size"]
        operation_used = response["operation"]
        
        # Model name for usage tracking
        model_for_usage = "flux-1-kontext-pro"
        
        # Convert base64 to binary
        image_data_result = base64.b64decode(b64_image)
        
        # Generate a unique name for the image
        file_extension = "png" if output_format_used == "png" else "jpg"
        image_name = f"flux-kontext-{operation_used}-{uuid.uuid4()}.{file_extension}"
        
        # Create a custom file-like object that mimics Flask's file object
        class MockFileObj:
            def __init__(self, data, filename, content_type):
                self.data = data
                self.filename = filename
                self.content_type = content_type
                self.stream = io.BytesIO(data)
            
            def read(self, size=-1):
                return self.stream.read(size)
            
            def seek(self, pos):
                return self.stream.seek(pos)
            
            def tell(self):
                return self.stream.tell()
        
        # Create the file object and upload using FileService
        content_type = "image/png" if output_format_used == "png" else "image/jpeg"
        file_obj = MockFileObj(image_data_result, image_name, content_type)
        file_info, error = FileService.upload_file(file_obj, user_id, FILE_UPLOAD_CONTAINER)

        if error:
            logger.error(f"Failed to upload generated image: {error}")
            return create_api_response({
                "response": "500",
                "message": f"Failed to upload generated image: {error}"
            }, 500)

        file_id_result = file_info["file_id"]
        
        if not file_id_result:
            logger.error("Failed to upload generated image")
            return create_api_response({
                "response": "500",
                "message": "Failed to upload generated image"
            }, 500)
        
        # Prepare successful response with user details
        return create_api_response({
            "response": "200",
            "message": f"Image {operation_used} completed successfully",
            "file_id": file_id_result,
            "user_id": user_details["id"],
            "user_name": user_details["user_name"],
            "user_email": user_details["user_email"],
            "model": model_for_usage,
            "output_format": output_format_used,
            "size": size_used,
            "operation": operation_used
        }, 200)
        
    except Exception as e:
        logger.error(f"FLUX.1-Kontext-pro Image Generation API error: {str(e)}")
        return create_api_response({
            "response": "500",
            "message": f"Internal server error: {str(e)}"
        }, 500)

def register_flux_kontext_image_generation_routes(app):
    """Register routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access

    # Register the route with middleware
    app.route('/image-generation/flux-1-kontext-pro', methods=['POST'])(
        track_usage(
            api_logger(
                check_endpoint_access(
                    check_balance(custom_flux_kontext_image_generation_route)
                )
            )
        )
    )