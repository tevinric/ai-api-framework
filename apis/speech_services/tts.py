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

def submit_tts_job_route():
    """
    Submit a text-to-speech job for asynchronous processing
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
            - text
          properties:
            text:
              type: string
              description: Text to convert to speech
              example: "Hello, this is a text-to-speech conversion."
            voice_name:
              type: string
              description: Voice name to use for synthesis (optional)
              example: "en-US-JennyNeural"
              default: "en-US-JennyNeural"
            output_format:
              type: string
              description: Audio output format (optional)
              example: "audio-16khz-32kbitrate-mono-mp3"
              default: "audio-16khz-32kbitrate-mono-mp3"
              enum: [
                "audio-16khz-32kbitrate-mono-mp3",
                "audio-16khz-128kbitrate-mono-mp3",
                "riff-16khz-16bit-mono-pcm",
                "riff-22050hz-16bit-mono-pcm",
                "riff-24khz-16bit-mono-pcm"
              ]
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
              example: Text-to-speech job submitted successfully
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
              enum: [Request body is required, text is required, Text exceeds maximum length of 10000 characters]
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
    text = data.get('text')
    if not text:
        return create_api_response({
            "error": "Bad Request",
            "message": "text is required"
        }, 400)
    
    # Validate text length (Azure Speech Service has limits)
    if len(text) > 10000:  # 10,000 character limit
        return create_api_response({
            "error": "Bad Request",
            "message": "Text exceeds maximum length of 10000 characters"
        }, 400)
    
    # Get optional parameters with defaults
    voice_name = data.get('voice_name', 'en-US-JennyNeural')
    output_format = data.get('output_format', 'audio-16khz-32kbitrate-mono-mp3')
    
    # Validate output format
    valid_formats = [
        'audio-16khz-32kbitrate-mono-mp3',
        'audio-16khz-128kbitrate-mono-mp3',
        'riff-16khz-16bit-mono-pcm',
        'riff-22050hz-16bit-mono-pcm',
        'riff-24khz-16bit-mono-pcm'
    ]
    
    if output_format not in valid_formats:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Invalid output_format. Must be one of: {', '.join(valid_formats)}"
        }, 400)
    
    try:
        # Get endpoint ID for tracking
        endpoint_id = DatabaseService.get_endpoint_id_by_path('/speech/tts')
        
        # Prepare job parameters
        job_parameters = {
            'text': text,
            'voice_name': voice_name,
            'output_format': output_format,
            'token_id': g.token_id
        }
        
        # Create a new job
        job_id, error = JobService.create_job(
            user_id=g.user_id, 
            job_type='tts', 
            file_id=None,  # No input file for TTS
            parameters=job_parameters,
            endpoint_id=endpoint_id
        )
        
        if error:
            return create_api_response({
                "error": "Job Creation Error",
                "message": f"Error creating job: {error}"
            }, 500)
        
        # Return the job ID immediately
        return create_api_response({
            "message": "Text-to-speech job submitted successfully",
            "job_id": job_id
        }, 202)  # 202 Accepted status code for async processing
        
    except Exception as e:
        logger.error(f"Error in submit TTS job endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

def register_text_to_speech_routes(app):
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    """Register text to speech routes with the Flask app"""
    app.route('/speech/tts', methods=['POST'])(track_usage(api_logger(check_endpoint_access(check_balance(submit_tts_job_route)))))
