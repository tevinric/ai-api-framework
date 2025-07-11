from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.fileService import FileService
from apis.utils.logMiddleware import api_logger
import logging
import os
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

# Define container for file uploads
FILE_UPLOAD_CONTAINER = os.environ.get("AZURE_STORAGE_UPLOAD_CONTAINER", "file-uploads")

from apis.utils.config import create_api_response

def upload_file_route():
    """
    Upload one or more files to Azure Blob Storage
    ---
    tags:
      - File Management
    summary: Upload one or more files to Azure Blob Storage
    description: Uploads one or more files to Azure Blob Storage and stores metadata in the database. Executable files (.exe, .bat, .cmd, .sh, .ps1, .dll, .msi, etc.) are not allowed.
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
      - name: files
        in: formData
        type: file
        required: true
        description: Files to upload (can be multiple). Executable files are not permitted.
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
                    example: document.pdf
                  file_id:
                    type: string
                    example: 12345678-1234-1234-1234-123456789012
                  content_type:
                    type: string
                    example: application/pdf
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
              enum:
                - No files part in the request
                - No files selected for upload
                - File type .exe is not allowed for security reasons
                - File type .bat is not allowed for security reasons
                - File type .cmd is not allowed for security reasons
                - File type .sh is not allowed for security reasons
                - File type .ps1 is not allowed for security reasons
                - File type .dll is not allowed for security reasons
                - File type .msi is not allowed for security reasons
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
              enum:
                - Missing X-Token header
                - Invalid token
                - Token has expired
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
              example: Error uploading files
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
    
    # Define list of forbidden file extensions (executable files)
    forbidden_extensions = [
        '.exe', '.bat', '.cmd', '.sh', '.ps1', '.msi', '.dll', '.com', '.vbs', 
        '.js', '.jse', '.wsf', '.wsh', '.msc', '.scr', '.reg', '.hta', '.pif',
        
        # LIST 1 FROM RUAN
        '.aaa', '.aac', '.accdb','.aacde', '.accdr', '.accdt', '.ace', '.acm', '.adn', '.adp',
        '.aesir','.aif','.aiff','.application','.arc','.arj','.asc','.asf','.asx','.au',
        '.bat','.bck','.bhx','.bkf','.bz2','.cab','.cgi','.cmd','.com','.cpl','.diablo6',
        '.dib','.exx','.flac','.gadget','.grv','.gsa','.gta','.gz','.hpk','.hqx','.idx',
        '.img','.inf','.jpe','.jse','.lha','.locky','.lukitus','.lzh','.lzx','.m3u',
        '.mad','.maf','.mbox','.mbx','.mda','.mdb','.mde','.mdf','.mdm','.mdt','.mdw',
        '.mdz','.mid','.midi','.mp1','.mp2','.mpa','.mpd','.mpt','.msc','.msh',
        '.msh1','.msh1xml','.msh2','.msh2xml','.mshxml','.nmf','.obt','.ocx',
        '.odb','.odin','.oft','.old','.onepkg','.osiris','.pab','.pak','.pcsc1',
        '.pcx','.php3','.pif','.pit','.pl','.ppa','.ppsm','.ps','.ps2',
        '.ps2xml','.psc2','.pwz','.qt','.qtw','.ram','.raw','.rif','.rm',
        '.rmi','.rmvb','.rqy','.rwz','.scf','.scr','.sea','.shtml',
        '.sit','.slk','.snd','.spiff','.sqz','.swf','.sys',
        '.temp','.text','.tgz','.thmx','.thor','.uu','.uue','.vb',
        '.vbe','.vbs','.vob','.vsl','.vst','.vsu','.vsw',
        '.vsx','.vtx','.vxd','.wax','.wcry','.wncry','.wma','.wncry',
        '.wncrpyt','.wnry','.wri','.ws','.wsc','.wsf','.wsh',
        '.wvx','.xlb','.xlc','.xld','.xlk','.xlv','.xsf',
        '.xsn','.z','.zepto','.zoo','.zzz','.zzzzz',
        
        # LIST 2 FROM RUAN
        '.ace','.ani','.app','.docm','.exe','.jar','.reg','.scr','.vbe',
        '.vbs','.bas','.bat','.chm','.cmd','.com','.cpl','.crt',
        '.csh','.dll','.fxp','.gadget','.hlp','.hta','.inf',
        '.ins','.isp','.js','.jse','.lnk','.msi',
        '.msp','.mst','.pcd','.pif','.ps1','.ps1xml',
        '.ps2','.ps2xml','.psc1','.psc2','.rar','.sct',
        '.shb','.shs','.url','.vb','.vxd','.ws','.wsc','.wsf','wsh','shtml','.one','.onenote','rdp'

    ]
    
    # Check each file for forbidden extensions
    for file in files:
        _, file_extension = os.path.splitext(file.filename.lower())
        if file_extension.lower() in forbidden_extensions:
            return create_api_response({
                "error": "Bad Request",
                "message": f"File type {file_extension} is forbidden for security reasons"
            }, 400)
    
    try:
        uploaded_files = []
        
        for file in files:
            # Use FileService to upload the file
            file_info, error = FileService.upload_file(file, g.user_id, FILE_UPLOAD_CONTAINER)
            
            if error:
                return create_api_response({
                    "error": "Server Error",
                    "message": f"Error uploading file {file.filename}: {error}"
                }, 500)
            
            uploaded_files.append(file_info)
        
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
      - File Management
    summary: Get access URL for a previously uploaded file
    description: Returns file details including access URL, content type, and upload date
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
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
              example: document.pdf
            file_url:
              type: string
              example: https://storage.blob.core.windows.net/file-uploads/12345678-1234-1234-1234-123456789012.pdf
            content_type:
              type: string
              example: application/pdf
            upload_date:
              type: string
              format: date-time
              example: 2024-03-16T10:30:45.123456+02:00
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
              example: file_id is required as a query parameter
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
              enum:
                - Missing X-Token header
                - Invalid token
                - Token has expired
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
              example: You don't have permission to access this file
      404:
        description: File not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: File with ID 12345678-1234-1234-1234-123456789012 not found
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
              example: Error retrieving file URL
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
            "message": "file_id is required as a query parameter"
        }, 400)
    
    # Use FileService to get file URL
    file_info, error = FileService.get_file_url(file_id, g.user_id)
    
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
    
    return create_api_response(file_info, 200)

def delete_file_route():
    """
    Delete a previously uploaded file using its ID
    ---
    tags:
      - File Management
    summary: Delete a previously uploaded file
    description: Deletes file from Azure Blob Storage and removes the database entry
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
      - name: file_id
        in: query
        type: string
        required: true
        description: Unique file identifier
    produces:
      - application/json
    responses:
      200:
        description: File deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: File deleted successfully
            file_id:
              type: string
              example: 12345678-1234-1234-1234-123456789012
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
              example: file_id is required as a query parameter
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
              enum:
                - Missing X-Token header
                - Invalid token
                - Token has expired
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
              example: You don't have permission to delete this file
      404:
        description: File not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: File with ID 12345678-1234-1234-1234-123456789012 not found
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
              example: Error deleting file
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
            "message": "file_id is required as a query parameter"
        }, 400)
    
    # Use FileService to delete the file
    success, message = FileService.delete_file(file_id, g.user_id, FILE_UPLOAD_CONTAINER)
    
    if not success:
        if "not found" in message:
            return create_api_response({
                "error": "Not Found",
                "message": message
            }, 404)
        elif "permission" in message:
            return create_api_response({
                "error": "Forbidden",
                "message": message
            }, 403)
        else:
            return create_api_response({
                "error": "Server Error",
                "message": message
            }, 500)
    
    return create_api_response({
        "message": "File deleted successfully",
        "file_id": file_id
    }, 200)

def list_user_files_route():
    """
    List all files uploaded by the authenticated user or all files for admin users
    ---
    tags:
      - File Management
    summary: List all files uploaded by the user
    description: Returns a list of all files uploaded by the authenticated user. Admin users can see all files.
    parameters:
      - name: API-Key
        in: header
        type: string
        required: false
        description: API Key for authentication
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
      - name: X-Token
        in: header
        type: string
        required: false
        description: Valid token for authentication
    produces:
      - application/json
    responses:
      200:
        description: Files retrieved successfully
        schema:
          type: object
          properties:
            files:
              type: array
              items:
                type: object
                properties:
                  file_id:
                    type: string
                    example: "12345678-1234-1234-1234-123456789012"
                  file_name:
                    type: string
                    example: "document.pdf"
                  content_type:
                    type: string
                    example: "application/pdf"
                  upload_date:
                    type: string
                    format: date-time
                    example: "2024-03-16T10:30:45+02:00"
                  file_size:
                    type: integer
                    example: 1024
                  user_id:
                    type: string
                    description: Only returned for admin users
                    example: "12345678-1234-1234-1234-123456789012"
                  user_name:
                    type: string
                    description: Only returned for admin users
                    example: "johndoe"
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
              example: Missing authentication headers
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
              example: Authentication token has expired
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
              example: Error retrieving files
    """
    # Check authentication - try both API-Key and X-Token
    api_key = request.headers.get('API-Key')
    token = request.headers.get('X-Token')
    
    user_id = None
    is_admin = False
    
    # Try to authenticate with API key first
    if api_key:
        user_info = DatabaseService.validate_api_key(api_key)
        if user_info:
            user_id = user_info['id']
            is_admin = user_info['scope'] == 0
            g.user_id = user_id
    
    # If not authenticated with API key, try token
    if not user_id and token:
        token_details = DatabaseService.get_token_details_by_value(token)
        if token_details:
            # Check if token is expired
            now = datetime.now(pytz.UTC)
            expiration_time = token_details["token_expiration_time"]
            
            # Ensure expiration_time is timezone-aware
            if expiration_time.tzinfo is None:
                johannesburg_tz = pytz.timezone('Africa/Johannesburg')
                expiration_time = johannesburg_tz.localize(expiration_time)
                
            if now > expiration_time:
                return create_api_response({
                    "error": "Forbidden",
                    "message": "Authentication token has expired"
                }, 403)
                
            user_id = token_details["user_id"]
            g.user_id = user_id
            g.token_id = token_details["id"]
            
            # Check if user is admin
            user_info = DatabaseService.get_user_by_id(user_id)
            is_admin = user_info and user_info.get('scope') == 0
    
    # If still not authenticated, return error
    if not user_id:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing or invalid authentication"
        }, 401)
    
    try:
        # Use FileService to list files
        files, error = FileService.list_files(user_id, is_admin)
        
        if error:
            return create_api_response({
                "error": "Server Error",
                "message": error
            }, 500)
        
        return create_api_response({
            "files": files
        }, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving files: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving files: {str(e)}"
        }, 500)

def register_file_upload_routes(app):
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    """Register file upload routes with the Flask app"""
    app.route('/file', methods=['POST'])(track_usage(api_logger(check_endpoint_access(upload_file_route))))
    app.route('/file/url', methods=['GET'])(api_logger(check_endpoint_access(get_file_url_route)))
    app.route('/file', methods=['DELETE'])(api_logger(check_endpoint_access(delete_file_route)))
    app.route('/file/list', methods=['GET'])(api_logger(check_endpoint_access(list_user_files_route)))

