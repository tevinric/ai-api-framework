"""
Agent Manager for OpenAI Agents SDK Integration
Handles agent creation, management, and execution with Azure OpenAI
"""

from typing import Dict, List, Optional, Any, Tuple
import json
import uuid
import logging
from datetime import datetime
import asyncio
from openai import AsyncAzureOpenAI
from openai.types.beta import Assistant, Thread
from openai.types.beta.threads import Message, Run
import os
from apis.utils.databaseService import DatabaseService
from apis.utils.config import get_azure_openai_config

logger = logging.getLogger(__name__)

class AgentManager:
    """Manages OpenAI Agents with Azure OpenAI integration"""
    
    def __init__(self):
        """Initialize the Agent Manager with Azure OpenAI client"""
        config = get_azure_openai_config()
        self.client = AsyncAzureOpenAI(
            api_key=config['api_key'],
            api_version=config['api_version'],
            azure_endpoint=config['endpoint']
        )
        self.deployment_name = config.get('deployment_name', 'gpt-4o')
        
    async def create_agent(
        self,
        user_id: str,
        name: str,
        instructions: str,
        tools: List[Dict[str, Any]] = None,
        model: str = None,
        metadata: Dict[str, Any] = None,
        temperature: float = 0.7,
        top_p: float = 1.0
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create a new agent using OpenAI Agents SDK
        
        Returns:
            Tuple of (agent_id, error_message)
        """
        try:
            # Use provided model or default deployment
            model_to_use = model or self.deployment_name
            
            # Prepare tools configuration
            tools_config = tools or []
            
            # Add default tools if none provided
            if not tools_config:
                tools_config = [
                    {"type": "code_interpreter"},
                    {"type": "file_search"}
                ]
            
            # Create metadata with user context
            agent_metadata = metadata or {}
            agent_metadata.update({
                "user_id": user_id,
                "created_by": "ai-api-framework",
                "created_at": datetime.utcnow().isoformat()
            })
            
            # Create assistant using OpenAI SDK
            assistant = await self.client.beta.assistants.create(
                name=name,
                instructions=instructions,
                tools=tools_config,
                model=model_to_use,
                metadata=agent_metadata,
                temperature=temperature,
                top_p=top_p
            )
            
            # Store agent configuration in database
            await self._store_agent_config(
                user_id=user_id,
                agent_id=assistant.id,
                name=name,
                instructions=instructions,
                tools=tools_config,
                model=model_to_use,
                metadata=agent_metadata
            )
            
            logger.info(f"Created agent {assistant.id} for user {user_id}")
            return assistant.id, None
            
        except Exception as e:
            error_msg = f"Failed to create agent: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    async def create_thread(
        self,
        user_id: str,
        agent_id: str,
        initial_message: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create a new conversation thread for an agent
        
        Returns:
            Tuple of (thread_id, error_message)
        """
        try:
            # Verify agent ownership
            if not await self._verify_agent_ownership(user_id, agent_id):
                return None, "Agent not found or unauthorized"
            
            # Create thread metadata
            thread_metadata = metadata or {}
            thread_metadata.update({
                "user_id": user_id,
                "agent_id": agent_id,
                "created_at": datetime.utcnow().isoformat()
            })
            
            # Create thread using OpenAI SDK
            thread = await self.client.beta.threads.create(
                metadata=thread_metadata
            )
            
            # Add initial message if provided
            if initial_message:
                await self.client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=initial_message
                )
            
            # Store thread info in database
            await self._store_thread_info(
                user_id=user_id,
                agent_id=agent_id,
                thread_id=thread.id,
                metadata=thread_metadata
            )
            
            logger.info(f"Created thread {thread.id} for agent {agent_id}")
            return thread.id, None
            
        except Exception as e:
            error_msg = f"Failed to create thread: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    async def run_agent(
        self,
        user_id: str,
        agent_id: str,
        thread_id: str,
        message: str,
        tools_override: Optional[List[Dict[str, Any]]] = None,
        additional_instructions: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """
        Run an agent with a message in a thread
        
        Returns:
            Tuple of (run_id, usage_metrics, error_message)
        """
        try:
            # Verify ownership
            if not await self._verify_agent_ownership(user_id, agent_id):
                return None, None, "Agent not found or unauthorized"
            
            if not await self._verify_thread_ownership(user_id, thread_id):
                return None, None, "Thread not found or unauthorized"
            
            # Add user message to thread
            await self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message
            )
            
            # Create and execute run
            run_metadata = metadata or {}
            run_metadata.update({
                "user_id": user_id,
                "initiated_at": datetime.utcnow().isoformat()
            })
            
            # Create run with optional overrides
            run_params = {
                "thread_id": thread_id,
                "assistant_id": agent_id,
                "metadata": run_metadata
            }
            
            if tools_override:
                run_params["tools"] = tools_override
            
            if additional_instructions:
                run_params["additional_instructions"] = additional_instructions
            
            run = await self.client.beta.threads.runs.create(**run_params)
            
            # Store run info for async processing
            await self._store_run_info(
                user_id=user_id,
                agent_id=agent_id,
                thread_id=thread_id,
                run_id=run.id,
                status="queued",
                metadata=run_metadata
            )
            
            # Return run ID for async status checking
            logger.info(f"Started run {run.id} for agent {agent_id}")
            return run.id, None, None
            
        except Exception as e:
            error_msg = f"Failed to run agent: {str(e)}"
            logger.error(error_msg)
            return None, None, error_msg
    
    async def get_run_status(
        self,
        user_id: str,
        thread_id: str,
        run_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Get the status of an agent run
        
        Returns:
            Tuple of (status_info, error_message)
        """
        try:
            # Verify ownership
            if not await self._verify_thread_ownership(user_id, thread_id):
                return None, "Thread not found or unauthorized"
            
            # Get run status from OpenAI
            run = await self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            
            # Prepare status response
            status_info = {
                "run_id": run.id,
                "status": run.status,
                "created_at": run.created_at,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "failed_at": run.failed_at,
                "expires_at": run.expires_at,
                "last_error": run.last_error.dict() if run.last_error else None,
                "metadata": run.metadata
            }
            
            # If completed, get the messages
            if run.status == "completed":
                messages = await self.client.beta.threads.messages.list(
                    thread_id=thread_id,
                    order="desc",
                    limit=10
                )
                
                # Extract assistant's response
                assistant_messages = []
                for msg in messages.data:
                    if msg.role == "assistant" and msg.run_id == run_id:
                        content_texts = []
                        for content in msg.content:
                            if content.type == "text":
                                content_texts.append(content.text.value)
                        if content_texts:
                            assistant_messages.append(" ".join(content_texts))
                
                status_info["response"] = assistant_messages[0] if assistant_messages else None
                
                # Extract usage metrics if available
                if hasattr(run, 'usage') and run.usage:
                    status_info["usage"] = {
                        "prompt_tokens": run.usage.prompt_tokens,
                        "completion_tokens": run.usage.completion_tokens,
                        "total_tokens": run.usage.total_tokens
                    }
            
            # Update run status in database
            await self._update_run_status(run_id, run.status, status_info)
            
            return status_info, None
            
        except Exception as e:
            error_msg = f"Failed to get run status: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    async def list_user_agents(
        self,
        user_id: str,
        include_shared: bool = False
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        List all agents available to a user
        
        Returns:
            Tuple of (agents_list, error_message)
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT 
                agent_id, name, instructions, model, tools, 
                metadata, created_at, is_shared, owner_id
            FROM agent_configurations
            WHERE owner_id = ? OR (is_shared = 1 AND ? = 1)
            ORDER BY created_at DESC
            """
            
            cursor.execute(query, [user_id, 1 if include_shared else 0])
            agents = cursor.fetchall()
            
            agents_list = []
            for agent in agents:
                agents_list.append({
                    "agent_id": agent[0],
                    "name": agent[1],
                    "instructions": agent[2],
                    "model": agent[3],
                    "tools": json.loads(agent[4]) if agent[4] else [],
                    "metadata": json.loads(agent[5]) if agent[5] else {},
                    "created_at": agent[6].isoformat() if agent[6] else None,
                    "is_shared": bool(agent[7]),
                    "is_owner": agent[8] == user_id
                })
            
            cursor.close()
            conn.close()
            
            return agents_list, None
            
        except Exception as e:
            error_msg = f"Failed to list agents: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    async def delete_agent(
        self,
        user_id: str,
        agent_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Delete an agent
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Verify ownership
            if not await self._verify_agent_ownership(user_id, agent_id):
                return False, "Agent not found or unauthorized"
            
            # Delete from OpenAI
            await self.client.beta.assistants.delete(agent_id)
            
            # Delete from database
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM agent_configurations WHERE agent_id = ? AND owner_id = ?",
                [agent_id, user_id]
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Deleted agent {agent_id} for user {user_id}")
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to delete agent: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    # Helper methods
    async def _verify_agent_ownership(self, user_id: str, agent_id: str) -> bool:
        """Verify that a user owns or has access to an agent"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT COUNT(*) FROM agent_configurations 
                WHERE agent_id = ? AND (owner_id = ? OR is_shared = 1)
                """,
                [agent_id, user_id]
            )
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return result[0] > 0 if result else False
            
        except Exception as e:
            logger.error(f"Error verifying agent ownership: {str(e)}")
            return False
    
    async def _verify_thread_ownership(self, user_id: str, thread_id: str) -> bool:
        """Verify that a user owns a thread"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT COUNT(*) FROM agent_threads 
                WHERE thread_id = ? AND user_id = ?
                """,
                [thread_id, user_id]
            )
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return result[0] > 0 if result else False
            
        except Exception as e:
            logger.error(f"Error verifying thread ownership: {str(e)}")
            return False
    
    async def _store_agent_config(self, **kwargs):
        """Store agent configuration in database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO agent_configurations (
                    id, owner_id, agent_id, name, instructions, 
                    model, tools, metadata, created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, GETUTCDATE()
                )
                """,
                [
                    str(uuid.uuid4()),
                    kwargs['user_id'],
                    kwargs['agent_id'],
                    kwargs['name'],
                    kwargs['instructions'],
                    kwargs['model'],
                    json.dumps(kwargs.get('tools', [])),
                    json.dumps(kwargs.get('metadata', {}))
                ]
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing agent config: {str(e)}")
    
    async def _store_thread_info(self, **kwargs):
        """Store thread information in database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO agent_threads (
                    id, user_id, agent_id, thread_id, metadata, created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, GETUTCDATE()
                )
                """,
                [
                    str(uuid.uuid4()),
                    kwargs['user_id'],
                    kwargs['agent_id'],
                    kwargs['thread_id'],
                    json.dumps(kwargs.get('metadata', {}))
                ]
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing thread info: {str(e)}")
    
    async def _store_run_info(self, **kwargs):
        """Store run information in database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO agent_runs (
                    id, user_id, agent_id, thread_id, run_id, 
                    status, metadata, created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, GETUTCDATE()
                )
                """,
                [
                    str(uuid.uuid4()),
                    kwargs['user_id'],
                    kwargs['agent_id'],
                    kwargs['thread_id'],
                    kwargs['run_id'],
                    kwargs['status'],
                    json.dumps(kwargs.get('metadata', {}))
                ]
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing run info: {str(e)}")
    
    async def _update_run_status(self, run_id: str, status: str, info: Dict[str, Any]):
        """Update run status in database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                UPDATE agent_runs 
                SET status = ?, result_data = ?, updated_at = GETUTCDATE()
                WHERE run_id = ?
                """,
                [status, json.dumps(info), run_id]
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating run status: {str(e)}")