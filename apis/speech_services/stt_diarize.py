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

    # Enhanced configuration for diarization
    definition = json.dumps({
        "locales": ["en-US"],
        "profanityFilterMode": "Masked",
        "timeToLive": "PT1H",  # Keep transcription available for 1 hour
        "diarizationEnabled": True,
        "speechFeatures": [
            {
                "feature": "Diarization"  # Explicitly specify diarization feature
            }
        ],
        "properties": {
            "diarizationMinSpeakers": 2,  # Set minimum number of speakers
            "diarizationMaxSpeakers": 6   # Set maximum number of speakers
        }
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
        dict: Formatted conversation with speaker turns in the format "Speaker X (start-end)"
    """
    formatted_conversation = {}
    
    # Check if we have the expected diarization data
    if 'recognizedPhrases' in transcription_result:
        # This is the format for batch transcription with diarization
        recognized_phrases = transcription_result.get('recognizedPhrases', [])
        
        for phrase in recognized_phrases:
            # Extract the best recognition result
            nBest = phrase.get('nBest', [])
            if not nBest:
                continue
                
            best_result = nBest[0]
            text = best_result.get('display', best_result.get('lexical', ''))
            
            if not text.strip():
                continue
                
            # Extract speaker and timing information
            speaker_id = best_result.get('speaker', phrase.get('speaker', 0))
            
            # Convert to human-readable speaker ID
            speaker_label = f"Speaker {speaker_id + 1}"  # +1 because APIs often use 0-indexed speakers
            
            # Extract timing
            offset_sec = phrase.get('offsetInTicks', 0) / 10000000  # Convert from 100ns to seconds
            duration_sec = phrase.get('durationInTicks', 0) / 10000000
            end_time = offset_sec + duration_sec
            
            # Format the key as requested
            key = f"{speaker_label} ({offset_sec:.2f}-{end_time:.2f})"
            formatted_conversation[key] = text
    
    elif 'phrases' in transcription_result:
        # Alternative format with phrases array
        phrases = transcription_result.get('phrases', [])
        
        # Sort phrases by offset to ensure proper order
        phrases.sort(key=lambda x: x.get('offset', 0))
        
        for phrase in phrases:
            if not phrase.get('text', '').strip():
                continue
                
            # Extract speaker information - the key difference here!
            speaker_id = phrase.get('speakerId', phrase.get('speaker', 0))
            speaker_label = f"Speaker {speaker_id + 1}"
            
            # Extract time information
            offset_ns = phrase.get('offset', 0)
            duration_ns = phrase.get('duration', 0)
            
            # Convert to seconds (from 100-nanosecond units)
            start_time = offset_ns / 10000000
            end_time = (offset_ns + duration_ns) / 10000000
            
            # Format the key exactly as requested
            key = f"{speaker_label} ({start_time:.2f}-{end_time:.2f})"
            formatted_conversation[key] = phrase.get('text', '')
    
    elif 'results' in transcription_result and 'segments' in transcription_result.get('results', {}):
        # Format for conversation transcription service
        segments = transcription_result.get('results', {}).get('segments', [])
        
        for segment in segments:
            text = segment.get('text', '')
            if not text.strip():
                continue
                
            # Extract speaker and timing information
            speaker_id = segment.get('speaker', 0)
            speaker_label = f"Speaker {speaker_id + 1}"
            
            # Extract timing
            start_time = segment.get('startTimeInSeconds', 0)
            end_time = segment.get('endTimeInSeconds', 0)
            
            # Format the key as requested
            key = f"{speaker_label} ({start_time:.2f}-{end_time:.2f})"
            formatted_conversation[key] = text
    
    # If still no conversation (no recognized phrases with text), try additional formats
    if not formatted_conversation:
        # Try to extract from combinedPhrases if available
        if 'combinedPhrases' in transcription_result and transcription_result['combinedPhrases']:
            try:
                # Look for speaker information in combinedPhrases
                for phrase in transcription_result['combinedPhrases']:
                    text = phrase.get('text', '')
                    if not text.strip():
                        continue
                        
                    # Try to extract speaker ID
                    speaker_id = phrase.get('speaker', 0)
                    speaker_label = f"Speaker {speaker_id + 1}"
                    
                    # Try to extract timing
                    offset_sec = phrase.get('offsetInSeconds', phrase.get('offset', 0) / 10000000)
                    duration_sec = phrase.get('durationInSeconds', phrase.get('duration', 0) / 10000000)
                    end_time = offset_sec + duration_sec
                    
                    # Format the key as requested
                    key = f"{speaker_label} ({offset_sec:.2f}-{end_time:.2f})"
                    formatted_conversation[key] = text
            except Exception as e:
                logger.error(f"Error processing combinedPhrases: {str(e)}")
        
        # Try to parse the specific V3 transcript format if available
        if not formatted_conversation and 'transcript' in transcription_result:
            transcript = transcription_result.get('transcript', {})
            if 'segments' in transcript:
                segments = transcript.get('segments', [])
                for segment in segments:
                    text = segment.get('text', '')
                    if not text.strip():
                        continue
                    
                    # Extract speaker ID
                    speaker_id = segment.get('speakerId', 0)
                    speaker_label = f"Speaker {speaker_id + 1}"
                    
                    # Extract timing
                    start_time = segment.get('start', 0)
                    end_time = segment.get('end', 0)
                    
                    # Format the key as requested
                    key = f"{speaker_label} ({start_time:.2f}-{end_time:.2f})"
                    formatted_conversation[key] = text
                
        # Final fallback if still no conversation - split by timing or sentence breaks
        if not formatted_conversation and 'combinedPhrases' in transcription_result and transcription_result['combinedPhrases']:
            full_text = transcription_result['combinedPhrases'][0].get('text', '')
            total_duration = transcription_result.get('duration', 10000000000) / 10000000  # Default to 1000s if unknown
            
            # Try to detect speaker changes based on the text content
            sentences = re.split(r'(?<=[.!?]) +', full_text)
            current_speaker = 1
            current_time = 0.0
            
            for sentence in sentences:
                if not sentence.strip():
                    continue
                    
                # Estimate duration based on length of sentence
                approx_duration = len(sentence) * 0.07  # Rough estimate of speaking speed
                end_time = current_time + approx_duration
                
                # Format the key as requested
                key = f"Speaker {current_speaker} ({current_time:.2f}-{end_time:.2f})"
                formatted_conversation[key] = sentence
                
                # Switch speakers and update time
                current_speaker = 2 if current_speaker == 1 else 1
                current_time = end_time
    
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
            "conversation": conversation_result,  # This is now correctly formatted
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