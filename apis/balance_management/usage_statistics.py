from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import pytz
from datetime import datetime
import calendar
import re

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def usage_by_user_route():
    """
    Get usage statistics for a specific user
    ---
    tags:
      - Balance Management
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
            - user_id
            - time_period
          properties:
            user_id:
              type: string
              description: ID of the user to get statistics for
            time_period:
              type: string
              description: Time period for statistics, either "all" or in format "YYYY-MM"
              example: "2024-03"
    produces:
      - application/json
    responses:
      200:
        description: Usage statistics retrieved successfully
        schema:
          type: object
          properties:
            name:
              type: string
              description: Common name of the user
            user_id:
              type: string
              description: ID of the user
            company:
              type: string
              description: Company name of the user
            department:
              type: string
              description: Department of the user
            tokens_generated:
              type: integer
              description: Number of tokens generated
            endpoints_used:
              type: array
              items:
                type: object
                properties:
                  endpoint_name:
                    type: string
                    description: Name of the endpoint
                  endpoint_id:
                    type: string
                    description: ID of the endpoint
                  number_calls:
                    type: integer
                    description: Total number of calls
                  number_successful_calls:
                    type: integer
                    description: Number of successful calls
                  number_failed_calls:
                    type: integer
                    description: Number of failed calls
                  average_response_time:
                    type: number
                    format: float
                    description: Average response time in milliseconds
                  credits_consumed:
                    type: integer
                    description: Credits consumed by this endpoint
            credits_consumed:
              type: integer
              description: Total credits consumed
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
              example: Missing required fields or Invalid time period format
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
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: You can only view your own usage statistics
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
              example: Error retrieving usage statistics
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
        
    # Set user_id and token_id in request context
    g.user_id = token_details["user_id"]
    g.token_id = token_details["id"]
    
    # Get user ID of authenticated user
    authenticated_user_id = token_details["user_id"]
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['user_id', 'time_period']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    user_id = data.get('user_id')
    time_period = data.get('time_period')
    
    # Check if user_id matches authenticated user, or user is an admin
    if user_id != authenticated_user_id:
        # Check if authenticated user is an admin (scope=0)
        user_info = DatabaseService.get_user_by_id(authenticated_user_id)
        if not user_info or user_info.get('scope') != 0:
            return create_api_response({
                "error": "Forbidden",
                "message": "You can only view your own usage statistics"
            }, 403)
    
    # Validate time_period format
    if time_period != "all" and not re.match(r'^\d{4}-\d{2}$', time_period):
        return create_api_response({
            "error": "Bad Request",
            "message": "Invalid time_period format. Must be 'all' or in format 'YYYY-MM'"
        }, 400)
    
    try:
        # Get user details
        user_details = DatabaseService.get_user_by_id(user_id)
        if not user_details:
            return create_api_response({
                "error": "Not Found",
                "message": f"User with ID {user_id} not found"
            }, 404)
        
        # Get usage statistics
        usage_stats = get_user_usage_statistics(user_id, time_period)
        
        # Prepare response
        response_data = {
            "name": user_details.get("common_name") or user_details.get("user_name"),
            "user_id": user_id,
            "company": user_details.get("company"),
            "department": user_details.get("department"),
            "tokens_generated": usage_stats.get("tokens_generated", 0),
            "endpoints_used": usage_stats.get("endpoints_used", []),
            "credits_consumed": usage_stats.get("credits_consumed", 0)
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving usage statistics: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving usage statistics: {str(e)}"
        }, 500)

def usage_by_department_route():
    """
    Get usage statistics for a department
    ---
    tags:
      - Balance Management
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
            - department
            - time_period
          properties:
            department:
              type: string
              description: Department to get statistics for
            time_period:
              type: string
              description: Time period for statistics, either "all" or in format "YYYY-MM"
              example: "2024-03"
    produces:
      - application/json
    responses:
      200:
        description: Department usage statistics retrieved successfully
        schema:
          type: object
          properties:
            department:
              type: string
              description: Department name
            active_users:
              type: integer
              description: Number of active users in the department
            company:
              type: string
              description: Company name
            tokens_generated:
              type: integer
              description: Total number of tokens generated by the department
            credits_consumed:
              type: number
              format: float
              description: Total credits consumed by the department
            user_consumption:
              type: array
              items:
                type: object
                properties:
                  user:
                    type: string
                    description: User name
                  user_id:
                    type: string
                    description: User ID
                  endpoints_used:
                    type: array
                    items:
                      type: object
                      properties:
                        endpoint_name:
                          type: string
                          description: Name of the endpoint
                        endpoint_id:
                          type: string
                          description: ID of the endpoint
                        number_calls:
                          type: integer
                          description: Total number of calls
                        number_successful_calls:
                          type: integer
                          description: Number of successful calls
                        number_failed_calls:
                          type: integer
                          description: Number of failed calls
                        average_response_time:
                          type: number
                          format: float
                          description: Average response time in milliseconds
                        credits_consumed:
                          type: integer
                          description: Credits consumed by this endpoint
                  credits_consumed:
                    type: integer
                    description: Credits consumed by this user
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
              example: Missing required fields or Invalid time period format
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
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: You can only view statistics for your own department
      404:
        description: Not Found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: Department not found or has no users
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
              example: Error retrieving department statistics
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
        
    # Set user_id and token_id in request context
    g.user_id = token_details["user_id"]
    g.token_id = token_details["id"]
    
    # Get user ID of authenticated user
    authenticated_user_id = token_details["user_id"]
    
    # Get authenticated user's details including department
    authenticated_user = DatabaseService.get_user_by_id(authenticated_user_id)
    if not authenticated_user:
        return create_api_response({
            "error": "Authentication Error",
            "message": "User not found"
        }, 401)
    
    user_department = authenticated_user.get("department")
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['department', 'time_period']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    requested_department = data.get('department')
    time_period = data.get('time_period')
    
    # Check if user is requesting their own department or is an admin
    if requested_department != user_department:
        # Check if authenticated user is an admin (scope=0)
        if authenticated_user.get('scope') != 0:
            return create_api_response({
                "error": "Forbidden",
                "message": "You can only view statistics for your own department"
            }, 403)
    
    # Validate time_period format
    if time_period != "all" and not re.match(r'^\d{4}-\d{2}$', time_period):
        return create_api_response({
            "error": "Bad Request",
            "message": "Invalid time_period format. Must be 'all' or in format 'YYYY-MM'"
        }, 400)
    
    try:
        # Get department statistics
        department_stats = get_department_statistics(requested_department, time_period)
        
        if not department_stats:
            return create_api_response({
                "error": "Not Found",
                "message": f"Department '{requested_department}' not found or has no users"
            }, 404)
        
        return create_api_response(department_stats, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving department statistics: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving department statistics: {str(e)}"
        }, 500)

def get_user_usage_statistics(user_id, time_period):
    """
    Get usage statistics for a specific user and time period
    
    Args:
        user_id (str): UUID of the user
        time_period (str): Time period for statistics, either "all" or in format "YYYY-MM"
        
    Returns:
        dict: Usage statistics including tokens generated, endpoints used, and credits consumed
    """
    conn = None
    cursor = None
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        # Prepare date filter based on time_period
        date_filter = ""
        date_params = []
        
        if time_period != "all":
            # Parse YYYY-MM format
            year, month = map(int, time_period.split('-'))
            
            # Get first and last day of month
            _, last_day = calendar.monthrange(year, month)
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{last_day}"
            
            # Use different column names based on the table
            token_date_filter = "AND (tt.created_at BETWEEN ? AND ?)"
            api_log_date_filter = "AND (al.timestamp BETWEEN ? AND ?)"
            balance_date_filter = "AND (bt.transaction_date BETWEEN ? AND ?)"
            date_params = [start_date, end_date]
        
        # Get tokens generated count
        token_query = f"""
        SELECT COUNT(*) 
        FROM token_transactions tt
        WHERE tt.user_id = ?
        {token_date_filter if time_period != 'all' else ''}
        """
        
        token_params = [user_id] + date_params if time_period != 'all' else [user_id]
        cursor.execute(token_query, token_params)
        tokens_generated = cursor.fetchone()[0]
        
        # Get endpoint usage statistics
        endpoint_query = f"""
        SELECT 
            e.id as endpoint_id,
            e.endpoint_name,
            COUNT(al.id) as number_calls,
            SUM(CASE WHEN al.response_status >= 200 AND al.response_status < 400 THEN 1 ELSE 0 END) as successful_calls,
            SUM(CASE WHEN al.response_status < 200 OR al.response_status >= 400 THEN 1 ELSE 0 END) as failed_calls,
            AVG(CAST(al.response_time_ms as FLOAT)) as avg_response_time,
            SUM(e.cost) as endpoint_credits_consumed
        FROM 
            api_logs al
        JOIN 
            endpoints e ON al.endpoint_id = e.id
        WHERE 
            al.user_id = ?
            {api_log_date_filter if time_period != 'all' else ''}
        GROUP BY 
            e.id, e.endpoint_name
        """
        
        endpoint_params = [user_id] + date_params if time_period != 'all' else [user_id]
        cursor.execute(endpoint_query, endpoint_params)
        endpoint_results = cursor.fetchall()
        
        endpoints_used = []
        for result in endpoint_results:
            endpoints_used.append({
                "endpoint_id": str(result[0]),
                "endpoint_name": result[1],
                "number_calls": result[2],
                "number_successful_calls": result[3],
                "number_failed_calls": result[4],
                "average_response_time": round(result[5], 2) if result[5] is not None else 0,
                "credits_consumed": result[6] if result[6] is not None else 0
            })
        
        # Get credits consumed from balance transactions
        credits_query = f"""
        SELECT 
            SUM(bt.deducted_amount) as total_credits
        FROM 
            balance_transactions bt
        WHERE 
            bt.user_id = ?
            {balance_date_filter if time_period != 'all' else ''}
        """
        
        credits_params = [user_id] + date_params if time_period != 'all' else [user_id]
        cursor.execute(credits_query, credits_params)
        credits_result = cursor.fetchone()
        credits_consumed = credits_result[0] if credits_result[0] is not None else 0
        
        return {
            "tokens_generated": tokens_generated,
            "endpoints_used": endpoints_used,
            "credits_consumed": credits_consumed
        }
        
    except Exception as e:
        logger.error(f"Error in get_user_usage_statistics: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_department_statistics(department, time_period):
    """
    Get usage statistics for a department
    
    Args:
        department (str): Department name
        time_period (str): Time period for statistics, either "all" or in format "YYYY-MM"
        
    Returns:
        dict: Department statistics including active users, tokens generated, endpoints used by users, 
              and credits consumed by department and by each user
    """
    conn = None
    cursor = None
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        # Prepare date filter based on time_period
        date_filter = ""
        date_params = []
        
        if time_period != "all":
            # Parse YYYY-MM format
            year, month = map(int, time_period.split('-'))
            
            # Get first and last day of month
            _, last_day = calendar.monthrange(year, month)
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{last_day}"
            
            date_params = [start_date, end_date]
        
        # Get users in department
        department_users_query = """
        SELECT id, user_name, common_name, company, active
        FROM users
        WHERE department = ? AND active = 1
        """
        
        cursor.execute(department_users_query, [department])
        users = cursor.fetchall()
        
        if not users:
            return None  # Department not found or has no users
        
        # Count active users
        active_users = len(users)
        
        # Get company (assume all users in same department have same company)
        company = users[0][3] if users[0][3] else ""
        
        # Initialize total counters
        total_tokens_generated = 0
        total_credits_consumed = 0
        user_consumption = []
        
        # Process each user
        for user in users:
            user_id = user[0]
            user_name = user[2] if user[2] else user[1]  # Use common_name if available, otherwise user_name
            
            # Get user statistics
            user_stats = get_user_usage_statistics(user_id, time_period)
            
            # Add to department totals
            total_tokens_generated += user_stats.get("tokens_generated", 0)
            total_credits_consumed += user_stats.get("credits_consumed", 0)
            
            # Add user consumption details
            user_consumption.append({
                "user": user_name,
                "user_id": str(user_id),
                "endpoints_used": user_stats.get("endpoints_used", []),
                "credits_consumed": user_stats.get("credits_consumed", 0)
            })
        
        # Prepare response
        department_stats = {
            "department": department,
            "active_users": active_users,
            "company": company,
            "tokens_generated": total_tokens_generated,
            "credits_consumed": total_credits_consumed,
            "user_consumption": user_consumption
        }
        
        return department_stats
        
    except Exception as e:
        logger.error(f"Error in get_department_statistics: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def register_usage_stats_routes(app):
    """Register usage statistics routes with the Flask app"""
    app.route('/usage-by-user', methods=['POST'])(api_logger(usage_by_user_route))
    app.route('/usage-by-department', methods=['POST'])(api_logger(usage_by_department_route))