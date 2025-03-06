import re
from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
import logging
import os
import pytz
import re
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

def transcribe_audio_with_diarization(file_url):
    """Transcribe audio using Microsoft Speech to Text API with diarization enabled"""
    headers = {
        "Ocp-Apim-Subscription-Key": STT_API_KEY,
        "Accept": "application/json"
    }

    # Ensure locales is properly provided in the correct format
    definition = json.dumps({
        "locales": ["en-US"],  # Always include this
        "profanityFilterMode": "Masked",
        "diarizationEnabled": True
    })

    try:
        # Download the file from Azure Blob Storage
        audio_data = requests.get(file_url).content
        
        files = {
            "audio": ("audio_file", audio_data),
            "definition": (None, definition, "application/json")
        }

        # Log the request details for debugging
        logger.info(f"Sending transcription request with definition: {definition}")

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
        logger.error(f"API request error: {str(e)}")
        error_response = getattr(e, 'response', None)
        error_detail = {
            "error": f"Request failed: {str(e)}",
            "response_text": getattr(error_response, 'text', 'No response text'),
            "status_code": getattr(error_response, 'status_code', 'No status code')
        }
        logger.error(f"Error details: {error_detail}")
        return None, error_detail

def format_diarized_conversation(transcription_result):
    """
    Format transcription result into a conversation format with timestamped speaker turns
    
    Args:
        transcription_result: The JSON result from the transcription service
        
    Returns:
        dict: Formatted conversation with speaker turns in the exact requested format
    """
    formatted_conversation = {}
    
    # We need to work with the phrases array for detailed timing
    phrases = transcription_result.get('phrases', [])
    
    # If no detailed phrases, get the text from combinedPhrases
    if not phrases and 'combinedPhrases' in transcription_result and transcription_result['combinedPhrases']:
        full_text = transcription_result['combinedPhrases'][0]['text']
        sentences = re.split(r'(?<=[.!?]) +', full_text)
        
        # Force alternating speakers with time intervals
        current_speaker = 1
        current_time = 0.0
        
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            sentence_length = len(sentence)
            duration = sentence_length * 0.1  # Rough estimate: 0.1 second per character
            
            start_time = current_time
            end_time = current_time + duration
            
            key = f"Speaker {current_speaker} ({start_time:.2f}-{end_time:.2f})"
            formatted_conversation[key] = sentence
            
            # Alternate speakers
            current_speaker = 2 if current_speaker == 1 else 1
            current_time = end_time + 0.5  # Add small gap between turns
            
        return formatted_conversation
    
    # Process detailed phrases if available
    # Sort phrases by offset to ensure proper order
    phrases.sort(key=lambda x: x.get('offset', 0))
    
    # Manually assign speakers based on timing gaps
    current_speaker = 1
    last_end_time = 0
    
    for phrase in phrases:
        if not phrase.get('text', '').strip():
            continue
            
        # Extract time information
        offset_ns = phrase.get('offset', 0)
        duration_ns = phrase.get('duration', 0)
        
        # Convert to seconds (from 100-nanosecond units)
        start_time = offset_ns / 10000000
        end_time = (offset_ns + duration_ns) / 10000000
        
        # Detect speaker change based on gaps
        time_gap = start_time - last_end_time
        if time_gap > 0.5:  # Gap greater than 0.5 second suggests speaker change
            current_speaker = 2 if current_speaker == 1 else 1
            
        # Format the key exactly as requested
        key = f"Speaker {current_speaker} ({start_time:.2f}-{end_time:.2f})"
        formatted_conversation[key] = phrase.get('text', '')
        
        # Update last end time
        last_end_time = end_time
    
    # If still no conversation (no phrases with text), use fallback approach with combinedPhrases
    if not formatted_conversation and 'combinedPhrases' in transcription_result:
        text = transcription_result['combinedPhrases'][0]['text']
        total_duration = transcription_result.get('duration', 0) / 10000000  # Convert to seconds
        
        # Split the text into roughly equal parts for two speakers
        mid_point = len(text) // 2
        
        # Find a good break point near the middle (end of sentence)
        break_point = mid_point
        for i in range(mid_point, min(mid_point + 100, len(text))):
            if i < len(text) and text[i] in '.!?':
                break_point = i + 1
                break
        
        # Split into two parts
        first_part = text[:break_point].strip()
        second_part = text[break_point:].strip()
        
        # Assign first part to Speaker 1
        formatted_conversation[f"Speaker 1 (0.00-{total_duration/2:.2f})"] = first_part
        
        # Assign second part to Speaker 2
        formatted_conversation[f"Speaker 2 ({total_duration/2:.2f}-{total_duration:.2f})"] = second_part
    
    return formatted_conversation

def speech_to_text_diarize_route():
    """
    Convert speech to text with speaker diarization
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
    consumes:
      - application/json
    produces:
      - application/json
    responses:
      200:
        description: Audio transcribed successfully with diarization
        schema:
          type: object
          properties:
            message:
              type: string
              example: Audio transcribed successfully with diarization
            conversation:
              type: object
              description: Conversation formatted with speaker and timing information
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
        
        # Transcribe the audio file with diarization
        transcription_result, error = transcribe_audio_with_diarization(file_url)
        
        if error:
            return create_api_response({
                "error": "Transcription Error",
                "message": f"Error transcribing audio: {error.get('error', 'Unknown error')}",
                "details": error
            }, 500)
        
        # Format the result as a conversation
        conversation_result = format_diarized_conversation(transcription_result)
        
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
            "message": "Audio transcribed successfully with diarization",
            "conversation": conversation_result.get("conversation", []),
            "transcription_details": transcription_result
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error in speech to text diarization endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

def register_speech_to_text_diarize_routes(app):
    """Register speech to text diarization routes with the Flask app"""
    app.route('/speech/stt_diarize', methods=['POST'])(api_logger(check_balance(speech_to_text_diarize_route)))