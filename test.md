# App folder structure
ai-api-framework/
|-- apis
|    |-- admin 
|           |-- admin_create_user.py
|           |-- admin_delete_user.py
|           |-- admin_update_user.py
|    |-- endpoint_management
|           |-- admin_endpoint_management.py
|    |-- image_generation
|           |-- dalle3.py
|    |-- llm
|           |-- deepseek_r1.py
|           |-- gpt_4o_mini.py
|           |-- gpt_4o.py
|           |-- gpt_o1_mini.py
|           |-- llama.py
|    |-- token_services
|           |-- get_token.py
|           |-- get_token_details.py
|           |-- refresh_token.py
|    |-- utils
|           |-- balanceMiddleware.py
|           |-- balanceService.py
|           |-- config.py
|           |-- databaseService.py
|           |-- logMiddleware.py
|           |-- tokenService.py
|    |-- balance_management
|           |-- balance_endpoints.py
|    |-- file_upload
|           |-- upload_file.py
|-- app.py
|-- requirements.txt

##################################################################################################################################################################

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/apis/admin/admin_create_user.py


from flask import jsonify, request, g , make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import uuid
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def create_user_route():
    """
    Create a new user in the system (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - token
            - user_name
            - user_email
          properties:
            token:
              type: string
              description: A valid token for verification
            user_name:
              type: string
              description: Username for the new user
            user_email:
              type: string
              description: Email address for the new user
            common_name:
              type: string
              description: Common name for the new user (optional)
            scope:
              type: integer
              description: Permission scope for the new user (1-5)
            active:
              type: boolean
              description: Whether the user is active
            comment:
              type: string
              description: Optional comment about the user
    produces:
      - application/json
    responses:
      201:
        description: User created successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: User created successfully
            user_id:
              type: string
              description: ID of the newly created user
            api_key:
              type: string
              description: API key assigned to the new user
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
              example: Missing required fields or invalid data
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
              example: Missing API Key header or Invalid API Key
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: Admin privileges required
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
              example: Error creating user
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to create users"
        }, 403)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate token from request body
    token = data.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Valid token is required in the request body"
        }, 400)
        
    # Verify the token is valid
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
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
    
    # Validate required fields for user creation
    required_fields = ['user_name', 'user_email']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Validate email format (basic check)
    if '@' not in data['user_email']:
        return create_api_response({
            "error": "Bad Request",
            "message": "Invalid email format"
        }, 400)
    
    # Extract user data from request
    new_user = {
        'user_name': data['user_name'],
        'user_email': data['user_email'],
        'common_name': data.get('common_name', None),
        'scope': data.get('scope', 1),  # Default scope is 1
        'active': data.get('active', True),  # Default active is True
        'comment': data.get('comment', None)
    }
    
    # Validate scope is within allowed range (1-5)
    if not (1 <= new_user['scope'] <= 5):
        return create_api_response({
            "error": "Bad Request",
            "message": "Scope must be between 1 and 5"
        }, 400)
    
    try:
        # Create user in the database
        user_id, api_key = DatabaseService.create_user(new_user)
        
        if not user_id:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to create user"
            }, 500)
        
        return create_api_response({
            "message": "User created successfully",
            "user_id": user_id,
            "api_key": api_key
        }, 201)
        
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error creating user: {str(e)}"
        }, 500)

def register_create_user_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/create-user', methods=['POST'])(api_logger(create_user_route))


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
apis\file_upload\upload_file.py

from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.config import get_azure_blob_client, ensure_container_exists
import logging
import uuid
import pytz
from datetime import datetime
import os

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

# Define container for file uploads - different from image container
FILE_UPLOAD_CONTAINER = os.environ.get("AZURE_STORAGE_UPLOAD_CONTAINER", "file-uploads")
STORAGE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT")
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{FILE_UPLOAD_CONTAINER}"

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def upload_file_route():
    """
    Upload one or more files to Azure Blob Storage
    ---
    tags:
      - File Upload
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
      - name: files
        in: formData
        type: file
        required: true
        description: Files to upload (can be multiple)
    consumes:
      - multipart/form-data
    produces:
      - application/json
    responses:
      200:
        description: Files uploaded successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Files uploaded successfully
            uploaded_files:
              type: array
              items:
                type: object
                properties:
                  file_name:
                    type: string
                  file_id:
                    type: string
                  content_type:
                    type: string
      400:
        description: Bad request
      401:
        description: Authentication error
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
    
    # Validate token and get token details
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token"
        }, 401)
        
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
        
    g.user_id = token_details["user_id"]
    g.token_id = token_details["id"]
    
    # Check if any files were uploaded
    if 'files' not in request.files:
        return create_api_response({
            "error": "Bad Request",
            "message": "No files part in the request"
        }, 400)
    
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return create_api_response({
            "error": "Bad Request",
            "message": "No files selected for upload"
        }, 400)
    
    try:
        # Ensure container exists
        ensure_container_exists(FILE_UPLOAD_CONTAINER)
        
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(FILE_UPLOAD_CONTAINER)
        
        uploaded_files = []
        
        for file in files:
            # Generate unique ID for the file
            file_id = str(uuid.uuid4())
            original_filename = file.filename
            
            # Create a blob name using the file_id to ensure uniqueness
            # Keep original extension if any
            _, file_extension = os.path.splitext(original_filename)
            blob_name = f"{file_id}{file_extension}"
            
            # Upload the file to blob storage
            blob_client = container_client.get_blob_client(blob_name)
            file_content = file.read()  # Read file content
            
            content_settings = None
            if file.content_type:
                from azure.storage.blob import ContentSettings
                content_settings = ContentSettings(content_type=file.content_type)
            
            blob_client.upload_blob(file_content, overwrite=True, content_settings=content_settings)
            
            # Generate URL to the blob
            blob_url = f"{BASE_BLOB_URL}/{blob_name}"
            
            # Store file info in database
            db_conn = None
            cursor = None
            try:
                db_conn = DatabaseService.get_connection()
                cursor = db_conn.cursor()
                
                insert_query = """
                INSERT INTO file_uploads (
                    id, 
                    user_id, 
                    original_filename, 
                    blob_name, 
                    blob_url, 
                    content_type, 
                    file_size, 
                    upload_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()))
                """
                
                cursor.execute(insert_query, [
                    file_id,
                    g.user_id,
                    original_filename,
                    blob_name,
                    blob_url,
                    file.content_type or 'application/octet-stream',
                    len(file_content)  # File size in bytes
                ])
                
                db_conn.commit()
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except:
                        pass
                if db_conn:
                    try:
                        db_conn.close()
                    except:
                        pass
            
            # Add to the list of uploaded files
            uploaded_files.append({
                "file_name": original_filename,
                "file_id": file_id,
                "content_type": file.content_type or 'application/octet-stream'
            })
            
            logger.info(f"File uploaded: {original_filename} with ID {file_id} by user {g.user_id}")
        
        return create_api_response({
            "message": "Files uploaded successfully",
            "uploaded_files": uploaded_files
        }, 200)
        
    except Exception as e:
        logger.error(f"Error uploading files: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error uploading files: {str(e)}"
        }, 500)

def get_file_url_route():
    """
    Get access URL for a previously uploaded file using its ID
    ---
    tags:
      - File Upload
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
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
              description: Unique file identifier
    produces:
      - application/json
    responses:
      200:
        description: File URL retrieved successfully
        schema:
          type: object
          properties:
            file_name:
              type: string
            file_url:
              type: string
            content_type:
              type: string
            upload_date:
              type: string
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
    
    # Validate token and get token details
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token"
        }, 401)
        
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
        
    g.user_id = token_details["user_id"]
    g.token_id = token_details["id"]
    
    # Get request data
    data = request.get_json()
    if not data or 'file_id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "file_id is required in the request body"
        }, 400)
    
    file_id = data['file_id']
    
    # Query database for file information
    db_conn = None
    cursor = None
    
    try:
        db_conn = DatabaseService.get_connection()
        cursor = db_conn.cursor()
        
        query = """
        SELECT id, user_id, original_filename, blob_url, content_type, upload_date
        FROM file_uploads
        WHERE id = ?
        """
        
        cursor.execute(query, [file_id])
        file_info = cursor.fetchone()
        
        if not file_info:
            return create_api_response({
                "error": "Not Found",
                "message": f"File with ID {file_id} not found"
            }, 404)
        
        # Get user scope from database
        user_scope_query = """
        SELECT scope FROM users WHERE id = ?
        """
        cursor.execute(user_scope_query, [g.user_id])
        user_scope_result = cursor.fetchone()
        user_scope = user_scope_result[0] if user_scope_result else 1  # Default to regular user if not found
    
        # Check if user has access to this file (admin or file owner)
        # Admins (scope=0) can access any file
        if user_scope != 0 and str(file_info[1]) != g.user_id:
            return create_api_response({
                "error": "Forbidden",
                "message": "You don't have permission to access this file"
            }, 403)
        
        # Return file info with URL
        result = {
            "file_name": file_info[2],
            "file_url": file_info[3],
            "content_type": file_info[4],
            "upload_date": file_info[5].isoformat() if file_info[5] else None
        }
        
        return create_api_response(result, 200)
    
    except Exception as e:
        logger.error(f"Error retrieving file URL: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving file URL: {str(e)}"
        }, 500)
        
    finally:
        # Ensure cursor and connection are closed even if an exception occurs
        if cursor:
            try:
                cursor.close()
            except:
                pass
        
        if db_conn:
            try:
                db_conn.close()
            except:
                pass

def delete_file_route():
    """
    Delete a previously uploaded file using its ID
    ---
    tags:
      - File Upload
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
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
              description: Unique file identifier
    produces:
      - application/json
    responses:
      200:
        description: File deleted successfully
      400:
        description: Bad request
      401:
        description: Authentication error
      403:
        description: Forbidden - not authorized to delete this file
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
    
    # Validate token and get token details
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token"
        }, 401)
        
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
        
    g.user_id = token_details["user_id"]
    g.token_id = token_details["id"]
    
    # Get request data
    data = request.get_json()
    if not data or 'file_id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "file_id is required in the request body"
        }, 400)
    
    file_id = data['file_id']
    
    # Query database for file information
    db_conn = None
    cursor = None
    
    try:
        db_conn = DatabaseService.get_connection()
        cursor = db_conn.cursor()
        
        query = """
        SELECT id, user_id, blob_name
        FROM file_uploads
        WHERE id = ?
        """
        
        cursor.execute(query, [file_id])
        file_info = cursor.fetchone()
        
        if not file_info:
            return create_api_response({
                "error": "Not Found",
                "message": f"File with ID {file_id} not found"
            }, 404)
        
        # Get user scope from database
        user_scope_query = """
        SELECT scope FROM users WHERE id = ?
        """
        cursor.execute(user_scope_query, [g.user_id])
        user_scope_result = cursor.fetchone()
        user_scope = user_scope_result[0] if user_scope_result else 1  # Default to regular user if not found
        
        # Check if user has permission to delete this file (admin or file owner)
        # Admins (scope=0) can delete any file
        if user_scope != 0 and str(file_info[1]) != g.user_id:
            return create_api_response({
                "error": "Forbidden",
                "message": "You don't have permission to delete this file"
            }, 403)
        
        # Delete from blob storage
        blob_name = file_info[2]
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(FILE_UPLOAD_CONTAINER)
        blob_client = container_client.get_blob_client(blob_name)
        
        # Try to delete the blob (may already be deleted)
        try:
            blob_client.delete_blob()
        except Exception as e:
            logger.warning(f"Error deleting blob {blob_name}, may already be deleted: {str(e)}")
        
        # Delete from database
        delete_query = """
        DELETE FROM file_uploads
        WHERE id = ?
        """
        
        cursor.execute(delete_query, [file_id])
        db_conn.commit()
        
        logger.info(f"File {file_id} deleted by user {g.user_id}")
        
        return create_api_response({
            "message": "File deleted successfully",
            "file_id": file_id
        }, 200)
    
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error deleting file: {str(e)}"
        }, 500)
    
    finally:
        # Ensure cursor and connection are closed even if an exception occurs
        if cursor:
            try:
                cursor.close()
            except:
                pass
        
        if db_conn:
            try:
                db_conn.close()
            except:
                pass

def register_file_upload_routes(app):
    """Register file upload routes with the Flask app"""
    app.route('/upload-file', methods=['POST'])(api_logger(upload_file_route))
    app.route('/get-file-url', methods=['POST'])(api_logger(get_file_url_route))
    app.route('/delete-file', methods=['DELETE'])(api_logger(delete_file_route))


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
apis\image_generation\dalle3.py

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
from apis.utils.config import get_openai_client, get_azure_blob_client, IMAGE_GENERATION_CONTAINER, STORAGE_ACCOUNT
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from azure.storage.blob import BlobServiceClient, ContentSettings

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = get_openai_client()

# Default deployment model for image generation
DEFAULT_IMAGE_DEPLOYMENT = 'dall-e-3'  # Options: 'dalle3', 'dalle3-hd'

# Azure Blob Storage container for images
BLOB_CONTAINER_NAME = IMAGE_GENERATION_CONTAINER
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{BLOB_CONTAINER_NAME}"

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def save_image_to_blob(image_data, image_name):
    """Save image to Azure Blob Storage and return the URL"""
    try:
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        
        # Get container client
        container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        
        # Create container if it doesn't exist
        if not container_client.exists():
            container_client.create_container()
        
        # Set content settings for the blob (image)
        content_settings = ContentSettings(content_type='image/png')
        
        # Upload image to blob
        blob_client = container_client.get_blob_client(image_name)
        blob_client.upload_blob(image_data, overwrite=True, content_settings=content_settings)
        
        # Return the URL to the image
        return f"{BASE_BLOB_URL}/{image_name}"
    
    except Exception as e:
        logger.error(f"Error saving image to blob storage: {str(e)}")
        raise

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
            deployment:
              type: string
              enum: [dall-e-3, dalle3-hd]
              default: dall-e-3
              description: The DALLE-3 model deployment to use
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
      - ApiKeyHeader: []
    x-code-samples:
      - lang: curl
        source: |-
          curl -X POST "https://your-api-domain.com/image/generate" \\
          -H "X-Token: your-api-token-here" \\
          -H "Content-Type: application/json" \\
          -d '{
            "prompt": "A futuristic city with flying cars and tall glass buildings",
            "deployment": "dall-e-3",
            "size": "1024x1024",
            "quality": "standard",
            "style": "vivid"
          }'
    x-sample-header:
      X-Token: your-api-token-here
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
            image_url:
              type: string
              description: URL to the generated image in Azure Blob Storage
              example: "https://yourstorageaccount.blob.core.windows.net/dalle-images/image-12345.png"
            prompt_tokens:
              type: integer
              description: Number of prompt tokens used
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
              description: The model deployment used
              enum: [dall-e-3, dalle3-hd]
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
              examples:
                - "Request body is required"
                - "Missing required field: prompt"
                - "Invalid deployment. Must be one of: dall-e-3, dalle3-hd"
                - "Invalid size. Must be one of: 1024x1024, 1792x1024, 1024x1792"
                - "Invalid quality. Must be one of: standard, hd"
                - "Invalid style. Must be one of: vivid, natural"
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
              examples:
                - "Missing X-Token header"
                - "Invalid token - not found in database"
                - "Token has expired"
                - "Token is no longer valid with provider"
                - "User associated with token not found"
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
              description: Error message from the server, OpenAI API, or Azure Blob Storage
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
    deployment = data.get('deployment', DEFAULT_IMAGE_DEPLOYMENT)
    size = data.get('size', '1024x1024')
    quality = data.get('quality', 'standard')
    style = data.get('style', 'vivid')
    
    # Validate deployment option
    valid_deployments = ['dall-e-3', 'dalle3-hd']
    if deployment not in valid_deployments:
        return create_api_response({
            "response": "400",
            "message": f"Invalid deployment. Must be one of: {', '.join(valid_deployments)}"
        }, 400)
    
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
        logger.info(f"Image Generation API called by user: {user_id}, deployment: {deployment}")
        
        # Make request to DALLE-3
        response = client.images.generate(
            model=deployment,
            prompt=prompt,
            n=1,  # Generate 1 image
            size=size,
            quality=quality,
            style=style,
            response_format="b64_json"  # Get base64 encoded image data
        )
        
        # Extract token usage
        prompt_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') and hasattr(response.usage, 'prompt_tokens') else 0
        
        # Get the image data (base64)
        b64_image = response.data[0].b64_json
        
        # Convert base64 to binary
        import base64
        image_data = base64.b64decode(b64_image)
        
        # Generate a unique name for the image
        image_name = f"image-{uuid.uuid4()}.png"
        
        # Save the image to Azure Blob Storage
        image_url = save_image_to_blob(image_data, image_name)
        
        # Prepare successful response with user details
        return create_api_response({
            "response": "200",
            "message": "Image generated successfully",
            "image_url": image_url,
            "prompt_tokens": prompt_tokens,
            "user_id": user_details["id"],
            "user_name": user_details["user_name"],
            "user_email": user_details["user_email"],
            "model": deployment
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
    
    app.route('/image-generation/dalle3', methods=['POST'])(api_logger(check_balance(custom_image_generation_route)))

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/apis/admin/admin_delete_user.py
from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response
  
def admin_delete_user_route():
    """
    Delete a user from the system (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: X-API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - token
            - id
          properties:
            token:
              type: string
              description: A valid token for verification
            id:
              type: string
              description: UUID of the user to delete
    produces:
      - application/json
    responses:
      200:
        description: User deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: User deleted successfully
            user_id:
              type: string
              description: ID of the deleted user
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
              example: Missing API Key header or Invalid API Key
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: Admin privileges required
      404:
        description: Not Found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: User not found
      409:
        description: Conflict
        schema:
          type: object
          properties:
            error:
              type: string
              example: Conflict
            message:
              type: string
              example: Cannot delete user with active tokens
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
              example: Error deleting user
    """
    # Get API key from request header
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (X-API-Key)"
        }, 401)
    
    # Validate API key
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to delete users"
        }, 403)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['token', 'id']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Validate token from request body
    token = data.get('token')
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
    
    g.token_id = token_details["id"]
    
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
    
    # Get user ID to delete
    user_id = data.get('id')
    
    # Check if user exists
    user_exists = DatabaseService.get_user_by_id(user_id)
    if not user_exists:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Prevent admins from deleting themselves
    if user_id == admin_info["id"]:
        return create_api_response({
            "error": "Forbidden",
            "message": "Administrators cannot delete their own accounts"
        }, 403)
    
    try:
        # Delete user from database
        success = DatabaseService.delete_user(user_id)
        
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to delete user"
            }, 500)
        
        return create_api_response({
            "message": "User deleted successfully",
            "user_id": user_id
        }, 200)
        
    except Exception as e:
        error_msg = str(e)
        
        # Handle specific error for users with active tokens
        if "foreign key constraint" in error_msg.lower():
            return create_api_response({
                "error": "Conflict",
                "message": "Cannot delete user with active tokens. Revoke all tokens first."
            }, 409
            )
            
        logger.error(f"Error deleting user: {error_msg}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error deleting user: {error_msg}"
        }, 500)

def register_admin_delete_user_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/delete-user', methods=['POST'])(api_logger(admin_delete_user_route))


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/apis/endpoint_management/admin_endpoint_management.py

from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import uuid
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def admin_add_endpoint_route():
    """
    Add a new endpoint to the endpoints table (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: "Admin API Key for authentication"
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - token
            - endpoint_path
            - endpoint_name
          properties:
            token:
              type: string
              description: "A valid token for verification"
            endpoint_path:
              type: string
              description: "The API endpoint path (e.g., /llm/custom)"
            endpoint_name:
              type: string
              description: "A user-friendly name for the endpoint"
            description:
              type: string
              description: "Optional description of the endpoint"
            active:
              type: boolean
              description: "Whether the endpoint is active (default: true)"
            cost:
              type: integer
              description: "Cost in balance units for each call to this endpoint (default: 1)"
    produces:
      - application/json
    responses:
      201:
        description: "Endpoint created successfully"
      400:
        description: "Bad request"
      401:
        description: "Authentication error"
      403:
        description: "Forbidden - not an admin"
      409:
        description: "Conflict - endpoint already exists"
      500:
        description: "Server error"
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to manage endpoints"
        }, 403)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate token
    token = data.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Valid token is required"
        }, 400)
        
    # Verify token is valid and not expired
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
    # Check token expiration
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Validate required fields
    required_fields = ['endpoint_path', 'endpoint_name']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Extract endpoint data
    endpoint_path = data.get('endpoint_path')
    endpoint_name = data.get('endpoint_name')
    description = data.get('description', '')
    active = data.get('active', True)
    cost = data.get('cost', 1)  # Default cost is 1
    
    # Validate cost is a positive integer
    try:
        cost = int(cost)
        if cost <= 0:
            return create_api_response({
                "error": "Bad Request",
                "message": "Cost must be a positive integer"
            }, 400)
    except (ValueError, TypeError):
        return create_api_response({
            "error": "Bad Request",
            "message": "Cost must be a valid integer"
        }, 400)
    
    # Ensure endpoint_path starts with /
    if not endpoint_path.startswith('/'):
        endpoint_path = '/' + endpoint_path
    
    try:
        # Check if endpoint already exists
        existing_endpoint = get_endpoint_by_path(endpoint_path)
        if existing_endpoint:
            return create_api_response({
                "error": "Conflict",
                "message": f"Endpoint with path '{endpoint_path}' already exists",
                "endpoint_id": existing_endpoint["id"]
            }, 409)
        
        # Add endpoint to database
        endpoint_id = add_endpoint_to_database(endpoint_path, endpoint_name, description, active, cost)
        
        if not endpoint_id:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to add endpoint to database"
            }, 500)
        
        logger.info(f"Endpoint '{endpoint_path}' added successfully by admin {admin_info['id']}")
        
        return create_api_response({
            "message": "Endpoint added successfully",
            "endpoint_id": endpoint_id,
            "endpoint_path": endpoint_path,
            "endpoint_name": endpoint_name,
            "active": active,
            "cost": cost
        }, 201)
        
    except Exception as e:
        logger.error(f"Error adding endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error adding endpoint: {str(e)}"
        }, 500)

def admin_get_endpoints_route():
    """
    Get all endpoints from the endpoints table (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: "Admin API Key for authentication"
      - name: active
        in: query
        type: boolean
        required: false
        description: "Filter by active status (optional)"
    produces:
      - application/json
    responses:
      200:
        description: "Endpoints retrieved successfully"
      401:
        description: "Authentication error"
      403:
        description: "Forbidden - not an admin"
      500:
        description: "Server error"
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to view endpoints"
        }, 403)
    
    # Get optional active filter
    active_filter = request.args.get('active')
    if active_filter:
        active_filter = active_filter.lower() == 'true'
    
    try:
        # Get endpoints from database
        endpoints = get_all_endpoints(active_filter)
        
        return create_api_response({
            "endpoints": endpoints,
            "count": len(endpoints)
        }, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving endpoints: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving endpoints: {str(e)}"
        }, 500)

def admin_update_endpoint_route():
    """
    Update an existing endpoint in the endpoints table (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: "Admin API Key for authentication"
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - token
            - endpoint_id
          properties:
            token:
              type: string
              description: "A valid token for verification"
            endpoint_id:
              type: string
              description: "ID of the endpoint to update"
            endpoint_path:
              type: string
              description: "New API endpoint path (optional)"
            endpoint_name:
              type: string
              description: "New user-friendly name (optional)"
            description:
              type: string
              description: "New description (optional)"
            active:
              type: boolean
              description: "New active status (optional)"
            cost:
              type: integer
              description: "New cost in balance units for each call (optional)"
    produces:
      - application/json
    responses:
      200:
        description: "Endpoint updated successfully"
      400:
        description: "Bad request"
      401:
        description: "Authentication error"
      403:
        description: "Forbidden - not an admin"
      404:
        description: "Endpoint not found"
      409:
        description: "Conflict - endpoint path already exists"
      500:
        description: "Server error"
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to update endpoints"
        }, 403)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate token
    token = data.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Valid token is required"
        }, 400)
        
    # Verify token is valid and not expired
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
    # Check token expiration
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Validate endpoint_id
    endpoint_id = data.get('endpoint_id')
    if not endpoint_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "endpoint_id is required"
        }, 400)
    
    try:
        # Check if endpoint exists
        endpoint = get_endpoint_by_id(endpoint_id)
        if not endpoint:
            return create_api_response({
                "error": "Not Found",
                "message": f"Endpoint with ID '{endpoint_id}' not found"
            }, 404)
        
        # Extract update fields
        update_data = {}
        if 'endpoint_path' in data:
            new_path = data['endpoint_path']
            # Ensure endpoint_path starts with /
            if not new_path.startswith('/'):
                new_path = '/' + new_path
                
            # Check if new path already exists for a different endpoint
            if new_path != endpoint['endpoint_path']:
                existing = get_endpoint_by_path(new_path)
                if existing and existing['id'] != endpoint_id:
                    return create_api_response({
                        "error": "Conflict",
                        "message": f"Endpoint with path '{new_path}' already exists"
                    }, 409)
            update_data['endpoint_path'] = new_path
            
        if 'endpoint_name' in data:
            update_data['endpoint_name'] = data['endpoint_name']
            
        if 'description' in data:
            update_data['description'] = data['description']
            
        if 'active' in data:
            update_data['active'] = 1 if data['active'] else 0
        
        if 'cost' in data:
            # Validate cost is a positive integer
            try:
                cost = int(data['cost'])
                if cost <= 0:
                    return create_api_response({
                        "error": "Bad Request",
                        "message": "Cost must be a positive integer"
                    }, 400)
                update_data['cost'] = cost
            except (ValueError, TypeError):
                return create_api_response({
                    "error": "Bad Request",
                    "message": "Cost must be a valid integer"
                }, 400)
        
        # Only proceed if there are fields to update
        if not update_data:
            return create_api_response({
                "message": "No changes to update",
                "endpoint": endpoint
            }, 200)
        
        # Update endpoint in database
        success = update_endpoint(endpoint_id, update_data)
        
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to update endpoint"
            }, 500)
        
        # Get updated endpoint
        updated_endpoint = get_endpoint_by_id(endpoint_id)
        
        logger.info(f"Endpoint '{endpoint_id}' updated successfully by admin {admin_info['id']}")
        
        return create_api_response({
            "message": "Endpoint updated successfully",
            "endpoint": updated_endpoint
        }, 200)
        
    except Exception as e:
        logger.error(f"Error updating endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error updating endpoint: {str(e)}"
        }, 500)

# Database utility functions
def get_endpoint_by_path(endpoint_path):
    """Get endpoint details by path"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT id, endpoint_name, endpoint_path, description, active, cost
        FROM endpoints
        WHERE endpoint_path = ?
        """
        
        cursor.execute(query, [endpoint_path])
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            return None
            
        return {
            "id": str(result[0]),
            "endpoint_name": result[1],
            "endpoint_path": result[2],
            "description": result[3],
            "active": bool(result[4]),
            "cost": result[5]
        }
        
    except Exception as e:
        logger.error(f"Error getting endpoint by path: {str(e)}")
        return None

def get_endpoint_by_id(endpoint_id):
    """Get endpoint details by ID"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT id, endpoint_name, endpoint_path, description, active, cost,
               created_at, modified_at
        FROM endpoints
        WHERE id = ?
        """
        
        cursor.execute(query, [endpoint_id])
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            return None
            
        return {
            "id": str(result[0]),
            "endpoint_name": result[1],
            "endpoint_path": result[2],
            "description": result[3],
            "active": bool(result[4]),
            "cost": result[5],
            "created_at": result[6].isoformat() if result[6] else None,
            "modified_at": result[7].isoformat() if result[7] else None
        }
        
    except Exception as e:
        logger.error(f"Error getting endpoint by ID: {str(e)}")
        return None

def get_all_endpoints(active_filter=None):
    """Get all endpoints, optionally filtered by active status"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT id, endpoint_name, endpoint_path, description, active, cost,
               created_at, modified_at
        FROM endpoints
        """
        
        params = []
        if active_filter is not None:
            query += " WHERE active = ?"
            params.append(1 if active_filter else 0)
        
        query += " ORDER BY endpoint_path"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        endpoints = []
        for row in results:
            endpoints.append({
                "id": str(row[0]),
                "endpoint_name": row[1],
                "endpoint_path": row[2],
                "description": row[3],
                "active": bool(row[4]),
                "cost": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "modified_at": row[7].isoformat() if row[7] else None
            })
            
        return endpoints
        
    except Exception as e:
        logger.error(f"Error getting all endpoints: {str(e)}")
        return []

def add_endpoint_to_database(endpoint_path, endpoint_name, description, active, cost=1):
    """Add a new endpoint to the database"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        endpoint_id = str(uuid.uuid4())
        
        query = """
        INSERT INTO endpoints (
            id, endpoint_name, endpoint_path, description, active, cost,
            created_at, modified_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?,
            DATEADD(HOUR, 2, GETUTCDATE()), DATEADD(HOUR, 2, GETUTCDATE())
        )
        """
        
        cursor.execute(query, [
            endpoint_id,
            endpoint_name,
            endpoint_path,
            description,
            1 if active else 0,
            cost
        ])
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return endpoint_id
        
    except Exception as e:
        logger.error(f"Error adding endpoint: {str(e)}")
        return None

def update_endpoint(endpoint_id, update_data):
    """Update an existing endpoint in the database"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        # Build dynamic update query
        set_clauses = []
        params = []
        
        for field, value in update_data.items():
            set_clauses.append(f"{field} = ?")
            params.append(value)
        
        # Add modified_at timestamp
        set_clauses.append("modified_at = DATEADD(HOUR, 2, GETUTCDATE())")
        
        query = f"""
        UPDATE endpoints
        SET {', '.join(set_clauses)}
        WHERE id = ?
        """
        
        # Add endpoint_id to params
        params.append(endpoint_id)
        
        cursor.execute(query, params)
        
        rows_affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        return rows_affected > 0
        
    except Exception as e:
        logger.error(f"Error updating endpoint: {str(e)}")
        return False

def register_admin_endpoint_routes(app):
    """Register admin endpoint management routes with the Flask app"""
    app.route('/admin/endpoints', methods=['GET'])(api_logger(admin_get_endpoints_route))
    app.route('/admin/add-endpoint', methods=['POST'])(api_logger(admin_add_endpoint_route))
    app.route('/admin/update-endpoint', methods=['PUT'])(api_logger(admin_update_endpoint_route))


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
\apis\token_services\get_token_details.py

from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
from datetime import datetime
import pytz

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def get_token_details_route():
    """
    Retrieve details for a specific token after validating the API key.
    ---
    tags:
      - Token Service
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
      - name: token
        in: query
        type: string
        required: true
        description: The token to validate and get details for
    produces:
      - application/json
    responses:
      200:
        description: Token details retrieved successfully
        schema:
          type: object
          properties:
            token_status:
              type: string
              enum: [valid, invalid, expired]
              description: Current status of the token
              example: valid
            user_id:
              type: string
              description: ID of the user who issued the token
              example: "12345678-1234-1234-1234-123456789012"
            token_scope:
              type: string
              description: Scope of the token
              example: "0,1,2,3,4,5"
            token_expiration_time:
              type: string
              format: date-time
              description: Token expiration timestamp
              example: "yyyy-mm-ddd hh:mm:ss SAST+0200"
          required:
            - token_status
            - user_id
            - token_scope
            - token_expiration_time
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
              example: Missing API Key header (API-Key) or Invalid API Key
      404:
        description: Token not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: Token details not found
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
              example: Error retrieving token details
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key
    user_info = DatabaseService.validate_api_key(api_key)
    if not user_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = user_info['id']
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    try:
        # Get token details from database
        token_details = DatabaseService.get_token_details_by_value(token)
        
        if not token_details:
            return create_api_response({
                "error": "Not Found",
                "message": "Token details not found"
            }, 404)
            
        g.token_id = token_details["id"]
        
        # Determine if token is expired
        now = datetime.now(pytz.UTC)
        expiration_time = token_details["token_expiration_time"]
        
        # Ensure expiration_time is timezone-aware
        if expiration_time.tzinfo is None:
            johannesburg_tz = pytz.timezone('Africa/Johannesburg')
            expiration_time = johannesburg_tz.localize(expiration_time)
            
        if now > expiration_time:
            token_status = "expired"
        else:
            # Validate token with Microsoft Graph
            is_valid = TokenService.validate_token(token)
            token_status = "valid" if is_valid else "invalid"
        
        response_data = {
            "token_status": token_status,
            "user_id": token_details["user_id"],
            "token_scope": token_details["token_scope"],
            "token_expiration_time": token_details["token_expiration_time"].strftime('%Y-%m-%d %H:%M:%S %Z%z')
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving token details: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving token details: {str(e)}"
        }, 500)

def register_token_details_routes(app):
    """Register routes with the Flask app"""
    app.route('/get-token-details', methods=['GET'])(api_logger(get_token_details_route))


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
apis\token_services\get_token.py

from flask import jsonify, request,  g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
from apis.utils.logMiddleware import api_logger

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

# INITIALIZE THE TOKEN SERVICE
token_service = TokenService()

def create_api_response(data, status_code=200):
  """Helper function to create consistent API responses"""
  response = make_response(jsonify(data))
  response.status_code = status_code
  return response
  

def get_token_route():
    """
    Generate a token for API access using a valid api authentication key.
    ---
    tags:
      - Token Service
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
    responses:
      200:
        description: Token generated successfully
        schema:
          type: object
          properties:
            access_token:
              type: string
              description: generated access token to use with api calls
            expires_in:
              type: integer
              format: seconds
              description: Time in seconds until token expiration
            expires_on:
              type: string
              format: date-time
              description: Token expiration timestamp
            token_type:
              type: string
              description: Type of token generated
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
              example: Missing API Key header (API-Key) or Invalid API Key
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
              example: Error generating token
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key
    user_info = DatabaseService.validate_api_key(api_key)
    if not user_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
    g.user_id = user_info['id']
    
    
    try:
        #GET TOKEN WITH USER INFO FOR LOGGING
        response_data, status_code = token_service.get_token(user_info)
        
        # RETURN TEH RESPONSE USING THE HELPER FUNCTION
        return create_api_response(response_data, status_code)
      
    except Exception as e:
        logger.error(f"Error generating token: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": "Error generating token"
        }, 500)
  
    # Get token with user info for logging
    #response, status_code = token_service.get_token(user_info)
    #return jsonify(response), status_code

def register_routes(app):
    """Register routes with the Flask app"""
    app.route('/get-token', methods=['GET'])(api_logger(get_token_route))

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
\apis\token_services\refresh_token.py

from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import pytz
import uuid
from datetime import datetime, timedelta

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def refresh_token_route():
    """
    Refresh an existing token to extend its expiration time
    ---
    tags:
      - Token Service
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
      - name: token
        in: query
        type: string
        required: true
        description: The token to refresh
    produces:
      - application/json
    responses:
      200:
        description: Token refreshed successfully
        schema:
          type: object
          properties:
            access_token:
              type: string
              description: The new refreshed token
            token_type:
              type: string
              description: Type of token generated
            expires_in:
              type: integer
              format: seconds
              description: Time in seconds until token expiration
            expires_on:
              type: string
              format: date-time
              description: Token expiration timestamp
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
              example: Missing token parameter or Invalid token format
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
              example: Missing API Key header (API-Key) or Invalid API Key
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
              example: Error refreshing token
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key
    user_info = DatabaseService.validate_api_key(api_key)
    if not user_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = user_info["id"]
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Get token details from database
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Bad Request",
            "message": "Invalid token"
        }, 400)
        
    g.token_id = token_details["id"]
    
    # Check if token is expired
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    
    # Ensure expiration_time is timezone-aware
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Bad Request",
            "message": "Token has expired and cannot be refreshed"
        }, 400)
    
    # Initialize TokenService
    token_service = TokenService()
    
    try:
        # Get a new token directly from the token service
        # This bypasses the log_token_transaction call in the get_token method
        import requests
        import os
        from apis.utils.config import Config
        
        # Define the token endpoint
        token_endpoint = f"https://login.microsoftonline.com/{Config.TENANT_ID}/oauth2/token/"
        
        # Prepare the request body
        data = {
            "client_id": Config.CLIENT_ID,
            "client_secret": Config.CLIENT_SECRET,
            "resource": 'https://graph.microsoft.com',
            "grant_type": "client_credentials"
        }
        
        # Make the POST request
        response = requests.post(token_endpoint, data=data)
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        
        if "access_token" not in result:
            logger.error(f"Token acquisition failed: {result.get('error_description', 'Unknown error')}")
            return create_api_response({
                "error": "Failed to acquire token",
                "details": result.get("error_description", "Unknown error")
            }, 500)
        
        # Extract token information
        new_token = result.get("access_token")
        expires_in = result.get("expires_in")
        
        # Calculate expiration time
        expires_on_timestamp = int(result.get("expires_on"))
        utc_time = datetime.fromtimestamp(expires_on_timestamp, pytz.UTC)
        gmt_plus_2 = pytz.timezone('Africa/Johannesburg')
        expires_on = utc_time.astimezone(gmt_plus_2)
        
        # Format for response
        formatted_expiry = expires_on.strftime('%Y-%m-%d %H:%M:%S %z')
        
        # Create the refreshed token record with regenerated_from field
        transaction_id = DatabaseService.log_refreshed_token(
            user_id=user_info["id"],
            token_scope=token_details["token_scope"],
            expires_in=expires_in,
            expires_on=expires_on,
            token_value=new_token,
            regenerated_from=token_details["id"],  # ID of the original token
            regenerated_by=user_info["id"]
        )
        
        if not transaction_id:
            logger.warning("Failed to log refreshed token in database")
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to store refreshed token"
            }, 500)
        
        # Prepare response data
        response_data = {
            "access_token": new_token,
            "token_type": result.get("token_type", "Bearer"),
            "expires_in": expires_in,
            "expires_on": formatted_expiry
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error refreshing token: {str(e)}"
        }, 500)

def register_refresh_token_routes(app):
    """Register refresh token routes with the Flask app"""
    app.route('/refresh-token', methods=['POST'])(api_logger(refresh_token_route))


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
\apis\admin\admin_update_user.py
from flask import jsonify, request,g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def admin_update_user_route():
    """
    Update existing user details (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - token
            - id
          properties:
            token:
              type: string
              description: A valid token for verification
            id:
              type: string
              description: UUID of the user to update
            user_name:
              type: string
              description: Updated username (optional)
            user_email:
              type: string
              description: Updated email address (optional)
            common_name:
              type: string
              description: Updated common name (optional)
            scope:
              type: integer
              description: Updated permission scope (optional, 1-5)
            active:
              type: boolean
              description: Updated active status (optional)
            comment:
              type: string
              description: Updated comment (optional)
    produces:
      - application/json
    responses:
      200:
        description: User updated successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: User updated successfully
            user_id:
              type: string
              description: ID of the updated user
            updated_fields:
              type: array
              items:
                type: string
              description: List of fields that were updated
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
              example: Missing required fields or invalid data
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
              example: Missing API Key header or Invalid API Key
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: Admin privileges required
      404:
        description: Not Found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: User not found
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
              example: Error updating user
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
    
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to update users"
        }, 403)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['token', 'id']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Validate token from request body
    token = data.get('token')
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
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
    
    # Get user ID to update
    user_id = data.get('id')
    
    # Get current user details
    current_user = DatabaseService.get_user_by_id(user_id)
    if not current_user:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Prepare update data (only include fields that are provided)
    update_data = {}
    valid_fields = ['user_name', 'user_email', 'common_name', 'scope', 'active', 'comment']
    
    for field in valid_fields:
        if field in data and data[field] is not None:
            # For email, validate format
            if field == 'user_email' and '@' not in data[field]:
                return create_api_response({
                    "error": "Bad Request",
                    "message": "Invalid email format"
                }, 400)
                
            # For scope, validate range
            if field == 'scope' and not (0 <= data[field] <= 5):
                return create_api_response({
                    "error": "Bad Request",
                    "message": "Scope must be between 0 and 5"
                }, 400)
                
            update_data[field] = data[field]
    
    # If no fields to update, return early
    if not update_data:
        return create_api_response({
            "message": "No fields to update",
            "user_id": user_id,
            "updated_fields": []
        }, 200)
    
    try:
        # Update user in database
        success, updated_fields = DatabaseService.update_user(user_id, update_data)
        
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to update user"
            }, 500)
        
        return create_api_response({
            "message": "User updated successfully",
            "user_id": user_id,
            "updated_fields": updated_fields
        }, 200)
        
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error updating user: {str(e)}"
        }, 500)

def register_admin_update_user_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/update-user', methods=['POST'])(api_logger(admin_update_user_route))


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
\apis\admin\admin_delete_user.py

from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response
  
def admin_delete_user_route():
    """
    Delete a user from the system (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: X-API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - token
            - id
          properties:
            token:
              type: string
              description: A valid token for verification
            id:
              type: string
              description: UUID of the user to delete
    produces:
      - application/json
    responses:
      200:
        description: User deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: User deleted successfully
            user_id:
              type: string
              description: ID of the deleted user
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
              example: Missing API Key header or Invalid API Key
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: Admin privileges required
      404:
        description: Not Found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: User not found
      409:
        description: Conflict
        schema:
          type: object
          properties:
            error:
              type: string
              example: Conflict
            message:
              type: string
              example: Cannot delete user with active tokens
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
              example: Error deleting user
    """
    # Get API key from request header
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (X-API-Key)"
        }, 401)
    
    # Validate API key
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to delete users"
        }, 403)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['token', 'id']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Validate token from request body
    token = data.get('token')
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
    
    g.token_id = token_details["id"]
    
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
    
    # Get user ID to delete
    user_id = data.get('id')
    
    # Check if user exists
    user_exists = DatabaseService.get_user_by_id(user_id)
    if not user_exists:
        return create_api_response({
            "error": "Not Found",
            "message": f"User with ID {user_id} not found"
        }, 404)
    
    # Prevent admins from deleting themselves
    if user_id == admin_info["id"]:
        return create_api_response({
            "error": "Forbidden",
            "message": "Administrators cannot delete their own accounts"
        }, 403)
    
    try:
        # Delete user from database
        success = DatabaseService.delete_user(user_id)
        
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to delete user"
            }, 500)
        
        return create_api_response({
            "message": "User deleted successfully",
            "user_id": user_id
        }, 200)
        
    except Exception as e:
        error_msg = str(e)
        
        # Handle specific error for users with active tokens
        if "foreign key constraint" in error_msg.lower():
            return create_api_response({
                "error": "Conflict",
                "message": "Cannot delete user with active tokens. Revoke all tokens first."
            }, 409
            )
            
        logger.error(f"Error deleting user: {error_msg}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error deleting user: {error_msg}"
        }, 500)

def register_admin_delete_user_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/delete-user', methods=['POST'])(api_logger(admin_delete_user_route))

##################################################################################################################################################################

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
\apis\utils\balanceMiddleware.py
from functools import wraps
from flask import request, g, jsonify, make_response
from apis.utils.balanceService import BalanceService
from apis.utils.databaseService import DatabaseService
import logging

logger = logging.getLogger(__name__)

def check_balance(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Skip balance check for admin endpoints
            if request.path.startswith('/admin'):
                return f(*args, **kwargs)

            # Get endpoint ID
            endpoint_id = DatabaseService.get_endpoint_id_by_path(request.path)
            if not endpoint_id:
                logger.error(f"Endpoint not configured for balance tracking: {request.path}")
                return make_response(jsonify({
                    "error": "Configuration Error",
                    "message": "Endpoint not configured for balance tracking"
                }), 500)

            # Check if user_id is already in g (set by previous middleware)
            user_id = getattr(g, 'user_id', None)
            
            # If user_id is not in g, try to get it from token or API key
            if not user_id:
                # Try from X-Token header (custom_llm uses this)
                token = request.headers.get('X-Token')
                if token:
                    token_details = DatabaseService.get_token_details_by_value(token)
                    if token_details:
                        user_id = token_details.get("user_id")
                        g.user_id = user_id  # Set it for subsequent middleware
                
                # If still no user_id, try from API-Key
                if not user_id:
                    api_key = request.headers.get('API-Key')
                    if api_key:
                        user_info = DatabaseService.validate_api_key(api_key)
                        if user_info:
                            user_id = user_info["id"]
                            g.user_id = user_id  # Set it for subsequent middleware
            
            if not user_id:
                logger.error("User ID not found in request context or authentication headers")
                return make_response(jsonify({
                    "error": "Authentication Error",
                    "message": "User ID not found in request context"
                }), 401)

            # Get the endpoint-specific cost
            endpoint_cost = DatabaseService.get_endpoint_cost_by_id(endpoint_id)
            logger.info(f"Endpoint {endpoint_id} cost: {endpoint_cost}")

            # Check and deduct balance using the endpoint-specific cost
            success, result = BalanceService.check_and_deduct_balance(user_id, endpoint_id, endpoint_cost)
            if not success:
                if result == "Insufficient balance":
                    logger.warning(f"Insufficient balance for user {user_id}")
                    return make_response(jsonify({
                        "error": "Insufficient Balance",
                        "message": "Your API call balance is depleted. Please upgrade your plan for additional calls."
                    }), 402)  # 402 Payment Required
                
                logger.error(f"Balance error for user {user_id}: {result}")
                return make_response(jsonify({
                    "error": "Balance Error",
                    "message": f"Error processing balance: {result}"
                }), 500)

            # Log successful balance deduction
            logger.info(f"Balance successfully deducted for user {user_id}, endpoint {endpoint_id}, cost {endpoint_cost}")
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error in balance middleware: {str(e)}")
            return make_response(jsonify({
                "error": "Balance System Error",
                "message": f"An error occurred: {str(e)}"
            }), 500)

    return decorated_function

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
\apis\utils\balanceService.py

from datetime import datetime, date
import logging
import pytz
from apis.utils.databaseService import DatabaseService

logger = logging.getLogger(__name__)

class BalanceService:
    @staticmethod
    def get_first_day_of_month():
        """Get first day of current month in SAST timezone"""
        sast = pytz.timezone('Africa/Johannesburg')
        current_date = datetime.now(sast)
        return date(current_date.year, current_date.month, 1)

    @staticmethod
    def initialize_monthly_balance(user_id):
        """Initialize or reset monthly balance for a user"""
        conn = None
        cursor = None
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()

            # Check if user exists first
            cursor.execute("SELECT id, scope FROM users WHERE id = ?", [user_id])
            user = cursor.fetchone()
            if not user:
                logger.error(f"User {user_id} not found")
                return False

            user_scope = user[1]

            # Get scope's monthly balance
            cursor.execute("SELECT monthly_balance FROM scope_balance_config WHERE scope = ?", [user_scope])
            scope_config = cursor.fetchone()
            
            if not scope_config:
                logger.error(f"No balance config found for scope {user_scope}")
                # Create a default entry with 100 balance
                monthly_balance = 100
                cursor.execute(
                    "INSERT INTO scope_balance_config (scope, monthly_balance, description) VALUES (?, ?, ?)", 
                    [user_scope, monthly_balance, f"Default for scope {user_scope}"]
                )
                conn.commit()
            else:
                monthly_balance = scope_config[0]

            # Get or create balance record for current month
            current_month = BalanceService.get_first_day_of_month()
            
            # Check if balance already exists for this month
            cursor.execute(
                "SELECT id, current_balance FROM user_balances WHERE user_id = ? AND balance_month = ?",
                [user_id, current_month]
            )
            existing_balance = cursor.fetchone()
            
            if existing_balance:
                # Record exists, no need to update if already initialized
                logger.info(f"Balance already exists for user {user_id} for {current_month}")
                return True
            else:
                # Create new balance record
                cursor.execute(
                    """
                    INSERT INTO user_balances (user_id, balance_month, current_balance, last_updated)
                    VALUES (?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()))
                    """,
                    [user_id, current_month, monthly_balance]
                )
                conn.commit()
                logger.info(f"Created new balance of {monthly_balance} for user {user_id} for {current_month}")
                return True

        except Exception as e:
            logger.error(f"Error initializing monthly balance: {str(e)}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def check_and_deduct_balance(user_id, endpoint_id, deduction_amount=None):
        """Check if user has sufficient balance and deduct if they do"""
        conn = None
        cursor = None
        try:
            logger.info(f"Checking balance for user {user_id}, endpoint {endpoint_id}")
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()

            # If deduction_amount is not provided, get it from endpoint's cost
            if deduction_amount is None:
                cursor.execute("SELECT cost FROM endpoints WHERE id = ?", [endpoint_id])
                result = cursor.fetchone()
                if not result:
                    logger.error(f"Endpoint {endpoint_id} not found")
                    return False, "Endpoint not found"
                deduction_amount = result[0]
                logger.info(f"Using endpoint cost of {deduction_amount} for endpoint {endpoint_id}")

            current_month = BalanceService.get_first_day_of_month()

            # First, ensure the user has a balance for current month
            initialized = BalanceService.initialize_monthly_balance(user_id)
            if not initialized:
                logger.error(f"Failed to initialize balance for user {user_id}")
                return False, "Failed to initialize balance"

            # Get current balance
            cursor.execute("""
                SELECT current_balance
                FROM user_balances
                WHERE user_id = ? AND balance_month = ?
            """, [user_id, current_month])

            result = cursor.fetchone()
            if not result:
                logger.error(f"No balance record found for user {user_id} for {current_month}")
                return False, "No balance record found"

            current_balance = result[0]
            logger.info(f"Current balance for user {user_id}: {current_balance}")

            if current_balance < deduction_amount:
                logger.warning(f"Insufficient balance for user {user_id}: {current_balance} < {deduction_amount}")
                return False, "Insufficient balance"

            # Deduct balance and log transaction
            new_balance = current_balance - deduction_amount
            
            cursor.execute("""
                UPDATE user_balances
                SET current_balance = ?,
                    last_updated = DATEADD(HOUR, 2, GETUTCDATE())
                WHERE user_id = ? AND balance_month = ?
            """, [new_balance, user_id, current_month])

            # Log the transaction
            cursor.execute("""
                INSERT INTO balance_transactions 
                (id, user_id, endpoint_id, deducted_amount, balance_after)
                VALUES (NEWID(), ?, ?, ?, ?)
            """, [user_id, endpoint_id, deduction_amount, new_balance])

            conn.commit()
            logger.info(f"Successfully deducted {deduction_amount} from user {user_id}, new balance: {new_balance}")
            return True, new_balance

        except Exception as e:
            logger.error(f"Error checking/deducting balance: {str(e)}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_current_balance(user_id):
        """Get current balance for a user"""
        conn = None
        cursor = None
        try:
            # Ensure user has current month's balance initialized
            initialized = BalanceService.initialize_monthly_balance(user_id)
            if not initialized:
                return None, "Failed to initialize balance"

            conn = DatabaseService.get_connection()
            cursor = conn.cursor()

            current_month = BalanceService.get_first_day_of_month()

            cursor.execute("""
                SELECT ub.current_balance, u.scope, sbc.description
                FROM user_balances ub
                JOIN users u ON ub.user_id = u.id
                LEFT JOIN scope_balance_config sbc ON u.scope = sbc.scope
                WHERE ub.user_id = ? AND ub.balance_month = ?
            """, [user_id, current_month])

            result = cursor.fetchone()
            if not result:
                return None, "Balance not found"

            scope_description = result[2] if result[2] else f"Scope {result[1]}"

            return {
                "current_balance": result[0],
                "scope": result[1],
                "tier_description": scope_description,
                "month": current_month.strftime("%B %Y")
            }, None

        except Exception as e:
            logger.error(f"Error getting current balance: {str(e)}")
            return None, str(e)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def update_user_balance(user_id, new_balance):
        """Update user's current balance (admin only)"""
        conn = None
        cursor = None
        try:
            # Validate user exists
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM users WHERE id = ?", [user_id])
            if not cursor.fetchone():
                return False, f"User {user_id} not found"
            
            current_month = BalanceService.get_first_day_of_month()

            # Check if balance record exists
            cursor.execute("""
                SELECT id FROM user_balances
                WHERE user_id = ? AND balance_month = ?
            """, [user_id, current_month])
            
            if cursor.fetchone():
                # Update existing record
                cursor.execute("""
                    UPDATE user_balances
                    SET current_balance = ?,
                        last_updated = DATEADD(HOUR, 2, GETUTCDATE())
                    WHERE user_id = ? AND balance_month = ?
                """, [new_balance, user_id, current_month])
            else:
                # Create new record
                cursor.execute("""
                    INSERT INTO user_balances (user_id, balance_month, current_balance)
                    VALUES (?, ?, ?)
                """, [user_id, current_month, new_balance])

            conn.commit()
            logger.info(f"Successfully updated balance for user {user_id} to {new_balance}")
            return True, None

        except Exception as e:
            logger.error(f"Error updating balance: {str(e)}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\E100545\Gi\apis\utils\config.py

import os 
from openai import AzureOpenAI

# MICROSOFT ENTRA CONFIGURATION 
class Config:
    CLIENT_ID = os.environ.get("ENTRA_APP_CLIENT_ID")
    CLIENT_SECRET = os.environ.get("ENTRA_APP_CLIENT_SECRET")
    TENANT_ID = os.environ.get("ENTRA_APP_TENANT_ID")
    

    # SET THE MS GRAPH API SCOPES
    GRAPH_SCOPES = [
        "https://graph.microsoft.com/.default" # REQUESTS ALL CONFIGURED PERMISSIONS ON THE APP REGISTRATION
    ]
    
    @staticmethod
    def validate():
        missing = []
        for attr in ['CLIENT_ID', 'CLIENT_SECRET', 'TENANT_ID']:
            if not getattr(Config, attr):
                missing.append(attr)
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_ENDPOINT = os.environ.get("OPENAI_API_ENDPOINT")

DEEPSEEK_API_KEY=os.environ.get("DEEPSEEK_API_KEY")
LLAMA_API_KEY=os.environ.get("LLAMA_API_KEY")

def get_openai_client():
    client = AzureOpenAI(
    azure_endpoint=OPENAI_API_ENDPOINT,
    api_key=OPENAI_API_KEY,
    api_version="2024-02-01",
)
    return client

# apis/utils/config.py

import os
import logging
from azure.storage.blob import BlobServiceClient, ContentSettings
from openai import AzureOpenAI
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

# Configure logging
logger = logging.getLogger(__name__)

# def get_openai_client():
#     """Get Azure OpenAI client with appropriate configuration"""
#     api_key = os.environ.get("AZURE_OPENAI_API_KEY")
#     azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
#     api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2023-07-01-preview")
    
#     if not api_key or not azure_endpoint:
#         logger.error("Azure OpenAI API key or endpoint not configured")
#         raise ValueError("Azure OpenAI API key and endpoint must be set in environment variables")
    
#     return AzureOpenAI(
#         api_key=api_key,  
#         api_version=api_version,
#         azure_endpoint=azure_endpoint
#     )

def get_azure_blob_client():
    """Get Azure Blob Storage client"""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        logger.error("Azure Storage connection string not found in environment variables")
        raise ValueError("Azure Storage connection string not found in environment variables")
    
    return BlobServiceClient.from_connection_string(connection_string)

# Azure Blob Storage configuration
BLOB_CONTAINER_NAME = os.environ.get("AZURE_STORAGE_CONTAINER", "dalle-images")
STORAGE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT")
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{BLOB_CONTAINER_NAME}"

def ensure_container_exists(container_name=BLOB_CONTAINER_NAME):
    """
    Ensures that the specified blob container exists.
    Creates it with public access if it doesn't exist.
    """
    try:
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(container_name)
        
        # Check if container exists
        try:
            container_client.get_container_properties()
            logger.info(f"Container {container_name} already exists")
        except ResourceNotFoundError:
            # Create container with public access
            container_client.create_container(public_access="blob")
            logger.info(f"Container {container_name} created successfully with public access")
        
        return True
    except Exception as e:
        logger.error(f"Error ensuring container exists: {str(e)}")
        raise

def save_image_to_blob(image_data, image_name, container_name=BLOB_CONTAINER_NAME):
    """
    Save image data to Azure Blob Storage and return the URL
    
    Args:
        image_data (bytes): The binary image data
        image_name (str): The name to give the image file in blob storage
        container_name (str): The container name to use
        
    Returns:
        str: The public URL to access the image
    """
    try:
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        
        # Get container client
        container_client = blob_service_client.get_container_client(container_name)
        
        # Ensure container exists (will create if it doesn't)
        ensure_container_exists(container_name)
        
        # Set content settings for the blob (image)
        content_settings = ContentSettings(content_type='image/png')
        
        # Upload image to blob
        blob_client = container_client.get_blob_client(image_name)
        blob_client.upload_blob(image_data, overwrite=True, content_settings=content_settings)
        
        # Generate the public URL for the blob
        blob_url = f"{BASE_BLOB_URL}/{image_name}"
        logger.info(f"Image saved successfully to {blob_url}")
        
        return blob_url
    
    except Exception as e:
        logger.error(f"Error saving image to blob storage: {str(e)}")
        raise Exception(f"Failed to save generated image: {str(e)}")

def delete_image_from_blob(image_name, container_name=BLOB_CONTAINER_NAME):
    """
    Delete an image from Azure Blob Storage
    
    Args:
        image_name (str): The name of the image file in blob storage
        container_name (str): The container name
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        
        # Get container client
        container_client = blob_service_client.get_container_client(container_name)
        
        # Delete the blob
        blob_client = container_client.get_blob_client(image_name)
        blob_client.delete_blob()
        
        logger.info(f"Image {image_name} deleted successfully")
        return True
    
    except ResourceNotFoundError:
        logger.warning(f"Image {image_name} not found in container {container_name}")
        return False
    except Exception as e:
        logger.error(f"Error deleting image from blob storage: {str(e)}")
        return False

def list_blob_images(container_name=BLOB_CONTAINER_NAME, max_results=100):
    """
    List all images in the blob container
    
    Args:
        container_name (str): The container name
        max_results (int): Maximum number of results to return
        
    Returns:
        list: List of image names and URLs
    """
    try:
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        
        # Get container client
        container_client = blob_service_client.get_container_client(container_name)
        
        # List blobs
        blobs = container_client.list_blobs(max_results=max_results)
        
        # Create a list of image details
        image_list = []
        for blob in blobs:
            image_list.append({
                'name': blob.name,
                'url': f"{BASE_BLOB_URL}/{blob.name}",
                'created_on': blob.creation_time,
                'size': blob.size
            })
        
        return image_list
    
    except Exception as e:
        logger.error(f"Error listing images in blob storage: {str(e)}")
        raise

def get_document_intelligence_config():
    """Get the Document Intelligence configuration"""
    return {
        'endpoint': os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"),
        'api_key': os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    }

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
\apis\utils\databaseService.py

import os
import pyodbc
import logging
import uuid
import json 

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DATABASE SERVICE
class DatabaseService:

    DB_CONFIG={
    "DRIVER" : os.environ['DB_DRIVER'],
    "SERVER" : os.environ['DB_SERVER'],
    "DATABASE" : os.environ['DB_NAME'],
    "UID" : os.environ['DB_USER'],
    "PASSWORD" : os.environ['DB_PASSWORD']}
    
    CONNECTION_STRING = (
        f"DRIVER={DB_CONFIG['DRIVER']};"
        f"SERVER={DB_CONFIG['SERVER']};"
        f"DATABASE={DB_CONFIG['DATABASE']};"
        f"UID={DB_CONFIG['UID']};"
        f"PWD={DB_CONFIG['PASSWORD']};"
    )
    
    
    @staticmethod
    def get_connection():
        try:
            conn = pyodbc.connect(DatabaseService.CONNECTION_STRING)
            return conn
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise

    @staticmethod
    def validate_api_key(api_key):
        """Validate API key and return user details if valid"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT id, user_name, user_email, common_name, api_key, scope, active
            FROM users
            WHERE api_key = ?
            """
            
            cursor.execute(query, [api_key])
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user:
                return {
                    "id": str(user[0]),
                    "user_name": user[1],
                    "user_email": user[2],
                    "common_name": user[3],
                    "api_key": str(user[4]),
                    "scope": user[5],
                    "active": user[6]
                }
            return None
            
        except Exception as e:
            logger.error(f"API key validation error: {str(e)}")
            return None

    @staticmethod
    def get_token_details_by_value(token_value):
        """Get token details by token value"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT 
                tt.id,
                tt.token_value,
                tt.user_id,
                tt.token_scope,
                tt.expires_on as token_expiration_time
            FROM 
                token_transactions tt
            WHERE 
                tt.token_value = ?
            """
            
            cursor.execute(query, [token_value])
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not result:
                return None
                
            return {
                "id": result[0],
                "token_value": result[1],
                "user_id": result[2],
                "token_scope": result[3],
                "token_expiration_time": result[4]
            }
            
        except Exception as e:
            logger.error(f"Token details retrieval error: {str(e)}")
            return None
    
    @staticmethod
    def log_token_transaction(user_id, token_scope, expires_in, expires_on, token_value):
        """Log token generation transaction to database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            INSERT INTO token_transactions (id, user_id, token_scope, expires_in, expires_on, token_provider, token_value, created_at)
            VALUES (?, ?, ?, ?, ?, 'Microsoft Entra App', ?, DATEADD(HOUR, 2, GETUTCDATE()))
            """
            
            transaction_id = str(uuid.uuid4())
            
            cursor.execute(query, [
                transaction_id,
                user_id,
                token_scope,
                expires_in,
                expires_on,
                token_value
            ])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return transaction_id
            
        except Exception as e:
            logger.error(f"Token logging error: {str(e)}")
            return None
    
    
    @staticmethod
    def update_token(existing_token, new_token_value, expires_in, expires_on, token_scope, regenerated_by, regenerated_from=None):
        """Update existing token with new values and regeneration info"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            UPDATE token_transactions
            SET token_value = ?,
                expires_in = ?,
                expires_on = ?,
                token_scope = ?,
                modified_at = DATEADD(HOUR, 2, GETUTCDATE()),
                regenerated_at = DATEADD(HOUR, 2, GETUTCDATE()),
                regenerated_by = ?,
                regenerated_from = ?
            WHERE token_value = ?
            """
            
            cursor.execute(query, [
                new_token_value,
                expires_in,
                expires_on,
                token_scope,
                regenerated_by,
                regenerated_from,
                existing_token
            ])
            
            # Check if any rows were affected
            rows_affected = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Token update error: {str(e)}")
            return False

    @staticmethod
    def log_refreshed_token(user_id, token_scope, expires_in, expires_on, token_value, regenerated_from, regenerated_by):
        """Log refreshed token transaction to database with reference to original token"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            INSERT INTO token_transactions (
                id, 
                user_id, 
                token_scope, 
                expires_in, 
                expires_on, 
                token_provider, 
                token_value, 
                created_at,
                regenerated_at,
                regenerated_by,
                regenerated_from
            )
            VALUES (
                ?, ?, ?, ?, ?, 'Microsoft Entra App', ?, 
                DATEADD(HOUR, 2, GETUTCDATE()),
                DATEADD(HOUR, 2, GETUTCDATE()),
                ?,
                ?
            )
            """
            
            transaction_id = str(uuid.uuid4())
            
            cursor.execute(query, [
                transaction_id,
                user_id,
                token_scope,
                expires_in,
                expires_on,
                token_value,
                regenerated_by,
                regenerated_from
            ])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return transaction_id
            
        except Exception as e:
            logger.error(f"Refreshed token logging error: {str(e)}")
            return None
        
    @staticmethod
    def create_user(user_data):
        """Create a new user in the database
        
        Args:
            user_data (dict): Dictionary containing user data:
                - user_name: Username for the new user
                - user_email: Email address for the new user
                - common_name: (Optional) Common name for the new user
                - scope: (Optional) Permission scope (1-5), defaults to 1
                - active: (Optional) Whether the user is active, defaults to True
                - comment: (Optional) Comment about the user
                
        Returns:
            tuple: (user_id, api_key) if successful, (None, None) otherwise
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Generate UUID for user ID and API key
            user_id = str(uuid.uuid4())
            api_key = str(uuid.uuid4())
            
            # Set default values for optional fields
            common_name = user_data.get('common_name')
            scope = user_data.get('scope', 1)
            active = user_data.get('active', True)
            comment = user_data.get('comment')
            
            # Prepare the SQL query
            query = """
            INSERT INTO users (
                id, 
                user_name, 
                user_email, 
                common_name, 
                api_key, 
                scope, 
                active, 
                created_at, 
                modified_at, 
                comment
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                DATEADD(HOUR, 2, GETUTCDATE()),
                DATEADD(HOUR, 2, GETUTCDATE()),
                ?
            )
            """
            
            # Execute the query
            cursor.execute(query, [
                user_id,
                user_data['user_name'],
                user_data['user_email'],
                common_name,
                api_key,
                scope,
                1 if active else 0,  # Convert boolean to bit
                comment
            ])
            
            # Commit the transaction
            conn.commit()
            cursor.close()
            conn.close()
            
            return (user_id, api_key)
            
        except pyodbc.IntegrityError as ie:
            # Handle unique constraint violations (e.g., duplicate email)
            if "Violation of UNIQUE constraint" in str(ie):
                logger.error(f"Duplicate email or API key: {str(ie)}")
            else:
                logger.error(f"Database integrity error: {str(ie)}")
            return (None, None)
            
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return (None, None)
        
    @staticmethod
    def get_user_by_id(user_id):
        """Get user details by ID
        
        Args:
            user_id (str): UUID of the user to retrieve
            
        Returns:
            dict: User details if found, None otherwise
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT id, user_name, user_email, common_name, api_key, scope, active, comment
            FROM users
            WHERE id = ?
            """
            
            cursor.execute(query, [user_id])
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user:
                return {
                    "id": str(user[0]),
                    "user_name": user[1],
                    "user_email": user[2],
                    "common_name": user[3],
                    "api_key": str(user[4]),
                    "scope": user[5],
                    "active": bool(user[6]),
                    "comment": user[7]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving user by ID: {str(e)}")
            return None

    @staticmethod
    def update_user(user_id, update_data):
        """Update user details
        
        Args:
            user_id (str): UUID of the user to update
            update_data (dict): Dictionary containing fields to update
                
        Returns:
            tuple: (success, updated_fields)
        """
        try:
            if not update_data:
                return True, []
                
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Build dynamic update query based on provided fields
            set_clauses = []
            params = []
            updated_fields = []
            
            for field, value in update_data.items():
                set_clauses.append(f"{field} = ?")
                
                # Convert boolean to bit for SQL if field is 'active'
                if field == 'active':
                    params.append(1 if value else 0)
                else:
                    params.append(value)
                    
                updated_fields.append(field)
            
            # Always update modified_at timestamp
            set_clauses.append("modified_at = DATEADD(HOUR, 2, GETUTCDATE())")
            
            # Build the final query
            query = f"""
            UPDATE users
            SET {', '.join(set_clauses)}
            WHERE id = ?
            """
            
            # Add user_id to params
            params.append(user_id)
            
            # Execute update
            cursor.execute(query, params)
            
            # Check if any rows were affected
            rows_affected = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return rows_affected > 0, updated_fields
            
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            return False, []
        
    @staticmethod
    def delete_user(user_id):
        """Delete a user from the database
        
        Args:
            user_id (str): UUID of the user to delete
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            Exception: If the user has active tokens or other database constraints
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Check if user has any active tokens first
            token_check_query = """
            SELECT COUNT(*) 
            FROM token_transactions 
            WHERE user_id = ?
            """
            
            cursor.execute(token_check_query, [user_id])
            token_count = cursor.fetchone()[0]
            
            if token_count > 0:
                # We could automatically delete tokens, but it's safer to make the admin
                # explicitly revoke tokens first to prevent accidental data loss
                cursor.close()
                conn.close()
                raise Exception("User has active tokens. Please revoke all tokens before deleting user.")
            
            # Delete the user
            delete_query = """
            DELETE FROM users
            WHERE id = ?
            """
            
            cursor.execute(delete_query, [user_id])
            
            # Check if any rows were affected
            rows_affected = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Error deleting user: {str(e)}")
            raise
        
    @staticmethod
    def get_endpoint_id_by_path(endpoint_path):
        """Get endpoint ID by path"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT id, cost FROM endpoints 
            WHERE endpoint_path = ?
            """
            
            cursor.execute(query, [endpoint_path])
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error getting endpoint ID: {str(e)}")
            return None
    
    @staticmethod
    def get_endpoint_cost_by_id(endpoint_id):
        """Get endpoint cost by ID"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT cost FROM endpoints 
            WHERE id = ?
            """
            
            cursor.execute(query, [endpoint_id])
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return result[0] if result else 1  # Default to 1 if not found
            
        except Exception as e:
            logger.error(f"Error getting endpoint cost: {str(e)}")
            return 1  # Default to 1 in case of error
    
    @staticmethod
    def log_api_call(endpoint_id, user_id=None, token_id=None, request_method=None, 
                    request_headers=None, request_body=None, response_status=None, 
                    response_time_ms=None, user_agent=None, ip_address=None, 
                    error_message=None, response_body=None):
        """Log API call to database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            INSERT INTO api_logs (
                id, endpoint_id, user_id, timestamp, request_method, 
                request_headers, request_body, response_status, response_time_ms,
                user_agent, ip_address, token_id, error_message, response_body
            )
            VALUES (
                ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()), ?, 
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """
            
            log_id = str(uuid.uuid4())
            
            # Convert dictionary to JSON string if necessary
            if request_headers and isinstance(request_headers, dict):
                request_headers = json.dumps(request_headers)
                
            if request_body and isinstance(request_body, dict):
                request_body = json.dumps(request_body)
                
            if response_body and isinstance(response_body, dict):
                response_body = json.dumps(response_body)
            
            cursor.execute(query, [
                log_id, endpoint_id, user_id, request_method,
                request_headers, request_body, response_status, response_time_ms,
                user_agent, ip_address, token_id, error_message, response_body
            ])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return log_id
            
        except Exception as e:
            logger.error(f"Error logging API call: {str(e)}")
            return None

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
\apis\utils\logMiddleware.py

import time
import json
from flask import request, g
from functools import wraps
import uuid
from apis.utils.databaseService import DatabaseService
import logging
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def get_token_details():
    """Extract token details from request"""
    # Try X-Token header first
    token = request.headers.get('X-Token')
    if token:
        return DatabaseService.get_token_details_by_value(token)
    
    # Try token in request body
    if request.is_json:
        data = request.get_json()
        if data and 'token' in data:
            token = data.get('token')
            return DatabaseService.get_token_details_by_value(token)
    
    return None

def get_user_id_from_request():
    """Extract user ID from various authentication methods"""
    user_id = None
    
    # Try to get user_id from API key (admin functions)
    api_key = request.headers.get('API-Key')
    if api_key:
        admin_info = DatabaseService.validate_api_key(api_key)
        if admin_info:
            return admin_info["id"]
    
    # Try to get user_id from token details
    token_details = get_token_details()
    if token_details:
        return token_details.get("user_id")
    
    # Fallback to user_id stored in Flask g object
    return getattr(g, 'user_id', None)

def api_logger(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Record start time
        start_time = time.time()
        
        # Get request info
        endpoint = request.path
        method = request.method
        headers = dict(request.headers)
        
        # Remove sensitive info from headers
        sensitive_headers = ['Authorization', 'API-Key', 'X-Token', 'Api-Key', 'api_key']
        for header in sensitive_headers:
            if header in headers:
                headers[header] = '[REDACTED]'
            
        # Get request body if it's JSON
        body = None
        if request.is_json:
            body = request.get_json()
            # Don't log sensitive fields
            if body and isinstance(body, dict):
                body_copy = body.copy()
                for key in ['password', 'token', 'api_key']:
                    if key in body_copy:
                        body_copy[key] = '[REDACTED]'
                body = body_copy
        
        # Get user agent and IP
        user_agent = request.headers.get('User-Agent')
        ip_address = request.remote_addr
        
        # Get token details before executing request
        token_details = get_token_details()
        token_id = token_details["id"] if token_details else None
        
        # Execute the request
        try:
            response = f(*args, **kwargs)
            
            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)
            
            # Get user_id using the helper function
            user_id = get_user_id_from_request()
            
            # Get endpoint ID from database
            endpoint_id = DatabaseService.get_endpoint_id_by_path(endpoint)
            if not endpoint_id:
                logger.warning(f"Endpoint not found in database: {endpoint}")
                return response
            
            # Extract response data
            response_status = response.status_code
            try:
                response_data = response.get_json() if hasattr(response, 'get_json') else None
            except:
                response_data = None
                
            # Log successful request
            DatabaseService.log_api_call(
                endpoint_id=endpoint_id,
                user_id=user_id,
                token_id=token_id,
                request_method=method,
                request_headers=json.dumps(headers),
                request_body=json.dumps(body) if body else None,
                response_status=response_status,
                response_time_ms=response_time,
                user_agent=user_agent,
                ip_address=ip_address,
                response_body=json.dumps(response_data) if response_data else None
            )
            
            return response
            
        except Exception as e:
            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)
            
            # Get endpoint ID from database
            endpoint_id = DatabaseService.get_endpoint_id_by_path(endpoint)
            
            # Get user_id using the helper function
            user_id = get_user_id_from_request()
            
            # Log failed request
            DatabaseService.log_api_call(
                endpoint_id=endpoint_id,
                user_id=user_id,
                token_id=token_id,
                request_method=method,
                request_headers=json.dumps(headers),
                request_body=json.dumps(body) if body else None,
                response_status=500,
                response_time_ms=response_time,
                user_agent=user_agent,
                ip_address=ip_address,
                error_message=str(e)
            )
            
            # Re-raise the exception
            raise
            
    return decorated_function

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
\apis\utils\tokenService.py

from apis.utils.config import Config
from apis.utils.databaseService import DatabaseService
from msal import ConfidentialClientApplication
from datetime import datetime, timedelta
import logging
import requests
import pytz

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TokenService:
    def __init__(self):
        Config.validate()
        self.msal_app = ConfidentialClientApplication(
            client_id=Config.CLIENT_ID,
            client_credential=Config.CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{Config.TENANT_ID}"
        )
        
    def get_token(self, user_info=None) -> dict:
        try:
            import requests
            
            # DEFINE THE TOKEN ENDPOINT
            token_endpoint = f"https://login.microsoftonline.com/{Config.TENANT_ID}/oauth2/token/"
            
            # PREPARE THE REQUEST BODY
            data = {
                "client_id": Config.CLIENT_ID,
                "client_secret": Config.CLIENT_SECRET,
                "resource": 'https://graph.microsoft.com',
                "grant_type": "client_credentials"
            }
            
            # MAKE THE POST REQUEST
            response = requests.post(token_endpoint, data=data)
            
            # CHECK IF THE REQUEST WAS SUCCESSFUL
            response.raise_for_status()
            
            # PARSE THE RESPONSE
            result = response.json()
            
            expires_on = int(result.get("expires_on"))
            utc_time = datetime.fromtimestamp(expires_on, pytz.UTC)
            gmt_plus_2 = pytz.timezone('Africa/Johannesburg')
            expires_gmt_plus_2 = utc_time.astimezone(gmt_plus_2)
            
            # Use a standard format without timezone abbreviation to avoid parsing issues
            formatted_expiry = expires_gmt_plus_2.strftime('%Y-%m-%d %H:%M:%S %z')
            
            if "access_token" not in result:
                logger.error(f"Token acquisition failed: {result.get('error_description', 'Unknown error')}")
                return {
                    "error": "Failed to acquire token",
                    "details": result.get("error_description", "Unknown error")
                }, 500
                
            # Log token transaction if user_info is provided
            if user_info:
                transaction_id = DatabaseService.log_token_transaction(
                    user_id=user_info["id"],
                    token_scope=user_info["scope"],
                    expires_in=result.get("expires_in"),
                    expires_on=expires_gmt_plus_2,
                    token_value=result.get("access_token")
                )
                
                if not transaction_id:
                    logger.warning("Failed to log token transaction")
                
            output = {
                "access_token": result.get("access_token"),
                "token_type": result.get("token_type"),
                "expires_in": result.get("expires_in"),
                "expires_on": formatted_expiry
            }
            return output, 200
            
        except Exception as e:
            logger.error(f"Token acquisition failed: {str(e)}")
            return {
                "error": "Failed to acquire token",
                "details": str(e)
            }, 500
 
    # CREATE THE TOKEN VALIDATION FUNCTION
    def validate_token(token):
        """ Validate token by making a simple call to MS Graph API"""
        
        try: 
            graph_endpoint = "https://graph.microsoft.com/v1.0/$metadata"
            headers = {
                "Authorization": f"Bearer {token}",      
                'Accept': 'application/xml' 
            }
            response = requests.get(graph_endpoint, headers=headers)
            
            # IF THE STATUS CODE IS 200, TOKEN IS VALID
            logger.info(f"Token validation status code: {response.status_code}")
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            return False

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
\apis\balance_endpoints.py

from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.balanceService import BalanceService
from apis.utils.logMiddleware import api_logger
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def check_balance_route():
    """
    Check current API call balance for authenticated user
    ---
    tags:
      - Balance Management
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
    produces:
      - application/json
    responses:
      200:
        description: Current balance retrieved successfully
      401:
        description: Authentication error
      500:
        description: Server error
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)

    # Validate API key
    user_info = DatabaseService.validate_api_key(api_key)
    if not user_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)

    g.user_id = user_info['id']

    try:
        # Get current balance
        balance_info, error = BalanceService.get_current_balance(user_info['id'])
        if error:
            return create_api_response({
                "error": "Balance Error",
                "message": f"Error retrieving balance: {error}"
            }, 500)

        return create_api_response({
            "user_id": user_info['id'],
            "user_email": user_info['user_email'],
            **balance_info
        }, 200)

    except Exception as e:
        logger.error(f"Error checking balance: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error checking balance: {str(e)}"
        }, 500)

def admin_update_balance_route():
    """
    Update user's API call balance (Admin only)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: token
        in: query
        type: string
        required: true
        description: Valid token for verification
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - user_id
            - new_balance
          properties:
            user_id:
              type: string
              description: ID of user to update
            new_balance:
              type: integer
              description: New balance value
    produces:
      - application/json
    responses:
      200:
        description: Balance updated successfully
      401:
        description: Authentication error
      403:
        description: Forbidden - not an admin
      500:
        description: Server error
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)

    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)

    g.user_id = admin_info['id']

    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to update balances"
        }, 403)

    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)

    # Verify token is valid and not expired
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)

    g.token_id = token_details["id"]

    # Check token expiration
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
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

    # Get required parameters
    user_id = data.get('user_id')
    new_balance = data.get('new_balance')

    if not user_id or new_balance is None:
        return create_api_response({
            "error": "Bad Request",
            "message": "user_id and new_balance are required"
        }, 400)

    try:
        # Update the user's balance
        success, error = BalanceService.update_user_balance(user_id, new_balance)
        if not success:
            return create_api_response({
                "error": "Balance Update Error",
                "message": f"Failed to update balance: {error}"
            }, 500)

        # Get updated balance info
        balance_info, error = BalanceService.get_current_balance(user_id)
        if error:
            return create_api_response({
                "error": "Balance Error",
                "message": f"Balance updated but error retrieving new balance: {error}"
            }, 500)

        return create_api_response({
            "message": "Balance updated successfully",
            "user_id": user_id,
            **balance_info
        }, 200)

    except Exception as e:
        logger.error(f"Error updating balance: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error updating balance: {str(e)}"
        }, 500)

def register_balance_routes(app):
    """Register balance-related routes with the Flask app"""
    app.route('/check-balance', methods=['GET'])(api_logger(check_balance_route))
    app.route('/admin/update-balance', methods=['POST'])(api_logger(admin_update_balance_route))


##################################################################################################################################################################
\ai-api-framework\sql_init\api_logs.sql

-- API LOGS TABLE TO LOG EACH API TRANSACTION

USE AIAPISDEV;

CREATE TABLE api_logs (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    endpoint_id UNIQUEIDENTIFIER NOT NULL,
    user_id UNIQUEIDENTIFIER,
    timestamp DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    request_method NVARCHAR(10) NOT NULL,
    request_headers NVARCHAR(MAX),
    request_body NVARCHAR(MAX),
    response_body NVARCHAR(MAX),
    response_status INT,
    response_time_ms INT,
    user_agent NVARCHAR(500),
    ip_address NVARCHAR(50),
    token_id UNIQUEIDENTIFIER,
    error_message NVARCHAR(MAX),
    CONSTRAINT FK_api_logs_endpoints FOREIGN KEY (endpoint_id) REFERENCES endpoints(id),
    CONSTRAINT FK_api_logs_users FOREIGN KEY (user_id) REFERENCES users(id)
);


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
sql_init\balance_transactions.sql

-- Create balance_transactions table for audit trail
CREATE TABLE balance_transactions (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    endpoint_id UNIQUEIDENTIFIER NOT NULL,
    transaction_date DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    deducted_amount INT NOT NULL,
    balance_after INT NOT NULL,
    CONSTRAINT FK_balance_transactions_users FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT FK_balance_transactions_endpoints FOREIGN KEY (endpoint_id) REFERENCES endpoints(id)
);

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
sql_init\change_user_scope.sql

-- This script is used to change scope of a user in the user tables:

UPDATE users
SET scope = 0, -- pass in the desired scope for the user
modified_at = DATEADD(HOUR,2, GETUTCDATE())
WHERE ID = '' -- pass in the user ID here
AND scope = 1; -- pass in the users's existing scope

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
sql_init\endpoints.sql

-- Create endpoints table 
USE AIAPISDEV;

CREATE TABLE endpoints (
    id UNIQUEIDENTIFIER PRIMIARY KEY DEFAULT NEWID(),
    endpoint_name NVARCHAR(100) NOT NULL,
    endpoint_path NVARCHAR(MAX) NOT NULL,
    description NVARCHAR(MAX),
    created_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    modifed_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE())
    active BIT NOT NULL DEFAULT 1,
    cost INT NOT NULL DEFAULT 1
);

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
sql_init\scope_balance_config.sql

-- Create scope_balance_config table
USE AIAPISDEV;

CREATE TABLE scope_balance_config (
    scope INT PRIMARY KEY CHECK (scope IN (0,1,2,3,4,5)),
    monthly_balance INT NOT NULL,
    description NVARCHAR(100),
    created_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    modified_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE())
);

-- Insert default scope balances
INSERT INTO scope_balance_config (scope, monthly_balance, description) VALUES
(0, 999999, 'Admin - Unlimited'),
(1, 999, 'Developer'),
(2, 5000, 'Production Tier 3 - Basic'),
(3, 10000, 'Production Tier 2 - Professional'),
(4, 25000, 'Production Tier 1 - Enterprise'),
(5, 100, 'Test/Trial');


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
sql_init\token_transactions.sql

-- Create token_transactions table
USE AIAPISDEV;

CREATE TABLE token_transactions (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    token_scope INT NOT NULL,
    expires_in INT NOT NULL,
    expires_on DATETIME2 NOT NULL,
    token_provider NVARCHAR(50) NOT NULL DEFAULT 'Microsoft Entra App',
    token_value NVARCHAR(MAX) NOT NULL,
    created_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    modified_at DATETIME2, -- Date and time when the token was last modified (regnerated counts)
    regenerated_at DATETIME2, -- Date and time when the token was regenerated (if applicable)
    regenerated_by UNIQUEIDENTIFIER,  -- User ID of the user who regenerated the token
    regenerated_from UNIQUEIDENTIFIER, -- ID of the original token that requested a refresh
    CONSTRAINT FK_token_transactions_users FOREIGN KEY (user_id) REFERENCES users(id)
);


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
sql_init\user_balances.sql

-- Create user_balances table
CREATE TABLE user_balances (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    balance_month DATE NOT NULL,  -- First day of the month
    current_balance INT NOT NULL,
    last_updated DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    CONSTRAINT FK_user_balances_users FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT UQ_user_month UNIQUE (user_id, balance_month)
);

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
sql_init\users.sql

-- Create users table
USE AIAPISDEV;

CREATE TABLE users (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_name NVARCHAR(100) NOT NULL,
    user_email NVARCHAR(255) NOT NULL UNIQUE,
    common_name NVARCHAR(100),
    api_key UNIQUEIDENTIFIER NOT NULL UNIQUE DEFAULT NEWID(),
    scope INT CHECK (scope IN (0,1,2,3,4,5)) DEFAULT 1,
    active BIT NOT NULL DEFAULT 1,
    created_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    modified_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    comment NVARCHAR(MAX)
);


##################################################################################################################################################################

app.py

from flask import Flask, jsonify, request, render_template
import requests
from msal import ConfidentialClientApplication
import os
from datetime import datetime, timedelta
import logging
from functools import wraps
from flasgger import Swagger

from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService


# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.config['SWAGGER'] = {
    'title': 'Swagger'
}

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "API Documentation",
        "description": "API endpoints with authentication",
        "version": "1.0.0"
    }     
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)


# INITIALIZE THE TOKEN SERVICE
token_service = TokenService()

# Serve the index.html file
# @app.route('/')
# def index():
#     return render_template('index.html')

# TOKEN SERVICE ENDPOINTS
## GET TOKEN
from apis.token_services.get_token import register_routes as get_token_endpoint 
get_token_endpoint(app)
## GET TOKEN DETAILS
from apis.token_services.get_token_details import register_token_details_routes as get_token_details_endpoint
get_token_details_endpoint(app)
## REFRESH TOKEN 
from apis.token_services.refresh_token import register_refresh_token_routes
register_refresh_token_routes(app)

# ADMIN ENDPOINTS
## CREATE USER
from apis.admin.admin_create_user import register_create_user_routes
register_create_user_routes(app)
## UPDATE USER
from apis.admin.admin_update_user import register_admin_update_user_routes
register_admin_update_user_routes(app)
## DELETE USER
from apis.admin.admin_delete_user import register_admin_delete_user_routes
register_admin_delete_user_routes(app)

# ENDPOINT MANAGEMENT
from apis.endpoint_management.admin_endpoint_management import register_admin_endpoint_routes
register_admin_endpoint_routes(app)

from apis.balance_endpoints import register_balance_routes
register_balance_routes(app)


from apis.llm.deepseek_r1 import register_llm_deepseek_r1
register_llm_deepseek_r1(app)

from apis.llm.llama import register_llm_llama
register_llm_llama(app)

from apis.llm.gpt_4o_mini import register_llm_gpt_4o_mini
register_llm_gpt_4o_mini(app)

from apis.llm.gpt_4o import register_llm_gpt_4o
register_llm_gpt_4o(app)

from apis.llm.gpt_o1_mini import register_llm_o1_mini
register_llm_o1_mini(app)

from apis.rag_query import register_rag_query_routes
register_rag_query_routes(app)

from apis.image_generation.dalle3 import register_image_generation_routes
register_image_generation_routes(app)

if __name__ == '__main__':
    app.run()

