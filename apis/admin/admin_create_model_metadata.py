from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import uuid
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

from apis.utils.config import create_api_response

def admin_create_model_metadata_route():
    """
    Create a new model metadata entry in the system (Admin only endpoint)
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
            - modelName
            - modelFamily
            - modelDescription
            - modelCostIndicator
          properties:
            modelName:
              type: string
              description: Name of the model (must be unique)
            modelFamily:
              type: string
              description: Model family (e.g., 'OpenAI', 'Meta', 'Mistral')
            modelDescription:
              type: string
              description: Detailed description of the model
            modelCostIndicator:
              type: integer
              description: Cost indicator from 1-5 (1=cheapest, 5=most expensive)
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
              description: Whether model supports multimodal input (default false)
            supportsJsonOutput:
              type: boolean
              description: Whether model supports JSON output (default false)
            supportsContextFiles:
              type: boolean
              description: Whether model supports context files (default false)
            maxContextTokens:
              type: integer
              description: Maximum context window size (optional)
            apiEndpoint:
              type: string
              description: API endpoint reference (optional)
            isActive:
              type: boolean
              description: Whether the model is active (default true)
    produces:
      - application/json
    responses:
      201:
        description: Model metadata created successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Model metadata created successfully
            model_id:
              type: integer
              description: ID of the newly created model metadata
            modelName:
              type: string
              description: Name of the created model
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
              example: Error creating model metadata
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
            "message": "Admin privileges required to create model metadata"
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
    
    # Ensure expiration_time is timezone-aware
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
    
    # Validate required fields
    required_fields = ['modelName', 'modelFamily', 'modelDescription', 'modelCostIndicator']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Validate modelCostIndicator
    cost_indicator = data.get('modelCostIndicator')
    if not isinstance(cost_indicator, int) or not (1 <= cost_indicator <= 5):
        return create_api_response({
            "error": "Bad Request",
            "message": "modelCostIndicator must be an integer between 1 and 5"
        }, 400)
    
    try:
        # Check if model name already exists
        existing_model_query = "SELECT id FROM model_metadata WHERE modelName = ?"
        result = DatabaseService.execute_query(existing_model_query, (data['modelName'],))
        
        if result['success'] and result['data']:
            return create_api_response({
                "error": "Conflict",
                "message": f"Model with name '{data['modelName']}' already exists"
            }, 409)
        
        # Prepare insert query
        insert_query = """
        INSERT INTO model_metadata (
            modelName, modelFamily, modelDescription, modelCostIndicator,
            promptTokens, completionTokens, cachedTokens, estimateCost,
            modelInputs, deploymentRegions, supportsMultimodal, 
            supportsJsonOutput, supportsContextFiles, maxContextTokens,
            apiEndpoint, isActive, created_at, modified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                 DATEADD(HOUR, 2, GETUTCDATE()), DATEADD(HOUR, 2, GETUTCDATE()))
        """
        
        # Prepare values
        values = (
            data['modelName'],
            data['modelFamily'],
            data['modelDescription'],
            data['modelCostIndicator'],
            data.get('promptTokens'),
            data.get('completionTokens'),
            data.get('cachedTokens'),
            data.get('estimateCost'),
            data.get('modelInputs'),
            data.get('deploymentRegions'),
            1 if data.get('supportsMultimodal', False) else 0,
            1 if data.get('supportsJsonOutput', False) else 0,
            1 if data.get('supportsContextFiles', False) else 0,
            data.get('maxContextTokens'),
            data.get('apiEndpoint'),
            1 if data.get('isActive', True) else 0
        )
        
        # Execute insert
        insert_result = DatabaseService.execute_query(insert_query, values)
        
        if not insert_result['success']:
            logger.error(f"Failed to create model metadata: {insert_result.get('error')}")
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to create model metadata"
            }, 500)
        
        # Get the created model ID
        get_id_query = "SELECT id FROM model_metadata WHERE modelName = ?"
        id_result = DatabaseService.execute_query(get_id_query, (data['modelName'],))
        
        model_id = id_result['data'][0][0] if id_result['success'] and id_result['data'] else None
        
        logger.info(f"Model metadata '{data['modelName']}' created successfully by admin {admin_info['id']}")
        
        return create_api_response({
            "message": "Model metadata created successfully",
            "model_id": model_id,
            "modelName": data['modelName']
        }, 201)
        
    except Exception as e:
        logger.error(f"Error creating model metadata: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error creating model metadata: {str(e)}"
        }, 500)

def register_admin_create_model_metadata_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/model-metadata', methods=['POST'])(api_logger(admin_create_model_metadata_route))