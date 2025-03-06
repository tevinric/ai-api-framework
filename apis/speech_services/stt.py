from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
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

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def transcribe_audio(file_url, diarization=False, south_african=True):
    """
    Transcribe audio using Microsoft Speech to Text API
    
    Args:
        file_url (str): URL to the audio file in blob storage
        diarization (bool): Whether to enable speaker diarization
        south_african (bool): Whether to optimize for South African languages
        
    Returns:
        tuple: (transcription_result, error)
    """
    headers = {
        "Ocp-Apim-Subscription-Key": STT_API_KEY,
        "Accept": "application/json"
    }
    
    # Set up options for transcription
    options = {
        "profanityFilterMode": "Masked",
        "locales": ["en-US"]  # Default locale, will be overridden for South African option
    }
    
    # Add speaker diarization if requested
    if diarization:
        options["diarizationEnabled"] = True
    
    # Configure for South African languages if requested
    if south_african:
        # South African languages with Microsoft Speech API codes
        options["locales"] = ["en-ZA"]  # Primary locale for South Africa
        
        # Add language identification to handle multiple South African languages
        options["languageIdentification"] = {
            "candidateLocales": [
                "en-ZA",  # South African English
                "af-ZA",  # Afrikaans
                "zu-ZA",  # Zulu
                "xh-ZA",  # Xhosa
                "en-US"   # Fallback to US English
            ]
        }
    
    # Convert options to JSON
    definition = json.dumps(options)
    
    logger.info(f"Transcription options: {definition}")

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
            diarization:
              type: boolean
              description: Enable speaker diarization (identify different speakers)
              default: false
            south_african:
              type: boolean
              description: Optimize for South African languages
              default: true
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
            settings:
              type: object
              properties:
                diarization:
                  type: boolean
                south_african:
                  type: boolean
              description: Settings used for the transcription
            transcription_details:
              type: object
              description: Full details of the transcription results
      400:
        description: Bad request
      401:
        description: Authentication error
      404:
        description: File not found
      500:
        description: Server error
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
    
    # Get optional parameters with defaults
    diarization = data.get('diarization', False)
    south_african = data.get('south_african', True)
    
    try:
        # Get file URL from file-upload system
        file_url_response = requests.post(
            f"{request.url_root.rstrip('/')}/get-file-url",
            headers={"X-Token": token},
            json={"file_id": file_id}
        )
        
        if file_url_response.status_code != 200:
            return create_api_response({
                "error": "File Error",
                "message": f"Error retrieving file URL: {file_url_response.json().get('message', 'Unknown error')}"
            }, file_url_response.status_code)
        
        file_info = file_url_response.json()
        file_url = file_info.get('file_url')
        
        if not file_url:
            return create_api_response({
                "error": "File Error",
                "message": "File URL not found in response"
            }, 500)
        
        # Transcribe the audio file with the simplified options
        transcription_result, error = transcribe_audio(file_url, diarization, south_african)
        
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
        
        # Delete the uploaded file to avoid storage bloat
        delete_response = requests.delete(
            f"{request.url_root.rstrip('/')}/delete-file",
            headers={"X-Token": token},
            json={"file_id": file_id}
        )
        
        if delete_response.status_code != 200:
            logger.warning(f"Failed to delete uploaded file {file_id}: {delete_response.text}")
        
        # Prepare the response
        response_data = {
            "message": "Audio transcribed successfully",
            "transcript": transcript,
            "settings": {
                "diarization": diarization,
                "south_african": south_african
            },
            "transcription_details": transcription_result
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error in speech to text endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

def register_speech_to_text_routes(app):
    """Register speech to text routes with the Flask app"""
    app.route('/speech/stt', methods=['POST'])(api_logger(check_balance(speech_to_text_route)))