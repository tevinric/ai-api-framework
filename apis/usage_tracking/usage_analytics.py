from flask import request, g
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.config import create_api_response
from flasgger import swag_from
import logging
from datetime import datetime, timedelta
import json
import pytz

# Configure logging
logger = logging.getLogger(__name__)

# Initialize token service
token_service = TokenService()

def token_required_usage(f):
    """
    Decorator for usage tracking endpoints that require token authentication
    """
    from functools import wraps
    
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            # Get token from header
            token = request.headers.get('X-Token')
            if not token:
                return create_api_response({
                    "error": "Authentication Error",
                    "message": "Missing X-Token header"
                }, 401)
            
            # Validate token using DatabaseService (same approach as other endpoints)
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
            
            # Store user info in g for use in the endpoint
            g.user_id = token_details["user_id"]
            g.token_id = token_details["id"]
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return create_api_response({
                "error": "Authentication Error",
                "message": "Token validation failed"
            }, 401)
    
    return decorated

def get_usage_analytics(start_date, end_date, user_id):
    """
    Get usage analytics grouped by model for a date range
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format  
        user_id (str): User ID to get usage for
        
    Returns:
        dict: Usage analytics grouped by model
    """
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        # Query to get usage grouped by model
        query = """
        SELECT 
            COALESCE(model_used, 'unknown') as model,
            COUNT(*) as total_requests,
            SUM(COALESCE(prompt_tokens, 0)) as total_prompt_tokens,
            SUM(COALESCE(completion_tokens, 0)) as total_completion_tokens, 
            SUM(COALESCE(total_tokens, 0)) as total_tokens,
            SUM(COALESCE(cached_tokens, 0)) as total_cached_tokens,
            SUM(COALESCE(audio_seconds_processed, 0)) as total_audio_seconds,
            SUM(COALESCE(images_generated, 0)) as total_images_generated,
            SUM(COALESCE(pages_processed, 0)) as total_pages_processed,
            SUM(COALESCE(documents_processed, 0)) as total_documents_processed,
            SUM(COALESCE(files_uploaded, 0)) as total_files_uploaded
        FROM user_usage 
        WHERE user_id = ? 
        AND CAST(timestamp AS DATE) >= CAST(? AS DATE)
        AND CAST(timestamp AS DATE) <= CAST(? AS DATE)
        GROUP BY model_used
        ORDER BY total_requests DESC
        """
        
        cursor.execute(query, [user_id, start_date, end_date])
        results = cursor.fetchall()
        
        # Format results
        usage_by_model = {}
        totals = {
            "total_requests": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "total_cached_tokens": 0,
            "total_audio_seconds": 0,
            "total_images_generated": 0,
            "total_pages_processed": 0,
            "total_documents_processed": 0,
            "total_files_uploaded": 0
        }
        
        for row in results:
            model = row[0]
            usage_data = {
                "total_requests": row[1],
                "total_prompt_tokens": row[2],
                "total_completion_tokens": row[3],
                "total_tokens": row[4],
                "total_cached_tokens": row[5],
                "total_audio_seconds": float(row[6]) if row[6] else 0.0,
                "total_images_generated": row[7],
                "total_pages_processed": row[8], 
                "total_documents_processed": row[9],
                "total_files_uploaded": row[10]
            }
            
            usage_by_model[model] = usage_data
            
            # Add to totals
            for key in totals:
                if key == "total_audio_seconds":
                    totals[key] += usage_data[key]
                else:
                    totals[key] += usage_data[key] or 0
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "usage_by_model": usage_by_model,
            "totals": totals,
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting usage analytics: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@token_required_usage
def usage_date_range():
    """
    Get usage analytics for a specific date range
    ---
    tags:
      - Usage Tracking
    security:
      - ApiKeyAuth: []
    parameters:
      - in: header
        name: X-Token
        type: string
        required: true
        description: User authentication token
      - in: body
        name: date_range
        required: true
        schema:
          type: object
          properties:
            start_date:
              type: string
              example: "2024-01-01"
              description: Start date in YYYY-MM-DD format
            end_date:
              type: string
              example: "2024-01-31" 
              description: End date in YYYY-MM-DD format
          required:
            - start_date
            - end_date
    responses:
      200:
        description: Usage analytics retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Usage analytics retrieved successfully"
            user_id:
              type: string
              example: "user_123"
            usage_by_model:
              type: object
              description: Usage statistics grouped by model
            totals:
              type: object
              description: Total usage across all models
            date_range:
              type: object
              properties:
                start_date:
                  type: string
                end_date:
                  type: string
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
              example: start_date and end_date are required
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
              example: Missing X-Token header
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return create_api_response({
                "error": "Bad Request",
                "message": "Request body is required"
            }, 400)
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if not start_date or not end_date:
            return create_api_response({
                "error": "Bad Request", 
                "message": "start_date and end_date are required (YYYY-MM-DD format)"
            }, 400)
        
        # Validate date format
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return create_api_response({
                "error": "Bad Request",
                "message": "Invalid date format. Use YYYY-MM-DD"
            }, 400)
        
        print(f"DEBUG: Getting usage analytics for user {g.user_id} from {start_date} to {end_date}")
        
        # Get usage analytics
        result = get_usage_analytics(start_date, end_date, g.user_id)
        
        if not result["success"]:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error retrieving usage data: {result['error']}"
            }, 500)
        
        return create_api_response({
            "message": "Usage analytics retrieved successfully",
            "user_id": g.user_id,
            "usage_by_model": result["usage_by_model"],
            "totals": result["totals"],
            "date_range": result["date_range"]
        }, 200)
        
    except Exception as e:
        logger.error(f"Error in usage_date_range endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

@token_required_usage  
def usage_mtd():
    """
    Get usage analytics for current month-to-date
    ---
    tags:
      - Usage Tracking
    security:
      - ApiKeyAuth: []
    parameters:
      - in: header
        name: X-Token
        type: string
        required: true
        description: User authentication token
    responses:
      200:
        description: MTD usage analytics retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "MTD usage analytics retrieved successfully"
            user_id:
              type: string
              example: "user_123"
            usage_by_model:
              type: object
              description: Usage statistics grouped by model
            totals:
              type: object
              description: Total usage across all models
            date_range:
              type: object
              properties:
                start_date:
                  type: string
                end_date:
                  type: string
            period_type:
              type: string
              example: "MTD"
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
              example: Missing X-Token header
    """
    try:
        # Calculate MTD date range
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        
        print(f"DEBUG: Getting MTD usage analytics for user {g.user_id} from {start_date} to {end_date}")
        
        # Get usage analytics
        result = get_usage_analytics(start_date, end_date, g.user_id)
        
        if not result["success"]:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error retrieving MTD usage data: {result['error']}"
            }, 500)
        
        return create_api_response({
            "message": "MTD usage analytics retrieved successfully",
            "user_id": g.user_id,
            "usage_by_model": result["usage_by_model"],
            "totals": result["totals"],
            "date_range": result["date_range"],
            "period_type": "MTD"
        }, 200)
        
    except Exception as e:
        logger.error(f"Error in usage_mtd endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing MTD request: {str(e)}"
        }, 500)

@token_required_usage
def usage_monthly():
    """
    Get usage analytics for a specific month (YYYYMM format)
    ---
    tags:
      - Usage Tracking
    security:
      - ApiKeyAuth: []
    parameters:
      - in: header
        name: X-Token
        type: string
        required: true
        description: User authentication token
      - in: body
        name: month_data
        required: true
        schema:
          type: object
          properties:
            month:
              type: string
              example: "202401"
              description: Month in YYYYMM format
          required:
            - month
    responses:
      200:
        description: Monthly usage analytics retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Usage analytics for 202401 retrieved successfully"
            user_id:
              type: string
              example: "user_123"
            usage_by_model:
              type: object
              description: Usage statistics grouped by model
            totals:
              type: object
              description: Total usage across all models
            date_range:
              type: object
              properties:
                start_date:
                  type: string
                end_date:
                  type: string
            period_type:
              type: string
              example: "Monthly"
            month:
              type: string
              example: "202401"
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
              example: Invalid month format. Use YYYYMM (e.g., 202401)
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
              example: Missing X-Token header
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return create_api_response({
                "error": "Bad Request",
                "message": "Request body is required"
            }, 400)
        
        month = data.get('month')
        if not month:
            return create_api_response({
                "error": "Bad Request",
                "message": "month is required (YYYYMM format)"
            }, 400)
        
        # Validate month format
        try:
            if len(month) != 6 or not month.isdigit():
                raise ValueError("Invalid format")
            
            year = int(month[:4])
            month_num = int(month[4:6])
            
            if month_num < 1 or month_num > 12:
                raise ValueError("Invalid month")
            
            # Calculate date range for the month
            start_date = datetime(year, month_num, 1).strftime('%Y-%m-%d')
            
            # Get last day of month
            if month_num == 12:
                next_month = datetime(year + 1, 1, 1)
            else:
                next_month = datetime(year, month_num + 1, 1)
            
            last_day = next_month - timedelta(days=1)
            end_date = last_day.strftime('%Y-%m-%d')
            
        except ValueError:
            return create_api_response({
                "error": "Bad Request",
                "message": "Invalid month format. Use YYYYMM (e.g., 202401)"
            }, 400)
        
        print(f"DEBUG: Getting usage analytics for user {g.user_id} for month {month} ({start_date} to {end_date})")
        
        # Get usage analytics
        result = get_usage_analytics(start_date, end_date, g.user_id)
        
        if not result["success"]:
            return create_api_response({
                "error": "Server Error", 
                "message": f"Error retrieving monthly usage data: {result['error']}"
            }, 500)
        
        return create_api_response({
            "message": f"Usage analytics for {month} retrieved successfully",
            "user_id": g.user_id,
            "usage_by_model": result["usage_by_model"],
            "totals": result["totals"], 
            "date_range": result["date_range"],
            "period_type": "Monthly",
            "month": month
        }, 200)
        
    except Exception as e:
        logger.error(f"Error in usage_monthly endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing monthly request: {str(e)}"
        }, 500)

def register_usage_tracking_routes(app):
    """Register usage tracking routes"""
    
    app.add_url_rule('/usage_tracking/date_range', 
                     'usage_date_range', 
                     usage_date_range, 
                     methods=['POST'])
                     
    app.add_url_rule('/usage_tracking/mtd',
                     'usage_mtd', 
                     usage_mtd,
                     methods=['GET'])
                     
    app.add_url_rule('/usage_tracking/monthly',
                     'usage_monthly',
                     usage_monthly, 
                     methods=['POST'])