import logging
from apis.jobs.job_service import JobService
from apis.utils.fileService import FileService
from apis.speech_services.stt import transcribe_audio, calculate_audio_duration
from apis.speech_services.stt_diarize import process_transcript_with_llm, split_transcript_into_chunks, count_tokens
import requests
import uuid
from apis.utils.databaseService import DatabaseService
import azure.cognitiveservices.speech as speechsdk
import os
import io
import tempfile
import wave
import tiktoken

# Configure logging
logger = logging.getLogger(__name__)

# Azure Speech Service configuration for TTS
TTS_SPEECH_KEY = os.environ.get("AZURE_SPEECH_KEY")
TTS_SERVICE_REGION = os.environ.get("AZURE_SPEECH_REGION", "southafricanorth")

class JobProcessor:
    """
    Class for processing asynchronous jobs
    
    This class contains methods to process different types of async jobs
    like speech-to-text, speech-to-text with diarization, and text-to-speech.
    """
    
    @staticmethod
    def get_tokenizer():
        """Get tiktoken encoder for token counting"""
        try:
            # Use GPT-4 tokenizer as a standard
            return tiktoken.encoding_for_model("gpt-4")
        except:
            # Fallback to cl100k_base encoding
            return tiktoken.get_encoding("cl100k_base")
    
    @staticmethod
    def count_text_tokens(text):
        """Count the number of tokens in the text using tiktoken"""
        try:
            tokenizer = JobProcessor.get_tokenizer()
            return len(tokenizer.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens: {str(e)}")
            # Fallback estimation: roughly 4 characters per token
            return len(text) // 4
    
    @staticmethod
    def get_accurate_audio_duration(audio_data, output_format):
        """
        Get accurate audio duration from the audio data
        
        Args:
            audio_data (bytes): The audio file data
            output_format (str): The output format used for synthesis
            
        Returns:
            float: Duration in seconds
        """
        try:
            # Create a temporary file to analyze the audio
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file.flush()
                
                try:
                    if 'mp3' in output_format.lower():
                        # For MP3 files, try to use mutagen if available, otherwise estimate
                        try:
                            from mutagen.mp3 import MP3
                            audio = MP3(temp_file.name)
                            duration = audio.info.length
                            logger.info(f"Got MP3 duration from mutagen: {duration} seconds")
                            return duration
                        except ImportError:
                            logger.warning("Mutagen not available for MP3 duration, using estimation")
                            # Estimate based on bitrate (more accurate than before)
                            if '32kbitrate' in output_format:
                                # 32 kbps MP3: roughly 4KB per second
                                estimated_duration = len(audio_data) / 4000
                            elif '128kbitrate' in output_format:
                                # 128 kbps MP3: roughly 16KB per second  
                                estimated_duration = len(audio_data) / 16000
                            else:
                                # Default estimate
                                estimated_duration = len(audio_data) / 4000
                            logger.info(f"Estimated MP3 duration: {estimated_duration} seconds")
                            return estimated_duration
                        except Exception as e:
                            logger.error(f"Error reading MP3 with mutagen: {str(e)}")
                            # Fallback to bitrate estimation
                            estimated_duration = len(audio_data) / 4000
                            return estimated_duration
                    
                    elif 'riff' in output_format.lower() or 'pcm' in output_format.lower():
                        # For WAV/PCM files, use wave library (built into Python)
                        try:
                            with wave.open(temp_file.name, 'rb') as wav_file:
                                frames = wav_file.getnframes()
                                sample_rate = wav_file.getframerate()
                                duration = frames / float(sample_rate)
                                logger.info(f"Got WAV duration from wave library: {duration} seconds")
                                return duration
                        except Exception as e:
                            logger.error(f"Error reading WAV with wave library: {str(e)}")
                            # Fallback calculation for PCM
                            if '16khz' in output_format:
                                sample_rate = 16000
                            elif '22050hz' in output_format:
                                sample_rate = 22050
                            elif '24khz' in output_format:
                                sample_rate = 24000
                            else:
                                sample_rate = 16000  # Default
                            
                            # 16-bit mono PCM: 2 bytes per sample
                            duration = len(audio_data) / (sample_rate * 2)
                            logger.info(f"Estimated PCM duration: {duration} seconds")
                            return duration
                    
                    else:
                        # Unknown format, use generic estimation
                        estimated_duration = len(audio_data) / (16000 * 2)
                        logger.warning(f"Unknown audio format, using generic estimation: {estimated_duration} seconds")
                        return estimated_duration
                        
                finally:
                    # Clean up temporary file
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Error getting accurate audio duration: {str(e)}")
            # Final fallback - use the original estimation method
            return len(audio_data) / (16000 * 2)
    
    @staticmethod
    def update_dual_usage_metrics_for_stt_diarize(user_id, audio_seconds, token_metrics):
        """Update existing usage record with dual records for stt_diarize job processing
        
        This finds the existing user_usage record created during job submission and 
        replaces it with two separate records - one for MS STT and one for GPT-4o-mini.
        
        Args:
            user_id (str): ID of the user who submitted the job
            audio_seconds (float): Duration of processed audio
            token_metrics (dict): Token usage metrics from GPT-4o-mini
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get endpoint ID for stt_diarize
            endpoint_id = DatabaseService.get_endpoint_id_by_path('/speech/stt_diarize')
            
            if not endpoint_id:
                logger.error("Endpoint ID not found for path: /speech/stt_diarize")
                return False
                
            # Connect to database
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Find existing usage record created during job submission (within the last hour)
            existing_query = """
            SELECT id, api_log_id
            FROM user_usage 
            WHERE user_id = ? 
            AND endpoint_id = ? 
            AND DATEDIFF(hour, timestamp, DATEADD(HOUR, 2, GETUTCDATE())) < 1
            ORDER BY timestamp DESC
            """
            
            cursor.execute(existing_query, [user_id, endpoint_id])
            existing_record = cursor.fetchone()
            
            if not existing_record:
                logger.warning("No existing usage record found to update for stt_diarize job")
                cursor.close()
                conn.close()
                return False
            
            existing_usage_id = existing_record[0]
            api_log_id = existing_record[1]
            
            logger.info(f"Updating existing usage record {existing_usage_id} with dual records")
            
            # Delete the existing single record
            delete_query = "DELETE FROM user_usage WHERE id = ?"
            cursor.execute(delete_query, [existing_usage_id])
            
            # Create first record for MS STT with audio seconds
            ms_stt_usage_id = str(uuid.uuid4())
            ms_stt_query = """
            INSERT INTO user_usage (
                id, user_id, endpoint_id, timestamp,
                images_generated, audio_seconds_processed, pages_processed,
                documents_processed, model_used, prompt_tokens,
                completion_tokens, total_tokens, cached_tokens, files_uploaded,
                api_log_id, embedded_tokens
            )
            VALUES (
                ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()),
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?
            )
            """
            
            logger.info(f"Creating MS STT usage record with audio_seconds_processed: {audio_seconds}")
            
            cursor.execute(ms_stt_query, [
                ms_stt_usage_id,
                user_id,
                endpoint_id,
                0,  # images_generated
                audio_seconds,  # audio seconds from MS STT
                0,  # pages_processed
                0,  # documents_processed
                "ms_stt",  # model_used
                0,  # prompt_tokens
                0,  # completion_tokens
                0,  # total_tokens
                0,  # cached_tokens
                0,  # files_uploaded
                api_log_id,  # api_log_id from existing record
                0   # embedded_tokens
            ])
            
            # Create second record for GPT-4o-mini with token usage
            gpt_usage_id = str(uuid.uuid4())
            gpt_query = """
            INSERT INTO user_usage (
                id, user_id, endpoint_id, timestamp,
                images_generated, audio_seconds_processed, pages_processed,
                documents_processed, model_used, prompt_tokens,
                completion_tokens, total_tokens, cached_tokens, files_uploaded,
                api_log_id, embedded_tokens
            )
            VALUES (
                ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()),
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?
            )
            """
            
            logger.info(f"Creating GPT-4o-mini usage record with prompt_tokens: {token_metrics.get('prompt_tokens', 0)}")
            
            cursor.execute(gpt_query, [
                gpt_usage_id,
                user_id,
                endpoint_id,
                0,  # images_generated
                0,  # audio_seconds_processed - zero for GPT model
                0,  # pages_processed
                0,  # documents_processed
                "gpt-4o-mini",  # model_used
                token_metrics.get("prompt_tokens", 0),
                token_metrics.get("completion_tokens", 0),
                token_metrics.get("total_tokens", 0),
                token_metrics.get("cached_tokens", 0),
                0,  # files_uploaded
                api_log_id,  # api_log_id from existing record
                token_metrics.get("embedded_tokens", 0)
            ])
            
            # Update the api_logs table to point to the MS STT record as primary
            if api_log_id:
                update_api_log_query = """
                UPDATE api_logs
                SET user_usage_id = ?
                WHERE id = ?
                """
                cursor.execute(update_api_log_query, [ms_stt_usage_id, api_log_id])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Replaced single usage record with dual records - MS STT: {ms_stt_usage_id}, GPT-4o-mini: {gpt_usage_id}, api_log_id: {api_log_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating dual usage metrics for stt_diarize job: {str(e)}")
            return False

    @staticmethod
    def update_usage_metrics(user_id, job_type, metrics):
        """Update or create usage metrics in the user_usage table
        
        This method will check if a usage record already exists for the job's API call
        and update it rather than creating a duplicate record.
        
        Args:
            user_id (str): ID of the user who submitted the job
            job_type (str): Type of job (e.g., 'stt', 'stt_diarize', 'tts')
            metrics (dict): Dictionary containing usage metrics
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get endpoint ID based on job type
            endpoint_path = f"/speech/{job_type}"
            endpoint_id = DatabaseService.get_endpoint_id_by_path(endpoint_path)
            
            if not endpoint_id:
                logger.error(f"Endpoint ID not found for path: {endpoint_path}")
                return False
                
            # Connect to database
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # First check if we already have a usage record for this user and endpoint
            # (created within the last hour to avoid updating very old records)
            query = """
            SELECT id 
            FROM user_usage 
            WHERE user_id = ? 
            AND endpoint_id = ? 
            AND DATEDIFF(hour, timestamp, DATEADD(HOUR, 2, GETUTCDATE())) < 1
            ORDER BY timestamp DESC
            """
            
            cursor.execute(query, [user_id, endpoint_id])
            existing_record = cursor.fetchone()
            
            if existing_record:
                # Update existing record
                usage_id = existing_record[0]
                logger.info(f"Updating existing usage record {usage_id} for {job_type}")
                
                update_query = """
                UPDATE user_usage
                SET audio_seconds_processed = ?,
                    model_used = ?,
                    prompt_tokens = ?,
                    completion_tokens = ?,
                    total_tokens = ?,
                    cached_tokens = ?,
                    files_uploaded = ?
                WHERE id = ?
                """
                
                cursor.execute(update_query, [
                    metrics.get("audio_seconds_processed", 0),
                    metrics.get("model_used"),
                    metrics.get("prompt_tokens", 0),
                    metrics.get("completion_tokens", 0),
                    metrics.get("total_tokens", 0),
                    metrics.get("cached_tokens", 0),
                    metrics.get("files_uploaded", 0),
                    usage_id
                ])
                
                conn.commit()
                cursor.close()
                conn.close()
                
                logger.info(f"Successfully updated usage metrics for {job_type} job, usage_id: {usage_id}")
                return True
                
            else:
                # If no existing record found (which shouldn't happen with middleware),
                # create a new one as fallback
                usage_id = str(uuid.uuid4())
                logger.warning(f"No existing usage record found for {job_type}. Creating new record {usage_id}")
                
                insert_query = """
                INSERT INTO user_usage (
                    id, user_id, endpoint_id, timestamp,
                    images_generated, audio_seconds_processed, pages_processed,
                    documents_processed, model_used, prompt_tokens,
                    completion_tokens, total_tokens, cached_tokens, files_uploaded
                )
                VALUES (
                    ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()),
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """
                
                cursor.execute(insert_query, [
                    usage_id,
                    user_id,
                    endpoint_id,
                    metrics.get("images_generated", 0),
                    metrics.get("audio_seconds_processed", 0),
                    metrics.get("pages_processed", 0),
                    metrics.get("documents_processed", 0),
                    metrics.get("model_used"),
                    metrics.get("prompt_tokens", 0),
                    metrics.get("completion_tokens", 0),
                    metrics.get("total_tokens", 0),
                    metrics.get("cached_tokens", 0),
                    metrics.get("files_uploaded", 0)
                ])
                
                conn.commit()
                cursor.close()
                conn.close()
                
                logger.info(f"Created new usage record {usage_id} for {job_type} as fallback")
                return True
            
        except Exception as e:
            logger.error(f"Error updating usage metrics for async job: {str(e)}")
            return False
    
    @staticmethod
    def process_stt_job(job_id, user_id, file_id):
        """
        Process a speech-to-text job
        
        Args:
            job_id (str): ID of the job to process
            user_id (str): ID of the user who submitted the job
            file_id (str): ID of the file to process
            
        Returns:
            bool: True if successful, False otherwise
            
        Response format (stored in job result):
            {
                "message": "Audio transcribed successfully",
                "transcript": "This is the transcribed text from the audio file.",
                "transcription_details": {
                    "combinedPhrases": [
                        {
                            "text": "This is the transcribed text from the audio file."
                        }
                    ],
                    "duration": 45600
                },
                "seconds_processed": 45.6
            }
            
        Error handling:
            - Updates job status to 'failed' with error message if:
                - File URL can't be retrieved
                - Transcription fails
                - Any other exception occurs
        """
        try:
            # Update job status to processing
            JobService.update_job_status(job_id, 'processing')
            
            # Get file URL
            file_info, error = FileService.get_file_url(file_id, user_id)
            if error:
                error_msg = f"Error retrieving file URL: {error}"
                logger.error(error_msg)
                JobService.update_job_status(job_id, 'failed', error_msg)
                return False
                
            file_url = file_info.get('file_url')
            
            if not file_url:
                error_msg = "File URL not found"
                logger.error(error_msg)
                JobService.update_job_status(job_id, 'failed', error_msg)
                return False
            
            # Transcribe the audio file
            transcription_result, error = transcribe_audio(file_url)
            
            if error:
                error_msg = f"Error transcribing audio: {error.get('error', 'Unknown error')}"
                logger.error(error_msg)
                JobService.update_job_status(job_id, 'failed', error_msg)
                return False
            
            # Extract the transcript text
            if 'combinedPhrases' in transcription_result and transcription_result['combinedPhrases']:
                transcript = transcription_result["combinedPhrases"][0]["text"]
            else:
                transcript = "No transcript available"
            
            # Calculate the duration of the audio file
            seconds_processed = calculate_audio_duration(transcription_result)
            
            # Delete the uploaded file to avoid storage bloat using FileService directly
            success, message = FileService.delete_file(file_id, user_id)
            if not success:
                logger.warning(f"Failed to delete uploaded file {file_id}: {message}")
            
            # Prepare the response
            result_data = {
                "message": "Audio transcribed successfully",
                "transcript": transcript,
                "transcription_details": transcription_result,
                "seconds_processed": seconds_processed,
                "model_used": "ms_stt"
            }
            
            # Update existing usage metrics
            metrics = {
                "audio_seconds_processed": seconds_processed,
                "model_used": "ms_stt"
            }
            JobProcessor.update_usage_metrics(user_id, "stt", metrics)
            
            # Update job status to completed with results
            JobService.update_job_status(job_id, 'completed', result_data=result_data)
            
            logger.info(f"STT job {job_id} processed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Error processing STT job: {str(e)}"
            logger.error(error_msg)
            JobService.update_job_status(job_id, 'failed', error_msg)
            return False
    
    @staticmethod
    def process_stt_diarize_job(job_id, user_id, file_id, token=None):
        """
        Process a speech-to-text with diarization job
        
        Args:
            job_id (str): ID of the job to process
            user_id (str): ID of the user who submitted the job
            file_id (str): ID of the file to process
            token (str): Authentication token for LLM service
            
        Returns:
            bool: True if successful, False otherwise
            
        Response format (stored in job result):
            {
                "message": "Audio processed successfully",
                "raw_transcript": "This is the raw transcribed text from the audio file.",
                "enhanced_transcript": "[00:00:00] Speaker 1: This is the enhanced transcribed text with speaker diarization.",
                "seconds_processed": 45.6,
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "total_tokens": 1500,
                "cached_tokens": 0,
                "embedded_tokens": 0,
                "model_used": "gpt-4o-mini"
            }
            
        Error handling:
            - Updates job status to 'failed' with error message if:
                - File URL can't be retrieved
                - Transcription fails
                - LLM processing fails
                - Any other exception occurs
        """
        try:
            # Update job status to processing
            JobService.update_job_status(job_id, 'processing')
            
            # Get file URL
            file_info, error = FileService.get_file_url(file_id, user_id)
            if error:
                error_msg = f"Error retrieving file URL: {error}"
                logger.error(error_msg)
                JobService.update_job_status(job_id, 'failed', error_msg)
                return False
                
            file_url = file_info.get('file_url')
            
            if not file_url:
                error_msg = "File URL not found"
                logger.error(error_msg)
                JobService.update_job_status(job_id, 'failed', error_msg)
                return False
            
            # Transcribe the audio file
            transcription_result, error = transcribe_audio(file_url)
            
            if error:
                error_msg = f"Error transcribing audio: {error.get('error', 'Unknown error')}"
                logger.error(error_msg)
                JobService.update_job_status(job_id, 'failed', error_msg)
                return False
            
            # Calculate the duration of the audio file
            seconds_processed = calculate_audio_duration(transcription_result)
            
            # Extract the transcript text
            raw_transcript = ""
            if 'combinedPhrases' in transcription_result and transcription_result['combinedPhrases']:
                # Extract full transcript from all combined phrases
                phrases = [phrase["text"] for phrase in transcription_result["combinedPhrases"]]
                raw_transcript = " ".join(phrases)
            else:
                error_msg = "No transcript content available in the response"
                logger.error(error_msg)
                JobService.update_job_status(job_id, 'failed', error_msg)
                return False
            
            # Initialize token usage counters
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_tokens = 0
            total_cached_tokens = 0
            total_embedded_tokens = 0
            
            # Get max tokens constant from stt_diarize.py
            from apis.speech_services.stt_diarize import MAX_CHUNK_TOKENS, model_deplopyment
            
            # Process the transcript with diarization
            token_count = count_tokens(raw_transcript)
            logger.info(f"Transcript token count: {token_count}")
            
            enhanced_transcript = ""
            
            if token_count <= MAX_CHUNK_TOKENS:
                # Process the entire transcript at once
                processed_result, error = process_transcript_with_llm(raw_transcript, token)
                if error:
                    error_msg = f"Error enhancing transcript: {error.get('message', 'Unknown error')}"
                    logger.error(error_msg)
                    JobService.update_job_status(job_id, 'failed', error_msg)
                    return False
                
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
                    logger.info(f"Processing chunk {i+1}/{total_chunks}")
                    processed_result, error = process_transcript_with_llm(
                        chunk, token, chunk_number=i+1, total_chunks=total_chunks
                    )
                    
                    if error:
                        error_msg = f"Error enhancing transcript chunk {i+1}: {error.get('message', 'Unknown error')}"
                        logger.error(error_msg)
                        JobService.update_job_status(job_id, 'failed', error_msg)
                        return False
                    
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
            success, message = FileService.delete_file(file_id, user_id)
            if not success:
                logger.warning(f"Failed to delete uploaded file {file_id}: {message}")
            
            # Prepare the response
            result_data = {
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
            
            # Create dual usage metrics - one for MS STT and one for GPT-4o-mini
            token_metrics = {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
                "cached_tokens": total_cached_tokens,
                "embedded_tokens": total_embedded_tokens
            }
            JobProcessor.update_dual_usage_metrics_for_stt_diarize(user_id, seconds_processed, token_metrics)
            
            # Update job status to completed with results
            JobService.update_job_status(job_id, 'completed', result_data=result_data)
            
            logger.info(f"STT diarize job {job_id} processed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Error processing STT diarize job: {str(e)}"
            logger.error(error_msg)
            JobService.update_job_status(job_id, 'failed', error_msg)
            return False
    
    @staticmethod
    def process_tts_job(job_id, user_id, job_parameters):
        """
        Process a text-to-speech job
        
        Args:
            job_id (str): ID of the job to process
            user_id (str): ID of the user who submitted the job
            job_parameters (dict): Job parameters containing text, voice_name, output_format
            
        Returns:
            bool: True if successful, False otherwise
            
        Response format (stored in job result):
            {
                "message": "Text converted to speech successfully",
                "file_id": "12345678-1234-1234-1234-123456789012",
                "voice_used": "en-US-JennyNeural",
                "output_format": "audio-16khz-32kbitrate-mono-mp3",
                "text_length": 45,
                "audio_duration_seconds": 3.2,
                "files_uploaded": 1,
                "prompt_tokens": 12,
                "model_used": "ms_tts"
            }
            
        Error handling:
            - Updates job status to 'failed' with error message if:
                - Text synthesis fails
                - File upload fails
                - Any other exception occurs
        """
        try:
            # Update job status to processing
            JobService.update_job_status(job_id, 'processing')
            
            # Extract parameters
            text = job_parameters.get('text')
            voice_name = job_parameters.get('voice_name', 'en-US-JennyNeural')
            output_format = job_parameters.get('output_format', 'audio-16khz-32kbitrate-mono-mp3')
            
            if not text:
                error_msg = "No text provided for synthesis"
                logger.error(error_msg)
                JobService.update_job_status(job_id, 'failed', error_msg)
                return False
            
            # Count tokens in the input text
            prompt_tokens = JobProcessor.count_text_tokens(text)
            logger.info(f"Input text has {prompt_tokens} tokens")
            
            # Check if Azure Speech Service credentials are configured
            if not TTS_SPEECH_KEY or not TTS_SERVICE_REGION:
                error_msg = "Azure Speech Service credentials not configured"
                logger.error(error_msg)
                JobService.update_job_status(job_id, 'failed', error_msg)
                return False
            
            # Configure Azure Speech Service
            speech_config = speechsdk.SpeechConfig(subscription=TTS_SPEECH_KEY, region=TTS_SERVICE_REGION)
            speech_config.speech_synthesis_voice_name = voice_name
            speech_config.set_speech_synthesis_output_format(
                getattr(speechsdk.SpeechSynthesisOutputFormat, output_format.replace('-', '_'), 
                       speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)
            )
            
            # Create synthesizer with null output (we'll get the audio data directly)
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
            
            # Synthesize speech
            logger.info(f"Starting TTS synthesis for job {job_id}")
            result = synthesizer.speak_text_async(text).get()
            
            # Check synthesis result
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info(f"Speech synthesized successfully for job {job_id}")
                
                # Get the audio data
                audio_data = result.audio_data
                
                # Get accurate audio duration using the improved method
                audio_duration = JobProcessor.get_accurate_audio_duration(audio_data, output_format)
                logger.info(f"Accurate audio duration: {audio_duration} seconds")
                
                # Create a file-like object from the audio data
                audio_file = io.BytesIO(audio_data)
                
                # Determine file extension based on output format
                if 'mp3' in output_format:
                    file_extension = '.mp3'
                    content_type = 'audio/mpeg'
                else:
                    file_extension = '.wav'
                    content_type = 'audio/wav'
                
                # Create a temporary file-like object with the required attributes
                class AudioFileObj:
                    def __init__(self, data, filename, content_type):
                        self.data = data
                        self.filename = filename
                        self.content_type = content_type
                        self._position = 0
                    
                    def read(self, size=-1):
                        if size == -1:
                            chunk = self.data[self._position:]
                            self._position = len(self.data)
                        else:
                            chunk = self.data[self._position:self._position + size]
                            self._position += len(chunk)
                        return chunk
                    
                    def seek(self, position):
                        self._position = position
                    
                    def tell(self):
                        return self._position
                
                # Create filename for the generated audio
                filename = f"tts_output_{job_id[:8]}{file_extension}"
                audio_file_obj = AudioFileObj(audio_data, filename, content_type)
                
                # Upload the audio file to blob storage
                file_info, upload_error = FileService.upload_file(audio_file_obj, user_id)
                
                if upload_error:
                    error_msg = f"Error uploading generated audio file: {upload_error}"
                    logger.error(error_msg)
                    JobService.update_job_status(job_id, 'failed', error_msg)
                    return False
                
                # Prepare the response
                result_data = {
                    "message": "Text converted to speech successfully",
                    "file_id": file_info["file_id"],
                    "voice_used": voice_name,
                    "output_format": output_format,
                    "text_length": len(text),
                    "audio_duration_seconds": round(audio_duration, 2),
                    "files_uploaded": 1,
                    "prompt_tokens": prompt_tokens,
                    "model_used": "ms_tts"
                }
                
                # Update existing usage metrics
                metrics = {
                    "files_uploaded": 1,
                    "audio_seconds_processed": round(audio_duration, 2),
                    "prompt_tokens": prompt_tokens,
                    "model_used": "ms_tts"
                }
                JobProcessor.update_usage_metrics(user_id, "tts", metrics)
                
                # Update job status to completed with results
                JobService.update_job_status(job_id, 'completed', result_data=result_data)
                
                logger.info(f"TTS job {job_id} processed successfully, file_id: {file_info['file_id']}")
                return True
                
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                error_msg = f"Speech synthesis canceled: {cancellation_details.reason}"
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    error_msg += f". Error details: {cancellation_details.error_details}"
                
                logger.error(error_msg)
                JobService.update_job_status(job_id, 'failed', error_msg)
                return False
            else:
                error_msg = f"Speech synthesis failed with reason: {result.reason}"
                logger.error(error_msg)
                JobService.update_job_status(job_id, 'failed', error_msg)
                return False
            
        except Exception as e:
            error_msg = f"Error processing TTS job: {str(e)}"
            logger.error(error_msg)
            JobService.update_job_status(job_id, 'failed', error_msg)
            return False
