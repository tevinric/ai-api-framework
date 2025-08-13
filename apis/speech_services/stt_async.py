from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.jobs.job_service import JobService
import logging
import os
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

from apis.utils.config import create_api_response

def submit_stt_job_route():
    """
    Submit a speech-to-text job for asynchronous processing
    ---
    tags:
      - Speech Services
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - file_id
          properties:
            file_id:
              type: string
              description: ID of the uploaded audio file
    consumes:
      - application/json
    produces:
      - application/json
    responses:
      202:
        description: Job submitted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Speech-to-text job submitted successfully
            job_id:
              type: string
              example: 12345678-1234-1234-1234-123456789012
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
              enum: [Request body is required, file_id is required]
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
              enum: [Missing X-Token header, Invalid token, Token has expired]
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              enum: [Server Error, Job Creation Error]
            message:
              type: string
              example: Error processing request
    """
    # Get token from X-Token header
    token = request.headers.get('X-Token')
    if not token:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing X-Token header"
        }, 401)
    
    # Validate token and get token details
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
        
    g.user_id = token_details["user_id"]
    g.token_id = token_details["id"]
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Get required parameters
    file_id = data.get('file_id')
    if not file_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "file_id is required"
        }, 400)
    
    try:
        # Get endpoint ID for tracking
        endpoint_id = DatabaseService.get_endpoint_id_by_path('/speech/stt')
        
        # Create a new job
        job_id, error = JobService.create_job(
            user_id=g.user_id, 
            job_type='stt', 
            file_id=file_id,
            parameters={'token_id': g.token_id},
            endpoint_id=endpoint_id
        )
        
        if error:
            return create_api_response({
                "error": "Job Creation Error",
                "message": f"Error creating job: {error}"
            }, 500)
        
        # Return the job ID immediately
        return create_api_response({
            "message": "Speech-to-text job submitted successfully",
            "job_id": job_id
        }, 202)  # 202 Accepted status code for async processing
        
    except Exception as e:
        logger.error(f"Error in submit STT job endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

def submit_stt_diarize_job_route():
    """
    Submit a speech-to-text with diarization job for asynchronous processing
    ---
    tags:
      - Speech Services
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - file_id
          properties:
            file_id:
              type: string
              description: ID of the uploaded audio file
    consumes:
      - application/json
    produces:
      - application/json
    responses:
      202:
        description: Job submitted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Speech-to-text diarization job submitted successfully
            job_id:
              type: string
              example: 12345678-1234-1234-1234-123456789012
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
              enum: [Request body is required, file_id is required]
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
              enum: [Missing X-Token header, Invalid token, Token has expired]
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              enum: [Server Error, Job Creation Error]
            message:
              type: string
              example: Error processing request
    """
    # Get token from X-Token header
    token = request.headers.get('X-Token')
    if not token:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing X-Token header"
        }, 401)
    
    # Validate token and get token details
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
        
    g.user_id = token_details["user_id"]
    g.token_id = token_details["id"]
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Get required parameters
    file_id = data.get('file_id')
    if not file_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "file_id is required"
        }, 400)
    
    try:
        # Get endpoint ID for tracking
        endpoint_id = DatabaseService.get_endpoint_id_by_path('/speech/stt_diarize')
        
        # Create a new job
        job_id, error = JobService.create_job(
            user_id=g.user_id, 
            job_type='stt_diarize', 
            file_id=file_id,
            parameters={'token_id': g.token_id, 'token_value': token},
            endpoint_id=endpoint_id
        )
        
        if error:
            return create_api_response({
                "error": "Job Creation Error",
                "message": f"Error creating job: {error}"
            }, 500)
        
        # Return the job ID immediately
        return create_api_response({
            "message": "Speech-to-text diarization job submitted successfully",
            "job_id": job_id
        }, 202)  # 202 Accepted status code for async processing
        
    except Exception as e:
        logger.error(f"Error in submit STT diarize job endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

def register_async_speech_to_text_routes(app):
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    """Register async speech to text routes with the Flask app"""
    # Submit endpoints (replacing the original synchronous ones)
    app.route('/speech/stt', methods=['POST'])(track_usage(api_logger(check_endpoint_access(check_balance(submit_stt_job_route)))))
    app.route('/speech/stt_diarize', methods=['POST'])(track_usage(api_logger(check_endpoint_access(check_balance(submit_stt_diarize_job_route)))))
