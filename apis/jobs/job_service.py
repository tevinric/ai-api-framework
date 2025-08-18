import uuid
import logging
import json
from datetime import datetime
import pytz
from apis.utils.databaseService import DatabaseService

# Configure logging
logger = logging.getLogger(__name__)

class JobService:
    @staticmethod
    def create_job(user_id, job_type, file_id=None, parameters=None, endpoint_id=None):
        """
        Create a new job for asynchronous processing
        
        Args:
            user_id (str): ID of the user who submitted the job
            job_type (str): Type of job (e.g., 'stt', 'stt_diarize')
            file_id (str, optional): ID of the file to process, if applicable
            parameters (dict, optional): Additional parameters for the job
            endpoint_id (str, optional): ID of the API endpoint
            
        Returns:
            tuple: (job_id, None) or (None, error_message)
        """
        try:
            # Generate job ID
            job_id = str(uuid.uuid4())
            
            # Get database connection
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Insert job record
            query = """
            INSERT INTO async_jobs (
                id, user_id, file_id, status, created_at, job_type, parameters, endpoint_id
            ) VALUES (
                ?, ?, ?, 'pending', DATEADD(HOUR, 2, GETUTCDATE()), ?, ?, ?
            )
            """
            
            params_json = json.dumps(parameters) if parameters else None
            
            cursor.execute(query, [
                job_id, 
                user_id, 
                file_id, 
                job_type, 
                params_json,
                endpoint_id
            ])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Created job {job_id} of type {job_type} for user {user_id}")
            return job_id, None
            
        except Exception as e:
            logger.error(f"Error creating job: {str(e)}")
            return None, str(e)
    
    @staticmethod
    def update_job_status(job_id, status, error_message=None, result_data=None):
        """
        Update the status of a job
        
        Args:
            job_id (str): ID of the job to update
            status (str): New status ('pending', 'processing', 'completed', 'failed')
            error_message (str, optional): Error message if status is 'failed'
            result_data (dict, optional): Results data if status is 'completed'
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get database connection
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Prepare the query
            if status == 'processing':
                query = """
                UPDATE async_jobs
                SET status = ?, started_at = DATEADD(HOUR, 2, GETUTCDATE())
                WHERE id = ?
                """
                params = [status, job_id]
            elif status == 'completed':
                query = """
                UPDATE async_jobs
                SET status = ?, 
                    completed_at = DATEADD(HOUR, 2, GETUTCDATE()),
                    result_data = ?
                WHERE id = ?
                """
                params = [status, json.dumps(result_data) if result_data else None, job_id]
            elif status == 'failed':
                query = """
                UPDATE async_jobs
                SET status = ?, 
                    completed_at = DATEADD(HOUR, 2, GETUTCDATE()),
                    error_message = ?
                WHERE id = ?
                """
                params = [status, error_message, job_id]
            else:
                query = """
                UPDATE async_jobs
                SET status = ?
                WHERE id = ?
                """
                params = [status, job_id]
            
            # Execute the query
            cursor.execute(query, params)
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Updated job {job_id} status to {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating job status: {str(e)}")
            return False
    
    @staticmethod
    def get_job(job_id, user_id=None):
        """
        Get job details
        
        Args:
            job_id (str): ID of the job to retrieve
            user_id (str, optional): ID of the user for permission check
            
        Returns:
            tuple: (job_details, None) or (None, error_message)
        """
        try:
            # Get database connection
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Get job details
            query = """
            SELECT 
                j.id, j.user_id, j.file_id, j.status, j.created_at, 
                j.started_at, j.completed_at, j.error_message, j.job_type, j.result_data,
                j.parameters, j.endpoint_id, u.scope as user_scope
            FROM 
                async_jobs j
            JOIN 
                users u ON j.user_id = u.id
            WHERE 
                j.id = ?
            """
            
            cursor.execute(query, [job_id])
            job = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not job:
                return None, f"Job {job_id} not found"
            
            # Check permission if user_id is provided
            if user_id and str(job[1]) != user_id:
                # Check if user is admin (scope = 0)
                user_scope = job[12]
                if user_scope != 0:
                    return None, "You don't have permission to access this job"
            
            # Parse result data if available
            result_data = json.loads(job[9]) if job[9] else None
            parameters = json.loads(job[10]) if job[10] else None
            
            # Format job details
            job_details = {
                "job_id": str(job[0]),
                "user_id": str(job[1]),
                "file_id": str(job[2]) if job[2] else None,
                "status": job[3],
                "created_at": job[4].isoformat() if job[4] else None,
                "started_at": job[5].isoformat() if job[5] else None,
                "completed_at": job[6].isoformat() if job[6] else None,
                "error_message": job[7],
                "job_type": job[8],
                "result": result_data,
                "parameters": parameters,
                "endpoint_id": str(job[11]) if job[11] else None
            }
            
            return job_details, None
            
        except Exception as e:
            logger.error(f"Error getting job details: {str(e)}")
            return None, str(e)
            
    @staticmethod
    def list_jobs(user_id, limit=10, offset=0, status=None, job_type=None):
        """
        List jobs for a user
        
        Args:
            user_id (str): ID of the user
            limit (int): Maximum number of jobs to return
            offset (int): Offset for pagination
            status (str, optional): Filter by status
            job_type (str, optional): Filter by job type
            
        Returns:
            tuple: (jobs_list, None) or (None, error_message)
        """
        try:
            # Get database connection
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Build query with filters
            query = """
            SELECT 
                id, user_id, file_id, status, created_at, 
                started_at, completed_at, error_message, job_type
            FROM 
                async_jobs
            WHERE 
                user_id = ?
            """
            
            params = [user_id]
            
            if status:
                query += " AND status = ?"
                params.append(status)
                
            if job_type:
                query += " AND job_type = ?"
                params.append(job_type)
                
            query += " ORDER BY created_at DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
            params.append(offset)
            params.append(limit)
            
            # Execute query
            cursor.execute(query, params)
            
            # Process results
            jobs_list = []
            for row in cursor.fetchall():
                job = {
                    "job_id": str(row[0]),
                    "user_id": str(row[1]),
                    "file_id": str(row[2]) if row[2] else None,
                    "status": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "started_at": row[5].isoformat() if row[5] else None,
                    "completed_at": row[6].isoformat() if row[6] else None,
                    "error_message": row[7],
                    "job_type": row[8]
                }
                jobs_list.append(job)
                
            cursor.close()
            conn.close()
            
            return jobs_list, None
            
        except Exception as e:
            logger.error(f"Error listing jobs: {str(e)}")
            return None, str(e)

    @staticmethod
    def get_pending_jobs(job_type=None, limit=10):
        """
        Get pending jobs for processing
        
        Args:
            job_type (str, optional): Filter by job type
            limit (int): Maximum number of jobs to return
            
        Returns:
            tuple: (jobs_list, None) or (None, error_message)
        """
        try:
            # Get database connection
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Build query with filters
            query = """
            SELECT 
                id, user_id, file_id, job_type, parameters, endpoint_id
            FROM 
                async_jobs
            WHERE 
                status = 'pending'
            """
            
            params = []
            
            if job_type:
                query += " AND job_type = ?"
                params.append(job_type)
                
            query += " ORDER BY created_at ASC OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY"
            params.append(limit)
            
            # Execute query
            cursor.execute(query, params)
            
            # Process results
            jobs_list = []
            for row in cursor.fetchall():
                parameters = json.loads(row[4]) if row[4] else None
                
                job = {
                    "job_id": str(row[0]),
                    "user_id": str(row[1]),
                    "file_id": str(row[2]) if row[2] else None,
                    "job_type": row[3],
                    "parameters": parameters,
                    "endpoint_id": str(row[5]) if row[5] else None
                }
                jobs_list.append(job)
                
            cursor.close()
            conn.close()
            
            return jobs_list, None
            
        except Exception as e:
            logger.error(f"Error getting pending jobs: {str(e)}")
            return None, str(e)