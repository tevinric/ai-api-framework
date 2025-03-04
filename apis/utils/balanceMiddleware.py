from functools import wraps
from flask import request, g, jsonify, make_response
from apis.utils.balanceService import BalanceService
from apis.utils.databaseService import DatabaseService
import logging

logger = logging.getLogger(__name__)

def check_balance(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Skip balance check for admin endpoints
            if request.path.startswith('/admin'):
                return f(*args, **kwargs)

            # Get endpoint ID
            endpoint_id = DatabaseService.get_endpoint_id_by_path(request.path)
            if not endpoint_id:
                logger.error(f"Endpoint not configured for balance tracking: {request.path}")
                return make_response(jsonify({
                    "error": "Configuration Error",
                    "message": "Endpoint not configured for balance tracking"
                }), 500)

            # Check if user_id is already in g (set by previous middleware)
            user_id = getattr(g, 'user_id', None)
            
            # If user_id is not in g, try to get it from token or API key
            if not user_id:
                # Try from X-Token header (custom_llm uses this)
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

            # Get the endpoint-specific cost
            endpoint_cost = DatabaseService.get_endpoint_cost_by_id(endpoint_id)
            logger.info(f"Endpoint {endpoint_id} cost: {endpoint_cost}")

            # Check and deduct balance using the endpoint-specific cost
            success, result = BalanceService.check_and_deduct_balance(user_id, endpoint_id, endpoint_cost)
            if not success:
                if result == "Insufficient balance":
                    logger.warning(f"Insufficient balance for user {user_id}")
                    return make_response(jsonify({
                        "error": "Insufficient Balance",
                        "message": "Your API call balance is depleted. Please upgrade your plan for additional calls."
                    }), 402)  # 402 Payment Required
                
                logger.error(f"Balance error for user {user_id}: {result}")
                return make_response(jsonify({
                    "error": "Balance Error",
                    "message": f"Error processing balance: {result}"
                }), 500)

            # Log successful balance deduction
            logger.info(f"Balance successfully deducted for user {user_id}, endpoint {endpoint_id}, cost {endpoint_cost}")
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error in balance middleware: {str(e)}")
            return make_response(jsonify({
                "error": "Balance System Error",
                "message": f"An error occurred: {str(e)}"
            }), 500)

    return decorated_function