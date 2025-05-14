import logging
from openai import AzureOpenAI
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from apis.utils.config import (
    get_openai_client, 
    DEEPSEEK_API_KEY, 
    DEEPSEEK_V3_API_KEY, 
    LLAMA_API_KEY,
    O3_MINI_API_KEY,
    get_document_intelligence_config
)
import os
import tempfile
import base64
from azure.ai.formrecognizer import DocumentAnalysisClient
from apis.utils.fileService import FileService
import requests
import re
from collections import defaultdict
import math

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = get_openai_client()

# Initialize Document Intelligence client
document_config = get_document_intelligence_config()
document_client = DocumentAnalysisClient(
    endpoint=document_config['endpoint'],
    credential=AzureKeyCredential(document_config['api_key'])
)

# Document types supported by Document Intelligence
DOCUMENT_INTELLIGENCE_FORMATS = {'pdf', 'doc', 'docx', 'xlsx', 'xls', 'pptx', 'ppt'}

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

# Native extraction functions for different document types
def extract_text_from_pdf(file_path):
    """Extract text from PDF files using PyMuPDF (faster and better for large files)"""
    try:
        import fitz  # PyMuPDF
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
        import docx
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
        
        full_text = "\n\n".join(paragraphs)
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
        from pptx import Presentation
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
        import pandas as pd
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

def extract_document_text_with_native_libraries(file_path, filename):
    """
    Try to extract document text using native libraries
    Returns: (extracted_text, total_pages, success)
    """
    try:
        # Determine file type from extension
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        extracted_text = None
        total_pages = 0
        
        # Try appropriate extraction method based on file type
        if ext == 'pdf':
            extracted_text, total_pages = extract_text_from_pdf(file_path)
        elif ext in ['docx', 'doc']:
            extracted_text, total_pages = extract_text_from_docx(file_path)
        elif ext in ['pptx', 'ppt']:
            extracted_text, total_pages = extract_text_from_pptx(file_path)
        elif ext in ['xlsx', 'xls', 'csv']:
            extracted_text, total_pages = extract_text_from_xlsx(file_path)
        else:
            logger.warning(f"No native library support for file type: {ext}")
            return None, 0, False
            
        if not extracted_text or not extracted_text.strip():
            logger.warning(f"Native extraction produced empty text for {filename}")
            return None, 0, False
            
        logger.info(f"Successfully extracted {len(extracted_text)} characters from {filename} using native libraries")
        return extracted_text, total_pages, True
        
    except Exception as e:
        logger.warning(f"Native extraction failed for {filename}: {str(e)}")
        return None, 0, False

def process_text_file(file_path):
    """Process a plain text file"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error processing text file: {str(e)}")
        return f"[Error processing text file: {str(e)}]"

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
                
        # Get page count from metadata if available
        total_pages = result.metadata.page_count if hasattr(result, 'metadata') and hasattr(result.metadata, 'page_count') else len(result.pages)
                
        return extracted_text, total_pages
    
    except Exception as e:
        logger.error(f"Error processing document with Document Intelligence: {str(e)}")
        return f"[Error processing document with Document Intelligence: {str(e)}]", 0

def extract_document_structure(result):
    """Extract document structure from Document Intelligence result"""
    structure = []
    
    # Add document metadata if available
    if hasattr(result, 'metadata') and result.metadata:
        structure.append({
            "type": "metadata",
            "content": {
                "pages": result.metadata.page_count,
                "author": result.metadata.author if hasattr(result.metadata, 'author') else None,
                "title": result.metadata.title if hasattr(result.metadata, 'title') else None
            }
        })
    
    # Extract headings and structure
    headings = []
    current_page = None
    
    # Process pages
    for page_idx, page in enumerate(result.pages):
        current_page = page_idx + 1
        
        # First pass to identify headings
        if hasattr(page, 'paragraphs') and page.paragraphs:
            for para in page.paragraphs:
                # Heuristic for headings: shorter text with specific formatting
                is_heading = False
                if len(para.content) < 200:  # Reasonable length for a heading
                    is_heading = (para.content.strip().isupper() or 
                                 para.content.strip().endswith(':') or
                                 re.match(r'^[0-9]+\.', para.content.strip()))
                    
                    # Check for common heading patterns
                    if re.match(r'^(chapter|section|appendix|part)\s+[0-9ivxIVX]+', para.content.lower()):
                        is_heading = True
                
                if is_heading:
                    headings.append({
                        "level": 1,  # Default level, can be refined with formatting analysis
                        "text": para.content,
                        "page": current_page,
                        "paragraph_index": len(structure)  # Position in the structure
                    })
        
        # Add page content entry
        structure.append({
            "type": "page",
            "page_num": current_page,
            "content": []  # To be filled with paragraphs and tables
        })
        
        # Add paragraphs
        if hasattr(page, 'paragraphs') and page.paragraphs:
            for para_idx, para in enumerate(page.paragraphs):
                structure[-1]["content"].append({
                    "type": "paragraph",
                    "text": para.content,
                    "index": para_idx
                })
        else:
            # If no paragraphs, use lines
            for line_idx, line in enumerate(page.lines):
                structure[-1]["content"].append({
                    "type": "line",
                    "text": line.content,
                    "index": line_idx
                })
    
    # Add tables as separate structure elements
    if hasattr(result, 'tables') and result.tables:
        for table_idx, table in enumerate(result.tables):
            table_content = []
            prev_row_idx = -1
            current_row = []
            
            for cell in table.cells:
                if cell.row_index > prev_row_idx:
                    if current_row:
                        table_content.append(current_row)
                    current_row = []
                    prev_row_idx = cell.row_index
                
                current_row.append(cell.content)
            
            if current_row:
                table_content.append(current_row)
            
            structure.append({
                "type": "table",
                "table_idx": table_idx,
                "content": table_content
            })
    
    return {"structure": structure, "headings": headings}

def split_into_semantic_chunks(content, max_chunk_size=1000):
    """Split content into logical chunks based on structure"""
    if not content or len(content) <= max_chunk_size:
        return [content] if content else []
        
    chunks = []
    current_chunk = ""
    current_chunk_size = 0
    
    # First try to split by double newlines (paragraphs)
    paragraphs = re.split(r'\n\s*\n', content)
    
    for para in paragraphs:
        para_size = len(para.split())
        
        # If paragraph itself is too large, split it further
        if para_size > max_chunk_size:
            sentences = re.split(r'(?<=[.!?])\s+', para)
            current_sentence_group = ""
            
            for sentence in sentences:
                if len(current_sentence_group.split()) + len(sentence.split()) < max_chunk_size:
                    current_sentence_group += " " + sentence if current_sentence_group else sentence
                else:
                    if current_sentence_group:
                        chunks.append(current_sentence_group.strip())
                    current_sentence_group = sentence
            
            if current_sentence_group:
                chunks.append(current_sentence_group.strip())
        
        # If this paragraph plus the current chunk is too big, start a new chunk
        elif current_chunk_size + para_size > max_chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para
            current_chunk_size = para_size
        else:
            # Add to current chunk
            current_chunk += "\n\n" + para if current_chunk else para
            current_chunk_size += para_size
    
    # Add the last chunk if there is one
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def calculate_relevance_score(text, query):
    """Calculate relevance score between text and query"""
    # Simple keyword-based scoring
    # In a production environment, this would use embeddings and vector similarity
    query_terms = set(query.lower().split())
    text_lower = text.lower()
    
    # Count term frequency
    term_count = sum(1 for term in query_terms if term in text_lower)
    
    # Calculate base score based on term frequency
    base_score = term_count / max(len(query_terms), 1)
    
    # Bonus for title-like sections or sections that contain complete phrases from query
    if any(re.search(r'^\s*' + re.escape(term) + r'\s*[:.-]', text, re.IGNORECASE) for term in query_terms):
        base_score *= 1.5
    
    # Check for exact phrase matches
    for i in range(len(query_terms) - 1):
        phrase = ' '.join(list(query_terms)[i:i+2])
        if phrase in text_lower:
            base_score *= 1.2
    
    # Look for exact matches of the full query
    if query.lower() in text_lower:
        base_score *= 2
    
    return base_score

def rank_by_relevance(chunks, query):
    """Rank content chunks by relevance to the query"""
    ranked_chunks = []
    
    for i, chunk in enumerate(chunks):
        score = calculate_relevance_score(chunk, query)
        ranked_chunks.append({
            "index": i,
            "chunk": chunk,
            "score": score
        })
    
    # Sort by score (descending)
    ranked_chunks.sort(key=lambda x: x["score"], reverse=True)
    
    return ranked_chunks

def summarize_content(content, max_length=200):
    """Create a brief summary of content"""
    # Extract first few sentences (max 3)
    sentences = re.split(r'(?<=[.!?])\s+', content)
    if len(sentences) <= 3:
        summary = ' '.join(sentences)
    else:
        summary = ' '.join(sentences[:3]) + '...'
    
    # Truncate if still too long
    if len(summary) > max_length:
        summary = summary[:max_length-3] + '...'
        
    return summary

def extract_document_outline(document_structure):
    """Extract a readable document outline from the structure"""
    outline = ""
    
    # Add metadata if available
    metadata = next((item for item in document_structure["structure"] if item["type"] == "metadata"), None)
    if metadata:
        meta_content = metadata["content"]
        outline += "Document Information:\n"
        if meta_content.get("title"):
            outline += f"Title: {meta_content['title']}\n"
        if meta_content.get("author"):
            outline += f"Author: {meta_content['author']}\n"
        outline += f"Pages: {meta_content.get('pages', 'Unknown')}\n\n"
    
    # Add table of contents based on headings
    if document_structure["headings"]:
        outline += "Table of Contents:\n"
        for heading in document_structure["headings"]:
            indent = "  " * (heading["level"] - 1)
            outline += f"{indent}* {heading['text']} (Page {heading['page']})\n"
        outline += "\n"
    
    # Count tables
    tables = [item for item in document_structure["structure"] if item["type"] == "table"]
    if tables:
        outline += f"Document contains {len(tables)} tables.\n\n"
    
    return outline

def process_with_intelligent_extraction(file_path, filename, user_query):
    """Process document with intelligent context extraction based on user query"""
    try:
        # First try to use native libraries for extraction
        extracted_text, total_pages, native_success = extract_document_text_with_native_libraries(file_path, filename)
        
        # If native extraction failed, fall back to Document Intelligence
        if not native_success:
            logger.info(f"Native extraction failed, falling back to Document Intelligence for {filename}")
            extracted_text, total_pages = process_with_document_intelligence(file_path, filename)
        else:
            logger.info(f"Successfully used native libraries for {filename}")
        
        # If we still don't have text, abort
        if not extracted_text or not extracted_text.strip():
            return f"Could not extract text from {filename} using any available method."
            
        # Document info header
        doc_info = f"--- Document: {filename} ---\n\n"
        doc_info += f"Document Type: {filename.rsplit('.', 1)[1].upper() if '.' in filename else 'Unknown'}\n"
        doc_info += f"Pages/Slides/Sheets: {total_pages}\n\n"
        
        # Split content into chunks to handle large documents
        # Use a larger chunk size for more context
        chunks = split_into_semantic_chunks(extracted_text, max_chunk_size=2000)
        logger.info(f"Split document into {len(chunks)} chunks")
        
        # Rank chunks by relevance to user query
        ranked_chunks = rank_by_relevance(chunks, user_query)
        
        # Build final content with relevant material
        final_content = doc_info
        
        # Calculate token budget to avoid hitting context limits
        # Simple approximation: 4 characters ≈ 1 token
        doc_info_tokens = len(doc_info) // 4
        
        # Determine the appropriate max tokens based on model
        MAX_CONTEXT_TOKENS = 90000  # Conservative limit for GPT-4o
        
        # Reserve tokens for top chunks and summary
        remaining_tokens = MAX_CONTEXT_TOKENS - doc_info_tokens - 1000  # Reserve 1000 tokens for overhead
        
        # Add most relevant chunks up to the remaining token budget
        tokens_used = 0
        chunks_included = 0
        
        final_content += "MOST RELEVANT CONTENT:\n\n"
        
        for chunk_info in ranked_chunks:
            chunk = chunk_info["chunk"]
            chunk_tokens = len(chunk) // 4
            
            if tokens_used + chunk_tokens <= remaining_tokens * 0.9:  # Use 90% for most relevant chunks
                final_content += f"[Content Section {chunks_included + 1}]\n{chunk}\n\n"
                tokens_used += chunk_tokens
                chunks_included += 1
            else:
                # If the full chunk doesn't fit, include a summary
                if chunks_included < len(ranked_chunks) // 2:  # Only summarize if we've included at least half
                    summary = summarize_content(chunk, max_length=300)
                    summary_tokens = len(summary) // 4
                    
                    if tokens_used + summary_tokens <= remaining_tokens * 0.9:
                        final_content += f"[Content Section {chunks_included + 1} - Summary]\n{summary}\n\n"
                        tokens_used += summary_tokens
                        chunks_included += 1
                
        # Add meta information about coverage
        if chunks_included < len(ranked_chunks):
            final_content += f"\nNote: {chunks_included} of {len(ranked_chunks)} content sections were included due to size constraints.\n"
        
        logger.info(f"Document processing complete. Included {chunks_included}/{len(ranked_chunks)} chunks, using ~{tokens_used} tokens.")
        
        return final_content
    
    except Exception as e:
        logger.error(f"Error in intelligent document processing: {str(e)}")
        # Fall back to basic document processing if advanced processing fails
        return f"Error processing {filename}: {str(e)}"

def deepseek_r1_service(system_prompt, user_input, temperature=0.5, json_output=False, max_tokens=2048):
    """DeepSeek-R1 LLM service function for chain of thought and deep reasoning"""
    try:
        # Fixed endpoint for DeepSeek R1
        ENDPOINT = 'https://deepseek-r1-aiapi.eastus.models.ai.azure.com'
        
        # Initialize Azure Inference client
        client = ChatCompletionsClient(
            endpoint=ENDPOINT,
            credential=AzureKeyCredential(DEEPSEEK_API_KEY)
        )
        
        # Prepare messages for the model
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user message
        messages.append({"role": "user", "content": user_input})
        
        # Prepare payload
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        # Add response format if JSON output is requested
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        
        # Make request to LLM
        response = client.complete(payload)
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name = response.model if hasattr(response, 'model') else "deepseek-r1-aiapi"
        cached_tokens = 0  # Default to 0 as this model doesn't support cached tokens
        
        return {
            "success": True,
            "result": result,
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"DeepSeek-R1 API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def deepseek_v3_service(system_prompt, user_input, temperature=0.7, json_output=False, max_tokens=1000):
    """DeepSeek-V3 LLM service function for general task completion"""
    try:
        # Fixed deployment endpoint
        ENDPOINT = 'https://ai-coe-services-dev.services.ai.azure.com/models'
        MODEL_NAME = 'DeepSeek-V3'
        
        # Initialize Azure Inference client
        client = ChatCompletionsClient(
            endpoint=ENDPOINT,
            credential=AzureKeyCredential(DEEPSEEK_V3_API_KEY)
        )
        
        # Prepare messages for the model
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user message
        messages.append({"role": "user", "content": user_input})
        
        # Prepare payload
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "model": MODEL_NAME
        }
        
        # Add response format if JSON output is requested
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        
        # Make request to LLM
        response = client.complete(payload)
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name = response.model if hasattr(response, 'model') else MODEL_NAME
        cached_tokens = 0  # Default to 0 as this model doesn't support cached tokens
        
        return {
            "success": True,
            "result": result,
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"DeepSeek-V3 API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def gpt4o_service(system_prompt, user_input, temperature=0.5, json_output=False):
    """OpenAI GPT-4o LLM service function for text completion and content generation"""
    try:
        # Fixed deployment model
        DEPLOYMENT = 'gpt-4o'
        
        # Make request to LLM
        response = openai_client.chat.completions.create(
            model=DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Provided text: {user_input}"}
            ],
            temperature=temperature,
            response_format={"type": "json_object"} if json_output else {"type": "text"}
        )
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        return {
            "success": True,
            "result": result,
            "model": DEPLOYMENT,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"GPT-4o API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def gpt4o_mini_service(system_prompt, user_input, temperature=0.5, json_output=False):
    """OpenAI GPT-4o-mini LLM service function for everyday text completion tasks"""
    try:
        # Fixed deployment model
        DEPLOYMENT = 'gpt-4o-mini'
        
        # Make request to LLM
        response = openai_client.chat.completions.create(
            model=DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Provided text: {user_input}"}
            ],
            temperature=temperature,
            response_format={"type": "json_object"} if json_output else {"type": "text"}
        )
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        return {
            "success": True,
            "result": result,
            "model": DEPLOYMENT,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"GPT-4o-mini API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def o1_mini_service(system_prompt, user_input, temperature=0.5, json_output=False):
    """OpenAI O1-mini LLM service function for complex tasks requiring reasoning"""
    try:
        # Fixed deployment model
        DEPLOYMENT = 'o1-mini'
        
        # o1-mini doesn't support 'system' role, so include system prompt in user message
        combined_input = f"{system_prompt}\n\nProvided text: {user_input}"
        
        # Make request to LLM
        response = openai_client.chat.completions.create(
            model=DEPLOYMENT,
            messages=[
                {"role": "user", "content": combined_input}
            ],
            response_format={"type": "json_object"} if json_output else {"type": "text"}
        )
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        return {
            "success": True,
            "result": result,
            "model": DEPLOYMENT,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"O1-mini API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def o3_mini_service(system_prompt, user_input, max_completion_tokens=100000, reasoning_effort="medium", json_output=False):
    """O3-Mini LLM service function with variable reasoning effort"""
    try:
        # Fixed deployment information
        ENDPOINT = "https://ai-coe-services-dev.openai.azure.com/"
        DEPLOYMENT = "o3-mini"
        API_VERSION = "2024-12-01-preview"
        
        # Initialize Azure OpenAI client
        client = AzureOpenAI(
            azure_endpoint=ENDPOINT,
            api_key=O3_MINI_API_KEY,
            api_version=API_VERSION,
        )
        
        # Prepare messages for the model
        chat_prompt = [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "text",
                        "text": system_prompt
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_input
                    }
                ]
            }
        ]
        
        # Prepare additional parameters
        additional_params = {
            "max_completion_tokens": max_completion_tokens,
            "reasoning_effort": reasoning_effort
        }
        
        # Add response format if JSON output is requested
        if json_output:
            additional_params["response_format"] = {"type": "json_object"}
        
        # Make request to LLM
        completion = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=chat_prompt,
            **additional_params,
            stop=None,
            stream=False
        )
        
        # Extract response data
        result = completion.choices[0].message.content
        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
        total_tokens = prompt_tokens + completion_tokens
        model_name = DEPLOYMENT
        cached_tokens = completion.usage.cached_tokens if hasattr(completion.usage, 'cached_tokens') else 0
        
        return {
            "success": True,
            "result": result,
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"O3-Mini API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def llama_service(system_prompt, user_input, temperature=0.8, json_output=False, max_tokens=2048, top_p=0.1, presence_penalty=0, frequency_penalty=0):
    """Meta Llama LLM service function for text generation"""
    try:
        # Fixed deployment endpoint
        ENDPOINT = 'https://Meta-Llama-3-1-405B-aiapis.eastus.models.ai.azure.com'
        
        # Initialize Azure Inference client
        client = ChatCompletionsClient(
            endpoint=ENDPOINT,
            credential=AzureKeyCredential(LLAMA_API_KEY)
        )
        
        # Prepare messages for the model
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user message
        messages.append({"role": "user", "content": user_input})
        
        # Prepare payload
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty
        }
        
        # Add response format if JSON output is requested
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        
        # Make request to LLM
        response = client.complete(payload)
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name = "llama-3-1-405b"
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        return {
            "success": True,
            "result": result,
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"Llama API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def gpt4o_multimodal_service(system_prompt, user_input, temperature=0.5, json_output=False, file_ids=None, user_id=None):
    """OpenAI GPT-4o LLM service function for multimodal content generation with file support"""
    try:
        # Fixed deployment model
        DEPLOYMENT = 'gpt-4o'
        temp_files = []  # Keep track of temporary files for cleanup
        
        # Track file processing statistics
        file_stats = {
            "documents_processed": 0,
            "images_processed": 0,
            "text_files_processed": 0
        }
        
        # Prepare message content
        message_content = []
        
        # First add the user's input text
        message_content.append({
            "type": "text", 
            "text": user_input
        })
        
        # Process file_ids if any
        if file_ids and isinstance(file_ids, list) and len(file_ids) > 0:
            for file_id in file_ids:
                # Get file details using FileService
                file_info, error = FileService.get_file_url(file_id, user_id)
                
                if error:
                    logger.error(f"Error retrieving file {file_id}: {error}")
                    continue
                
                # Check if we have the necessary file information
                if not file_info or 'file_url' not in file_info or 'content_type' not in file_info:
                    logger.error(f"Incomplete file information for file {file_id}")
                    continue
                
                file_url = file_info['file_url']
                content_type = file_info['content_type']
                file_name = file_info.get('file_name', f"file_{file_id}")
                
                try:
                    # Create a temporary file to store the downloaded content
                    fd, temp_path = tempfile.mkstemp(suffix=f'.{file_name.rsplit(".", 1)[1].lower()}' if '.' in file_name else '')
                    temp_files.append(temp_path)
                    
                    # Download the file from Azure Blob Storage
                    import requests
                    response = requests.get(file_url)
                    response.raise_for_status()
                    
                    with os.fdopen(fd, 'wb') as tmp:
                        tmp.write(response.content)
                    
                    # Check file type and process accordingly
                    if content_type.startswith('image/'):
                        # For images, encode as base64 and add to message
                        file_stats["images_processed"] += 1
                        
                        with open(temp_path, 'rb') as img_file:
                            base64_image = base64.b64encode(img_file.read()).decode('utf-8')
                        
                        # Add as image content
                        message_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{base64_image}"
                            }
                        })
                        
                    elif '.' in file_name and file_name.rsplit(".", 1)[1].lower() in ['pdf', 'docx', 'doc', 'pptx', 'ppt', 'xlsx', 'xls']:
                        # Process document with intelligent extraction
                        file_stats["documents_processed"] += 1
                        
                        # Process document with intelligent extraction - will try native libs first
                        extracted_content = process_with_intelligent_extraction(temp_path, file_name, user_input)
                        
                        # Add to message content
                        message_content.append({
                            "type": "text",
                            "text": f"\n\n--- Content from {file_name} ---\n{extracted_content}\n--- End of {file_name} ---\n"
                        })
                        
                    elif file_name.endswith('.txt') or content_type == 'text/plain':
                        # Process plain text file
                        file_stats["text_files_processed"] += 1
                        
                        # Extract text
                        extracted_content = process_text_file(temp_path)
                        
                        # Add to message content
                        message_content.append({
                            "type": "text",
                            "text": f"\n\n--- Content from {file_name} ---\n{extracted_content}\n--- End of {file_name} ---\n"
                        })
                        
                    else:
                        # For unsupported file types, just mention they were uploaded
                        message_content.append({
                            "type": "text",
                            "text": f"\n\nA file named '{file_name}' was uploaded, but its content type ({content_type}) is not supported for extraction."
                        })
                        
                except requests.RequestException as e:
                    logger.error(f"Error downloading file {file_id}: {str(e)}")
                    message_content.append({
                        "type": "text",
                        "text": f"\n\nFailed to download file {file_name}: {str(e)}"
                    })
                except Exception as e:
                    logger.error(f"Error processing file {file_id}: {str(e)}")
                    message_content.append({
                        "type": "text",
                        "text": f"\n\nError processing file {file_name}: {str(e)}"
                    })
        
        # Create the chat completion request
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_content}
        ]
        
        # Make the API call
        response = openai_client.chat.completions.create(
            model=DEPLOYMENT,
            messages=messages,
            temperature=temperature,
            max_tokens=4000,  # Add reasonable limit
            response_format={"type": "json_object"} if json_output else {"type": "text"}
        )
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        # Total files processed
        total_files_processed = file_stats["documents_processed"] + file_stats["images_processed"] + file_stats["text_files_processed"]
        
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except Exception as e:
                logger.error(f"Error removing temporary file {temp_file}: {str(e)}")
        
        return {
            "success": True,
            "result": result,
            "model": DEPLOYMENT,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "files_processed": total_files_processed,
            "file_processing_details": file_stats
        }
        
    except Exception as e:
        # Clean up temporary files in case of error
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass
                
        logger.error(f"GPT-4o Multimodal API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
