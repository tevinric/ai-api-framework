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
import re
import requests

# For Azure AI Document Intelligence
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
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

def format_table_markdown(table, header_row=True):
    """
    Format a table in markdown format.
    
    Args:
        table: Table object from Document Intelligence
        header_row (bool): Whether to treat the first row as a header
        
    Returns:
        str: Markdown formatted table
    """
    if not table or not hasattr(table, 'cells') or not table.cells:
        return ""
    
    # Organize cells by row and column
    rows = {}
    for cell in table.cells:
        row_idx = cell.row_index
        col_idx = cell.column_index
        
        if row_idx not in rows:
            rows[row_idx] = {}
        
        rows[row_idx][col_idx] = cell.content.strip()
    
    # Create markdown table
    markdown = []
    
    # Generate header row
    if rows and 0 in rows:
        header = "|"
        separator = "|"
        
        for col_idx in range(table.column_count):
            content = rows[0].get(col_idx, "").replace("|", "\\|")
            header += f" {content} |"
            separator += " --- |"
        
        markdown.append(header)
        
        # Add separator row if we're treating the first row as a header
        if header_row:
            markdown.append(separator)
            start_row = 1
        else:
            start_row = 0
    else:
        # If no header row, create a generic one
        header = "|"
        separator = "|"
        
        for col_idx in range(table.column_count):
            header += f" Column {col_idx+1} |"
            separator += " --- |"
        
        markdown.append(header)
        markdown.append(separator)
        start_row = 0
    
    # Generate data rows
    for row_idx in range(start_row, table.row_count):
        if row_idx not in rows:
            continue
            
        row_md = "|"
        for col_idx in range(table.column_count):
            content = rows[row_idx].get(col_idx, "").replace("|", "\\|")
            row_md += f" {content} |"
        
        markdown.append(row_md)
    
    return "\n".join(markdown)

def format_table_text(table):
    """
    Format a table in plain text format with proper alignment.
    
    Args:
        table: Table object from Document Intelligence
        
    Returns:
        str: Plain text formatted table
    """
    if not table or not hasattr(table, 'cells') or not table.cells:
        return ""
    
    # Organize cells by row and column
    rows = {}
    column_widths = [0] * table.column_count  # To track the max width of each column
    
    for cell in table.cells:
        row_idx = cell.row_index
        col_idx = cell.column_index
        content = cell.content.strip()
        
        if row_idx not in rows:
            rows[row_idx] = {}
        
        rows[row_idx][col_idx] = content
        
        # Update column width if this cell is wider
        column_widths[col_idx] = max(column_widths[col_idx], len(content))
    
    # Create text table
    text_table = []
    
    # Add a separator line before the table
    separator = "+" + "+".join(["-" * (width + 2) for width in column_widths]) + "+"
    text_table.append(separator)
    
    # Generate rows
    for row_idx in range(table.row_count):
        if row_idx not in rows:
            continue
            
        row_text = "|"
        for col_idx in range(table.column_count):
            content = rows[row_idx].get(col_idx, "")
            padding = column_widths[col_idx] - len(content)
            row_text += f" {content}{' ' * padding} |"
        
        text_table.append(row_text)
        
        # Add separator after each row
        text_table.append(separator)
    
    return "\n".join(text_table)

def process_keyvalue_pairs(result, output_format):
    """
    Process key-value pairs from the document.
    
    Args:
        result: Document analysis result
        output_format: 'text' or 'markdown'
        
    Returns:
        list: List of formatted key-value pairs
    """
    if not hasattr(result, 'key_value_pairs') or not result.key_value_pairs:
        return []
    
    kv_pairs = []
    
    for kv in result.key_value_pairs:
        key = kv.key.content if kv.key else "Unknown"
        value = kv.value.content if kv.value else ""
        
        if output_format == "markdown":
            kv_pairs.append(f"**{key}**: {value}")
        else:
            kv_pairs.append(f"{key}: {value}")
    
    return kv_pairs

def document_layout_route():
    """
    Extract tables, checkboxes, and text from forms and documents
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
            include_barcode:
              type: boolean
              default: false
              description: Enable barcode detection
            include_language:
              type: boolean
              default: false
              description: Include language identification
            include_keyvalue_pairs:
              type: boolean
              default: false
              description: Include key-value pairs extraction
            output_format:
              type: string
              enum: [text, markdown]
              default: text
              description: Output format for tables and structured content
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
                                description: Type of text element (e.g., "paragraph", "line")
                              content:
                                type: string
                                description: Text content
                              role:
                                type: string
                                description: Role of the text (if available)
                          description: Extracted text content
                        tables:
                          type: array
                          items:
                            type: object
                            properties:
                              row_count:
                                type: integer
                                description: Number of rows in the table
                              column_count:
                                type: integer
                                description: Number of columns in the table
                              cells:
                                type: array
                                items:
                                  type: object
                                  properties:
                                    row_index:
                                      type: integer
                                      description: Row index of the cell
                                    column_index:
                                      type: integer
                                      description: Column index of the cell
                                    row_span:
                                      type: integer
                                      description: Row span of the cell
                                    column_span:
                                      type: integer
                                      description: Column span of the cell
                                    content:
                                      type: string
                                      description: Content of the cell
                                    kind:
                                      type: string
                                      description: Kind of cell (if available)
                                description: Cell information
                              formatted:
                                type: string
                                description: Formatted table in requested format
                              table_summary:
                                type: string
                                description: Markdown summary of the table
                          description: Extracted tables
                        selection_marks:
                          type: array
                          items:
                            type: object
                            properties:
                              state:
                                type: string
                                description: State of the selection mark (e.g., "selected", "unselected")
                              confidence:
                                type: number
                                description: Confidence score for the state detection
                          description: Extracted selection marks (checkboxes)
                        barcodes:
                          type: array
                          items:
                            type: object
                            properties:
                              value:
                                type: string
                                description: Decoded barcode value
                              type:
                                type: string
                                description: Type of barcode detected
                              confidence:
                                type: number
                                description: Confidence score for the barcode detection
                          description: Extracted barcodes
                        page_text_all:
                          type: string
                          description: All text content from the page combined
                        detected_languages:
                          type: array
                          items:
                            type: object
                            properties:
                              language:
                                type: string
                                description: Detected language code
                              confidence:
                                type: number
                                description: Confidence score for language detection
                          description: Detected languages for this page
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
        'include_barcode': data.get('include_barcode', False),
        'include_language': data.get('include_language', False),
        'include_keyvalue_pairs': data.get('include_keyvalue_pairs', False),
        'output_format': data.get('output_format', 'text'),
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
        temp_file_path = None
        try:
            # Get file URL using FileService instead of making an HTTP request
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
            
            # Download the file content - REFACTORED: Instead of passing URL directly, download file first
            try:
                logger.info(f"Downloading file from URL: {file_url}")
                
                # Download the file directly
                response = requests.get(file_url, timeout=60)
                
                # If it's an Azure blob URL, we might need to add authorization
                if response.status_code != 200 and "blob.core.windows.net" in file_url:
                    response = requests.get(
                        file_url,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=60
                    )
                
                if response.status_code != 200:
                    logger.error(f"Failed to download file: Status {response.status_code}")
                    results.append({
                        "file_id": file_id,
                        "file_name": file_name,
                        "error": f"Failed to download file: Status {response.status_code}"
                    })
                    continue
                
                content_length = len(response.content)
                logger.info(f"Downloaded {content_length} bytes for file {file_name}")
                
                if content_length == 0:
                    logger.error("Downloaded file is empty")
                    results.append({
                        "file_id": file_id,
                        "file_name": file_name,
                        "error": "Downloaded file is empty"
                    })
                    continue
                
                # Save to a temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
                temp_file_path = temp_file.name
                temp_file.write(response.content)
                temp_file.close()
                
                logger.info(f"Saved file to temporary location: {temp_file_path}")
                
                # Call Document Intelligence to analyze the document from the file
                try:
                    logger.info(f"Sending document to Document Intelligence layout service")
                    
                    # Create analyzer options based on requested features
                    analyzer_options = {}
                    features = []
                    
                    if options['include_language']:
                        features.append("languages")
                    
                    if options['include_keyvalue_pairs']:
                        features.append("keyValuePairs")
                    
                    if options['include_barcode']:
                        features.append("barcodes")
                    
                    if features:
                        analyzer_options["features"] = features
                    
                    # REFACTORED: Use local file instead of URL
                    with open(temp_file_path, "rb") as document_file:
                        # Start the document analysis
                        poller = document_client.begin_analyze_document(
                            "prebuilt-layout",  # Use layout model to get structured content
                            document_file,
                            **analyzer_options
                        )
                    
                    logger.info(f"Waiting for Document Intelligence to complete layout analysis...")
                    result = poller.result()
                    
                    # Check if document was analyzed successfully
                    if not result or not result.pages:
                        logger.warning(f"No results returned from Document Intelligence for file: {file_name}")
                        results.append({
                            "file_id": file_id,
                            "file_name": file_name,
                            "error": "No content detected in document"
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
                        "has_handwritten_content": False,  # Will update if handwritten content is detected
                        "pages": []
                    }
                    
                    # Check for handwritten content if styles are available
                    if hasattr(result, 'styles') and result.styles:
                        document_result["has_handwritten_content"] = any(
                            style.is_handwritten for style in result.styles if hasattr(style, 'is_handwritten')
                        )
                    
                    # Process key-value pairs if requested
                    if options['include_keyvalue_pairs'] and hasattr(result, 'key_value_pairs') and result.key_value_pairs:
                        document_result["key_value_pairs"] = process_keyvalue_pairs(result, options['output_format'])
                    
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
                        }
                        
                        # Check if page has handwritten content (safely)
                        if hasattr(result, 'styles') and result.styles:
                            for style in result.styles:
                                if (hasattr(style, 'is_handwritten') and 
                                    style.is_handwritten and 
                                    hasattr(style, 'page_number') and
                                    style.page_number == page.page_number):
                                    page_info["has_handwritten_content"] = True
                                    break
                        
                        # Process text paragraphs
                        if hasattr(page, 'paragraphs') and page.paragraphs:
                            # Use paragraphs from the layout analysis
                            page_info["text"] = []
                            for para in page.paragraphs:
                                if para.content.strip():  # Skip empty paragraphs
                                    page_info["text"].append({
                                        "type": "paragraph",
                                        "content": para.content,
                                        "role": para.role if hasattr(para, 'role') else None
                                    })
                        elif hasattr(page, 'lines') and page.lines:
                            # Fall back to lines if paragraphs aren't available
                            page_info["text"] = []
                            for line in page.lines:
                                if line.content.strip():  # Skip empty lines
                                    page_info["text"].append({
                                        "type": "line",
                                        "content": line.content
                                    })
                        
                        # Process selection marks (checkboxes)
                        if hasattr(page, 'selection_marks') and page.selection_marks:
                            page_info["selection_marks"] = []
                            for mark in page.selection_marks:
                                page_info["selection_marks"].append({
                                    "state": mark.state,
                                    "confidence": mark.confidence
                                })
                        
                        # Process barcodes if requested
                        if options['include_barcode'] and hasattr(page, 'barcodes') and page.barcodes:
                            page_info["barcodes"] = []
                            for barcode in page.barcodes:
                                page_info["barcodes"].append({
                                    "value": barcode.value,
                                    "type": barcode.type,
                                    "confidence": barcode.confidence
                                })
                        
                        # Process tables for this page
                        if hasattr(result, 'tables') and result.tables:
                            page_tables = []
                            for table in result.tables:
                                # Check if this table belongs to the current page
                                if (hasattr(table, 'bounding_regions') and 
                                    any(region.page_number == page.page_number for region in table.bounding_regions)):
                                    
                                    # Create a table structure
                                    try:
                                        table_obj = {
                                            "row_count": table.row_count,
                                            "column_count": table.column_count,
                                            "cells": []
                                        }
                                        
                                        # Extract table content
                                        for cell in table.cells:
                                            if not hasattr(cell, 'content'):
                                                continue
                                                
                                            table_obj["cells"].append({
                                                "row_index": cell.row_index,
                                                "column_index": cell.column_index,
                                                "row_span": cell.row_span,
                                                "column_span": cell.column_span,
                                                "content": cell.content,
                                                "kind": cell.kind if hasattr(cell, 'kind') else None
                                            })
                                        
                                        # Format table according to requested output format
                                        if options['output_format'] == 'markdown':
                                            table_obj["formatted"] = format_table_markdown(table)
                                        else:
                                            table_obj["formatted"] = format_table_text(table)
                                        
                                        # Always include a markdown version of the table as table_summary
                                        table_obj["table_summary"] = format_table_markdown(table)
                                        
                                        page_tables.append(table_obj)
                                    except Exception as e:
                                        logger.error(f"Error processing table: {str(e)}")
                            
                            if page_tables:
                                page_info["tables"] = page_tables
                        
                        # Create page_text_all with all paragraphs from this page
                        page_text_all = ""
                        
                        # Add text content
                        if "text" in page_info:
                            for text_item in page_info["text"]:
                                if text_item.get("content", "").strip():
                                    page_text_all += text_item["content"] + "\n\n"
                        
                        # Add tables if present
                        if "tables" in page_info and page_info["tables"]:
                            for table in page_info["tables"]:
                                if "formatted" in table:
                                    page_text_all += table["formatted"] + "\n\n"
                        
                        # Add the consolidated page text
                        page_info["page_text_all"] = page_text_all.strip()
                        
                        # If language detection was requested, include that
                        if options['include_language'] and hasattr(page, 'languages') and page.languages:
                            page_info["detected_languages"] = [
                                {
                                    "language": lang.locale,
                                    "confidence": lang.confidence
                                } 
                                for lang in page.languages
                            ]
                        
                        # Add to results
                        document_result["pages"].append(page_info)
                    
                    # Clean up the temporary file
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                        temp_file_path = None
                    
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
                    
                    # Clean up the temporary file
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                        temp_file_path = None
                        
                    continue
                    
                except Exception as e:
                    logger.error(f"Error analyzing document: {str(e)}")
                    results.append({
                        "file_id": file_id,
                        "file_name": file_name,
                        "error": f"Document analysis error: {str(e)}"
                    })
                    
                    # Clean up the temporary file
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                        temp_file_path = None
                        
                    continue
                
            except Exception as e:
                logger.error(f"Error downloading or processing file: {str(e)}")
                results.append({
                    "file_id": file_id,
                    "file_name": file_name if file_name else "Unknown",
                    "error": f"Error downloading or processing file: {str(e)}"
                })
                
                # Clean up the temporary file if it exists
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    temp_file_path = None
                    
                continue
                
        except Exception as e:
            logger.error(f"Error processing file ID {file_id}: {str(e)}")
            results.append({
                "file_id": file_id,
                "error": f"Processing error: {str(e)}"
            })
            
            # Clean up the temporary file if it exists
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
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

def register_document_intelligence_layout_routes(app):
    """Register document intelligence routes with the Flask app"""
    app.route('/docint/layout', methods=['POST'])(api_logger(check_balance(document_layout_route)))
