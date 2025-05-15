import time
import json
from flask import request, g
from functools import wraps
import uuid
from apis.utils.databaseService import DatabaseService
import logging
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def get_token_details():
    """Extract token details from request"""
    # Try X-Token header first
    token = request.headers.get('X-Token')
    if token:
        return DatabaseService.get_token_details_by_value(token)
    
    # Try token in request body
    if request.is_json:
        data = request.get_json()
        if data and 'token' in data:
            token = data.get('token')
            return DatabaseService.get_token_details_by_value(token)
    
    return None

def get_user_id_from_request():
    """Extract user ID from various authentication methods"""
    user_id = None
    
    # Try to get user_id from API key (admin functions)
    api_key = request.headers.get('API-Key')
    if api_key:
        admin_info = DatabaseService.validate_api_key(api_key)
        if admin_info:
            return admin_info["id"]
    
    # Try to get user_id from token details
    token_details = get_token_details()
    if token_details:
        return token_details.get("user_id")
    
    # Fallback to user_id stored in Flask g object
    return getattr(g, 'user_id', None)

def api_logger(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Record start time
        start_time = time.time()
        
        # Get request info
        endpoint = request.path
        method = request.method
        headers = dict(request.headers)
        
        # Extract correlation ID from header (or generate one if not provided)
        correlation_id = headers.get('X-Correlation-ID') or str(uuid.uuid4())
        
        # Store correlation ID in Flask g object for other middleware to access
        g.correlation_id = correlation_id
        
        # Remove sensitive info from headers
        sensitive_headers = ['Authorization', 'API-Key', 'X-Token', 'Api-Key', 'api_key']
        for header in sensitive_headers:
            if header in headers:
                headers[header] = '[REDACTED]'
            
        # Get request body if it's JSON
        body = None
        if request.is_json:
            body = request.get_json()
            # Don't log sensitive fields
            if body and isinstance(body, dict):
                body_copy = body.copy()
                for key in ['password', 'token', 'api_key']:
                    if key in body_copy:
                        body_copy[key] = '[REDACTED]'
                body = body_copy
        
        # Get user agent and IP
        user_agent = request.headers.get('User-Agent')
        ip_address = request.remote_addr
        
        # Get token details before executing request
        token_details = get_token_details()
        token_id = token_details["id"] if token_details else None
        
        # Execute the request
        try:
            response = f(*args, **kwargs)
            
            # Add correlation ID to response headers for tracking
            if hasattr(response, 'headers'):
                response.headers['X-Correlation-ID'] = correlation_id
            
            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)
            
            # Get user_id using the helper function
            user_id = get_user_id_from_request()
            
            # Get endpoint ID from database
            endpoint_id = DatabaseService.get_endpoint_id_by_path(endpoint)
            if not endpoint_id:
                logger.warning(f"Endpoint not found in database: {endpoint}")
                return response
            
            # Extract response data
            response_status = response.status_code
            try:
                response_data = response.get_json() if hasattr(response, 'get_json') else None
            except:
                response_data = None
                
            # Log successful request - IMPORTANT: Store the returned log_id
            log_id = DatabaseService.log_api_call(
                endpoint_id=endpoint_id,
                user_id=user_id,
                token_id=token_id,
                request_method=method,
                request_headers=json.dumps(headers),
                request_body=json.dumps(body) if body else None,
                response_status=response_status,
                response_time_ms=response_time,
                user_agent=user_agent,
                ip_address=ip_address,
                response_body=json.dumps(response_data) if response_data else None,
                correlation_id=correlation_id
            )
            
            # Store the log ID in g for usageMiddleware to access
            if log_id:
                # Set in Flask g object
                g.current_api_log_id = log_id
                # Also set directly on request object as a backup
                setattr(request, '_api_log_id', log_id)
                logger.info(f"API Log ID set: {log_id}, Correlation ID: {correlation_id}")
            else:
                logger.warning("Failed to get API Log ID from DatabaseService")
            
            return response
            
        except Exception as e:
            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)
            
            # Get endpoint ID from database
            endpoint_id = DatabaseService.get_endpoint_id_by_path(endpoint)
            
            # Get user_id using the helper function
            user_id = get_user_id_from_request()
            
            # Log failed request
            error_log_id = DatabaseService.log_api_call(
                endpoint_id=endpoint_id,
                user_id=user_id,
                token_id=token_id,
                request_method=method,
                request_headers=json.dumps(headers),
                request_body=json.dumps(body) if body else None,
                response_status=500,
                response_time_ms=response_time,
                user_agent=user_agent,
                ip_address=ip_address,
                error_message=str(e),
                correlation_id=correlation_id
            )
            
            # Store the error log ID in g
            if error_log_id:
                g.current_api_log_id = error_log_id
                setattr(request, '_api_log_id', error_log_id)
                logger.info(f"Error API Log ID set: {error_log_id}, Correlation ID: {correlation_id}")
            
            # Re-raise the exception
            raise
            
    return decorated_function
