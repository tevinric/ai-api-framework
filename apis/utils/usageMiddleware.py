from functools import wraps
from flask import request, g, jsonify, make_response
from apis.utils.databaseService import DatabaseService
import logging
import json
import uuid
import time

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def extract_usage_metrics(response):
    """Extract usage metrics from API response"""
    metrics = {
        "user_id": getattr(g, 'user_id', None),
        "endpoint_id": DatabaseService.get_endpoint_id_by_path(request.path),
        "images_generated": 0,
        "audio_seconds_processed": 0,
        "pages_processed": 0,
        "documents_processed": 0,
        "model_used": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "files_uploaded": 0,
        "embedded_tokens": 0  # Added embedded_tokens field
    }
    
    try:
        # Try to extract JSON data from response
        response_data = response.get_json() if hasattr(response, 'get_json') else None
        
        if not response_data:
            return metrics
        
        # Extract model information
        if "model" in response_data:
            metrics["model_used"] = response_data["model"]
            print(f"DEBUG: UsageMiddleware - Extracted model from 'model': {response_data['model']}")
        elif "model_used" in response_data:
            metrics["model_used"] = response_data["model_used"]
            print(f"DEBUG: UsageMiddleware - Extracted model from 'model_used': {response_data['model_used']}")
        
        # Token usage metrics - direct fields
        if "prompt_tokens" in response_data:
            metrics["prompt_tokens"] = response_data["prompt_tokens"]
        if "completion_tokens" in response_data:
            metrics["completion_tokens"] = response_data["completion_tokens"]
        if "total_tokens" in response_data:
            metrics["total_tokens"] = response_data["total_tokens"]
        if "cached_tokens" in response_data:
            metrics["cached_tokens"] = response_data["cached_tokens"]
        
        # Add extraction of embedded_tokens
        if "embedded_tokens" in response_data:
            metrics["embedded_tokens"] = response_data["embedded_tokens"]
        
        # Token usage metrics - nested in 'usage' field
        if "usage" in response_data and isinstance(response_data["usage"], dict):
            usage = response_data["usage"]
            if "prompt_tokens" in usage:
                metrics["prompt_tokens"] = usage["prompt_tokens"]
            if "completion_tokens" in usage:
                metrics["completion_tokens"] = usage["completion_tokens"]
            if "total_tokens" in usage:
                metrics["total_tokens"] = usage["total_tokens"]
            if "cached_tokens" in usage:
                metrics["cached_tokens"] = usage["cached_tokens"]
            if "embedded_tokens" in usage:
                metrics["embedded_tokens"] = usage["embedded_tokens"]
        
        # Image generation metrics
        if "images_generated" in response_data:
            metrics["images_generated"] = response_data["images_generated"]
        # For DALL-E or Stable Diffusion endpoints
        elif request.path.startswith('/image-generation') and "file_id" in response_data:
            # Count successful image generation as 1 image
            metrics["images_generated"] = 1
        
        # File upload metrics
        if "files_uploaded" in response_data:
            metrics["files_uploaded"] = response_data["files_uploaded"]
        elif "uploaded_files" in response_data and isinstance(response_data["uploaded_files"], list):
            metrics["files_uploaded"] = len(response_data["uploaded_files"])
        
        # Audio processing metrics
        if "seconds_processed" in response_data:
            metrics["audio_seconds_processed"] = response_data["seconds_processed"]
            print(f"DEBUG: UsageMiddleware - Extracted audio seconds: {response_data['seconds_processed']}")
        
        # Document processing metrics
        if "pages_processed" in response_data:
            metrics["pages_processed"] = response_data["pages_processed"]
        if "documents_processed" in response_data:
            metrics["documents_processed"] = response_data["documents_processed"]
        elif "file_processing_details" in response_data and isinstance(response_data["file_processing_details"], dict):
            details = response_data["file_processing_details"]
            if "documents_processed" in details:
                metrics["documents_processed"] = details["documents_processed"]
            if "pages_processed" in details:
                metrics["pages_processed"] = details["pages_processed"]
        
        # OCR endpoint special cases
        if request.path.startswith('/ocr/'):
            if "extraction_method" in response_data and "documents_processed" not in response_data:
                # If extraction method is present, at least one document was processed
                metrics["documents_processed"] = 1
        
        # RAG endpoint special cases
        if request.path.startswith('/rag/'):
            if "file_count" in response_data:
                metrics["documents_processed"] = response_data["file_count"]
        
        return metrics
    
    except Exception as e:
        logger.error(f"Error extracting usage metrics: {str(e)}")
        return metrics

def log_usage_metrics_and_update_api_log(metrics, api_log_id, usage_id):
    """Log usage metrics to database and update the api_logs table with the usage ID"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        # 1. Insert into user_usage table with api_log_id field
        query = """
        INSERT INTO user_usage (
            id, user_id, endpoint_id, timestamp,
            images_generated, audio_seconds_processed, pages_processed,
            documents_processed, model_used, prompt_tokens,
            completion_tokens, total_tokens, cached_tokens, files_uploaded,
            api_log_id, embedded_tokens
        )
        VALUES (
            ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()),
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?
        )
        """
        
        cursor.execute(query, [
            usage_id,
            metrics["user_id"],
            metrics["endpoint_id"],
            metrics["images_generated"],
            metrics["audio_seconds_processed"],
            metrics["pages_processed"],
            metrics["documents_processed"],
            metrics["model_used"],
            metrics["prompt_tokens"],
            metrics["completion_tokens"],
            metrics["total_tokens"],
            metrics["cached_tokens"],
            metrics["files_uploaded"],
            api_log_id,  # Add api_log_id parameter
            metrics["embedded_tokens"]  # Add embedded_tokens parameter
        ])
        
        # 2. Update the api_logs table with the user_usage_id
        if api_log_id:
            update_query = """
            UPDATE api_logs
            SET user_usage_id = ?
            WHERE id = ?
            """
            
            cursor.execute(update_query, [usage_id, api_log_id])
            
            rows_affected = cursor.rowcount
            if rows_affected > 0:
                logger.info(f"Updated API log {api_log_id} with usage ID {usage_id}")
            else:
                logger.warning(f"No API log found with ID {api_log_id} to update")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Usage metrics logged with ID: {usage_id}" + (f", linked to API log: {api_log_id}" if api_log_id else ""))
        return True
        
    except Exception as e:
        logger.error(f"Error logging usage metrics: {str(e)}")
        return False

def create_api_log_and_get_id(user_id, endpoint_id, request_method, response_status, response_time_ms):
    """Create a new API log entry specifically for usage tracking"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        log_id = str(uuid.uuid4())
        
        # Get correlation ID from Flask g object if available
        correlation_id = getattr(g, 'correlation_id', None)
        
        query = """
        INSERT INTO api_logs (
            id, endpoint_id, user_id, timestamp, request_method, 
            response_status, response_time_ms, correlation_id
        )
        VALUES (
            ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()), ?, 
            ?, ?, ?
        )
        """
        
        cursor.execute(query, [
            log_id, endpoint_id, user_id, request_method,
            response_status, response_time_ms, correlation_id
        ])
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Created API log with ID {log_id} for usage tracking, Correlation ID: {correlation_id}")
        return log_id
        
    except Exception as e:
        logger.error(f"Error creating API log for usage tracking: {str(e)}")
        return None

def log_dual_usage_for_stt_diarize(metrics, api_log_id, response_data):
    """Create two separate usage records for stt_diarize - one for MS STT and one for GPT-4o-mini"""
    try:
        # Debug logging
        logger.info(f"DEBUG: stt_diarize dual logging - audio_seconds_processed: {metrics.get('audio_seconds_processed', 'NOT_FOUND')}")
        logger.info(f"DEBUG: stt_diarize dual logging - prompt_tokens: {metrics.get('prompt_tokens', 'NOT_FOUND')}")
        
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        # Create first record for MS STT with audio seconds
        ms_stt_usage_id = str(uuid.uuid4())
        ms_stt_query = """
        INSERT INTO user_usage (
            id, user_id, endpoint_id, timestamp,
            images_generated, audio_seconds_processed, pages_processed,
            documents_processed, model_used, prompt_tokens,
            completion_tokens, total_tokens, cached_tokens, files_uploaded,
            api_log_id, embedded_tokens
        )
        VALUES (
            ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()),
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?
        )
        """
        
        # Debug logging for MS STT record
        ms_stt_audio_seconds = metrics["audio_seconds_processed"]
        logger.info(f"DEBUG: Inserting MS STT record - audio_seconds_processed: {ms_stt_audio_seconds}")
        
        cursor.execute(ms_stt_query, [
            ms_stt_usage_id,
            metrics["user_id"],
            metrics["endpoint_id"],
            0,  # images_generated
            ms_stt_audio_seconds,  # audio seconds from MS STT
            0,  # pages_processed
            0,  # documents_processed
            "ms_stt",  # model_used
            0,  # prompt_tokens
            0,  # completion_tokens
            0,  # total_tokens
            0,  # cached_tokens
            0,  # files_uploaded
            api_log_id,
            0   # embedded_tokens
        ])
        
        # Create second record for GPT-4o-mini with token usage
        gpt_usage_id = str(uuid.uuid4())
        gpt_query = """
        INSERT INTO user_usage (
            id, user_id, endpoint_id, timestamp,
            images_generated, audio_seconds_processed, pages_processed,
            documents_processed, model_used, prompt_tokens,
            completion_tokens, total_tokens, cached_tokens, files_uploaded,
            api_log_id, embedded_tokens
        )
        VALUES (
            ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()),
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?
        )
        """
        
        # Debug logging for GPT-4o-mini record
        gpt_prompt_tokens = metrics["prompt_tokens"]
        logger.info(f"DEBUG: Inserting GPT-4o-mini record - audio_seconds_processed: 0, prompt_tokens: {gpt_prompt_tokens}")
        
        cursor.execute(gpt_query, [
            gpt_usage_id,
            metrics["user_id"],
            metrics["endpoint_id"],
            0,  # images_generated
            0,  # audio_seconds_processed - explicitly zero for GPT model
            0,  # pages_processed
            0,  # documents_processed
            "gpt-4o-mini",  # model_used
            gpt_prompt_tokens,
            metrics["completion_tokens"],
            metrics["total_tokens"],
            metrics["cached_tokens"],
            0,  # files_uploaded
            api_log_id,
            metrics["embedded_tokens"]
        ])
        
        # Update the api_logs table with the first usage ID (MS STT)
        if api_log_id:
            update_query = """
            UPDATE api_logs
            SET user_usage_id = ?
            WHERE id = ?
            """
            
            cursor.execute(update_query, [ms_stt_usage_id, api_log_id])
            
            rows_affected = cursor.rowcount
            if rows_affected > 0:
                logger.info(f"Updated API log {api_log_id} with primary usage ID {ms_stt_usage_id}")
            else:
                logger.warning(f"No API log found with ID {api_log_id} to update")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Dual usage metrics logged - MS STT: {ms_stt_usage_id}, GPT-4o-mini: {gpt_usage_id}, linked to API log: {api_log_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error logging dual usage metrics for stt_diarize: {str(e)}")
        return False

def track_usage(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        # Execute the API function and get the response
        response = f(*args, **kwargs)
        response_time = int((time.time() - start_time) * 1000)
        
        try:
            # Extract usage metrics from the response
            metrics = extract_usage_metrics(response)
            
            # Don't continue if we don't have the basic info needed
            if not metrics["user_id"] or not metrics["endpoint_id"]:
                if not metrics["user_id"]:
                    logger.warning(f"Cannot log usage metrics: missing user_id for {request.path}")
                if not metrics["endpoint_id"]:
                    logger.warning(f"Cannot log usage metrics: missing endpoint_id for {request.path}")
                return response
            
            # Generate a new UUID for the usage metrics
            usage_id = str(uuid.uuid4())
            
            # First, check if an API log ID was created by the api_logger middleware
            api_log_id = getattr(g, 'current_api_log_id', None)
            
            # If not in g, try to get it from the request object
            if not api_log_id:
                api_log_id = getattr(request, '_api_log_id', None)
                
            # If still no API log ID, create one ourselves
            if not api_log_id:
                api_log_id = create_api_log_and_get_id(
                    metrics["user_id"],
                    metrics["endpoint_id"],
                    request.method,
                    response.status_code if hasattr(response, 'status_code') else 200,
                    response_time
                )
            
            # Special handling for stt_diarize endpoint - create two separate usage records
            if request.path == '/speech/stt_diarize':
                response_data = response.get_json() if hasattr(response, 'get_json') else None
                log_dual_usage_for_stt_diarize(metrics, api_log_id, response_data)
            else:
                # Log usage metrics and update the api_logs table for all other endpoints
                log_usage_metrics_and_update_api_log(metrics, api_log_id, usage_id)
            
        except Exception as e:
            # Log the error but don't affect the response
            logger.error(f"Error in usage tracking: {str(e)}")
        
        # Return the original response
        return response
    
    return decorated_function
