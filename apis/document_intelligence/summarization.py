from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.utils.config import get_azure_blob_client, ensure_container_exists
import logging
import uuid
import pytz
from datetime import datetime
import os
import io
import json
import requests
import base64
import time
import re

# For document processing
import fitz  # PyMuPDF for PDF processing
from pptx import Presentation
import docx
import pandas as pd
import tempfile

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

# Define container for file uploads
FILE_UPLOAD_CONTAINER = os.environ.get("AZURE_STORAGE_UPLOAD_CONTAINER", "file-uploads")
STORAGE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT")
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{FILE_UPLOAD_CONTAINER}"

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def extract_text_from_pdf(file_path):
    """Extract text from PDF files using PyMuPDF (faster and better for large files)"""
    try:
        logger.info(f"Opening PDF file: {file_path}")
        doc = fitz.open(file_path)
        total_pages = len(doc)
        logger.info(f"PDF has {total_pages} pages")
        
        if total_pages == 0:
            raise ValueError("PDF file has no pages")
            
        text_content = []
        
        # Process each page without truncation
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            page_text = page.get_text()
            text_content.append(page_text)
            
            # Log first few characters of first and last page for debugging
            if page_num == 0 or page_num == total_pages - 1:
                preview = page_text[:100].replace('\n', ' ').strip()
                logger.info(f"Page {page_num+1} preview: {preview}...")
        
        full_text = "\n".join(text_content)
        logger.info(f"Extracted {len(full_text)} characters of text from PDF")
        
        return full_text, total_pages
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise

def extract_text_from_docx(file_path):
    """Extract text from DOCX files"""
    try:
        logger.info(f"Opening DOCX file: {file_path}")
        doc = docx.Document(file_path)
        paragraphs = []
        
        # Extract paragraphs
        logger.info(f"DOCX has {len(doc.paragraphs)} paragraphs")
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)
                
        # Extract text from tables
        logger.info(f"DOCX has {len(doc.tables)} tables")
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(cell.text)
        
        # Number of paragraphs as a proxy for "pages"
        # This is not perfect but gives an estimate
        total_pages = max(1, len(paragraphs) // 4)  # Rough estimate: ~4 paragraphs per page
        
        full_text = "\n".join(paragraphs)
        logger.info(f"Extracted {len(full_text)} characters from DOCX")
        
        # Log a preview of the text for debugging
        if paragraphs:
            preview = paragraphs[0][:100].replace('\n', ' ').strip()
            logger.info(f"Text preview: {preview}...")
            
        return full_text, total_pages
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {str(e)}")
        raise

def extract_text_from_pptx(file_path):
    """Extract text from PPTX files"""
    try:
        logger.info(f"Opening PPTX file: {file_path}")
        presentation = Presentation(file_path)
        total_slides = len(presentation.slides)
        logger.info(f"PPTX has {total_slides} slides")
        
        text_content = []
        
        # Process each slide
        for slide_idx, slide in enumerate(presentation.slides):
            slide_text = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_text.append(shape.text)
            
            slide_content = "\n".join(slide_text)
            text_content.append(f"--- Slide {slide_idx + 1} ---\n{slide_content}")
            
            # Log preview of first and last slide for debugging
            if slide_idx == 0 or slide_idx == total_slides - 1:
                preview = slide_content[:100].replace('\n', ' ').strip()
                logger.info(f"Slide {slide_idx+1} preview: {preview}...")
        
        full_text = "\n\n".join(text_content)
        logger.info(f"Extracted {len(full_text)} characters from PPTX")
        
        return full_text, total_slides
    except Exception as e:
        logger.error(f"Error extracting text from PPTX: {str(e)}")
        raise

def extract_text_from_xlsx(file_path):
    """Extract text from Excel files"""
    try:
        logger.info(f"Opening Excel file: {file_path}")
        
        # Read all sheets
        all_sheets = pd.read_excel(file_path, sheet_name=None)
        total_sheets = len(all_sheets)
        logger.info(f"Excel file has {total_sheets} sheets")
        
        text_content = []
        
        # Process each sheet
        for sheet_name, df in all_sheets.items():
            logger.info(f"Processing sheet '{sheet_name}' with {len(df)} rows and {len(df.columns)} columns")
            
            # Add a clear sheet header
            text_content.append(f"=== Sheet: {sheet_name} ===")
            
            # Convert dataframe to string representation
            sheet_text = df.to_string(index=False)
            text_content.append(sheet_text)
            text_content.append("\n")
            
            # Log preview for debugging
            if not df.empty:
                preview = str(df.head(1)).replace('\n', ' ')[:100]
                logger.info(f"Sheet '{sheet_name}' preview: {preview}...")
        
        full_text = "\n".join(text_content)
        logger.info(f"Extracted {len(full_text)} characters from Excel file")
        
        return full_text, total_sheets
    except Exception as e:
        logger.error(f"Error extracting text from Excel: {str(e)}")
        raise

def chunk_text(text, max_chunk_size=12000, overlap=500):  # Increased overlap for better context
    """
    Split text into chunks of maximum size with overlap
    Args:
        text: The text to split
        max_chunk_size: Maximum size of each chunk
        overlap: Overlap between chunks
    Returns:
        List of text chunks
    """
    logger.info(f"Chunking text of length {len(text)} with max_chunk_size={max_chunk_size}, overlap={overlap}")
    
    if len(text) <= max_chunk_size:
        logger.info("Text fits in a single chunk")
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + max_chunk_size
        if end < len(text):
            # Find a good breaking point for natural text flow
            # Look for a paragraph break first
            paragraph_break = text.rfind('\n\n', start + max_chunk_size - overlap, end)
            if paragraph_break != -1:
                end = paragraph_break + 2
                logger.info(f"Found paragraph break at position {paragraph_break}")
            else:
                # Look for a sentence break
                sentence_break = text.rfind('. ', start + max_chunk_size - overlap, end)
                if sentence_break != -1:
                    end = sentence_break + 2
                    logger.info(f"Found sentence break at position {sentence_break}")
                else:
                    # If all else fails, look for any space
                    space = text.rfind(' ', start + max_chunk_size - overlap, end)
                    if space != -1:
                        end = space + 1
                        logger.info(f"Found space break at position {space}")
                    else:
                        logger.info(f"No natural break found, using hard cutoff at position {end}")
        
        # Ensure we're not creating tiny chunks at the end
        if end >= len(text) - (overlap / 2) and end < len(text):
            end = len(text)
            logger.info(f"Extending final chunk to include remaining {len(text) - end} characters")
        
        chunk = text[start:end]
        chunks.append(chunk)
        logger.info(f"Created chunk {len(chunks)} with length {len(chunk)}")
        
        # Check for potential data loss
        if end < len(text) and len(chunk) < (max_chunk_size * 0.75):
            logger.warning(f"Chunk {len(chunks)} is significantly smaller than max size, possible content splitting issue")
        
        start = end - overlap
    
    # Verify that all text has been chunked properly
    total_unique_chars = len(text)
    chunked_chars = sum(len(c) for c in chunks) - (overlap * (len(chunks) - 1))
    if chunked_chars < total_unique_chars:
        logger.warning(f"Potential data loss: Original text has {total_unique_chars} chars, chunks cover {chunked_chars} chars")
    
    logger.info(f"Text split into {len(chunks)} chunks")
    return chunks

def format_docx_summary(summary_data):
    """Format summary data for docx - ensures no data is truncated"""
    formatted = {
        "summary": summary_data.get("summary", ""),
        "key_points": summary_data.get("key_points", []),
        "document_structure": summary_data.get("document_structure", {}),
        "pages_processed": summary_data.get("pages_processed", 0),
        "tokens": summary_data.get("tokens", {})
    }
    
    # Check for any missing data
    if not formatted["summary"] and "content" in summary_data:
        logger.warning("Missing summary field, using content field instead")
        formatted["summary"] = summary_data["content"]
        
    return formatted

def format_pdf_summary(summary_data):
    """Format summary data for PDF - ensures no data is truncated"""
    formatted = {
        "summary": summary_data.get("summary", ""),
        "key_points": summary_data.get("key_points", []),
        "document_structure": summary_data.get("document_structure", {}),
        "pages_processed": summary_data.get("pages_processed", 0),
        "tokens": summary_data.get("tokens", {})
    }
    
    # Check for any missing data
    if not formatted["summary"] and "content" in summary_data:
        logger.warning("Missing summary field, using content field instead")
        formatted["summary"] = summary_data["content"]
        
    return formatted

def format_pptx_summary(summary_data):
    """Format summary data for PowerPoint - ensures no data is truncated"""
    formatted = {
        "summary": summary_data.get("summary", ""),
        "key_points": summary_data.get("key_points", []),
        "slides_processed": summary_data.get("pages_processed", 0),
        "presentation_structure": summary_data.get("document_structure", {}),
        "tokens": summary_data.get("tokens", {})
    }
    
    # Check for any missing data
    if not formatted["summary"] and "content" in summary_data:
        logger.warning("Missing summary field, using content field instead")
        formatted["summary"] = summary_data["content"]
        
    return formatted

def format_xlsx_summary(summary_data):
    """Format summary data for Excel - ensures no data is truncated"""
    formatted = {
        "summary": summary_data.get("summary", ""),
        "key_points": summary_data.get("key_points", []),
        "sheets_processed": summary_data.get("pages_processed", 0),
        "data_insights": summary_data.get("document_structure", {}),
        "tokens": summary_data.get("tokens", {})
    }
    
    # Check for any missing data
    if not formatted["summary"] and "content" in summary_data:
        logger.warning("Missing summary field, using content field instead")
        formatted["summary"] = summary_data["content"]
        
    return formatted

def chunk_and_summarize(text, total_pages, llm_endpoint, summary_options):
    """
    Process text in chunks and combine summaries
    Args:
        text: Full text content
        total_pages: Number of pages in document
        llm_endpoint: Endpoint for LLM API
        summary_options: Configuration for summarization
    Returns:
        Combined summary and token usage
    """
    chunks = chunk_text(text, max_chunk_size=summary_options.get('chunk_size', 12000))
    logger.info(f"Document split into {len(chunks)} chunks for processing")
    
    all_summaries = []
    token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    for idx, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {idx+1}/{len(chunks)} (length: {len(chunk)})")
        
        # Adjust the system prompt for intermediary chunks vs. final summary
        if len(chunks) > 1:
            if idx < len(chunks) - 1:
                system_prompt = f"""You are a document summarization expert tasked with creating an intermediate summary of a portion of a document. 
                This is chunk {idx+1} of {len(chunks)}. Focus on extracting the main points and key information only.
                Be concise but thorough. The final summary will be created by combining these intermediary summaries.
                IMPORTANT: Do NOT truncate or omit ANY information from the document. Your summary must be comprehensive and include ALL key points."""
            else:
                system_prompt = f"""You are a document summarization expert tasked with combining all previous summaries into a final coherent summary.
                This is the final chunk {idx+1} of {len(chunks)}. Create a well-structured final summary that captures the key points from all chunks.
                The length should be {summary_options.get('length', 'medium')} and the style should be {summary_options.get('style', 'concise')}.
                IMPORTANT: Do NOT truncate or omit ANY information from the document. Your summary must be comprehensive and include ALL key points."""
        else:
            # For documents that fit in a single chunk
            system_prompt = f"""You are a document summarization expert tasked with creating a comprehensive summary of a document.
            The summary should be {summary_options.get('length', 'medium')} in length and {summary_options.get('style', 'concise')} in style.
            IMPORTANT: Do NOT truncate or omit ANY information from the document. Your summary must be comprehensive and include ALL key points and important details.
            The document has {total_pages} pages total."""
        
        # Prepare specific instructions based on document type and options
        specific_instructions = ""
        if summary_options.get('document_type') == 'pdf':
            specific_instructions = """For this PDF document, identify the main sections, key arguments, and supporting evidence."""
        elif summary_options.get('document_type') == 'pptx':
            specific_instructions = """For this presentation, focus on the main message of each slide and the overall narrative flow."""
        elif summary_options.get('document_type') == 'docx':
            specific_instructions = """For this text document, identify the thesis, main arguments, and supporting details."""
        elif summary_options.get('document_type') == 'xlsx':
            specific_instructions = """For this spreadsheet data, identify patterns, key metrics, and insights from the numeric data."""
        
        # Add structure instructions if requested
        structure_instructions = ""
        if summary_options.get('include_structure', False):
            structure_instructions = """In addition to the summary, provide an outline of the document's structure, identifying main sections and subsections."""
        
        # Create full prompt with all instructions
        full_system_prompt = f"""{system_prompt}
        {specific_instructions}
        {structure_instructions}
        
        Respond in JSON format with the following structure:
        {{
            "summary": "Comprehensive summary of the text",
            "key_points": ["Key point 1", "Key point 2", ...],
            "document_structure": {{"section_name": "description", ...}}
        }}
        """
        
        # Prepare the API request to the LLM endpoint
        headers = {
            "X-Token": summary_options.get('token'),
            "Content-Type": "application/json"
        }
        
        # Create the combined prompt with system instructions and user content
        system_prompt = full_system_prompt.strip()
        user_content = f"Here's the document content to summarize:\n\n{chunk}"
        
        data = {
            "system_message": system_prompt,
            "user_input": user_content,
            "temperature": summary_options.get('temperature', 0.3),
            "response_format": {"type": "json_object"}
        }
        
        # Log request details for debugging
        logger.info(f"Sending request to LLM endpoint: {llm_endpoint}")
        
        # Make the request to the LLM endpoint with better error handling
        try:
            response = requests.post(llm_endpoint, headers=headers, json=data, timeout=120)  # Increased timeout for larger content
            
            if response.status_code != 200:
                logger.error(f"Error from LLM API: Status {response.status_code}")
                raise Exception(f"LLM API error: {response.status_code}")
            
            # Log response received
            logger.info(f"Received response from LLM API for chunk {idx+1}")
            
            result = response.json()
            logger.info(f"Successfully parsed JSON response")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            # Create a fallback summary if API request fails
            all_summaries.append({
                "summary": f"Error: Unable to process document chunk {idx+1} due to API connection issue: {str(e)}",
                "key_points": ["Error occurred during processing"],
                "document_structure": {}
            })
            continue
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: Error: {str(e)}")
            # Create a fallback with the raw response if JSON parsing fails
            all_summaries.append({
                "summary": f"Error: Unable to process document chunk {idx+1}. Raw response not parseable as JSON.",
                "key_points": ["Error occurred during processing"],
                "document_structure": {}
            })
            continue
        
        # Extract token usage information
        if "usage" in result:
            token_usage["prompt_tokens"] += result["usage"].get("prompt_tokens", 0)
            token_usage["completion_tokens"] += result["usage"].get("completion_tokens", 0)
            token_usage["total_tokens"] += result["usage"].get("total_tokens", 0)
            logger.info(f"Token usage: {result['usage'].get('total_tokens', 0)} tokens for chunk {idx+1}")
        else:
            logger.warning(f"No token usage information in LLM response for chunk {idx+1}")
        
        # Parse the response with improved error handling
        try:
            # Handle different response formats that might be returned by the LLM
            if "choices" in result and result["choices"]:
                choice = result["choices"][0]
                
                if "message" in choice and "content" in choice["message"]:
                    content = choice["message"]["content"]
                    logger.info(f"Found content in standard format, length: {len(content)}")
                elif "text" in choice:
                    # Alternative format some LLMs might use
                    content = choice["text"]
                    logger.info(f"Found content in alternate format, length: {len(content)}")
                else:
                    # Last resort, try to use the whole choice
                    content = json.dumps(choice)
                    logger.warning(f"Could not find standard content field, using whole choice")
            else:
                # If no choices field, try to use the whole result
                content = json.dumps(result)
                logger.warning(f"No choices in response, using whole result")
            
            # Try to parse as JSON if it looks like it
            if content and (content.strip().startswith('{') and content.strip().endswith('}')):
                try:
                    summary_result = json.loads(content)
                    logger.info(f"Successfully parsed content as JSON")
                except json.JSONDecodeError as e:
                    logger.error(f"Content looks like JSON but failed to parse: Error: {str(e)}")
                    summary_result = {
                        "summary": content,  # Use full content without truncation
                        "key_points": [],
                        "document_structure": {}
                    }
            else:
                # If not JSON, use as raw text
                logger.warning(f"Content is not in JSON format")
                summary_result = {
                    "summary": content,  # Use full content without truncation
                    "key_points": [],
                    "document_structure": {}
                }
            
            # Ensure the summary has all required fields
            if not isinstance(summary_result, dict):
                logger.warning(f"Summary result is not a dictionary: {type(summary_result)}")
                summary_result = {
                    "summary": str(summary_result),  # Convert to string but don't truncate
                    "key_points": [],
                    "document_structure": {}
                }
            
            if "summary" not in summary_result or not summary_result["summary"]:
                logger.warning("Missing or empty summary field in result")
                # Extract a summary from the content if possible
                if isinstance(content, str) and len(content) > 0:
                    summary_result["summary"] = content  # Use full content without truncation
                else:
                    summary_result["summary"] = f"Summary could not be generated for chunk {idx+1}."
            
            if "key_points" not in summary_result:
                summary_result["key_points"] = []
            
            if "document_structure" not in summary_result:
                summary_result["document_structure"] = {}
            
            all_summaries.append(summary_result)
            logger.info(f"Successfully processed chunk {idx+1}, summary length: {len(summary_result['summary'])}")
            
        except Exception as e:
            logger.error(f"Error processing LLM response: {str(e)}")
            all_summaries.append({
                "summary": f"Error processing document chunk {idx+1}: {str(e)}",
                "key_points": ["Error occurred during processing"],
                "document_structure": {}
            })
    
    # If no summaries were generated at all, create a fallback
    if not all_summaries:
        logger.error("No summaries were generated for any chunks")
        return {
            "summary": "Failed to generate summary. The document could not be processed successfully.",
            "key_points": ["Document processing failed"],
            "document_structure": {},
            "pages_processed": total_pages,
            "tokens": token_usage
        }
    
    # For multiple chunks, we need to combine them
    if len(all_summaries) > 1:
        # Extract all summaries and key points
        combined_text = "\n\n".join([s.get("summary", "") for s in all_summaries])
        all_key_points = []
        for summary in all_summaries:
            all_key_points.extend(summary.get("key_points", []))
        
        # Combine document structures
        combined_structure = {}
        for summary in all_summaries:
            combined_structure.update(summary.get("document_structure", {}))
        
        # Create final combined summary
        if len(combined_text) > 12000:
            # If combined text is still too long, summarize it again
            headers = {
                "X-Token": summary_options.get('token'),
                "Content-Type": "application/json"
            }
            
            # Create full prompt with all instructions
            final_system_prompt = f"""You are a document summarization expert tasked with creating a final cohesive summary from multiple partial summaries.
            Create a well-structured final summary that integrates all the information.
            The length should be {summary_options.get('length', 'medium')} and the style should be {summary_options.get('style', 'concise')}.
            IMPORTANT: Do NOT truncate or omit ANY information from the document. Your summary must be comprehensive and include ALL key points.
            
            Respond in JSON format with the following structure:
            {{
                "summary": "Final comprehensive summary",
                "key_points": ["Key point 1", "Key point 2", ...],
                "document_structure": {{"section_name": "description", ...}}
            }}
            """
            
            combined_content = f"Here are all the partial summaries to combine:\n\n{combined_text}\n\nAnd all key points:\n\n{json.dumps(all_key_points)}"
            
            data = {
                "system_message": final_system_prompt,
                "user_input": combined_content,
                "temperature": summary_options.get('temperature', 0.3),
                "response_format": {"type": "json_object"}
            }
            
            try:
                response = requests.post(llm_endpoint, headers=headers, json=data, timeout=120)  # Increased timeout for larger content
                
                if response.status_code != 200:
                    logger.error(f"Error from LLM API during final summary: Status {response.status_code}")
                    # Use the last summary as fallback but preserve ALL key points
                    final_summary = all_summaries[-1]
                    final_summary["key_points"] = all_key_points  # No limit on key points
                    final_summary["document_structure"] = combined_structure
                else:
                    result = response.json()
                    
                    # Add token usage
                    if "usage" in result:
                        token_usage["prompt_tokens"] += result["usage"].get("prompt_tokens", 0)
                        token_usage["completion_tokens"] += result["usage"].get("completion_tokens", 0)
                        token_usage["total_tokens"] += result["usage"].get("total_tokens", 0)
                    
                    try:
                        if "choices" in result and result["choices"] and "message" in result["choices"][0]:
                            content = result["choices"][0]["message"].get("content", "{}")
                            final_summary = json.loads(content)
                            
                            # If the final summary doesn't include all key points, add them
                            existing_key_points = final_summary.get("key_points", [])
                            if len(existing_key_points) < len(all_key_points):
                                logger.warning(f"Final summary contains fewer key points ({len(existing_key_points)}) than collected ({len(all_key_points)}). Adding all key points.")
                                final_summary["key_points"] = all_key_points
                                
                        else:
                            logger.warning("Unexpected format in final summary response")
                            final_summary = {
                                "summary": combined_text,  # Use full combined text instead of truncated
                                "key_points": all_key_points,  # No limit on key points
                                "document_structure": combined_structure
                            }
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON in final summary")
                        final_summary = {
                            "summary": content,  # Use full content
                            "key_points": all_key_points,  # No limit on key points
                            "document_structure": combined_structure
                        }
            except Exception as e:
                logger.error(f"Error during final summary generation: {str(e)}")
                # Use the last summary as fallback
                final_summary = all_summaries[-1]
                final_summary["key_points"] = all_key_points  # No limit on key points
                final_summary["document_structure"] = combined_structure
        else:
            # If combined text is manageable, use the last summary as the final one
            # but enrich it with all key points and structure
            final_summary = all_summaries[-1]
            final_summary["key_points"] = all_key_points  # No limit on key points
            final_summary["document_structure"] = combined_structure
    else:
        # For single chunk documents, just use the one summary
        final_summary = all_summaries[0]
    
    # Add page count and token usage to the final summary
    final_summary["pages_processed"] = total_pages
    final_summary["tokens"] = token_usage
    
    # Final validation to ensure we're returning usable data
    if not final_summary.get("summary"):
        logger.warning("Empty summary in final result, adding fallback text")
        final_summary["summary"] = "The document was processed, but no meaningful summary could be generated. Please check the document content or try again."
    
    logger.info(f"Final summary generated successfully, length: {len(final_summary.get('summary', ''))}")
    return final_summary

def upload_summary_to_blob(summary_content, file_name, user_id, token):
    """
    Upload summary to blob storage and return file ID
    Args:
        summary_content: The summary content to upload
        file_name: Original file name to use as a base
        user_id: User ID for the request
        token: Authentication token
    Returns:
        File ID from the upload endpoint
    """
    # Create a text file with the summary
    summary_file_name = f"summary_{os.path.splitext(file_name)[0]}.txt"
    
    # Convert summary to formatted text
    if isinstance(summary_content, dict):
        text_content = f"# Document Summary\n\n"
        text_content += f"## Executive Summary\n\n{summary_content.get('summary', '')}\n\n"
        
        text_content += "## Key Points\n\n"
        for idx, point in enumerate(summary_content.get('key_points', [])):
            text_content += f"{idx+1}. {point}\n"
        text_content += "\n"
        
        if summary_content.get('document_structure'):
            text_content += "## Document Structure\n\n"
            for section, description in summary_content.get('document_structure', {}).items():
                text_content += f"### {section}\n{description}\n\n"
        
        text_content += f"## Metadata\n\n"
        text_content += f"- Pages/Slides Processed: {summary_content.get('pages_processed', 0)}\n"
        text_content += f"- Tokens Used: {summary_content.get('tokens', {}).get('total_tokens', 0)}\n"
        text_content += f"  - Prompt Tokens: {summary_content.get('tokens', {}).get('prompt_tokens', 0)}\n"
        text_content += f"  - Completion Tokens: {summary_content.get('tokens', {}).get('completion_tokens', 0)}\n"
    else:
        # If it's not a dict, just use the content directly
        text_content = summary_content
    
    logger.info(f"Preparing to upload summary file: {summary_file_name}, size: {len(text_content)} characters")
    
    # For very large summaries, we may need to split them into multiple files
    max_upload_size = 10 * 1024 * 1024  # 10MB limit for upload
    
    if len(text_content) > max_upload_size:
        logger.warning(f"Summary text exceeds maximum upload size ({len(text_content)} > {max_upload_size})")
        # Split into multiple files if needed
        parts = []
        current_part = 1
        for i in range(0, len(text_content), max_upload_size):
            part_name = f"{summary_file_name}.part{current_part}"
            part_content = text_content[i:i+max_upload_size]
            parts.append((part_name, part_content))
            current_part += 1
            
        logger.info(f"Split summary into {len(parts)} parts for upload")
        
        # Upload each part
        uploaded_ids = []
        for part_name, part_content in parts:
            file_data = io.BytesIO(part_content.encode('utf-8'))
            file_data.name = part_name
            
            # Create multipart form data
            files = {'files': (part_name, file_data, 'text/plain')}
            
            # Prepare headers
            headers = {"X-Token": token}
            
            # Make POST request to upload-file endpoint
            upload_response = requests.post(
                f"{request.url_root.rstrip('/')}/upload-file",
                headers=headers,
                files=files
            )
            
            if upload_response.status_code != 200:
                logger.error(f"Failed to upload summary file part {part_name}: {upload_response.text}")
                raise Exception(f"Failed to upload summary file part {part_name}: {upload_response.text}")
            
            upload_result = upload_response.json()
            if "uploaded_files" in upload_result and len(upload_result["uploaded_files"]) > 0:
                uploaded_ids.append(upload_result["uploaded_files"][0]["file_id"])
            else:
                logger.error(f"No file ID in upload response for part {part_name}: {upload_result}")
                raise Exception(f"No file ID returned from upload endpoint for part {part_name}")
        
        # Create a manifest file that lists all the parts
        manifest = f"# Summary Split into Multiple Files\n\nThis summary was split into {len(parts)} files due to size limitations.\n\n"
        for i, file_id in enumerate(uploaded_ids):
            manifest += f"Part {i+1}: {file_id}\n"
        
        # Upload the manifest
        manifest_name = f"{summary_file_name}.manifest"
        manifest_data = io.BytesIO(manifest.encode('utf-8'))
        manifest_data.name = manifest_name
        
        files = {'files': (manifest_name, manifest_data, 'text/plain')}
        headers = {"X-Token": token}
        
        upload_response = requests.post(
            f"{request.url_root.rstrip('/')}/upload-file",
            headers=headers,
            files=files
        )
        
        if upload_response.status_code != 200:
            logger.error(f"Failed to upload manifest file: {upload_response.text}")
            # Return the first part ID if manifest upload fails
            return uploaded_ids[0] if uploaded_ids else None
        
        upload_result = upload_response.json()
        if "uploaded_files" in upload_result and len(upload_result["uploaded_files"]) > 0:
            return upload_result["uploaded_files"][0]["file_id"]
        else:
            # Return the first part ID if manifest result parsing fails
            return uploaded_ids[0] if uploaded_ids else None
    else:
        # Normal upload for reasonable sized files
        # Prepare file data
        file_data = io.BytesIO(text_content.encode('utf-8'))
        file_data.name = summary_file_name
        
        # Create multipart form data
        files = {'files': (summary_file_name, file_data, 'text/plain')}
        
        # Prepare headers
        headers = {"X-Token": token}
        
        # Make POST request to upload-file endpoint
        upload_response = requests.post(
            f"{request.url_root.rstrip('/')}/upload-file",
            headers=headers,
            files=files
        )
        
        if upload_response.status_code != 200:
            logger.error(f"Failed to upload summary file: {upload_response.text}")
            raise Exception(f"Failed to upload summary file: {upload_response.text}")
        
        upload_result = upload_response.json()
        if "uploaded_files" in upload_result and len(upload_result["uploaded_files"]) > 0:
            return upload_result["uploaded_files"][0]["file_id"]
        else:
            logger.error(f"No file ID in upload response: {upload_result}")
            raise Exception("No file ID returned from upload endpoint")

def document_summarization_route():
    """
    Summarize documents using AI (PDF, DOCX, PPTX, XLSX)
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
            - file_id
          properties:
            file_id:
              type: string
              description: ID of the uploaded file to summarize
            length:
              type: string
              enum: [short, medium, long, very_long]
              default: medium
              description: Desired summary length
            style:
              type: string
              enum: [concise, detailed, creative, technical, narrative, bullet_points]
              default: concise
              description: Style of the summary
            include_structure:
              type: boolean
              default: true
              description: Whether to include document structure in the summary
            temperature:
              type: number
              format: float
              minimum: 0
              maximum: 1.0
              default: 0.3
              description: Creativity level (0.0 = deterministic, 1.0 = creative)
            include_file_upload:
              type: boolean
              default: true
              description: Whether to create and upload a text file with the summary
    consumes:
      - application/json
    produces:
      - application/json
    responses:
      200:
        description: Document successfully summarized
        schema:
          type: object
          properties:
            message:
              type: string
              example: Document successfully summarized
            original_file_id:
              type: string
              description: ID of the original document
            summary_file_id:
              type: string
              description: ID of the uploaded summary file (if requested)
            summary:
              type: string
              description: Text summary of the document
            key_points:
              type: array
              items:
                type: string
              description: List of key points from the document
            document_structure:
              type: object
              description: Outline of document structure (if requested)
            pages_processed:
              type: integer
              description: Number of pages/slides/sheets processed
            token_usage:
              type: object
              properties:
                prompt_tokens:
                  type: integer
                completion_tokens:
                  type: integer
                total_tokens:
                  type: integer
              description: Token usage statistics
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
              example: File with specified ID not found
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
              example: File type not supported for summarization
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
    
    # Validate file_id
    file_id = data.get('file_id')
    if not file_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "file_id is required"
        }, 400)
    
    # Extract other parameters with defaults
    summary_options = {
        'length': data.get('length', 'medium'),
        'style': data.get('style', 'concise'),
        'include_structure': data.get('include_structure', True),
        'temperature': data.get('temperature', 0.3),
        'include_file_upload': data.get('include_file_upload', True),
        'token': token,  # Pass token for LLM API calls
        'chunk_size': 12000  # Default chunk size for text processing
    }
    
    # Validate length parameter
    valid_lengths = ['short', 'medium', 'long', 'very_long']
    if summary_options['length'] not in valid_lengths:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Invalid length parameter. Must be one of: {', '.join(valid_lengths)}"
        }, 400)
    
    # Validate style parameter
    valid_styles = ['concise', 'detailed', 'creative', 'technical', 'narrative', 'bullet_points']
    if summary_options['style'] not in valid_styles:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Invalid style parameter. Must be one of: {', '.join(valid_styles)}"
        }, 400)
    
    # Validate temperature parameter
    if not 0 <= summary_options['temperature'] <= 1:
        return create_api_response({
            "error": "Bad Request",
            "message": "Temperature must be between 0.0 and 1.0"
        }, 400)
    
    try:
        # Get file URL from the file ID
        headers = {"X-Token": token}
        logger.info(f"Getting file URL for file ID: {file_id}")
        file_url_response = requests.post(
            f"{request.url_root.rstrip('/')}/get-file-url",
            headers=headers,
            json={"file_id": file_id}
        )
        
        if file_url_response.status_code != 200:
            logger.error(f"Error retrieving file URL: Status {file_url_response.status_code}, Response: {file_url_response.text[:500]}")
            return create_api_response({
                "error": "Not Found",
                "message": f"File with ID {file_id} not found or you don't have access"
            }, 404)
        
        file_info = file_url_response.json()
        file_url = file_info.get("file_url")
        file_name = file_info.get("file_name")
        
        logger.info(f"Retrieved file URL: {file_url} for file: {file_name}")
        
        if not file_url:
            logger.error("Missing file_url in response from get-file-url endpoint")
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to retrieve file URL"
            }, 500)
        
        # Download the file from the URL with better error handling
        try:
            logger.info(f"Downloading file from URL: {file_url}")
            
            # Try first with standard request
            file_response = requests.get(file_url, timeout=60)  # Increased timeout for larger files
            
            # If it's an Azure blob URL, we might need to add authorization
            if file_response.status_code != 200 and "blob.core.windows.net" in file_url:
                logger.info("Attempting download with authorization header")
                file_response = requests.get(
                    file_url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=60
                )
            
            if file_response.status_code != 200:
                logger.error(f"Failed to download file: Status {file_response.status_code}")
                return create_api_response({
                    "error": "Server Error",
                    "message": f"Failed to download file from {file_url} (Status {file_response.status_code})"
                }, 500)
            
            content_length = len(file_response.content)
            logger.info(f"File downloaded successfully: {content_length} bytes")
            
            if content_length == 0:
                logger.error("Downloaded file is empty")
                return create_api_response({
                    "error": "Bad Request",
                    "message": "The downloaded file is empty"
                }, 400)
            
            # Save the file to a temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as temp_file:
                temp_file.write(file_response.content)
                temp_file_path = temp_file.name
                
            logger.info(f"Downloaded file saved to temporary location: {temp_file_path}")
            
            # Verify the file exists and has content
            if not os.path.exists(temp_file_path) or os.path.getsize(temp_file_path) == 0:
                logger.error(f"Temporary file is missing or empty: {temp_file_path}")
                return create_api_response({
                    "error": "Server Error",
                    "message": "Downloaded file is empty or not accessible"
                }, 500)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading file: {str(e)}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error downloading file: {str(e)}"
            }, 500)
        
        # Determine file type and extract text
        try:
            file_extension = os.path.splitext(file_name)[1].lower()
            
            logger.info(f"Processing file with extension: {file_extension}")
            
            if file_extension == '.pdf':
                logger.info(f"Extracting text from PDF file: {temp_file_path}")
                text_content, total_pages = extract_text_from_pdf(temp_file_path)
                summary_options['document_type'] = 'pdf'
            elif file_extension == '.docx':
                logger.info(f"Extracting text from DOCX file: {temp_file_path}")
                text_content, total_pages = extract_text_from_docx(temp_file_path)
                summary_options['document_type'] = 'docx'
            elif file_extension == '.pptx':
                logger.info(f"Extracting text from PPTX file: {temp_file_path}")
                text_content, total_pages = extract_text_from_pptx(temp_file_path)
                summary_options['document_type'] = 'pptx'
            elif file_extension in ['.xlsx', '.xls']:
                logger.info(f"Extracting text from Excel file: {temp_file_path}")
                text_content, total_pages = extract_text_from_xlsx(temp_file_path)
                summary_options['document_type'] = 'xlsx'
            else:
                # Clean up the temporary file
                os.unlink(temp_file_path)
                logger.error(f"Unsupported file extension: {file_extension}")
                return create_api_response({
                    "error": "Unsupported Media Type",
                    "message": f"File type {file_extension} is not supported for summarization"
                }, 415)
            
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
            # Validate extracted text
            if not text_content or not text_content.strip():
                logger.error("No text content extracted from the document")
                return create_api_response({
                    "error": "Bad Request",
                    "message": "The document contains no extractable text content"
                }, 400)
                
            # Log the total content length for debugging
            content_length = len(text_content)
            logger.info(f"Document processed successfully: {content_length} characters extracted from {total_pages} pages")
            
            # Log a preview of the content
            if content_length > 0:
                preview = text_content[:200].replace('\n', ' ').strip()
                logger.info(f"Content preview: {preview}...")
            
        except Exception as e:
            # Clean up the temporary file if it exists
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            
            logger.error(f"Error extracting text from file: {str(e)}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error extracting text from file: {str(e)}"
            }, 500)
            
        # Set endpoint for LLM summarization
        llm_endpoint = f"{request.url_root.rstrip('/')}/llm/gpt-4o-mini"
        
        # Process text and generate summary
        summary_result = chunk_and_summarize(text_content, total_pages, llm_endpoint, summary_options)
        
        # Format the summary based on document type
        if summary_options['document_type'] == 'pdf':
            formatted_summary = format_pdf_summary(summary_result)
        elif summary_options['document_type'] == 'docx':
            formatted_summary = format_docx_summary(summary_result)
        elif summary_options['document_type'] == 'pptx':
            formatted_summary = format_pptx_summary(summary_result)
        elif summary_options['document_type'] == 'xlsx':
            formatted_summary = format_xlsx_summary(summary_result)
        else:
            formatted_summary = summary_result
        
        # Upload summary file if requested
        summary_file_id = None
        if summary_options['include_file_upload']:
            try:
                summary_file_id = upload_summary_to_blob(formatted_summary, file_name, g.user_id, token)
            except Exception as e:
                logger.error(f"Error uploading summary file: {str(e)}")
                # Continue with the process even if file upload fails
        
        # Prepare response with formatted summary
        response_data = {
            "message": "Document successfully summarized",
            "original_file_id": file_id,
            "summary": formatted_summary.get("summary", ""),
            "key_points": formatted_summary.get("key_points", []),
            "pages_processed": formatted_summary.get("pages_processed", 0),
            "token_usage": formatted_summary.get("tokens", {})
        }
        
        # Add document structure if included
        if summary_options['include_structure']:
            if summary_options['document_type'] == 'pptx':
                response_data["presentation_structure"] = formatted_summary.get("document_structure", {})
            elif summary_options['document_type'] == 'xlsx':
                response_data["data_insights"] = formatted_summary.get("document_structure", {})
            else:
                response_data["document_structure"] = formatted_summary.get("document_structure", {})
        
        # Add summary file ID if available
        if summary_file_id:
            response_data["summary_file_id"] = summary_file_id
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error in document summarization: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing document: {str(e)}"
        }, 500)

def register_document_intelligence_routes(app):
    """Register document intelligence routes with the Flask app"""
    app.route('/docint/summarization', methods=['POST'])(api_logger(check_balance(document_summarization_route)))