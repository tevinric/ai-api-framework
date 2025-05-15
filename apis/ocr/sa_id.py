from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.utils.fileService import FileService
from apis.utils.llmServices import gpt4o_mini_service
import logging
import pytz
from datetime import datetime
import os
import io
import re
import json
import requests

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Document Intelligence Feature Imports
try:
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import DocumentAnalysisFeature
    from azure.ai.documentintelligence.models import DocumentBarcodeKind
    from azure.core.exceptions import HttpResponseError
except ImportError:
    logger.warning("Azure AI Document Intelligence SDK not found. Please install it with pip.")

# Define allowed file extensions for ID OCR
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'tiff', 'tif'}

from apis.utils.config import create_api_response

def allowed_file(filename):
    """Check if the file extension is allowed for OCR processing"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_text(text):
    """Clean extracted text by removing extra whitespace and special characters"""
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    # Remove any standalone newline characters
    text = text.replace('\n', ' ')
    # Remove special characters
    text = re.sub(r'[^A-Za-z0-9 ]+', '', text)
    return text

def create_document_intelligence_client():
    """Create Azure Document Intelligence Client"""
    try:
        # Get Document Intelligence credentials from environment variables
        endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        api_key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        
        if not endpoint or not api_key:
            logger.error("Document Intelligence API credentials not configured")
            return None

        client = DocumentIntelligenceClient(
            endpoint=endpoint, 
            credential=AzureKeyCredential(api_key)
        )
        
        return client
    except Exception as ex:
        logger.error(f"Document Intelligence client creation error: {str(ex)}")
        return None
    
def process_document_content(file_stream):
    """Process content using Azure Document Intelligence"""
    try:
        document_intelligence_client = create_document_intelligence_client()
        if not document_intelligence_client:
            raise ValueError("Failed to create Document Intelligence client")

        # Read the file stream into a bytes object
        file_content = file_stream.read()
        
        # The API expects the file content directly as the 'body' parameter
        poller = document_intelligence_client.begin_analyze_document(
            "prebuilt-layout",
            file_content,
            content_type="application/octet-stream",
            features=[DocumentAnalysisFeature.BARCODES]
        )
         
        result = poller.result()
        return result
    except HttpResponseError as error:
        logger.error(f"Document Intelligence API error: {str(error)}")
        raise ValueError(f"Document processing error: {str(error)}")
    except Exception as ex:
        logger.error(f"Document processing error: {str(ex)}")
        raise ValueError(f"Document processing error: {str(ex)}")

def create_json_barcode(raw_barcode):
    """Process barcode content from South African ID document"""
    try:
        if not raw_barcode or len(raw_barcode) == 0:
            return None
            
        results = [x for x in raw_barcode.split('|')]
        
        # Check if the barcode contains sufficient data
        if len(results) < 7:
            logger.warning(f"Barcode data insufficient, found only {len(results)} fields")
            return None
            
        id_json = {
            "surname": results[0].strip(), 
            "names": results[1].strip(),
            "sex": results[2].strip(),
            "nationality": results[3].strip(),
            "identity_number": results[4].strip(),
            "date_of_birth": results[5].strip(),
            "country_of_birth": results[6].strip(),
        }      

        return id_json
    except Exception as ex:
        logger.error(f"Error processing barcode: {str(ex)}")
        return None

def create_json_gpt(text, token):
    """Extract ID information using GPT when barcode is unavailable"""
    if not text or len(text.strip()) == 0:
        logger.warning("No text content for GPT processing")
        return None
        
    try:
        system_prompt = """
            You are an OCR extraction assistant. 
            You are provided with the text from an OCR extraction and you must extract the requested key pieces of information 
            from a South African Identity Document, which is either a Smart ID Card (front or back) or a Green ID Book.
            Please ensure that the resulting JSON contains only plain characters and no special characters.
        """

        user_input = f"""    
            Please ensure that the resulting JSON contains only plain characters and no special characters from this text: '''{text}'''
            Respond in the following JSON format: 
            "Surname": "answer",
            "Names": "answer",
            "Sex": "answer",
            "Nationality": "answer",
            "RSA Identity Number": "answer",
            "Date of Birth": "answer",
            "Country of Birth": "answer"
        """

        # Use gpt4o_mini_service from llmServices instead of making HTTP request
        logger.info("Calling gpt-4o-mini for ID data extraction")
        llm_result = gpt4o_mini_service(
            system_prompt=system_prompt,
            user_input=user_input,
            temperature=0.25,
            json_output=True
        )
        
        if not llm_result.get("success", False):
            logger.error(f"GPT API error: {llm_result.get('error')}")
            return None
            
        result_content = llm_result.get("result", "{}")
        
        # Ensure the content is valid JSON
        if isinstance(result_content, str):
            results = json.loads(result_content)
        else:
            results = result_content  # Already a JSON object
        
        id_json = {
            "surname": results.get("Surname", ""), 
            "names": results.get("Names", ""),
            "sex": results.get("Sex", ""),
            "nationality": results.get("Nationality", ""),
            "identity_number": results.get("RSA Identity Number", ""),
            "date_of_birth": results.get("Date of Birth", ""),
            "country_of_birth": results.get("Country of Birth", ""),
        }
            
        # Store LLM token usage - UPDATED TOKEN REFERENCES
        id_json["prompt_tokens"] = llm_result.get("prompt_tokens", 0)
        id_json["completion_tokens"] = llm_result.get("completion_tokens", 0)
        id_json["total_tokens"] = llm_result.get("total_tokens", 0)
        id_json["cached_tokens"] = llm_result.get("cached_tokens", 0)
        id_json["model_used"] = llm_result.get("model", "gpt-4o-mini")
        
        return id_json
    except Exception as ex:
        logger.error(f"Error processing text with GPT: {str(ex)}")
        return None
    
def extract_id_data(result, token):
    """Extract barcode and/or content from South African ID document"""
    if not result:
        logger.error("No result from Document Intelligence")
        return None
        
    try:
        # First, try to extract from barcode
        for page in result.pages:
            if hasattr(page, 'barcodes') and page.barcodes:
                for barcode in page.barcodes:
                    if hasattr(barcode, 'kind') and barcode.kind == DocumentBarcodeKind.PDF417:
                        barcode_json = create_json_barcode(barcode.value)
                        if barcode_json:
                            # Add document processing information
                            barcode_json["documents_processed"] = 1
                            barcode_json["pages_processed"] = len(result.pages)
                            barcode_json["prompt_tokens"] = 0
                            barcode_json["completion_tokens"] = 0
                            barcode_json["total_tokens"] = 0
                            barcode_json["cached_tokens"] = 0
                            barcode_json["model_used"] = "none"
                            return barcode_json
                            
        # If no barcode found or valid barcode data extracted, fall back to OCR + GPT
        extracted_text = []
        for page in result.pages:
            if hasattr(page, 'lines') and page.lines:
                for line in page.lines:
                    if hasattr(line, 'content') and line.content:
                        extracted_text.append(line.content)
        
        if not extracted_text:
            logger.warning("No text could be extracted from the document")
            return None
            
        cleaned_text = clean_text(" ".join(extracted_text))
        id_json = create_json_gpt(cleaned_text, token)
        
        if id_json:
            # Add document processing information
            id_json["documents_processed"] = 1
            id_json["pages_processed"] = len(result.pages)
            
        return id_json
    except Exception as ex:
        logger.error(f"Error extracting ID data: {str(ex)}")
        return None

def sa_id_ocr_route():
    """
    Perform OCR on South African ID documents
    ---
    tags:
      - OCR
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
              description: ID of the previously uploaded file to process
    produces:
      - application/json
    responses:
      200:
        description: Successful OCR extraction
        schema:
          type: object
          properties:
            surname:
              type: string
              description: Last name of the ID holder
            names:
              type: string
              description: Given names of the ID holder
            sex:
              type: string
              description: Gender of the ID holder
            nationality:
              type: string
              description: Nationality of the ID holder
            identity_number:
              type: string
              description: South African ID number
            date_of_birth:
              type: string
              description: Birth date
            country_of_birth:
              type: string
              description: Country where ID holder was born
            documents_processed:
              type: integer
              description: Number of documents processed
            pages_processed:
              type: integer
              description: Number of pages processed
            prompt_tokens:
              type: integer
              description: Number of prompt tokens consumed (if GPT was used)
            completion_tokens:
              type: integer
              description: Number of completion tokens consumed (if GPT was used)
            total_tokens:
              type: integer
              description: Total number of tokens consumed (if GPT was used)
            cached_tokens:
              type: integer
              description: Number of cached tokens (if available)
            model_used:
              type: string
              description: The LLM model used for processing (or "none" if barcode was used)
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
              example: Missing file_id parameter
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
              example: Missing X-Token header
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
              example: Error processing file
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
            "message": "Missing file_id parameter"
        }, 400)
    
    file_id = data['file_id']
    
    try:
        # Use FileService to get file URL instead of making HTTP request
        file_info, error = FileService.get_file_url(file_id, g.user_id)
        
        # Check if there was an error
        if error:
            logger.error(f"Failed to get file URL: {error}")
            return create_api_response({
                "error": "Bad Request",
                "message": "File ID not found"
            }, 400)
        
        # Extract the file URL and content type
        file_url = file_info.get('file_url')
        content_type = file_info.get('content_type')
        file_name = file_info.get('file_name')
        
        # Check if the file type is supported
        if not file_name or not allowed_file(file_name):
            logger.warning(f"Unsupported file type: {content_type}, {file_name}")
            return create_api_response({
                "error": "Bad Request",
                "message": f"Unsupported file type. Supported types: {', '.join(ALLOWED_EXTENSIONS)}"
            }, 400)
        
        # Download the file (still need to use HTTP request for this)
        file_response = requests.get(file_url)
        if file_response.status_code != 200:
            logger.error(f"Failed to download file: {file_response.status_code}")
            return create_api_response({
                "error": "Server Error",
                "message": "Error downloading file"
            }, 500)
        
        # Check file size (limit to 10MB to prevent abuse)
        file_size = len(file_response.content)
        if file_size > 10 * 1024 * 1024:  # 10MB
            logger.warning(f"File too large: {file_size} bytes")
            return create_api_response({
                "error": "Bad Request",
                "message": "File too large for processing (max 10MB)"
            }, 400)
        
        # Process the file
        file_stream = io.BytesIO(file_response.content)
        
        # Extract document content
        try:
            extracted_content = process_document_content(file_stream)
        except ValueError as ve:
            logger.error(f"Document processing error: {str(ve)}")
            return create_api_response({
                "error": "Server Error",
                "message": str(ve)
            }, 500)
        
        # Extract ID data from the document content
        id_data = extract_id_data(extracted_content, token)
        
        if not id_data:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to extract data from ID document"
            }, 500)
        
        # Delete the file after successful processing using FileService
        try:
            success, message = FileService.delete_file(file_id, g.user_id)
            
            if success:
                logger.info(f"Successfully deleted file {file_id} after processing")
            else:
                logger.warning(f"Failed to delete file {file_id}: {message}")
        except Exception as delete_error:
            # Log but don't fail if deletion fails
            logger.warning(f"Error deleting file {file_id}: {str(delete_error)}")
        
        # Return the ID data
        return create_api_response(id_data, 200)
        
    except Exception as e:
        logger.error(f"Error processing ID document: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing ID document: {str(e)}"
        }, 500)

def register_sa_id_ocr_routes(app):
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access    
    
    """Register SA ID OCR routes with the Flask app"""
    app.route('/ocr/sa_id_card', methods=['POST'])(track_usage(api_logger(check_endpoint_access(check_balance(sa_id_ocr_route)))))
