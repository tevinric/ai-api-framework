from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.balanceService import BalanceService
from apis.utils.logMiddleware import api_logger
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def check_balance_route():
    """
    Check current API call balance for authenticated user
    ---
    tags:
      - Balance Management
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
    produces:
      - application/json
    responses:
      200:
        description: Current balance retrieved successfully
      401:
        description: Authentication error
      500:
        description: Server error
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)

    # Validate API key
    user_info = DatabaseService.validate_api_key(api_key)
    if not user_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)

    g.user_id = user_info['id']

    try:
        # Get current balance
        balance_info, error = BalanceService.get_current_balance(user_info['id'])
        if error:
            return create_api_response({
                "error": "Balance Error",
                "message": f"Error retrieving balance: {error}"
            }, 500)

        return create_api_response({
            "user_id": user_info['id'],
            "user_email": user_info['user_email'],
            **balance_info
        }, 200)

    except Exception as e:
        logger.error(f"Error checking balance: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error checking balance: {str(e)}"
        }, 500)

def admin_update_balance_route():
    """
    Update user's API call balance (Admin only)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - token
            - user_id
            - new_balance
          properties:
            token:
              type: string
              description: Valid token for verification
            user_id:
              type: string
              description: ID of user to update
            new_balance:
              type: integer
              description: New balance value
    produces:
      - application/json
    responses:
      200:
        description: Balance updated successfully
      401:
        description: Authentication error
      403:
        description: Forbidden - not an admin
      500:
        description: Server error
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)

    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)

    g.user_id = admin_info['id']

    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to update balances"
        }, 403)

    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)

    # Validate token
    token = data.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Valid token is required"
        }, 400)

    # Verify token is valid and not expired
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)

    g.token_id = token_details["id"]

    # Check token expiration
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)

    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)

    # Get required parameters
    user_id = data.get('user_id')
    new_balance = data.get('new_balance')

    if not user_id or new_balance is None:
        return create_api_response({
            "error": "Bad Request",
            "message": "user_id and new_balance are required"
        }, 400)

    try:
        # Update the user's balance
        success, error = BalanceService.update_user_balance(user_id, new_balance)
        if not success:
            return create_api_response({
                "error": "Balance Update Error",
                "message": f"Failed to update balance: {error}"
            }, 500)

        # Get updated balance info
        balance_info, error = BalanceService.get_current_balance(user_id)
        if error:
            return create_api_response({
                "error": "Balance Error",
                "message": f"Balance updated but error retrieving new balance: {error}"
            }, 500)

        return create_api_response({
            "message": "Balance updated successfully",
            "user_id": user_id,
            **balance_info
        }, 200)

    except Exception as e:
        logger.error(f"Error updating balance: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error updating balance: {str(e)}"
        }, 500)

def register_balance_routes(app):
    """Register balance-related routes with the Flask app"""
    app.route('/check-balance', methods=['GET'])(api_logger(check_balance_route))
    app.route('/admin/update-balance', methods=['POST'])(api_logger(admin_update_balance_route))