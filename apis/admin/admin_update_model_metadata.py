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

def admin_update_model_metadata_route():
    """
    Update existing model metadata (Admin only endpoint)
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
              description: ID of the model metadata to update
            modelName:
              type: string
              description: Name of the model (optional)
            modelFamily:
              type: string
              description: Model family (optional)
            modelDescription:
              type: string
              description: Detailed description of the model (optional)
            modelCostIndicator:
              type: integer
              description: Cost indicator from 1-5 (optional)
            promptTokens:
              type: number
              format: float
              description: Cost per 1M prompt tokens (optional)
            completionTokens:
              type: number
              format: float
              description: Cost per 1M completion tokens (optional)
            cachedTokens:
              type: number
              format: float
              description: Cost per 1M cached tokens (optional)
            estimateCost:
              type: number
              format: float
              description: Estimated cost per 1M tokens (optional)
            modelInputs:
              type: string
              description: Comma-separated list of supported inputs (optional)
            deploymentRegions:
              type: string
              description: Comma-separated list of deployment regions (optional)
            supportsMultimodal:
              type: boolean
              description: Whether model supports multimodal input (optional)
            supportsJsonOutput:
              type: boolean
              description: Whether model supports JSON output (optional)
            supportsContextFiles:
              type: boolean
              description: Whether model supports context files (optional)
            maxContextTokens:
              type: integer
              description: Maximum context window size (optional)
            apiEndpoint:
              type: string
              description: API endpoint reference (optional)
            isActive:
              type: boolean
              description: Whether the model is active (optional)
    produces:
      - application/json
    responses:
      200:
        description: Model metadata updated successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Model metadata updated successfully
            model_id:
              type: integer
              description: ID of the updated model metadata
            updated_fields:
              type: array
              items:
                type: string
              description: List of fields that were updated
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
      409:
        description: Conflict
        schema:
          type: object
          properties:
            error:
              type: string
              example: Conflict
            message:
              type: string
              example: Model name already exists
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
              example: Error updating model metadata
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
            "message": "Admin privileges required to update model metadata"
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
    
    try:
        # Check if model exists
        check_query = "SELECT id, modelName FROM model_metadata WHERE id = ?"
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
        
        current_model_name = check_result['data'][0][1]
        
        # Build update query dynamically
        update_fields = []
        update_values = []
        updated_field_names = []
        
        # List of valid fields that can be updated
        valid_fields = {
            'modelName': 'modelName',
            'modelFamily': 'modelFamily', 
            'modelDescription': 'modelDescription',
            'modelCostIndicator': 'modelCostIndicator',
            'promptTokens': 'promptTokens',
            'completionTokens': 'completionTokens',
            'cachedTokens': 'cachedTokens',
            'estimateCost': 'estimateCost',
            'modelInputs': 'modelInputs',
            'deploymentRegions': 'deploymentRegions',
            'supportsMultimodal': 'supportsMultimodal',
            'supportsJsonOutput': 'supportsJsonOutput',
            'supportsContextFiles': 'supportsContextFiles',
            'maxContextTokens': 'maxContextTokens',
            'apiEndpoint': 'apiEndpoint',
            'isActive': 'isActive'
        }
        
        for field, db_field in valid_fields.items():
            if field in data:
                # Special validation for modelCostIndicator
                if field == 'modelCostIndicator':
                    cost_indicator = data[field]
                    if not isinstance(cost_indicator, int) or not (1 <= cost_indicator <= 5):
                        return create_api_response({
                            "error": "Bad Request",
                            "message": "modelCostIndicator must be an integer between 1 and 5"
                        }, 400)
                
                # Special validation for modelName uniqueness
                if field == 'modelName' and data[field] != current_model_name:
                    name_check_query = "SELECT id FROM model_metadata WHERE modelName = ? AND id != ?"
                    name_check_result = DatabaseService.execute_query(name_check_query, (data[field], model_id))
                    
                    if name_check_result['success'] and name_check_result['data']:
                        return create_api_response({
                            "error": "Conflict",
                            "message": f"Model with name '{data[field]}' already exists"
                        }, 409)
                
                # Convert boolean fields for SQL Server
                if field in ['supportsMultimodal', 'supportsJsonOutput', 'supportsContextFiles', 'isActive']:
                    update_fields.append(f"{db_field} = ?")
                    update_values.append(1 if data[field] else 0)
                else:
                    update_fields.append(f"{db_field} = ?")
                    update_values.append(data[field])
                
                updated_field_names.append(field)
        
        if not update_fields:
            return create_api_response({
                "message": "No fields to update",
                "model_id": model_id
            }, 200)
        
        # Add modified timestamp
        update_fields.append("modified_at = DATEADD(HOUR, 2, GETUTCDATE())")
        
        # Build and execute update query
        update_query = f"UPDATE model_metadata SET {', '.join(update_fields)} WHERE id = ?"
        update_values.append(model_id)
        
        update_result = DatabaseService.execute_query(update_query, update_values)
        
        if not update_result['success']:
            logger.error(f"Failed to update model metadata: {update_result.get('error')}")
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to update model metadata"
            }, 500)
        
        logger.info(f"Model metadata {model_id} updated successfully by admin {admin_info['id']}")
        
        return create_api_response({
            "message": "Model metadata updated successfully",
            "model_id": model_id,
            "updated_fields": updated_field_names
        }, 200)
        
    except Exception as e:
        logger.error(f"Error updating model metadata: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error updating model metadata: {str(e)}"
        }, 500)

def register_admin_update_model_metadata_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/model-metadata', methods=['PUT'])(api_logger(admin_update_model_metadata_route))