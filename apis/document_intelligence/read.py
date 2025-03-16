from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
import logging
import pytz
from datetime import datetime
import os
import json
import requests
import tempfile

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

def process_text_into_paragraphs(lines, spans, tables):
    """
    Convert individual lines into paragraphs and identify tables.
    
    Args:
        lines: List of line objects from Document Intelligence
        spans: List of spans for the document
        tables: List of tables found in the document
        
    Returns:
        list: Structured text content with paragraphs and tables
    """
    if not lines:
        return []
    
    # Step 1: Organize lines by their vertical position and identify tables
    paragraphs = []
    current_paragraph = []
    previous_line = None
    
    # Track which spans are part of tables
    table_spans = set()
    if tables:
        for table in tables:
            for cell in table.cells:
                if cell.spans_indices:
                    for index in cell.spans_indices:
                        table_spans.add(index)
    
    for line in lines:
        # Skip the line if it's part of a table
        if hasattr(line, 'spans_indices') and any(index in table_spans for index in line.spans_indices):
            continue
            
        if previous_line is None:
            # First line, start a new paragraph
            current_paragraph.append(line.content)
        else:
            # Check if this line should be part of the current paragraph
            # The heuristic can be adjusted based on your requirements
            line_spacing = line.polygon[0].y - previous_line.polygon[2].y
            avg_height = (previous_line.polygon[2].y - previous_line.polygon[0].y + 
                          line.polygon[2].y - line.polygon[0].y) / 2
            
            # If the line spacing is small compared to the line height, it's likely part of the same paragraph
            if line_spacing <= avg_height * 1.5:  # Threshold can be adjusted
                current_paragraph.append(line.content)
            else:
                # This is a new paragraph
                if current_paragraph:
                    paragraphs.append({
                        "type": "paragraph",
                        "content": " ".join(current_paragraph)
                    })
                current_paragraph = [line.content]
        
        previous_line = line
    
    # Add the last paragraph if there's any
    if current_paragraph:
        paragraphs.append({
            "type": "paragraph",
            "content": " ".join(current_paragraph)
        })
    
    # Step 2: Process tables if any
    if tables:
        # Sort paragraphs and tables by their vertical position
        table_paragraphs = []
        for table in tables:
            table_obj = {
                "type": "table",
                "rows": len(table.row_count),
                "columns": len(table.column_count),
                "cells": []
            }
            
            # Extract table cells
            for row_idx in range(table.row_count):
                table_row = []
                for col_idx in range(table.column_count):
                    cell_content = ""
                    # Find the cell at this position
                    for cell in table.cells:
                        if cell.row_index == row_idx and cell.column_index == col_idx:
                            # Get text from spans
                            if hasattr(cell, 'spans_indices') and cell.spans_indices:
                                cell_texts = []
                                for span_idx in cell.spans_indices:
                                    if span_idx < len(spans):
                                        cell_texts.append(spans[span_idx].content)
                                cell_content = " ".join(cell_texts)
                            break
                    table_row.append(cell_content)
                table_obj["cells"].append(table_row)
            
            # Store table with position information
            table_top = min(cell.polygon[0].y for cell in table.cells) if table.cells else 0
            table_paragraphs.append((table_top, table_obj))
        
        # Merge paragraphs and tables based on vertical position
        if table_paragraphs:
            paragraph_positions = []
            for i, para in enumerate(paragraphs):
                # Estimate paragraph position (top)
                para_top = 0  # This is a placeholder - you'd need actual position data
                paragraph_positions.append((para_top, i, para))
            
            # Combine and sort all elements by vertical position
            all_elements = paragraph_positions + table_paragraphs
            all_elements.sort()
            
            # Rebuild paragraphs with tables in the right positions
            result = []
            for _, elem in all_elements:
                if isinstance(elem, int):  # It's a paragraph index
                    result.append(paragraphs[elem])
                else:  # It's a table
                    result.append(elem)
            return result
    
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
                                description: Type of text element (paragraph or table)
                              content:
                                type: string
                                description: Text content for paragraphs
                              rows:
                                type: integer
                                description: Number of rows (for tables)
                              columns:
                                type: integer
                                description: Number of columns (for tables)
                              cells:
                                type: array
                                description: Table cells contents (for tables)
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
            # Get file URL from the file ID
            headers = {"X-Token": token}
            logger.info(f"Getting file URL for file ID: {file_id}")
            # Make a request to the file/url endpoint using GET method
            # The endpoint expects file_id as a query parameter
            file_url_endpoint = f"{request.url_root.rstrip('/')}/file/url?file_id={file_id}"
            logger.info(f"Requesting file URL from endpoint: {file_url_endpoint}")
            
            file_url_response = requests.get(
                file_url_endpoint,
                headers=headers
            )
            
            # Log the response details for debugging
            logger.info(f"File URL response status: {file_url_response.status_code}")
            if file_url_response.status_code != 200:
                logger.error(f"File URL response error: {file_url_response.text}")
            else:
                logger.info(f"File URL response: {file_url_response.text[:100]}...")
            
            if file_url_response.status_code != 200:
                logger.error(f"Error retrieving file URL: Status {file_url_response.status_code}, Response: {file_url_response.text[:500]}")
                results.append({
                    "file_id": file_id,
                    "error": f"File not found or you don't have access"
                })
                continue
            
            file_info = file_url_response.json()
            file_url = file_info.get("file_url")
            file_name = file_info.get("file_name")
            
            logger.info(f"Retrieved file URL: {file_url} for file: {file_name}")
            
            if not file_url:
                logger.error("Missing file_url in response from get-file-url endpoint")
                results.append({
                    "file_id": file_id,
                    "file_name": file_name if file_name else "Unknown",
                    "error": "Failed to retrieve file URL"
                })
                continue
            
            # Call Document Intelligence to analyze the document
            try:
                logger.info(f"Sending document to Document Intelligence service: {file_url}")
                
                # Create analyzer options based on requested features
                analyzer_options = {}
                features = []
                
                if options['language']:
                    features.append("languages")
                
                # Add layout feature to detect tables
                features.append("layout")
                
                if features:
                    analyzer_options["features"] = features
                
                # Start the document analysis
                poller = document_client.begin_analyze_document(
                    "prebuilt-layout",  # Use layout model to get paragraphs and tables
                    AnalyzeDocumentRequest(url_source=file_url),
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
                    "has_handwritten_content": any(style.is_handwritten for style in result.styles if style.is_handwritten),
                    "pages": []
                }
                
                # Process each requested page
                for page_idx, page in enumerate(result.pages):
                    # Skip pages not in the requested range
                    if page.page_number not in pages_to_process:
                        continue
                    
                    # Get tables for this page
                    page_tables = []
                    if hasattr(result, 'tables'):
                        page_tables = [table for table in result.tables if table.bounding_regions and 
                                     any(region.page_number == page.page_number for region in table.bounding_regions)]
                    
                    page_info = {
                        "page_number": page.page_number,
                        "width": page.width,
                        "height": page.height,
                        "unit": page.unit,
                        "has_handwritten_content": False,  # Will update based on styles
                    }
                    
                    # Process text into paragraphs and tables
                    spans = result.spans if hasattr(result, 'spans') else []
                    page_info["text"] = process_text_into_paragraphs(
                        page.lines, 
                        spans,
                        page_tables
                    )
                    
                    # If Document Intelligence supports paragraphs directly, use them
                    if hasattr(page, 'paragraphs') and page.paragraphs:
                        paragraph_texts = []
                        for para in page.paragraphs:
                            paragraph_texts.append({
                                "type": "paragraph",
                                "content": para.content
                            })
                        
                        # Replace our heuristic-based paragraphs with actual paragraphs
                        # but keep the tables we detected
                        tables = [item for item in page_info["text"] if item.get("type") == "table"]
                        page_info["text"] = paragraph_texts + tables
                    
                    # If language detection was requested, include that
                    if options['language'] and hasattr(page, 'languages') and page.languages:
                        page_info["detected_languages"] = [
                            {
                                "language": lang.locale,
                                "confidence": lang.confidence
                            } 
                            for lang in page.languages
                        ]
                    
                    # Check if page has handwritten content
                    for style in result.styles:
                        if style.is_handwritten and style.page_number == page.page_number:
                            page_info["has_handwritten_content"] = True
                            break
                    
                    # Add to results
                    document_result["pages"].append(page_info)
                
                # Add to overall results
                results.append(document_result)
                total_documents += 1
                total_pages += len(document_result["pages"])
                
            except HttpResponseError as e:
                logger.error(f"Azure Document Intelligence service error: {str(e)}")
                results.append({
                    "file_id": file_id,
                    "file_name": file_name,
                    "error": f"Document analysis error: {str(e)}"
                })
                continue
                
            except Exception as e:
                logger.error(f"Error analyzing document: {str(e)}")
                results.append({
                    "file_id": file_id,
                    "file_name": file_name,
                    "error": f"Document analysis error: {str(e)}"
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

def register_document_intelligence_routes(app):
    """Register document intelligence routes with the Flask app"""
    app.route('/docint/read', methods=['POST'])(api_logger(check_balance(document_read_route)))
