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
        "files_uploaded": 0
    }
    
    try:
        # Try to extract JSON data from response
        response_data = response.get_json() if hasattr(response, 'get_json') else None
        
        if not response_data:
            return metrics
        
        # Extract model information
        if "model" in response_data:
            metrics["model_used"] = response_data["model"]
        elif "model_used" in response_data:
            metrics["model_used"] = response_data["model_used"]
        
        # Token usage metrics - direct fields
        if "prompt_tokens" in response_data:
            metrics["prompt_tokens"] = response_data["prompt_tokens"]
        if "completion_tokens" in response_data:
            metrics["completion_tokens"] = response_data["completion_tokens"]
        if "total_tokens" in response_data:
            metrics["total_tokens"] = response_data["total_tokens"]
        if "cached_tokens" in response_data:
            metrics["cached_tokens"] = response_data["cached_tokens"]
        
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
        
        # 1. Insert into user_usage table
        query = """
        INSERT INTO user_usage (
            id, user_id, endpoint_id, timestamp,
            images_generated, audio_seconds_processed, pages_processed,
            documents_processed, model_used, prompt_tokens,
            completion_tokens, total_tokens, cached_tokens, files_uploaded
        )
        VALUES (
            ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()),
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
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
            metrics["files_uploaded"]
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

def find_most_recent_api_log(user_id, endpoint_id, window_seconds=10):
    """Find the most recent API log for this user and endpoint"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT TOP 1 id
        FROM api_logs
        WHERE user_id = ?
        AND endpoint_id = ?
        AND timestamp >= DATEADD(SECOND, -?, DATEADD(HOUR, 2, GETUTCDATE()))
        ORDER BY timestamp DESC
        """
        
        cursor.execute(query, [user_id, endpoint_id, window_seconds])
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            logger.info(f"Found recent API log: {result[0]}")
            return result[0]
        
        logger.warning(f"No recent API log found for user {user_id} and endpoint {endpoint_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error finding recent API log: {str(e)}")
        return None

def track_usage(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Execute the API function and get the response
        response = f(*args, **kwargs)
        
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
            
            # First, try to get the API log ID from g object
            api_log_id = getattr(g, 'current_api_log_id', None)
            
            # If not found in g, try to get it from the request object (backup)
            if not api_log_id:
                api_log_id = getattr(request, '_api_log_id', None)
            
            # If still not found, try to find the most recent API log as fallback
            if not api_log_id:
                api_log_id = find_most_recent_api_log(
                    metrics["user_id"], 
                    metrics["endpoint_id"],
                    window_seconds=10
                )
            
            # Log usage metrics and update the api_logs table
            log_usage_metrics_and_update_api_log(metrics, api_log_id, usage_id)
            
        except Exception as e:
            # Log the error but don't affect the response
            logger.error(f"Error in usage tracking: {str(e)}")
        
        # Return the original response
        return response
    
    return decorated_function
