from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.utils.fileService import FileService
import logging
import pytz
from datetime import datetime
import os
import json
import tempfile
import requests

# For Azure AI Document Intelligence
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.exceptions import HttpResponseError

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def parse_page_range(page_range_str, total_pages):
    """
    Parse a page range string like "1,3-6" into a list of page numbers.
    
    Args:
        page_range_str (str): String specifying the page range
        total_pages (int): Total number of pages in the document
        
    Returns:
        list: List of page numbers to process
    """
    if not page_range_str or page_range_str.lower() == "all_pages":
        return list(range(1, total_pages + 1))
        
    page_numbers = []
    parts = page_range_str.split(',')
    
    for part in parts:
        if '-' in part:
            start, end = part.split('-')
            try:
                start_num = int(start.strip())
                end_num = int(end.strip())
                # Ensure start and end are valid page numbers
                start_num = max(1, start_num)
                end_num = min(total_pages, end_num)
                page_numbers.extend(range(start_num, end_num + 1))
            except ValueError:
                # If there's a parsing error, skip this part
                logger.warning(f"Invalid page range: {part}")
                continue
        else:
            try:
                page_num = int(part.strip())
                if 1 <= page_num <= total_pages:
                    page_numbers.append(page_num)
            except ValueError:
                # If there's a parsing error, skip this part
                logger.warning(f"Invalid page number: {part}")
                continue
    
    # Remove duplicates and sort
    page_numbers = sorted(list(set(page_numbers)))
    
    # If no valid pages were specified, default to all pages
    if not page_numbers:
        return list(range(1, total_pages + 1))
        
    return page_numbers

def group_lines_into_paragraphs(lines):
    """
    Group sequential lines into paragraphs.
    
    Args:
        lines (list): List of line content strings
        
    Returns:
        list: List of paragraph content strings
    """
    if not lines:
        return []
    
    paragraphs = []
    current_paragraph = []
    
    for line in lines:
        # Skip empty lines
        if not line.strip():
            if current_paragraph:
                # End of paragraph
                paragraphs.append(" ".join(current_paragraph))
                current_paragraph = []
            continue
        
        # Check if this line is likely the start of a new paragraph
        if current_paragraph and (
            line.strip().startswith(('-', '•', '*', '>', '1.', '2.')) or  # List markers
            line.strip()[0:1].isupper() and ( # First char is uppercase AND
                # Previous line ends with sentence-ending punctuation
                (current_paragraph[-1].rstrip().endswith(('.', '!', '?')) and 
                 not current_paragraph[-1].rstrip().endswith('Fig.')) or  # Skip Fig. abbreviations
                # Previous line is very short (potential header)
                len(current_paragraph[-1].strip()) < 25
            )
        ):
            # End the current paragraph and start a new one
            paragraphs.append(" ".join(current_paragraph))
            current_paragraph = [line]
        else:
            # Continue current paragraph
            current_paragraph.append(line)
    
    # Add the last paragraph if there's any
    if current_paragraph:
        paragraphs.append(" ".join(current_paragraph))
    
    return paragraphs

def document_read_route():
    """
    Extract printed and handwritten text from images and documents
    ---
    tags:
      - Document Intelligence
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
            - file_ids
          properties:
            file_ids:
              type: array
              items:
                type: string
              description: Array of file IDs to process (uploaded via /file endpoint)
            barcode_detection:
              type: boolean
              default: false
              description: Enable barcode detection
            language:
              type: boolean
              default: false
              description: Include language identification
            page_selection:
              type: string
              enum: [all_pages, range]
              default: all_pages
              description: Page selection strategy
            page_range:
              type: string
              description: Page range to process (e.g., "1,3-6"), only used if page_selection is "range"
    consumes:
      - application/json
    produces:
      - application/json
    responses:
      200:
        description: Documents successfully processed
        schema:
          type: object
          properties:
            message:
              type: string
              example: Documents successfully processed
            documents_processed:
              type: integer
              description: Number of documents processed
            pages_processed:
              type: integer
              description: Total number of pages processed across all documents
            results:
              type: array
              items:
                type: object
                properties:
                  file_id:
                    type: string
                    description: ID of the processed file
                  file_name:
                    type: string
                    description: Original name of the processed file
                  pages:
                    type: array
                    items:
                      type: object
                      properties:
                        page_number:
                          type: integer
                          description: Page number
                        width:
                          type: number
                          description: Page width
                        height:
                          type: number
                          description: Page height
                        unit:
                          type: string
                          description: Measurement unit (e.g., "pixel", "inch")
                        has_handwritten_content:
                          type: boolean
                          description: Whether page contains handwritten content
                        text:
                          type: array
                          items:
                            type: object
                            properties:
                              type:
                                type: string
                                description: Type of text element (paragraph)
                              content:
                                type: string
                                description: Text content
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
              example: Missing file_ids parameter or empty file_ids array
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
              example: Missing X-Token header or Invalid token
      404:
        description: Not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: One or more files not found
      415:
        description: Unsupported media type
        schema:
          type: object
          properties:
            error:
              type: string
              example: Unsupported Media Type
            message:
              type: string
              example: File type not supported for text extraction
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
              example: Error processing document
    """
    # Get token from X-Token header
    token = request.headers.get('X-Token')
    if not token:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing X-Token header"
        }, 401)
    
    # Validate token
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
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate file_ids
    file_ids = data.get('file_ids')
    if not file_ids or not isinstance(file_ids, list) or len(file_ids) == 0:
        return create_api_response({
            "error": "Bad Request",
            "message": "file_ids must be a non-empty array of file IDs"
        }, 400)
    
    # Extract other parameters with defaults
    options = {
        'barcode_detection': data.get('barcode_detection', False),
        'language': data.get('language', False),
        'page_selection': data.get('page_selection', 'all_pages'),
        'page_range': data.get('page_range', None),
        'token': token
    }
    
    # Get Document Intelligence configuration
    endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    api_key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    
    if not endpoint or not api_key:
        return create_api_response({
            "error": "Server Error",
            "message": "Document Intelligence service not properly configured"
        }, 500)
    
    # Initialize Document Intelligence client
    try:
        document_client = DocumentIntelligenceClient(
            endpoint=endpoint, 
            credential=AzureKeyCredential(api_key)
        )
    except Exception as e:
        logger.error(f"Error initializing Document Intelligence client: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error initializing Document Intelligence service: {str(e)}"
        }, 500)
    
    # Process each file
    results = []
    total_documents = 0
    total_pages = 0
    
    for file_id in file_ids:
        try:
            # Get file URL using FileService
            file_info, error = FileService.get_file_url(file_id, g.user_id)
            
            if error:
                logger.error(f"Error retrieving file URL: {error}")
                results.append({
                    "file_id": file_id,
                    "error": error
                })
                continue
            
            file_url = file_info.get("file_url")
            file_name = file_info.get("file_name")
            
            logger.info(f"Retrieved file URL: {file_url} for file: {file_name}")
            
            if not file_url:
                logger.error("Missing file_url in file info")
                results.append({
                    "file_id": file_id,
                    "file_name": file_name if file_name else "Unknown",
                    "error": "Failed to retrieve file URL"
                })
                continue
            
            # Check if the file has a supported extension
            supported_extensions = ['.jpg', '.jpeg', '.jpe', '.jif', '.jfi', '.jfif', '.png', '.tif', '.tiff', '.pdf']
            file_extension = os.path.splitext(file_name.lower())[1] if file_name else ''
            
            if not file_extension or file_extension not in supported_extensions:
                logger.warning(f"Unsupported file type: {file_extension} for file: {file_name}")
                results.append({
                    "file_id": file_id,
                    "file_name": file_name if file_name else "Unknown",
                    "error": f"Unsupported file type. Only {', '.join(supported_extensions)} files are supported."
                })
                continue
            
            logger.info(f"File type validation passed for file: {file_name} with extension: {file_extension}")
            
            # Download the file content directly instead of relying on URL access
            try:
                # Try to download the file directly
                file_response = requests.get(file_url, timeout=60)
                
                # If it's an Azure blob URL, we might need to add authorization
                if file_response.status_code != 200 and "blob.core.windows.net" in file_url:
                    file_response = requests.get(
                        file_url,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=60
                    )
                
                if file_response.status_code != 200:
                    logger.error(f"Failed to download file content: Status {file_response.status_code}")
                    results.append({
                        "file_id": file_id,
                        "file_name": file_name,
                        "error": f"Failed to download file content: Status {file_response.status_code}"
                    })
                    continue
                
                # Create a temporary file to store the content
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                    temp_file.write(file_response.content)
                    temp_file_path = temp_file.name
                
                logger.info(f"File content downloaded and saved to temporary file: {temp_file_path}")
                
                try:
                    # Call Document Intelligence using file content instead of URL
                    logger.info(f"Sending document to Document Intelligence service from local file")
                    
                    # Create analyzer options based on requested features
                    analyzer_options = {}
                    if options['language']:
                        analyzer_options["features"] = ["languages"]
                    
                    # Start the document analysis with the file content
                    with open(temp_file_path, "rb") as document_file:
                        file_content = document_file.read()
                        poller = document_client.begin_analyze_document(
                            model_id="prebuilt-read",
                            analyze_request=AnalyzeDocumentRequest(base64_source=base64.b64encode(file_content).decode()),
                            **analyzer_options
                        )
                    
                    logger.info(f"Waiting for Document Intelligence to complete analysis...")
                    result = poller.result()
                    
                    # Check if document was analyzed successfully
                    if not result or not result.pages:
                        logger.warning(f"No results returned from Document Intelligence for file: {file_name}")
                        results.append({
                            "file_id": file_id,
                            "file_name": file_name,
                            "error": "No text content detected in document"
                        })
                        # Clean up temporary file
                        os.unlink(temp_file_path)
                        continue
                    
                    # Determine which pages to process
                    document_page_count = len(result.pages)
                    if options['page_selection'] == 'range' and options['page_range']:
                        pages_to_process = parse_page_range(options['page_range'], document_page_count)
                    else:
                        pages_to_process = list(range(1, document_page_count + 1))
                    
                    # Format results for the response
                    document_result = {
                        "file_id": file_id,
                        "file_name": file_name,
                        "total_pages": document_page_count,
                        "processed_pages": len(pages_to_process),
                        "has_handwritten_content": False,  # Will update if handwritten content is detected
                        "pages": []
                    }
                    
                    # Check for handwritten content if styles are available
                    if hasattr(result, 'styles') and result.styles:
                        document_result["has_handwritten_content"] = any(
                            style.is_handwritten for style in result.styles if hasattr(style, 'is_handwritten')
                        )
                    
                    # Process each requested page
                    for page in result.pages:
                        # Skip pages not in the requested range
                        if page.page_number not in pages_to_process:
                            continue
                        
                        page_info = {
                            "page_number": page.page_number,
                            "width": page.width,
                            "height": page.height,
                            "unit": page.unit,
                            "has_handwritten_content": False,  # Will update based on styles
                            "text": []
                        }
                        
                        # Extract all line content
                        line_contents = [line.content for line in page.lines if line.content.strip()]
                        
                        # Group lines into paragraphs
                        paragraphs = group_lines_into_paragraphs(line_contents)
                        
                        # Add paragraphs to the response
                        for paragraph in paragraphs:
                            if paragraph.strip():  # Skip empty paragraphs
                                page_info["text"].append({
                                    "type": "paragraph",
                                    "content": paragraph
                                })
                        
                        # Create page_text_all with all paragraphs from this page
                        page_text_all = ""
                        for text_item in page_info["text"]:
                            if text_item["type"] == "paragraph" and text_item["content"].strip():
                                page_text_all += text_item["content"] + "\n\n"
                        
                        # Add the consolidated page text
                        page_info["page_text_all"] = page_text_all.strip()
                        
                        # If language detection was requested, include that
                        if options['language'] and hasattr(page, 'languages') and page.languages:
                            page_info["detected_languages"] = [
                                {
                                    "language": lang.locale,
                                    "confidence": lang.confidence
                                } 
                                for lang in page.languages
                            ]
                        
                        # Check if page has handwritten content (safely)
                        if hasattr(result, 'styles') and result.styles:
                            for style in result.styles:
                                if (hasattr(style, 'is_handwritten') and 
                                    style.is_handwritten and 
                                    hasattr(style, 'page_number') and
                                    style.page_number == page.page_number):
                                    page_info["has_handwritten_content"] = True
                                    break
                        
                        # Add to results
                        document_result["pages"].append(page_info)
                    
                    # Clean up temporary file
                    os.unlink(temp_file_path)
                    
                    # Add to overall results
                    results.append(document_result)
                    total_documents += 1
                    total_pages += len(document_result["pages"])
                    
                except HttpResponseError as e:
                    # Clean up temporary file in case of error
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                        
                    logger.error(f"Azure Document Intelligence service error: {str(e)}")
                    results.append({
                        "file_id": file_id,
                        "file_name": file_name,
                        "error": f"Document analysis error: {str(e)}"
                    })
                    continue
                    
                except Exception as e:
                    # Clean up temporary file in case of error
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                        
                    logger.error(f"Error analyzing document: {str(e)}")
                    results.append({
                        "file_id": file_id,
                        "file_name": file_name,
                        "error": f"Document analysis error: {str(e)}"
                    })
                    continue
                    
            except Exception as e:
                logger.error(f"Error downloading file content: {str(e)}")
                results.append({
                    "file_id": file_id,
                    "file_name": file_name if file_name else "Unknown",
                    "error": f"Error downloading file content: {str(e)}"
                })
                continue
                
        except Exception as e:
            logger.error(f"Error processing file ID {file_id}: {str(e)}")
            results.append({
                "file_id": file_id,
                "error": f"Processing error: {str(e)}"
            })
            continue
    
    # If no documents were processed successfully, return an error
    if total_documents == 0:
        return create_api_response({
            "error": "Processing Error",
            "message": "No documents were processed successfully",
            "results": results
        }, 400)
    
    # Return the processed results
    return create_api_response({
        "message": "Documents successfully processed",
        "documents_processed": total_documents,
        "pages_processed": total_pages,
        "results": results
    }, 200)

def register_document_intelligence_read_routes(app):
    """Register document intelligence routes with the Flask app"""
    app.route('/docint/read', methods=['POST'])(api_logger(check_balance(document_read_route)))
