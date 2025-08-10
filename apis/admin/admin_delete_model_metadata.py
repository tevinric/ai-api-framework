from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

from apis.utils.config import create_api_response

def admin_delete_model_metadata_route():
    """
    Delete model metadata from the system (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
      - name: token
        in: query
        type: string
        required: true
        description: A valid token for verification
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - id
          properties:
            id:
              type: integer
              description: ID of the model metadata to delete
            soft_delete:
              type: boolean
              description: If true, sets isActive=0 instead of deleting (default false)
    produces:
      - application/json
    responses:
      200:
        description: Model metadata deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Model metadata deleted successfully
            model_id:
              type: integer
              description: ID of the deleted model metadata
            deletion_type:
              type: string
              description: Type of deletion performed (hard or soft)
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
              example: Missing required fields or invalid data
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
              example: Missing API Key header or Invalid API Key
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
              example: Admin privileges required
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
              example: Model metadata not found
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
              example: Error deleting model metadata
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to delete model metadata"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Verify the token is valid
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
    # Check if token is expired
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
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required field
    if 'id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: id"
        }, 400)
    
    model_id = data.get('id')
    soft_delete = data.get('soft_delete', False)
    
    try:
        # Check if model exists
        check_query = "SELECT id, modelName, isActive FROM model_metadata WHERE id = ?"
        check_result = DatabaseService.execute_query(check_query, (model_id,))
        
        if not check_result['success']:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to verify model existence"
            }, 500)
        
        if not check_result['data']:
            return create_api_response({
                "error": "Not Found",
                "message": f"Model with ID {model_id} not found"
            }, 404)
        
        model_name = check_result['data'][0][1]
        current_active_status = check_result['data'][0][2]
        
        if soft_delete:
            # Soft delete - set isActive to 0
            if not current_active_status:
                return create_api_response({
                    "message": "Model metadata already inactive",
                    "model_id": model_id,
                    "deletion_type": "soft"
                }, 200)
            
            update_query = """
            UPDATE model_metadata 
            SET isActive = 0, modified_at = DATEADD(HOUR, 2, GETUTCDATE())
            WHERE id = ?
            """
            
            update_result = DatabaseService.execute_query(update_query, (model_id,))
            
            if not update_result['success']:
                logger.error(f"Failed to soft delete model metadata: {update_result.get('error')}")
                return create_api_response({
                    "error": "Server Error",
                    "message": "Failed to deactivate model metadata"
                }, 500)
            
            deletion_type = "soft"
            logger.info(f"Model metadata {model_id} ({model_name}) soft deleted by admin {admin_info['id']}")
            
        else:
            # Hard delete - actually remove the record
            delete_query = "DELETE FROM model_metadata WHERE id = ?"
            delete_result = DatabaseService.execute_query(delete_query, (model_id,))
            
            if not delete_result['success']:
                logger.error(f"Failed to hard delete model metadata: {delete_result.get('error')}")
                return create_api_response({
                    "error": "Server Error",
                    "message": "Failed to delete model metadata"
                }, 500)
            
            deletion_type = "hard"
            logger.info(f"Model metadata {model_id} ({model_name}) hard deleted by admin {admin_info['id']}")
        
        return create_api_response({
            "message": "Model metadata deleted successfully",
            "model_id": model_id,
            "deletion_type": deletion_type
        }, 200)
        
    except Exception as e:
        logger.error(f"Error deleting model metadata: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error deleting model metadata: {str(e)}"
        }, 500)

def admin_bulk_delete_model_metadata_route():
    """
    Bulk delete multiple model metadata entries (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: Admin API Key for authentication
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
      - name: token
        in: query
        type: string
        required: true
        description: A valid token for verification
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - model_ids
          properties:
            model_ids:
              type: array
              items:
                type: integer
              description: Array of model metadata IDs to delete
            soft_delete:
              type: boolean
              description: If true, sets isActive=0 instead of deleting (default false)
    produces:
      - application/json
    responses:
      200:
        description: Bulk deletion completed
        schema:
          type: object
          properties:
            message:
              type: string
              example: Bulk deletion completed
            deleted_count:
              type: integer
              description: Number of models successfully deleted
            failed_count:
              type: integer
              description: Number of models that failed to delete
            deletion_type:
              type: string
              description: Type of deletion performed (hard or soft)
            deleted_models:
              type: array
              items:
                type: integer
              description: IDs of successfully deleted models
            failed_models:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  reason:
                    type: string
              description: IDs and reasons for failed deletions
      400:
        description: Bad request
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
    
    # Validate API key
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to delete model metadata"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Verify the token is valid
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
    # Check if token is expired
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
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required field
    if 'model_ids' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: model_ids"
        }, 400)
    
    model_ids = data.get('model_ids')
    soft_delete = data.get('soft_delete', False)
    
    if not isinstance(model_ids, list) or not model_ids:
        return create_api_response({
            "error": "Bad Request",
            "message": "model_ids must be a non-empty array of integers"
        }, 400)
    
    try:
        deleted_models = []
        failed_models = []
        
        for model_id in model_ids:
            try:
                # Check if model exists
                check_query = "SELECT id, modelName, isActive FROM model_metadata WHERE id = ?"
                check_result = DatabaseService.execute_query(check_query, (model_id,))
                
                if not check_result['success'] or not check_result['data']:
                    failed_models.append({
                        "id": model_id,
                        "reason": "Model not found"
                    })
                    continue
                
                model_name = check_result['data'][0][1]
                current_active_status = check_result['data'][0][2]
                
                if soft_delete:
                    # Soft delete - set isActive to 0
                    if not current_active_status:
                        # Already inactive, count as successful
                        deleted_models.append(model_id)
                        continue
                    
                    update_query = """
                    UPDATE model_metadata 
                    SET isActive = 0, modified_at = DATEADD(HOUR, 2, GETUTCDATE())
                    WHERE id = ?
                    """
                    
                    update_result = DatabaseService.execute_query(update_query, (model_id,))
                    
                    if update_result['success']:
                        deleted_models.append(model_id)
                        logger.info(f"Model metadata {model_id} ({model_name}) soft deleted by admin {admin_info['id']}")
                    else:
                        failed_models.append({
                            "id": model_id,
                            "reason": "Failed to deactivate model"
                        })
                else:
                    # Hard delete - actually remove the record
                    delete_query = "DELETE FROM model_metadata WHERE id = ?"
                    delete_result = DatabaseService.execute_query(delete_query, (model_id,))
                    
                    if delete_result['success']:
                        deleted_models.append(model_id)
                        logger.info(f"Model metadata {model_id} ({model_name}) hard deleted by admin {admin_info['id']}")
                    else:
                        failed_models.append({
                            "id": model_id,
                            "reason": "Failed to delete model"
                        })
                        
            except Exception as e:
                failed_models.append({
                    "id": model_id,
                    "reason": f"Error: {str(e)}"
                })
        
        deletion_type = "soft" if soft_delete else "hard"
        
        return create_api_response({
            "message": "Bulk deletion completed",
            "deleted_count": len(deleted_models),
            "failed_count": len(failed_models),
            "deletion_type": deletion_type,
            "deleted_models": deleted_models,
            "failed_models": failed_models
        }, 200)
        
    except Exception as e:
        logger.error(f"Error in bulk delete model metadata: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error in bulk delete model metadata: {str(e)}"
        }, 500)

def register_admin_delete_model_metadata_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/model-metadata', methods=['DELETE'])(api_logger(admin_delete_model_metadata_route))
    app.route('/admin/model-metadata/bulk', methods=['DELETE'])(api_logger(admin_bulk_delete_model_metadata_route))