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

def admin_get_all_model_metadata_route():
    """
    Get all model metadata entries (Admin only endpoint)
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
      - name: active_only
        in: query
        type: boolean
        required: false
        description: Filter to show only active models (default false - shows all)
      - name: family
        in: query
        type: string
        required: false
        description: Filter by model family (e.g., 'OpenAI', 'Meta', 'Mistral')
    produces:
      - application/json
    responses:
      200:
        description: Model metadata retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Model metadata retrieved successfully
            count:
              type: integer
              description: Number of models returned
            models:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  modelName:
                    type: string
                  modelFamily:
                    type: string
                  modelDescription:
                    type: string
                  modelCostIndicator:
                    type: integer
                  promptTokens:
                    type: number
                  completionTokens:
                    type: number
                  cachedTokens:
                    type: number
                  estimateCost:
                    type: number
                  modelInputs:
                    type: string
                  deploymentRegions:
                    type: string
                  supportsMultimodal:
                    type: boolean
                  supportsJsonOutput:
                    type: boolean
                  supportsContextFiles:
                    type: boolean
                  maxContextTokens:
                    type: integer
                  apiEndpoint:
                    type: string
                  isActive:
                    type: boolean
                  created_at:
                    type: string
                  modified_at:
                    type: string
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
            "message": "Admin privileges required to view model metadata"
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
    
    try:
        # Build query based on filters
        base_query = """
        SELECT id, modelName, modelFamily, modelDescription, modelCostIndicator,
               promptTokens, completionTokens, cachedTokens, estimateCost,
               modelInputs, deploymentRegions, supportsMultimodal, 
               supportsJsonOutput, supportsContextFiles, maxContextTokens,
               apiEndpoint, isActive, created_at, modified_at
        FROM model_metadata
        """
        
        conditions = []
        params = []
        
        # Filter by active status
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        if active_only:
            conditions.append("isActive = 1")
        
        # Filter by family
        family = request.args.get('family')
        if family:
            conditions.append("modelFamily = ?")
            params.append(family)
        
        # Add WHERE clause if we have conditions
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        
        base_query += " ORDER BY modelFamily, modelName"
        
        # Execute query
        result = DatabaseService.execute_query(base_query, params if params else None)
        
        if not result['success']:
            logger.error(f"Failed to retrieve model metadata: {result.get('error')}")
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to retrieve model metadata"
            }, 500)
        
        # Format the response
        models = []
        for row in result['data']:
            model = {
                'id': row[0],
                'modelName': row[1],
                'modelFamily': row[2],
                'modelDescription': row[3],
                'modelCostIndicator': row[4],
                'promptTokens': float(row[5]) if row[5] is not None else None,
                'completionTokens': float(row[6]) if row[6] is not None else None,
                'cachedTokens': float(row[7]) if row[7] is not None else None,
                'estimateCost': float(row[8]) if row[8] is not None else None,
                'modelInputs': row[9],
                'deploymentRegions': row[10],
                'supportsMultimodal': bool(row[11]),
                'supportsJsonOutput': bool(row[12]),
                'supportsContextFiles': bool(row[13]),
                'maxContextTokens': row[14],
                'apiEndpoint': row[15],
                'isActive': bool(row[16]),
                'created_at': row[17].isoformat() if row[17] else None,
                'modified_at': row[18].isoformat() if row[18] else None
            }
            models.append(model)
        
        logger.info(f"Retrieved {len(models)} model metadata entries for admin {admin_info['id']}")
        
        return create_api_response({
            "message": "Model metadata retrieved successfully",
            "count": len(models),
            "models": models
        }, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving model metadata: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving model metadata: {str(e)}"
        }, 500)

def admin_get_model_metadata_by_id_route():
    """
    Get specific model metadata by ID (Admin only endpoint)
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
      - name: model_id
        in: query
        type: integer
        required: true
        description: ID of the model metadata to retrieve
    produces:
      - application/json
    responses:
      200:
        description: Model metadata retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Model metadata retrieved successfully
            model:
              type: object
              properties:
                id:
                  type: integer
                modelName:
                  type: string
                modelFamily:
                  type: string
                modelDescription:
                  type: string
                modelCostIndicator:
                  type: integer
                promptTokens:
                  type: number
                completionTokens:
                  type: number
                cachedTokens:
                  type: number
                estimateCost:
                  type: number
                modelInputs:
                  type: string
                deploymentRegions:
                  type: string
                supportsMultimodal:
                  type: boolean
                supportsJsonOutput:
                  type: boolean
                supportsContextFiles:
                  type: boolean
                maxContextTokens:
                  type: integer
                apiEndpoint:
                  type: string
                isActive:
                  type: boolean
                created_at:
                  type: string
                modified_at:
                  type: string
      400:
        description: Bad request
      401:
        description: Authentication error
      403:
        description: Forbidden - not an admin
      404:
        description: Model not found
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
            "message": "Admin privileges required to view model metadata"
        }, 403)
    
    # Get token from query parameter
    token = request.args.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing token parameter"
        }, 400)
    
    # Get model_id from query parameter
    model_id = request.args.get('model_id')
    if not model_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing model_id parameter"
        }, 400)
    
    try:
        model_id = int(model_id)
    except ValueError:
        return create_api_response({
            "error": "Bad Request",
            "message": "model_id must be a valid integer"
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
    
    try:
        # Query for specific model
        query = """
        SELECT id, modelName, modelFamily, modelDescription, modelCostIndicator,
               promptTokens, completionTokens, cachedTokens, estimateCost,
               modelInputs, deploymentRegions, supportsMultimodal, 
               supportsJsonOutput, supportsContextFiles, maxContextTokens,
               apiEndpoint, isActive, created_at, modified_at
        FROM model_metadata
        WHERE id = ?
        """
        
        result = DatabaseService.execute_query(query, (model_id,))
        
        if not result['success']:
            logger.error(f"Failed to retrieve model metadata: {result.get('error')}")
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to retrieve model metadata"
            }, 500)
        
        if not result['data']:
            return create_api_response({
                "error": "Not Found",
                "message": f"Model with ID {model_id} not found"
            }, 404)
        
        # Format the response
        row = result['data'][0]
        model = {
            'id': row[0],
            'modelName': row[1],
            'modelFamily': row[2],
            'modelDescription': row[3],
            'modelCostIndicator': row[4],
            'promptTokens': float(row[5]) if row[5] is not None else None,
            'completionTokens': float(row[6]) if row[6] is not None else None,
            'cachedTokens': float(row[7]) if row[7] is not None else None,
            'estimateCost': float(row[8]) if row[8] is not None else None,
            'modelInputs': row[9],
            'deploymentRegions': row[10],
            'supportsMultimodal': bool(row[11]),
            'supportsJsonOutput': bool(row[12]),
            'supportsContextFiles': bool(row[13]),
            'maxContextTokens': row[14],
            'apiEndpoint': row[15],
            'isActive': bool(row[16]),
            'created_at': row[17].isoformat() if row[17] else None,
            'modified_at': row[18].isoformat() if row[18] else None
        }
        
        logger.info(f"Retrieved model metadata {model_id} for admin {admin_info['id']}")
        
        return create_api_response({
            "message": "Model metadata retrieved successfully",
            "model": model
        }, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving model metadata: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving model metadata: {str(e)}"
        }, 500)

def register_admin_read_model_metadata_routes(app):
    """Register routes with the Flask app"""
    app.route('/admin/model-metadata', methods=['GET'])(api_logger(admin_get_all_model_metadata_route))
    app.route('/admin/model-metadata/detail', methods=['GET'])(api_logger(admin_get_model_metadata_by_id_route))