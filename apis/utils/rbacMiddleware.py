from functools import wraps
from flask import request, g, jsonify, make_response
from apis.utils.databaseService import DatabaseService
import logging

logger = logging.getLogger(__name__)

def check_endpoint_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Skip access check for admin endpoints (they're already protected)
            if request.path.startswith('/admin'):
                return f(*args, **kwargs)

            # Get endpoint ID
            endpoint_id = DatabaseService.get_endpoint_id_by_path(request.path)
            if not endpoint_id:
                logger.error(f"Endpoint not configured for access control: {request.path}")
                return make_response(jsonify({
                    "error": "Configuration Error",
                    "message": "Endpoint not configured for access control"
                }), 500)

            # Get user_id from context
            user_id = getattr(g, 'user_id', None)
            
            # If user_id is not in g, try to get it from token or API key
            if not user_id:
                # Try from X-Token header
                token = request.headers.get('X-Token')
                if token:
                    token_details = DatabaseService.get_token_details_by_value(token)
                    if token_details:
                        user_id = token_details.get("user_id")
                        g.user_id = user_id  # Set it for subsequent middleware
                
                # If still no user_id, try from API-Key
                if not user_id:
                    api_key = request.headers.get('API-Key')
                    if api_key:
                        user_info = DatabaseService.validate_api_key(api_key)
                        if user_info:
                            user_id = user_info["id"]
                            g.user_id = user_id  # Set it for subsequent middleware
            
            if not user_id:
                logger.error("User ID not found in request context or authentication headers")
                return make_response(jsonify({
                    "error": "Authentication Error",
                    "message": "User ID not found in request context"
                }), 401)

            # Check if user has access to this endpoint
            has_access = DatabaseService.check_user_endpoint_access(user_id, endpoint_id)
            if not has_access:
                logger.warning(f"Access denied for user {user_id} to endpoint {request.path}")
                return make_response(jsonify({
                    "error": "Access Denied",
                    "message": "You do not have permission to access this endpoint"
                }), 403)
            
            # User has access, proceed with the request
            logger.info(f"Access granted for user {user_id} to endpoint {request.path}")
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error in RBAC middleware: {str(e)}")
            return make_response(jsonify({
                "error": "Access Control Error",
                "message": f"An error occurred: {str(e)}"
            }), 500)

    return decorated_function
