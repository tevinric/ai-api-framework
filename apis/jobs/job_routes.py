from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.jobs.job_service import JobService
import logging
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def get_job_status_route():
    """
    Get the status of a previously submitted job
    ---
    tags:
      - Job Management
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
      - name: job_id
        in: query
        type: string
        required: true
        description: ID of the job to check
    produces:
      - application/json
    responses:
      200:
        description: Job status retrieved successfully
        schema:
          type: object
          properties:
            job_id:
              type: string
              example: 12345678-1234-1234-1234-123456789012
            user_id:
              type: string
              example: 87654321-4321-4321-4321-210987654321
            file_id:
              type: string
              example: 11111111-1111-1111-1111-111111111111
            status:
              type: string
              enum: [pending, processing, completed, failed]
              example: completed
            created_at:
              type: string
              format: date-time
              example: 2024-03-16T10:30:45+02:00
            started_at:
              type: string
              format: date-time
              example: 2024-03-16T10:30:46+02:00
            completed_at:
              type: string
              format: date-time
              example: 2024-03-16T10:31:15+02:00
            error_message:
              type: string
              example: null
            job_type:
              type: string
              example: stt
            has_results:
              type: boolean
              example: true
            parameters:
              type: object
              example: null
            endpoint_id:
              type: string
              example: null
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
              example: job_id is required as a query parameter
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
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: You don't have permission to access this job
      404:
        description: Job not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: Job 12345678-1234-1234-1234-123456789012 not found
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Server Error
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
    
    # Get job_id from query parameter
    job_id = request.args.get('job_id')
    if not job_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "job_id is required as a query parameter"
        }, 400)
    
    try:
        # Get job details
        job_details, error = JobService.get_job(job_id, g.user_id)
        
        if error:
            if "not found" in error.lower():
                return create_api_response({
                    "error": "Not Found",
                    "message": error
                }, 404)
            elif "permission" in error.lower():
                return create_api_response({
                    "error": "Forbidden",
                    "message": error
                }, 403)
            else:
                return create_api_response({
                    "error": "Server Error",
                    "message": error
                }, 500)
        
        # For status endpoint, remove the actual result data if status is "completed"
        # This keeps the response size smaller
        if job_details["status"] == "completed" and "result" in job_details:
            # Just include a flag that results are available instead of the full results
            job_details["has_results"] = True
            job_details.pop("result")
        
        return create_api_response(job_details, 200)
        
    except Exception as e:
        logger.error(f"Error in get job status endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

def get_job_result_route():
    """
    Get the result of a completed job
    ---
    tags:
      - Job Management
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
      - name: job_id
        in: query
        type: string
        required: true
        description: ID of the job to retrieve results for
    produces:
      - application/json
    responses:
      200:
        description: Job result retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Job result retrieved successfully
            job_id:
              type: string
              example: 12345678-1234-1234-1234-123456789012
            status:
              type: string
              enum: [completed, failed]
              example: completed
            created_at:
              type: string
              format: date-time
              example: 2024-03-16T10:30:45+02:00
            started_at:
              type: string
              format: date-time
              example: 2024-03-16T10:30:46+02:00
            completed_at:
              type: string
              format: date-time
              example: 2024-03-16T10:31:15+02:00
            job_type:
              type: string
              example: stt
            result:
              type: object
              description: Result data specific to the job type
              properties:
                # For STT job type
                message:
                  type: string
                  example: Audio transcribed successfully
                transcript:
                  type: string
                  example: This is the transcribed text from the audio file.
                transcription_details:
                  type: object
                  description: Full details of the transcription results
                seconds_processed:
                  type: number
                  example: 45.6
                # For STT Diarize job type
                raw_transcript:
                  type: string
                  example: This is the raw transcribed text from the audio file.
                enhanced_transcript:
                  type: string
                  example: "[00:00:00] Speaker 1: This is the enhanced transcribed text with speaker diarization."
                prompt_tokens:
                  type: integer
                  example: 1000
                completion_tokens:
                  type: integer
                  example: 500
                total_tokens:
                  type: integer
                  example: 1500
                cached_tokens:
                  type: integer
                  example: 0
                embedded_tokens:
                  type: integer
                  example: 0
                model_used:
                  type: string
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
              example: job_id is required as a query parameter
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
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: Forbidden
            message:
              type: string
              example: You don't have permission to access this job
      404:
        description: Job not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: Not Found
            message:
              type: string
              example: Job 12345678-1234-1234-1234-123456789012 not found
      409:
        description: Job not completed
        schema:
          type: object
          properties:
            error:
              type: string
              example: Job Not Completed
            message:
              type: string
              example: Job is still in processing status. Please wait for completion.
            job_id:
              type: string
              example: 12345678-1234-1234-1234-123456789012
            status:
              type: string
              enum: [pending, processing]
              example: processing
            created_at:
              type: string
              format: date-time
              example: 2024-03-16T10:30:45+02:00
            started_at:
              type: string
              format: date-time
              example: 2024-03-16T10:30:46+02:00
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Server Error
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
    
    # Get job_id from query parameter
    job_id = request.args.get('job_id')
    if not job_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "job_id is required as a query parameter"
        }, 400)
    
    try:
        # Get job details
        job_details, error = JobService.get_job(job_id, g.user_id)
        
        if error:
            if "not found" in error.lower():
                return create_api_response({
                    "error": "Not Found",
                    "message": error
                }, 404)
            elif "permission" in error.lower():
                return create_api_response({
                    "error": "Forbidden",
                    "message": error
                }, 403)
            else:
                return create_api_response({
                    "error": "Server Error",
                    "message": error
                }, 500)
        
        # Check if job is completed
        if job_details["status"] == "pending" or job_details["status"] == "processing":
            return create_api_response({
                "error": "Job Not Completed",
                "message": f"Job is still in {job_details['status']} status. Please wait for completion.",
                "job_id": job_id,
                "status": job_details["status"],
                "created_at": job_details["created_at"],
                "started_at": job_details["started_at"]
            }, 409)
        
        # Prepare the response based on job status
        if job_details["status"] == "failed":
            response_data = {
                "message": "Job failed",
                "job_id": job_id,
                "status": "failed",
                "error_message": job_details.get("error_message", "Unknown error"),
                "created_at": job_details["created_at"],
                "started_at": job_details["started_at"],
                "completed_at": job_details["completed_at"],
                "job_type": job_details["job_type"]
            }
        else:
            response_data = {
                "message": "Job result retrieved successfully",
                "job_id": job_id,
                "status": "completed",
                "created_at": job_details["created_at"],
                "started_at": job_details["started_at"],
                "completed_at": job_details["completed_at"],
                "job_type": job_details["job_type"],
                "result": job_details.get("result", {})
            }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Error in get job result endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

def list_jobs_route():
    """
    List jobs for the authenticated user
    ---
    tags:
      - Job Management
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Valid token for authentication
      - name: limit
        in: query
        type: integer
        required: false
        default: 10
        description: Maximum number of jobs to return
      - name: offset
        in: query
        type: integer
        required: false
        default: 0
        description: Offset for pagination
      - name: status
        in: query
        type: string
        required: false
        description: Filter by job status (pending, processing, completed, failed)
      - name: job_type
        in: query
        type: string
        required: false
        description: Filter by job type (stt, stt_diarize)
    produces:
      - application/json
    responses:
      200:
        description: Jobs retrieved successfully
        schema:
          type: object
          properties:
            jobs:
              type: array
              items:
                type: object
                properties:
                  job_id:
                    type: string
                    example: 12345678-1234-1234-1234-123456789012
                  user_id:
                    type: string
                    example: 87654321-4321-4321-4321-210987654321
                  file_id:
                    type: string
                    example: 11111111-1111-1111-1111-111111111111
                  status:
                    type: string
                    enum: [pending, processing, completed, failed]
                    example: completed
                  created_at:
                    type: string
                    format: date-time
                    example: 2024-03-16T10:30:45+02:00
                  started_at:
                    type: string
                    format: date-time
                    example: 2024-03-16T10:30:46+02:00
                  completed_at:
                    type: string
                    format: date-time
                    example: 2024-03-16T10:31:15+02:00
                  error_message:
                    type: string
                    example: null
                  job_type:
                    type: string
                    example: stt
            count:
              type: integer
              example: 5
            offset:
              type: integer
              example: 0
            limit:
              type: integer
              example: 10
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
              example: limit and offset must be integer values
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
              example: Server Error
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
    
    # Get query parameters
    try:
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return create_api_response({
            "error": "Bad Request",
            "message": "limit and offset must be integer values"
        }, 400)
        
    status = request.args.get('status')
    job_type = request.args.get('job_type')
    
    try:
        # Get jobs for user
        jobs, error = JobService.list_jobs(g.user_id, limit, offset, status, job_type)
        
        if error:
            return create_api_response({
                "error": "Server Error",
                "message": error
            }, 500)
        
        return create_api_response({
            "jobs": jobs,
            "count": len(jobs),
            "offset": offset,
            "limit": limit
        }, 200)
        
    except Exception as e:
        logger.error(f"Error in list jobs endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

def register_job_routes(app):
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    """Register job management routes with the Flask app"""
    app.route('/jobs/status', methods=['GET'])(api_logger(check_endpoint_access(get_job_status_route)))
    app.route('/jobs/result', methods=['GET'])(api_logger(check_endpoint_access(get_job_result_route)))
    app.route('/jobs', methods=['GET'])(api_logger(check_endpoint_access(list_jobs_route)))
