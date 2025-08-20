"""
Async Execution Handler for Agent System
Handles asynchronous agent execution to work within KONG timeout limitations
"""

import asyncio
import json
import uuid
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from apis.jobs.job_service import JobService
from apis.agents.agent_manager import AgentManager
from apis.agents.tool_registry import tool_registry
from apis.utils.databaseService import DatabaseService
import threading
import queue
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class AsyncAgentExecutor:
    """Handles asynchronous execution of agent tasks"""
    
    def __init__(self):
        self.agent_manager = AgentManager()
        self.job_service = JobService()
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.active_runs: Dict[str, Dict[str, Any]] = {}
        
    async def submit_agent_task(
        self,
        user_id: str,
        agent_id: str,
        message: str,
        thread_id: Optional[str] = None,
        tools: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        webhook_url: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Submit an agent task for async execution
        Returns immediately with a job ID for status tracking
        
        Returns:
            Tuple of (job_id, error_message)
        """
        try:
            # Create or use existing thread
            if not thread_id:
                thread_id, error = await self.agent_manager.create_thread(
                    user_id=user_id,
                    agent_id=agent_id,
                    initial_message=None,
                    metadata={"async_execution": True}
                )
                if error:
                    return None, error
            
            # Prepare job parameters
            job_params = {
                "agent_id": agent_id,
                "thread_id": thread_id,
                "message": message,
                "tools": tools,
                "context": context,
                "webhook_url": webhook_url
            }
            
            # Get endpoint ID for agent endpoint
            endpoint_id = self._get_agent_endpoint_id()
            
            # Create async job
            job_id, error = self.job_service.create_job(
                user_id=user_id,
                job_type="agent_execution",
                parameters=job_params,
                endpoint_id=endpoint_id
            )
            
            if error:
                return None, error
            
            # Submit to executor for background processing
            self.executor.submit(
                self._execute_agent_task_async,
                job_id,
                user_id,
                agent_id,
                thread_id,
                message,
                tools,
                context,
                webhook_url
            )
            
            logger.info(f"Submitted agent task {job_id} for async execution")
            return job_id, None
            
        except Exception as e:
            error_msg = f"Failed to submit agent task: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    def _execute_agent_task_async(
        self,
        job_id: str,
        user_id: str,
        agent_id: str,
        thread_id: str,
        message: str,
        tools: Optional[List[str]],
        context: Optional[Dict[str, Any]],
        webhook_url: Optional[str]
    ):
        """Execute agent task in background thread"""
        try:
            # Run async function in new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                self._execute_agent_task(
                    job_id, user_id, agent_id, thread_id,
                    message, tools, context
                )
            )
            
            # Send webhook notification if URL provided
            if webhook_url and result:
                self._send_webhook_notification(webhook_url, job_id, result)
            
            loop.close()
            
        except Exception as e:
            logger.error(f"Error in async agent execution: {str(e)}")
            self.job_service.update_job_status(
                job_id=job_id,
                status="failed",
                error_message=str(e)
            )
    
    async def _execute_agent_task(
        self,
        job_id: str,
        user_id: str,
        agent_id: str,
        thread_id: str,
        message: str,
        tools: Optional[List[str]],
        context: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Execute the actual agent task"""
        try:
            # Update job status to processing
            self.job_service.update_job_status(job_id, "processing")
            
            # Store run info
            self.active_runs[job_id] = {
                "user_id": user_id,
                "agent_id": agent_id,
                "thread_id": thread_id,
                "started_at": datetime.utcnow(),
                "status": "running"
            }
            
            # Get available tools for user if specified
            tools_config = None
            if tools:
                user_tools = tool_registry.get_tools_for_user(user_id)
                tools_config = [
                    tool.to_openai_function()
                    for tool in user_tools
                    if tool.name in tools
                ]
            
            # Run agent
            run_id, usage_metrics, error = await self.agent_manager.run_agent(
                user_id=user_id,
                agent_id=agent_id,
                thread_id=thread_id,
                message=message,
                tools_override=tools_config,
                metadata={"job_id": job_id, "context": context}
            )
            
            if error:
                raise Exception(error)
            
            # Poll for completion with timeout
            max_wait_time = 55  # 55 seconds to stay under KONG timeout
            poll_interval = 2  # Poll every 2 seconds
            start_time = datetime.utcnow()
            
            while (datetime.utcnow() - start_time).total_seconds() < max_wait_time:
                status_info, error = await self.agent_manager.get_run_status(
                    user_id=user_id,
                    thread_id=thread_id,
                    run_id=run_id
                )
                
                if error:
                    raise Exception(error)
                
                if status_info["status"] == "completed":
                    # Successful completion
                    result_data = {
                        "run_id": run_id,
                        "thread_id": thread_id,
                        "response": status_info.get("response"),
                        "usage": status_info.get("usage", {}),
                        "completed_at": datetime.utcnow().isoformat()
                    }
                    
                    # Log usage metrics
                    await self._log_usage_metrics(
                        job_id=job_id,
                        user_id=user_id,
                        agent_id=agent_id,
                        usage=status_info.get("usage", {})
                    )
                    
                    # Update job status
                    self.job_service.update_job_status(
                        job_id=job_id,
                        status="completed",
                        result_data=result_data
                    )
                    
                    # Clean up active run
                    del self.active_runs[job_id]
                    
                    return result_data
                
                elif status_info["status"] in ["failed", "cancelled", "expired"]:
                    # Handle failure
                    error_msg = status_info.get("last_error", {}).get("message", "Agent run failed")
                    raise Exception(error_msg)
                
                # Still running, wait before next poll
                await asyncio.sleep(poll_interval)
            
            # Timeout reached
            raise Exception("Agent execution timed out after 55 seconds")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Agent task {job_id} failed: {error_msg}")
            
            # Update job status
            self.job_service.update_job_status(
                job_id=job_id,
                status="failed",
                error_message=error_msg
            )
            
            # Clean up active run
            if job_id in self.active_runs:
                del self.active_runs[job_id]
            
            return None
    
    async def get_agent_job_status(
        self,
        user_id: str,
        job_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Get the status of an async agent job
        
        Returns:
            Tuple of (status_info, error_message)
        """
        try:
            # Get job details
            job_details, error = self.job_service.get_job(job_id, user_id)
            
            if error:
                return None, error
            
            # Format response
            status_info = {
                "job_id": job_details["job_id"],
                "status": job_details["status"],
                "created_at": job_details["created_at"],
                "started_at": job_details["started_at"],
                "completed_at": job_details["completed_at"],
                "error_message": job_details["error_message"]
            }
            
            # Include result data if completed
            if job_details["status"] == "completed" and job_details["result"]:
                status_info["result"] = job_details["result"]
            
            # Include progress info if still running
            if job_id in self.active_runs:
                run_info = self.active_runs[job_id]
                elapsed = (datetime.utcnow() - run_info["started_at"]).total_seconds()
                status_info["elapsed_seconds"] = elapsed
                status_info["estimated_remaining"] = max(0, 55 - elapsed)
            
            return status_info, None
            
        except Exception as e:
            error_msg = f"Failed to get job status: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    async def cancel_agent_job(
        self,
        user_id: str,
        job_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Cancel a running agent job
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Verify job ownership
            job_details, error = self.job_service.get_job(job_id, user_id)
            
            if error:
                return False, error
            
            if job_details["status"] not in ["pending", "processing"]:
                return False, f"Job {job_id} is not cancellable (status: {job_details['status']})"
            
            # Update job status
            self.job_service.update_job_status(
                job_id=job_id,
                status="cancelled",
                error_message="Cancelled by user"
            )
            
            # Clean up active run if exists
            if job_id in self.active_runs:
                del self.active_runs[job_id]
            
            logger.info(f"Cancelled agent job {job_id}")
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to cancel job: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def _log_usage_metrics(
        self,
        job_id: str,
        user_id: str,
        agent_id: str,
        usage: Dict[str, Any]
    ):
        """Log usage metrics for agent execution"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Get endpoint ID
            endpoint_id = self._get_agent_endpoint_id()
            
            # Insert usage record
            usage_id = str(uuid.uuid4())
            
            query = """
            INSERT INTO user_usage (
                id, user_id, endpoint_id, timestamp,
                model_used, prompt_tokens, completion_tokens,
                total_tokens, api_log_id
            ) VALUES (
                ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()),
                ?, ?, ?, ?, ?
            )
            """
            
            cursor.execute(query, [
                usage_id,
                user_id,
                endpoint_id,
                f"agent_{agent_id}",
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0),
                job_id  # Use job_id as api_log_id reference
            ])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Logged usage metrics for job {job_id}")
            
        except Exception as e:
            logger.error(f"Error logging usage metrics: {str(e)}")
    
    def _get_agent_endpoint_id(self) -> Optional[str]:
        """Get the endpoint ID for agent APIs"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id FROM endpoints WHERE endpoint_path = '/agents/execute'",
                []
            )
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return str(result[0]) if result else None
            
        except Exception as e:
            logger.error(f"Error getting agent endpoint ID: {str(e)}")
            return None
    
    def _send_webhook_notification(
        self,
        webhook_url: str,
        job_id: str,
        result: Dict[str, Any]
    ):
        """Send webhook notification when job completes"""
        try:
            import requests
            
            payload = {
                "job_id": job_id,
                "status": "completed",
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info(f"Webhook notification sent for job {job_id}")
            else:
                logger.warning(f"Webhook notification failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending webhook notification: {str(e)}")

# Global executor instance
async_executor = AsyncAgentExecutor()