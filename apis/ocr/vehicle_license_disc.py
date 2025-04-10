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

# Define allowed file extensions for vehicle license disc OCR
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'tiff', 'tif'}

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

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
    """Process barcode content from vehicle license disc"""
    try:
        if not raw_barcode or len(raw_barcode) == 0:
            return None
            
        results = [x for x in raw_barcode.split('%')]
        
        # Check if the barcode contains sufficient data
        if len(results) < 15:
            logger.warning(f"Barcode data insufficient, found only {len(results)} fields")
            return None
            
        vehicle_json = {
            "veh_no": results[5], 
            "veh_reg_no": results[6],
            "veh_register_no": results[7],
            "veh_description": results[8],
            "veh_make": results[9],
            "veh_model": results[10],
            "veh_color": results[11],
            "veh_vin_no": results[12],
            "veh_engine_no": results[13],
            "veh_expiry": results[14]
        }

        return vehicle_json
    except Exception as ex:
        logger.error(f"Error processing barcode: {str(ex)}")
        return None

def create_json_gpt(text, token):
    """Extract vehicle license disc information using GPT when barcode is unavailable"""
    if not text or len(text.strip()) == 0:
        logger.warning("No text content for GPT processing")
        return None
        
    try:
        system_prompt = """
            You are an OCR extraction assistant. 
            You are provided with the text from an OCR extraction from a South African vehicle license disc. You must extract the requested key pieces of information. 
            The extracted information contains both English and Afrikaans labels for each of the values to be extracted.
            Engine no./Enjinnr. is an alphanumeric value that is manufacturer specifc.
            VIN Number/Vinaginemr is an alphanumeric value that is unique to each vehicle.
        """

        user_input = f"""    
            Please ensure that the resulting JSON contains only plain characters and no special characters from this text: '''{text}'''
            Respond in the following JSON format, without additional code blocks or any new lines. 
            {{
                "RSA NO.": "answer",
                "License no./Lisensienr.": "answer",
                "Veh. register no./Vrt.registerer.": "answer",
                "VIN": "answer",
                "Fees/Gelde": "answer",
                "Engine no./Enjinnr.": "answer",
                "GVM/PVM": "answer",
                "Tare/Tarra": "answer",
                "Make": "answer",
                "Description/Beskrywing": "answer",
                "Persons/Personne": "answer",
                "Seated/Sittende": "answer",
                "Date of expiry/Vervaldatum": "answer"
            }}
        """
        
        # Use gpt4o_mini_service from llmServices instead of making HTTP request
        logger.info("Calling gpt-4o-mini for vehicle license disc data extraction")
        llm_result = gpt4o_mini_service(
            system_prompt=system_prompt,
            user_input=user_input,
            temperature=0.3,
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
        
        # Map the GPT output fields to our standard output format
        vehicle_json = {
            "veh_no": results.get("RSA NO.", ""), 
            "veh_reg_no": results.get("License no./Lisensienr.", ""),
            "veh_register_no": results.get("Veh. register no./Vrt.registerer.", ""),
            "veh_description": results.get("Description/Beskrywing", ""),
            "veh_make": results.get("Make", ""),
            "veh_model": "",  # Not available in OCR text
            "veh_color": "",  # Not available in OCR text
            "veh_vin_no": results.get("VIN", ""),
            "veh_engine_no": results.get("Engine no./Enjinnr.", ""),
            "veh_expiry": results.get("Date of expiry/Vervaldatum", "")
        }
            
        # Store LLM token usage - UPDATED TOKEN REFERENCES
        vehicle_json["prompt_tokens"] = llm_result.get("prompt_tokens", 0)
        vehicle_json["completion_tokens"] = llm_result.get("completion_tokens", 0)
        vehicle_json["total_tokens"] = llm_result.get("total_tokens", 0)
        vehicle_json["cached_tokens"] = llm_result.get("cached_tokens", 0)
        vehicle_json["model_used"] = llm_result.get("model", "gpt-4o-mini")
        
        return vehicle_json
    except Exception as ex:
        logger.error(f"Error processing text with GPT: {str(ex)}")
        return None

def extract_vehicle_data(result, token):
    """Extract barcode and/or content from vehicle license disc"""
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
                            barcode_json["extraction_method"] = "barcode analysis"
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
        vehicle_json = create_json_gpt(cleaned_text, token)
        
        if vehicle_json:
            # Add document processing information
            vehicle_json["documents_processed"] = 1
            vehicle_json["pages_processed"] = len(result.pages)
            vehicle_json["extraction_method"] = "image ocr"
            
        return vehicle_json
    except Exception as ex:
        logger.error(f"Error extracting vehicle data: {str(ex)}")
        return None

def vehicle_license_disc_route():
    """
    Perform OCR on South African vehicle license discs
    ---
    tags:
      - OCR
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
              description: ID of the previously uploaded file to process
    produces:
      - application/json
    responses:
      200:
        description: Successful OCR extraction
        schema:
          type: object
          properties:
            veh_no:
              type: string
              description: RSA identification number
            veh_reg_no:
              type: string
              description: Vehicle license number
            veh_register_no:
              type: string
              description: Vehicle registration number
            veh_description:
              type: string
              description: Vehicle model and details
            veh_make:
              type: string
              description: Vehicle manufacturer
            veh_model:
              type: string
              description: Vehicle model
            veh_color:
              type: string
              description: Vehicle color
            veh_vin_no:
              type: string
              description: Vehicle Identification Number
            veh_engine_no:
              type: string
              description: Unique engine number
            veh_expiry:
              type: string
              description: License expiry date
            extraction_method:
              type: string
              description: Method used to extract the data (barcode analysis or image ocr)
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
              examples:
                - "Missing file_id parameter"
                - "Unsupported file type. Supported types: png, jpg, jpeg, pdf, tiff, tif"
                - "File ID not found"
                - "File too large for processing"
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
              examples:
                - "Missing X-Token header"
                - "Invalid token"
                - "Token has expired"
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
              examples:
                - "Error processing file"
                - "Error downloading file"
                - "Document intelligence service unavailable"
                - "Error extracting document content"
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
        
        # Extract vehicle data from the document content
        vehicle_data = extract_vehicle_data(extracted_content, token)
        
        if not vehicle_data:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to extract data from vehicle license disc"
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
        
        # Return the vehicle data
        return create_api_response(vehicle_data, 200)
        
    except Exception as e:
        logger.error(f"Error processing vehicle license disc: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing vehicle license disc: {str(e)}"
        }, 500)

def register_vehicle_license_disc_routes(app):
    from apis.utils.usageMiddleware import track_usage
    """Register vehicle license disc OCR routes with the Flask app"""
    app.route('/ocr/vehicle_license_disc', methods=['POST'])(api_logger(track_usage(check_balance(vehicle_license_disc_route))))
