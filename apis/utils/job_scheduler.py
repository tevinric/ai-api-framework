import logging
import threading
import time
from apis.jobs.job_service import JobService
from apis.jobs.job_processor import JobProcessor
from apis.utils.databaseService import DatabaseService

# Configure logging
logger = logging.getLogger(__name__)

def process_pending_jobs():
    """Process pending jobs from the queue"""
    try:
        # Get pending STT jobs
        stt_jobs, error = JobService.get_pending_jobs('stt', limit=5)
        if error:
            logger.error(f"Error getting pending STT jobs: {error}")
        
        if stt_jobs and len(stt_jobs) > 0:
            logger.info(f"Found {len(stt_jobs)} pending STT jobs")
            
            for job in stt_jobs:
                # Process each job in a separate thread
                thread = threading.Thread(
                    target=JobProcessor.process_stt_job,
                    args=(job['job_id'], job['user_id'], job['file_id'])
                )
                thread.daemon = True
                thread.start()
                logger.info(f"Started processing thread for STT job {job['job_id']}")
            
        # Get pending STT diarize jobs
        stt_diarize_jobs, error = JobService.get_pending_jobs('stt_diarize', limit=5)
        if error:
            logger.error(f"Error getting pending STT diarize jobs: {error}")
        
        if stt_diarize_jobs and len(stt_diarize_jobs) > 0:
            logger.info(f"Found {len(stt_diarize_jobs)} pending STT diarize jobs")
            
            for job in stt_diarize_jobs:
                # Get token for LLM service from the job's user
                # This could be a custom token or the user's own token
                user_id = job['user_id']
                token = None
                
                # Try to get a valid token for this user
                token_query = """
                SELECT token_value 
                FROM token_transactions 
                WHERE user_id = ? 
                AND DATEADD(HOUR, 2, GETUTCDATE()) < expires_on
                ORDER BY created_at DESC
                """
                
                try:
                    conn = DatabaseService.get_connection()
                    cursor = conn.cursor()
                    cursor.execute(token_query, [user_id])
                    result = cursor.fetchone()
                    if result:
                        token = result[0]
                    cursor.close()
                    conn.close()
                except Exception as e:
                    logger.error(f"Error fetching token for user {user_id}: {str(e)}")
                
                # Process each job in a separate thread
                thread = threading.Thread(
                    target=JobProcessor.process_stt_diarize_job,
                    args=(job['job_id'], job['user_id'], job['file_id'], token)
                )
                thread.daemon = True
                thread.start()
                logger.info(f"Started processing thread for STT diarize job {job['job_id']}")
        
        # Get pending TTS jobs
        tts_jobs, error = JobService.get_pending_jobs('tts', limit=5)
        if error:
            logger.error(f"Error getting pending TTS jobs: {error}")
        
        if tts_jobs and len(tts_jobs) > 0:
            logger.info(f"Found {len(tts_jobs)} pending TTS jobs")
            
            for job in tts_jobs:
                # Process each job in a separate thread
                thread = threading.Thread(
                    target=JobProcessor.process_tts_job,
                    args=(job['job_id'], job['user_id'], job['parameters'])
                )
                thread.daemon = True
                thread.start()
                logger.info(f"Started processing thread for TTS job {job['job_id']}")
                
        # Process generic jobs for other endpoints - extensible for future needs
        generic_jobs, error = JobService.get_pending_jobs(limit=5)
        if error:
            logger.error(f"Error getting pending generic jobs: {error}")
            
        if generic_jobs and len(generic_jobs) > 0:
            # Only look at jobs that aren't already covered by the specific handlers
            other_jobs = [job for job in generic_jobs if job['job_type'] not in ['stt', 'stt_diarize', 'tts']]
            
            if other_jobs:
                logger.info(f"Found {len(other_jobs)} pending jobs of other types")
                # Here we would handle other job types as needed
                
    except Exception as e:
        logger.error(f"Error in job scheduler: {str(e)}")

def start_job_scheduler():
    """Start the job scheduler in a background thread"""
    def scheduler_thread():
        logger.info("Job scheduler thread started")
        while True:
            try:
                process_pending_jobs()
            except Exception as e:
                logger.error(f"Error in scheduler thread: {str(e)}")
            
            # Sleep for a short interval before checking again
            time.sleep(10)  # Check every 10 seconds
    
    # Start the scheduler in a daemon thread
    thread = threading.Thread(target=scheduler_thread)
    thread.daemon = True
    thread.start()
    logger.info("Job scheduler started")
