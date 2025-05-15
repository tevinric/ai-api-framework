from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.utils.fileService import FileService  # Import FileService
from apis.utils.llmServices import gpt4o_mini_service  # Import LLM service
import logging
import os
import pytz
from datetime import datetime
import requests
import json
import uuid
import tiktoken

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

if gpt4o_mini_service:
    model_deplopyment = "gpt-4o-mini"

# Speech to Text API configuration
STT_API_KEY = os.environ.get("MS_STT_API_KEY")
STT_ENDPOINT = os.environ.get("MS_STT_ENDPOINT")

# Maximum tokens for GPT-4o-mini
MAX_LLM_TOKENS = 128000
# Token buffer for LLM responses (reserving space for system prompt + response)
TOKEN_BUFFER = 10000
# Maximum tokens per chunk for processing
MAX_CHUNK_TOKENS = MAX_LLM_TOKENS - TOKEN_BUFFER

# Initialize tokenizer for token counting
def get_tokenizer():
    try:
        # This is for GPT-4 family models
        return tiktoken.encoding_for_model("gpt-4")
    except:
        # Fallback to cl100k_base encoding which is used by many OpenAI models
        return tiktoken.get_encoding("cl100k_base")

def count_tokens(text):
    """Count the number of tokens in the text using tiktoken"""
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text))

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

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
        if 'duration' in transcription_result:
            # Convert milliseconds to seconds
            return transcription_result['duration'] / 1000.0
            
        # If all else fails, return a default value
        return 0
            
    except Exception as e:
        logger.error(f"Error calculating audio duration: {str(e)}")
        return 0

def split_transcript_into_chunks(transcript, max_tokens=MAX_CHUNK_TOKENS):
    """Split transcript into chunks respecting sentence boundaries where possible"""
    tokenizer = get_tokenizer()
    tokens = tokenizer.encode(transcript)
    
    if len(tokens) <= max_tokens:
        return [transcript]
    
    chunks = []
    sentences = transcript.split('. ')
    current_chunk = []
    current_token_count = 0
    
    for sentence in sentences:
        # Add period back except for the last sentence if it doesn't end with one
        sentence_text = sentence + '. ' if not sentence.endswith('.') else sentence + ' '
        sentence_token_count = len(tokenizer.encode(sentence_text))
        
        # If adding this sentence would exceed max_tokens, start a new chunk
        if current_token_count + sentence_token_count > max_tokens and current_chunk:
            chunks.append(''.join(current_chunk).strip())
            current_chunk = [sentence_text]
            current_token_count = sentence_token_count
        else:
            current_chunk.append(sentence_text)
            current_token_count += sentence_token_count
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(''.join(current_chunk).strip())
    
    return chunks

def process_transcript_with_llm(transcript, token, chunk_number=None, total_chunks=None):
    """Process transcript with GPT-4o-mini to get diarized output with timestamps"""
    system_prompt = """
    You are a speech-to-text post-processor specialized in creating speaker-diarized transcripts with timestamps.
    
    TASK:
    Analyze the provided transcript and convert it into a properly formatted transcript with:
    1. Speaker identification (Speaker 1, Speaker 2, etc.)
    2. Timestamps in [HH:MM:SS] format for each speaker turn
    3. Natural paragraph breaks
    
    IMPORTANT FORMATTING RULES:
    - Format each speaker turn as: "[HH:MM:SS] Speaker X: {spoken text}"
    - Start timestamps at [00:00:00] and estimate progression based on spoken content
    - Estimate approximately 150 words per minute when calculating timestamps
    - Maintain the exact same content and meaning as the original transcript
    - For multiple speakers, identify them consistently throughout the transcript
    """
    
    if chunk_number is not None and total_chunks is not None:
        system_prompt += f"""
        
        SPECIAL INSTRUCTIONS:
        This is chunk {chunk_number} of {total_chunks}. Maintain consistent speaker numbering and logical timestamp continuation from previous chunks.
        """
    
    try:
        # Use the LLM service directly instead of making an API call
        llm_response = gpt4o_mini_service(
            system_prompt=system_prompt,
            user_input=transcript,
            temperature=0.2
        )
        
        if not llm_response.get("success", False):
            logger.error(f"LLM service error: {llm_response.get('error')}")
            return None, {
                "error": "LLM Processing Error",
                "message": f"Error from LLM service: {llm_response.get('error', 'Unknown error')}"
            }
        
        # Add token usage information to the response
        result = {
            "text": llm_response.get("result"),
            "token_usage": {
                "prompt_tokens": llm_response.get("prompt_tokens", 0),
                "completion_tokens": llm_response.get("completion_tokens", 0),
                "total_tokens": llm_response.get("total_tokens", 0),
                "cached_tokens": llm_response.get("cached_tokens", 0),
                "embedded_tokens": llm_response.get("embedded_tokens", 0)
            }
        }
        
        return result, None
        
    except Exception as e:
        logger.error(f"Error in LLM processing: {str(e)}")
        return None, {
            "error": "LLM Processing Error",
            "message": f"Error processing with LLM: {str(e)}"
        }

def enhanced_speech_to_text_route():
    """
    Convert speech to text using Microsoft Speech to Text API and enhance with GPT-4o-mini
    for speaker diarization and timestamps
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
        description: Audio transcribed and enhanced successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Audio processed successfully
            raw_transcript:
              type: string
              description: Original transcript text
              example: This is the raw transcribed text from the audio file without any speaker identification or timestamps.
            enhanced_transcript:
              type: string
              description: Enhanced transcript with speaker diarization and timestamps
              example: "[00:00:00] Speaker 1: This is the enhanced transcribed text with speaker diarization.\n[00:00:15] Speaker 2: And this is another speaker responding in the conversation."
            seconds_processed:
              type: number
              description: Duration of the processed audio in seconds
              example: 45.6
            prompt_tokens:
              type: integer
              description: Number of tokens in the prompt sent to the LLM
              example: 1000
            completion_tokens:
              type: integer
              description: Number of tokens in the response from the LLM
              example: 500
            total_tokens:
              type: integer
              description: Total number of tokens processed
              example: 1500
            cached_tokens:
              type: integer
              description: Number of tokens that were cached
              example: 0
            embedded_tokens:
              type: integer
              description: Number of tokens embedded
              example: 0
            model_used:
              type: string
              description: LLM model used for diarization
              example: gpt-4o-mini
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
              enum: [Server Error, File Error, Transcription Error, LLM Processing Error]
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
        
        if error:
            return create_api_response({
                "error": "Transcription Error",
                "message": f"Error transcribing audio: {error.get('error', 'Unknown error')}",
                "details": error
            }, 500)
        
        # Calculate the duration of the audio file
        seconds_processed = calculate_audio_duration(transcription_result)
        
        # Extract the transcript text
        raw_transcript = ""
        if 'combinedPhrases' in transcription_result and transcription_result['combinedPhrases']:
            # Extract full transcript from all combined phrases
            phrases = [phrase["text"] for phrase in transcription_result["combinedPhrases"]]
            raw_transcript = " ".join(phrases)
        else:
            return create_api_response({
                "error": "Transcription Error",
                "message": "No transcript content available in the response"
            }, 500)
        
        # Process the transcript with GPT-4o-mini for speaker diarization
        token_count = count_tokens(raw_transcript)
        logger.info(f"Transcript token count: {token_count}")
        
        enhanced_transcript = ""
        
        # Initialize token usage counters
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0
        total_cached_tokens = 0
        total_embedded_tokens = 0
        
        if token_count <= MAX_CHUNK_TOKENS:
            # Process the entire transcript at once
            processed_result, error = process_transcript_with_llm(raw_transcript, token)
            if error:
                return create_api_response({
                    "error": "LLM Processing Error",
                    "message": f"Error enhancing transcript: {error.get('message', 'Unknown error')}",
                    "details": error
                }, 500)
            
            enhanced_transcript = processed_result["text"]
            
            # Track token usage
            token_usage = processed_result.get("token_usage", {})
            total_prompt_tokens = token_usage.get("prompt_tokens", 0)
            total_completion_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)
            total_cached_tokens = token_usage.get("cached_tokens", 0)
            total_embedded_tokens = token_usage.get("embedded_tokens", 0)
            
        else:
            # Split the transcript into chunks and process each one
            chunks = split_transcript_into_chunks(raw_transcript)
            total_chunks = len(chunks)
            logger.info(f"Splitting transcript into {total_chunks} chunks")
            
            enhanced_chunks = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Processing chunk {i+1}/{total_chunks}, token count: {count_tokens(chunk)}")
                processed_result, error = process_transcript_with_llm(
                    chunk, token, chunk_number=i+1, total_chunks=total_chunks
                )
                
                if error:
                    return create_api_response({
                        "error": "LLM Processing Error",
                        "message": f"Error enhancing transcript chunk {i+1}: {error.get('message', 'Unknown error')}",
                        "details": error
                    }, 500)
                
                enhanced_chunks.append(processed_result["text"])
                
                # Accumulate token usage
                token_usage = processed_result.get("token_usage", {})
                total_prompt_tokens += token_usage.get("prompt_tokens", 0)
                total_completion_tokens += token_usage.get("completion_tokens", 0)
                total_tokens += token_usage.get("total_tokens", 0)
                total_cached_tokens += token_usage.get("cached_tokens", 0)
                total_embedded_tokens += token_usage.get("embedded_tokens", 0)
            
            # Combine the processed chunks
            enhanced_transcript = "\n\n".join(enhanced_chunks)
        
        # Delete the uploaded file to avoid storage bloat using FileService directly
        success, message = FileService.delete_file(file_id, g.user_id)
        if not success:
            logger.warning(f"Failed to delete uploaded file {file_id}: {message}")
        
        # Prepare the response
        response_data = {
            "message": "Audio processed successfully",
            "raw_transcript": raw_transcript,
            "enhanced_transcript": enhanced_transcript,
            "seconds_processed": seconds_processed,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": total_cached_tokens,
            "embedded_tokens": total_embedded_tokens,
            "model_used": model_deplopyment
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error in enhanced speech to text endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

def register_speech_to_text_diarize_routes(app):
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    """Register enhanced speech to text routes with the Flask app"""
    app.route('/speech/stt_diarize', methods=['POST'])(track_usage(api_logger(check_endpoint_access(check_balance(enhanced_speech_to_text_route)))))
