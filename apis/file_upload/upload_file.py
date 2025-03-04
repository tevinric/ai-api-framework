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
            cursor.close()
            db_conn.close()
            
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
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
      - name: file_id
        in: query
        type: string
        required: true
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
    
    # Get file_id from query parameter
    file_id = request.args.get('file_id')
    if not file_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "file_id is required"
        }, 400)
    
    try:
        # Query database for file information
        db_conn = DatabaseService.get_connection()
        cursor = db_conn.cursor()
        
        query = """
        SELECT id, user_id, original_filename, blob_url, content_type, upload_date
        FROM file_uploads
        WHERE id = ?
        """
        
        cursor.execute(query, [file_id])
        file_info = cursor.fetchone()
        cursor.close()
        db_conn.close()
        
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
        return create_api_response({
            "file_name": file_info[2],
            "file_url": file_info[3],
            "content_type": file_info[4],
            "upload_date": file_info[5].isoformat() if file_info[5] else None
        }, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving file URL: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving file URL: {str(e)}"
        }, 500)

def delete_file_route():
    """
    Delete a previously uploaded file using its ID
    ---
    tags:
      - File Upload
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
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
    
    # Get request data
    data = request.get_json()
    if not data or 'file_id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "file_id is required in the request body"
        }, 400)
    
    file_id = data['file_id']
    
    try:
        # Query database for file information
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
            cursor.close()
            db_conn.close()
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
            cursor.close()
            db_conn.close()
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
        cursor.close()
        db_conn.close()
        
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

def register_file_upload_routes(app):
    """Register file upload routes with the Flask app"""
    app.route('/upload-file', methods=['POST'])(api_logger(upload_file_route))
    app.route('/get-file-url', methods=['GET'])(api_logger(get_file_url_route))
    app.route('/delete-file', methods=['DELETE'])(api_logger(delete_file_route))