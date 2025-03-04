from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
import pytz
from datetime import datetime
import os
import tempfile
import base64
import json
from werkzeug.utils import secure_filename
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.exceptions import ResourceNotFoundError
from apis.utils.config import get_openai_client, get_document_intelligence_config
from apis.utils.config import get_document_intelligence_config


# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = get_openai_client()

# Initialize Document Intelligence client (from config)
document_config = get_document_intelligence_config()
document_client = DocumentAnalysisClient(
    endpoint=document_config['endpoint'],
    credential=AzureKeyCredential(document_config['api_key'])
)

# Fixed deployment model - using GPT-4o
DEPLOYMENT = 'gpt-4o'

# Allowed file extensions and MIME types
ALLOWED_EXTENSIONS = {
    'pdf': 'application/pdf',
    'txt': 'text/plain',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'csv': 'text/csv',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'xls': 'application/vnd.ms-excel',
    'ppt': 'application/vnd.ms-powerpoint',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg'
}

# Document types supported by Document Intelligence
DOCUMENT_INTELLIGENCE_FORMATS = {'pdf', 'doc', 'docx', 'xlsx', 'xls', 'pptx', 'ppt'}

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def allowed_file(filename):
    """Check if file has an allowed extension"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def is_image_file(filename):
    """Check if the file is an image"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ['png', 'jpg', 'jpeg']

def is_document_intelligence_supported(filename):
    """Check if file is supported by Document Intelligence"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in DOCUMENT_INTELLIGENCE_FORMATS

def process_text_file(file_path):
    """Process a plain text file"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error processing text file: {str(e)}")
        return f"[Error processing text file: {str(e)}]"

def process_with_document_intelligence(file_path, filename):
    """Process a document file using Azure Document Intelligence"""
    try:
        # Determine the best model to use based on file type
        ext = filename.rsplit('.', 1)[1].lower()
        
        # Select appropriate prebuilt model
        if ext in ['xlsx', 'xls', 'csv']:
            model = "prebuilt-layout"  # Good for tables and structured data
        else:
            model = "prebuilt-document"  # General document understanding
        
        # Process the document
        with open(file_path, "rb") as document:
            poller = document_client.begin_analyze_document(model, document)
            result = poller.result()
        
        # Extract content
        extracted_text = ""
        
        # Add document metadata if available
        if hasattr(result, 'metadata') and result.metadata:
            extracted_text += f"Document Metadata:\n"
            extracted_text += f"Pages: {result.metadata.page_count}\n"
            if hasattr(result.metadata, 'author') and result.metadata.author:
                extracted_text += f"Author: {result.metadata.author}\n"
            if hasattr(result.metadata, 'title') and result.metadata.title:
                extracted_text += f"Title: {result.metadata.title}\n"
            extracted_text += "\n"
        
        # Get page-by-page content
        for page_idx, page in enumerate(result.pages):
            extracted_text += f"\n--- Page {page_idx + 1} ---\n"
            
            # Extract text from paragraphs if available
            if hasattr(page, 'paragraphs') and page.paragraphs:
                for para in page.paragraphs:
                    extracted_text += f"{para.content}\n"
            # Otherwise extract from lines
            else:
                for line in page.lines:
                    extracted_text += f"{line.content}\n"
        
        # Extract tables if present
        if hasattr(result, 'tables') and result.tables:
            extracted_text += "\n--- Tables ---\n"
            for i, table in enumerate(result.tables):
                extracted_text += f"\nTable {i+1}:\n"
                
                # Build a text representation of the table
                prev_row_idx = -1
                for cell in table.cells:
                    if cell.row_index > prev_row_idx:
                        extracted_text += "\n"
                        prev_row_idx = cell.row_index
                    
                    extracted_text += f"{cell.content}\t"
                extracted_text += "\n"
        
        # Include key-value pairs if detected
        if hasattr(result, 'key_value_pairs') and result.key_value_pairs:
            extracted_text += "\n--- Key-Value Pairs ---\n"
            for pair in result.key_value_pairs:
                key = pair.key.content if pair.key else "N/A"
                value = pair.value.content if pair.value else "N/A"
                extracted_text += f"{key}: {value}\n"
                
        return extracted_text
    
    except Exception as e:
        logger.error(f"Error processing document with Document Intelligence: {str(e)}")
        return f"[Error processing document with Document Intelligence: {str(e)}]"

def gpt4o_document_intelligence_route():
    """
    GPT-4o API endpoint with Document Intelligence for file processing (2 AIC per call)
    ---
    tags:
      - LLM
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: system_prompt
        in: formData
        type: string
        required: false
        default: "You are a helpful AI assistant"
        description: System prompt to control model behavior
      - name: user_input
        in: formData
        type: string
        required: true
        description: Text for the model to process
      - name: temperature
        in: formData
        type: number
        format: float
        minimum: 0
        maximum: 1
        default: 0.5
        required: false
        description: Controls randomness (0=focused, 1=creative)
      - name: files
        in: formData
        type: file
        required: false
        description: Files to be used as context (multiple files can be uploaded)
    consumes:
      - multipart/form-data
    produces:
      - application/json
    responses:
      200:
        description: Successful model response
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            message:
              type: string
              example: "I'll help you with that question. Based on the information provided..."
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
            input_tokens:
              type: integer
              example: 125
            completion_tokens:
              type: integer
              example: 84
            output_tokens:
              type: integer
              example: 209
            files_processed:
              type: integer
              example: 1
            file_processing_details:
              type: object
              properties:
                documents_processed:
                  type: integer
                  example: 1
                images_processed:
                  type: integer
                  example: 1
                text_files_processed:
                  type: integer
                  example: 1
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
              example: "Missing required fields: user_input"
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
              example: "Internal server error occurred during API request"
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
    
    # Extract form data
    system_prompt = request.form.get('system_prompt', 'You are a helpful AI assistant')
    user_input = request.form.get('user_input', '')
    temperature = float(request.form.get('temperature', 0.5))
    
    # Validate required fields
    if not user_input:
        return create_api_response({
            "response": "400",
            "message": "Missing required field: user_input"
        }, 400)
    
    # Validate temperature range
    if not (0 <= temperature <= 1):
        return create_api_response({
            "response": "400",
            "message": "Temperature must be between 0 and 1"
        }, 400)
    
    # Process uploaded files
    uploaded_files = request.files.getlist('files')
    temp_files = []  # Keep track of temporary files for cleanup
    
    # Track file processing statistics
    file_stats = {
        "documents_processed": 0,
        "images_processed": 0,
        "text_files_processed": 0
    }
    
    try:
        # Log API usage
        logger.info(f"GPT-4o Document Intelligence API called by user: {user_id}")
        
        # Prepare message content
        message_content = []
        
        # First add the user's input text
        message_content.append({
            "type": "text", 
            "text": user_input
        })
        
        # Process uploaded files
        for file in uploaded_files:
            if not file or not file.filename or not allowed_file(file.filename):
                continue
                
            # Create a temporary file to store the uploaded content
            fd, temp_path = tempfile.mkstemp(suffix=f'.{file.filename.rsplit(".", 1)[1].lower()}')
            temp_files.append(temp_path)
            
            # Save the uploaded file to the temporary path
            with os.fdopen(fd, 'wb') as tmp:
                file.save(tmp)
            
            # Check file type and process accordingly
            if is_image_file(file.filename):
                # For images, encode as base64 and add to message
                file_stats["images_processed"] += 1
                
                with open(temp_path, 'rb') as img_file:
                    base64_image = base64.b64encode(img_file.read()).decode('utf-8')
                
                # Get MIME type
                ext = file.filename.rsplit('.', 1)[1].lower()
                mime_type = ALLOWED_EXTENSIONS[ext]
                
                # Add as image content
                message_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_image}"
                    }
                })
                
            elif is_document_intelligence_supported(file.filename):
                # Process document with Azure Document Intelligence
                file_stats["documents_processed"] += 1
                
                # Process document
                extracted_content = process_with_document_intelligence(temp_path, file.filename)
                
                # Add to message content
                message_content.append({
                    "type": "text",
                    "text": f"\n\n--- Content from {file.filename} ---\n{extracted_content}\n--- End of {file.filename} ---\n"
                })
                
            elif file.filename.endswith('.txt'):
                # Process plain text file
                file_stats["text_files_processed"] += 1
                
                # Extract text
                extracted_content = process_text_file(temp_path)
                
                # Add to message content
                message_content.append({
                    "type": "text",
                    "text": f"\n\n--- Content from {file.filename} ---\n{extracted_content}\n--- End of {file.filename} ---\n"
                })
                
            else:
                # For unsupported file types, just mention they were uploaded
                message_content.append({
                    "type": "text",
                    "text": f"\n\nA file named '{file.filename}' was uploaded, but its content type is not supported for extraction."
                })
        
        # If the message is too long, truncate it
        # Estimate token count (rough approximation)
        estimated_tokens = sum(len(content.get("text", "")) // 4 for content in message_content if content["type"] == "text")
        
        # If we're approaching token limit, truncate content
        if estimated_tokens > 100000:  # Leave room for response
            logger.warning(f"Message content too large: ~{estimated_tokens} tokens. Truncating.")
            
            # Keep user input and truncate document content
            truncated_content = [message_content[0]]  # Keep user input
            
            for content in message_content[1:]:
                if content["type"] == "image_url":
                    truncated_content.append(content)  # Keep all images
                elif content["type"] == "text" and "[Error processing" not in content["text"]:
                    # Truncate long text content
                    if len(content["text"]) > 5000:
                        truncated_text = content["text"][:5000] + "... [Content truncated due to length]"
                        truncated_content.append({"type": "text", "text": truncated_text})
                    else:
                        truncated_content.append(content)
            
            # Add a note about truncation
            truncated_content.append({
                "type": "text",
                "text": "\n\n[Note: Some document content was truncated due to length constraints.]"
            })
            
            message_content = truncated_content
        
        # Create the chat completion request
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_content}
        ]
        
        # Make the API call
        response = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=messages,
            temperature=temperature,
            max_tokens=4000  # Add reasonable limit
        )
        
        # Extract response data
        result = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        output_tokens = response.usage.total_tokens
        
        # Total files processed
        total_files_processed = file_stats["documents_processed"] + file_stats["images_processed"] + file_stats["text_files_processed"]
        
        # Prepare successful response with user details
        return create_api_response({
            "response": "200",
            "message": result,
            "user_id": user_details["id"],
            "user_name": user_details["user_name"],
            "user_email": user_details["user_email"],
            "model": DEPLOYMENT,
            "input_tokens": input_tokens,
            "completion_tokens": completion_tokens,
            "output_tokens": output_tokens,
            "files_processed": total_files_processed,
            "file_processing_details": file_stats
        }, 200)
        
    except Exception as e:
        logger.error(f"GPT-4o Document Intelligence API error: {str(e)}")
        status_code = 500 if not str(e).startswith("4") else 400
        return create_api_response({
            "response": str(status_code),
            "message": str(e)
        }, status_code)
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except Exception as e:
                logger.error(f"Error removing temporary file {temp_file}: {str(e)}")

def register_llm_gpt_4o(app):
    """Register routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    
    # Note: This route consumes 2 AI Credits per call (higher than gpt-4o-mini)
    app.route('/llm/gpt-4o', methods=['POST'])(api_logger(check_balance(gpt4o_document_intelligence_route)))


