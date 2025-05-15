import logging
from apis.jobs.job_service import JobService
from apis.utils.fileService import FileService
from apis.speech_services.stt import transcribe_audio, calculate_audio_duration
from apis.speech_services.stt_diarize import process_transcript_with_llm, split_transcript_into_chunks, count_tokens
import requests
import uuid
from apis.utils.databaseService import DatabaseService

# Configure logging
logger = logging.getLogger(__name__)

class JobProcessor:
    """
    Class for processing asynchronous jobs
    
    This class contains methods to process different types of async jobs
    like speech-to-text and speech-to-text with diarization.
    """
    
    @staticmethod
    def log_usage_metrics(user_id, job_type, metrics):
        """Log usage metrics to the user_usage table
        
        Args:
            user_id (str): ID of the user who submitted the job
            job_type (str): Type of job (e.g., 'stt', 'stt_diarize')
            metrics (dict): Dictionary containing usage metrics
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate a unique ID for the usage record
            usage_id = str(uuid.uuid4())
            
            # Get endpoint ID based on job type
            endpoint_path = f"/speech/{job_type}"
            endpoint_id = DatabaseService.get_endpoint_id_by_path(endpoint_path)
            
            if not endpoint_id:
                logger.error(f"Endpoint ID not found for path: {endpoint_path}")
                return False
                
            # Connect to database
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Insert usage record
            query = """
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
            
            cursor.execute(query, [
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
            
            logger.info(f"Usage metrics logged for async {job_type} job with ID: {usage_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging usage metrics for async job: {str(e)}")
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
                "seconds_processed": seconds_processed
            }
            
            # Log usage metrics
            metrics = {
                "audio_seconds_processed": seconds_processed
            }
            JobProcessor.log_usage_metrics(user_id, "stt", metrics)
            
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
            
            # Log usage metrics
            metrics = {
                "audio_seconds_processed": seconds_processed,
                "model_used": model_deplopyment,
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
                "cached_tokens": total_cached_tokens
            }
            JobProcessor.log_usage_metrics(user_id, "stt_diarize", metrics)
            
            # Update job status to completed with results
            JobService.update_job_status(job_id, 'completed', result_data=result_data)
            
            logger.info(f"STT diarize job {job_id} processed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Error processing STT diarize job: {str(e)}"
            logger.error(error_msg)
            JobService.update_job_status(job_id, 'failed', error_msg)
            return False
