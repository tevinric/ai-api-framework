from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.utils.fileService import FileService  # Import FileService
import logging
import os
import pytz
from datetime import datetime
import requests
import json
import uuid

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

# Speech to Text API configuration
STT_API_KEY = os.environ.get("MS_STT_API_KEY")
STT_ENDPOINT = os.environ.get("MS_STT_ENDPOINT")

from apis.utils.config import create_api_response

def transcribe_audio(file_url):
    """Transcribe audio using Microsoft Speech to Text API"""
    headers = {
        "Ocp-Apim-Subscription-Key": STT_API_KEY,
        "Accept": "application/json"
    }

    definition = json.dumps({
        "locales": ["en-US"],
        "profanityFilterMode": "Masked",
        "channels": []
    })

    try:
        # Download the file from Azure Blob Storage
        audio_data = requests.get(file_url).content
        
        files = {
            "audio": ("audio_file", audio_data),
            "definition": (None, definition, "application/json")
        }

        # Call Microsoft Speech to Text API
        response = requests.post(STT_ENDPOINT, headers=headers, files=files)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Try to parse JSON, but have a fallback for non-JSON responses
        try:
            return response.json(), None
        except json.JSONDecodeError:
            return None, {
                "error": "Response was not in JSON format",
                "response_text": response.text,
                "status_code": response.status_code
            }
    
    except requests.RequestException as e:
        return None, {
            "error": f"Request failed: {str(e)}",
            "response_text": getattr(e.response, 'text', None),
            "status_code": getattr(e.response, 'status_code', None)
        }

def calculate_audio_duration(transcription_result):
    """
    Calculate the total audio duration in seconds from the transcription result
    
    The Microsoft Speech API returns duration in milliseconds
    """
    try:
        # Check if duration is directly available in milliseconds
        if 'durationMilliseconds' in transcription_result:
            # Convert milliseconds to seconds
            return transcription_result['durationMilliseconds'] / 1000.0

        # If all else fails, return a default value
        return 0
            
    except Exception as e:
        logger.error(f"Error calculating audio duration: {str(e)}")
        return 0

def speech_to_text_route():
    """
    Convert speech to text using Microsoft Speech to Text API
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
      200:
        description: Audio transcribed successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Audio transcribed successfully
            transcript:
              type: string
              description: Transcript text
              example: This is the transcribed text from the audio file.
            transcription_details:
              type: object
              description: Full details of the transcription results
              properties:
                combinedPhrases:
                  type: array
                  items:
                    type: object
                    properties:
                      text:
                        type: string
                        example: This is the transcribed text from the audio file.
                duration:
                  type: number
                  description: Duration in milliseconds
                  example: 45600
            seconds_processed:
              type: number
              description: Duration of the processed audio in seconds
              example: 45.6
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
      404:
        description: File not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: File Error
            message:
              type: string
              example: File not found
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              enum: [Server Error, File Error, Transcription Error]
            message:
              type: string
              example: Error processing request
            details:
              type: object
              description: Additional error details if available
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
        # Get file URL using FileService directly
        file_info, error = FileService.get_file_url(file_id, g.user_id)
        if error:
            return create_api_response({
                "error": "File Error",
                "message": f"Error retrieving file URL: {error}"
            }, 404 if "not found" in error.lower() else 500)
            
        file_url = file_info.get('file_url')
        
        if not file_url:
            return create_api_response({
                "error": "File Error",
                "message": "File URL not found"
            }, 500)
        
        # Transcribe the audio file
        
        transcription_result, error = transcribe_audio(file_url)
        logger.info(f"The result is: {transcription_result}")

        if error:
            return create_api_response({
                "error": "Transcription Error",
                "message": f"Error transcribing audio: {error.get('error', 'Unknown error')}",
                "details": error
            }, 500)
        
        # Extract the transcript text
        if 'combinedPhrases' in transcription_result and transcription_result['combinedPhrases']:
            transcript = transcription_result["combinedPhrases"][0]["text"]
        else:
            transcript = "No transcript available"
        
        # Calculate the duration of the audio file
        seconds_processed = calculate_audio_duration(transcription_result)
        
        # Delete the uploaded file to avoid storage bloat using FileService directly
        success, message = FileService.delete_file(file_id, g.user_id)
        if not success:
            logger.warning(f"Failed to delete uploaded file {file_id}: {message}")
        
        # Prepare the response
        response_data = {
            "message": "Audio transcribed successfully",
            "transcript": transcript,
            "transcription_details": transcription_result,
            "seconds_processed": seconds_processed,
            "model_used": "ms_stt"
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error in speech to text endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

def register_speech_to_text_routes(app):
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    """Register speech to text routes with the Flask app"""
    app.route('/speech/stt', methods=['POST'])(track_usage(api_logger(check_endpoint_access(check_balance(speech_to_text_route)))))
