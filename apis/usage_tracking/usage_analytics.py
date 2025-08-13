from flask import request, g
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.config import create_api_response
import logging
from datetime import datetime, timedelta
import json

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
            
            # Validate token and get user info
            validation_result = token_service.validate_token(token)
            if not validation_result["valid"]:
                return create_api_response({
                    "error": "Authentication Error", 
                    "message": validation_result["message"]
                }, 401)
            
            # Store user info in g for use in the endpoint
            g.user_id = validation_result["user_id"]
            g.token_id = validation_result["token_id"]
            
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
    
    POST /usage_tracking/date_range
    Headers: X-Token: <user_token>
    Body: {
        "start_date": "2024-01-01", 
        "end_date": "2024-01-31"
    }
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
    
    GET /usage_tracking/mtd
    Headers: X-Token: <user_token>
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
    
    POST /usage_tracking/monthly
    Headers: X-Token: <user_token>
    Body: {
        "month": "202401"
    }
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