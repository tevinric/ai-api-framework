# apis/agentic/agent_core.py
import json
import uuid
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import asyncio
from apis.utils.databaseService import DatabaseService
from apis.utils.llmServices import gpt4o_service, deepseek_v3_service
from apis.agentic.tools import ToolRegistry, ToolExecutor
from apis.agentic.memory import ConversationMemory
from apis.agentic.planner import TaskPlanner

logger = logging.getLogger(__name__)

class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class AgentTask:
    task_id: str
    user_input: str
    context: Dict[str, Any]
    status: AgentStatus
    steps: List[Dict[str, Any]]
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = None
    completed_at: Optional[datetime] = None

class Agent:
    def __init__(self, agent_id: str, user_id: str, model: str = "gpt-4o"):
        self.agent_id = agent_id
        self.user_id = user_id
        self.model = model
        self.status = AgentStatus.IDLE
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor()
        self.memory = ConversationMemory(agent_id)
        self.planner = TaskPlanner()
        self.max_iterations = 10
        self.current_task: Optional[AgentTask] = None
        
        # Token usage tracking
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_cached_tokens = 0
        self.llm_call_count = 0
        
    async def execute_task(self, user_input: str, context: Dict[str, Any] = None) -> AgentTask:
        """Execute an agentic task with planning, tool use, and iteration"""
        task_id = str(uuid.uuid4())
        
        # Reset token counters for this task
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_cached_tokens = 0
        self.llm_call_count = 0
        
        # Ensure context is a dictionary
        if context is None:
            context = {}
        elif not isinstance(context, dict):
            logger.warning(f"Context is not a dict, got: {type(context)}, converting to empty dict")
            context = {}
        
        task = AgentTask(
            task_id=task_id,
            user_input=user_input,
            context=context.copy(),  # Make a copy to avoid mutations
            status=AgentStatus.THINKING,
            steps=[],
            created_at=datetime.utcnow()
        )
        
        self.current_task = task
        
        try:
            # Add user input to memory
            self.memory.add_message("user", user_input)
            
            # Step 1: Analyze and plan
            task.status = AgentStatus.PLANNING
            await self._plan_task(task)
            
            # Step 2: Execute plan iteratively
            task.status = AgentStatus.EXECUTING
            await self._execute_plan(task)
            
            # Step 3: Final synthesis
            await self._synthesize_result(task)
            
            task.status = AgentStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            
        except Exception as e:
            task.status = AgentStatus.ERROR
            task.error = str(e)
            logger.error(f"Agent task failed: {str(e)}", exc_info=True)
            
        finally:
            # Ensure task.context is still a dictionary
            if not isinstance(task.context, dict):
                logger.error(f"Task context is not a dict: {type(task.context)}, resetting to empty dict")
                task.context = {}
            
            # Add token usage to task context for later retrieval
            task.context.update({
                'token_usage': {
                    'prompt_tokens': self.total_prompt_tokens,
                    'completion_tokens': self.total_completion_tokens,
                    'total_tokens': self.total_tokens,
                    'cached_tokens': self.total_cached_tokens,
                    'llm_calls': self.llm_call_count,
                    'model': self.model
                }
            })
            
            # Save task to database
            await self._save_task(task)
            
        return task
    
    async def _plan_task(self, task: AgentTask):
        """Create a plan for executing the task"""
        planning_prompt = f"""
You are an AI agent that needs to break down complex tasks into executable steps.

Available tools: {self._get_available_tools_description()}

Task: {task.user_input}
Context: {json.dumps(task.context, indent=2)}

Create a step-by-step plan to complete this task. Each step should specify:
1. The action to take
2. Which tool to use (if any)
3. Expected outcome

Return your plan as a JSON array of steps:
[
  {{
    "step": 1,
    "action": "description of action",
    "tool": "tool_name or null",
    "parameters": {{}},
    "expected_outcome": "what this step should achieve"
  }}
]
"""
        
        # Get plan from LLM
        try:
            response = await self._call_llm(planning_prompt, json_output=True)
            
            if response:
                plan = json.loads(response)
                task.steps = plan
                logger.info(f"Created plan with {len(plan)} steps for task {task.task_id}")
            else:
                raise Exception("Empty response from LLM")
                
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse plan JSON: {e}, using fallback plan")
            # Fallback to single step if JSON parsing fails
            task.steps = [{
                "step": 1,
                "action": "Execute task directly",
                "tool": None,
                "parameters": {},
                "expected_outcome": "Complete the user's request"
            }]
    
    async def _execute_plan(self, task: AgentTask):
        """Execute the planned steps iteratively"""
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Agent iteration {iteration} for task {task.task_id}")
            
            # Determine next action
            next_action = await self._determine_next_action(task)
            
            if next_action and next_action.get("action") == "complete":
                break
                
            # Execute the action
            if next_action:
                result = await self._execute_action(next_action)
                
                # Update memory with the action and result
                self.memory.add_message("assistant", f"Action: {next_action.get('description', 'Unknown action')}")
                self.memory.add_message("system", f"Result: {result}")
            
            # Check if task is complete
            is_complete = await self._check_completion(task)
            if is_complete:
                break
    
    async def _determine_next_action(self, task: AgentTask) -> Dict[str, Any]:
        """Determine the next action to take"""
        conversation_history = self.memory.get_conversation_history()
        
        action_prompt = f"""
You are an AI agent executing a task. Based on the conversation history and current progress, determine the next action.

Original task: {task.user_input}
Plan: {json.dumps(task.steps, indent=2)}

Conversation history:
{conversation_history}

Available tools: {self._get_available_tools_description()}

Determine the next action. Return JSON:
{{
  "action": "tool_name or 'complete' or 'think'",
  "description": "what you're doing",
  "parameters": {{}},
  "reasoning": "why you're taking this action"
}}
"""
        
        try:
            response = await self._call_llm(action_prompt, json_output=True)
            
            if response:
                return json.loads(response)
            else:
                raise Exception("Empty response from LLM")
                
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse action JSON: {e}, using fallback action")
            return {
                "action": "think",
                "description": "Analyze the current situation",
                "parameters": {},
                "reasoning": "JSON parsing failed, defaulting to thinking"
            }
    
    async def _execute_action(self, action: Dict[str, Any]) -> str:
        """Execute a specific action"""
        if not action or not isinstance(action, dict):
            return "Invalid action provided"
            
        action_type = action.get("action")
        
        if action_type == "think":
            # Pure reasoning step
            thinking_prompt = f"""
Think through the current situation and what needs to be done next.

Action: {action.get('description')}
Parameters: {json.dumps(action.get('parameters', {}), indent=2)}

Provide your thoughts and analysis.
"""
            return await self._call_llm(thinking_prompt)
        
        elif action_type == "complete":
            return "Task marked as complete"
        
        else:
            # Tool execution
            try:
                return await self.tool_executor.execute_tool(
                    action_type,
                    action.get("parameters", {}),
                    self.user_id
                )
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                return f"Tool execution failed: {str(e)}"
    
    async def _check_completion(self, task: AgentTask) -> bool:
        """Check if the task has been completed satisfactorily"""
        conversation_history = self.memory.get_conversation_history()
        
        completion_prompt = f"""
Review the conversation and determine if the original task has been completed satisfactorily.

Original task: {task.user_input}
Conversation history:
{conversation_history}

Has the task been completed? Respond with just "YES" or "NO" and a brief explanation.
"""
        
        try:
            response = await self._call_llm(completion_prompt)
            return response and response.strip().upper().startswith("YES")
        except Exception as e:
            logger.error(f"Completion check failed: {e}")
            return False
    
    async def _synthesize_result(self, task: AgentTask):
        """Create a final synthesized response"""
        conversation_history = self.memory.get_conversation_history()
        
        synthesis_prompt = f"""
Synthesize the conversation into a final, comprehensive response to the user's original request.

Original request: {task.user_input}
Conversation history:
{conversation_history}

Provide a clear, helpful response that addresses the user's original request based on all the work done.
"""
        
        try:
            result = await self._call_llm(synthesis_prompt)
            task.result = result or "Task completed successfully"
            
            # Add final result to memory
            self.memory.add_message("assistant", task.result)
            
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            task.result = "Task completed, but synthesis failed"
    
    async def _call_llm(self, prompt: str, json_output: bool = False) -> str:
        """Call the configured LLM and track token usage"""
        system_prompt = """You are a helpful AI agent capable of reasoning, planning, and using tools to complete complex tasks."""
        
        try:
            if self.model == "gpt-4o":
                response = gpt4o_service(
                    system_prompt=system_prompt,
                    user_input=prompt,
                    temperature=0.3,
                    json_output=json_output
                )
            elif self.model == "deepseek-v3":
                response = deepseek_v3_service(
                    system_prompt=system_prompt,
                    user_input=prompt,
                    temperature=0.3,
                    json_output=json_output
                )
            else:
                raise ValueError(f"Unsupported model: {self.model}")
            
            # Validate response structure
            if not isinstance(response, dict):
                raise Exception(f"LLM service returned unexpected type: {type(response)}")
            
            if not response.get("success"):
                error_msg = response.get("error", "Unknown error")
                raise Exception(f"LLM call failed: {error_msg}")
            
            # Track token usage
            self.llm_call_count += 1
            self.total_prompt_tokens += response.get("prompt_tokens", 0)
            self.total_completion_tokens += response.get("completion_tokens", 0)
            self.total_tokens += response.get("total_tokens", 0)
            self.total_cached_tokens += response.get("cached_tokens", 0)
            
            logger.info(f"LLM call #{self.llm_call_count}: {response.get('total_tokens', 0)} tokens")
            
            result = response.get("result", "")
            if not result:
                logger.warning("LLM returned empty result")
            
            return result
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
    
    def _get_available_tools_description(self) -> str:
        """Get description of available tools"""
        try:
            tools = self.tool_registry.get_all_tools()
            descriptions = []
            
            for tool_name, tool_info in tools.items():
                description = tool_info.get('description', 'No description available')
                descriptions.append(f"- {tool_name}: {description}")
            
            return "\n".join(descriptions) if descriptions else "No tools available"
            
        except Exception as e:
            logger.error(f"Error getting tools description: {e}")
            return "Error retrieving available tools"
    
    async def _save_task(self, task: AgentTask):
        """Save task to database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Get token usage from context - with safe fallback
            token_usage = {}
            if isinstance(task.context, dict):
                token_usage = task.context.get('token_usage', {})
            
            if not isinstance(token_usage, dict):
                logger.warning(f"token_usage is not a dict: {type(token_usage)}")
                token_usage = {}
            
            query = """
            INSERT INTO agent_tasks (
                id, agent_id, user_id, task_input, context, status,
                steps, result, error, created_at, completed_at,
                prompt_tokens, completion_tokens, total_tokens, 
                cached_tokens, llm_calls, model_used
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            cursor.execute(query, [
                task.task_id,
                self.agent_id,
                self.user_id,
                task.user_input,
                json.dumps(task.context) if isinstance(task.context, dict) else "{}",
                task.status.value,
                json.dumps(task.steps) if isinstance(task.steps, list) else "[]",
                task.result,
                task.error,
                task.created_at,
                task.completed_at,
                token_usage.get('prompt_tokens', 0),
                token_usage.get('completion_tokens', 0),
                token_usage.get('total_tokens', 0),
                token_usage.get('cached_tokens', 0),
                token_usage.get('llm_calls', 0),
                token_usage.get('model', self.model)
            ])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Successfully saved task {task.task_id} to database")
            
        except Exception as e:
            logger.error(f"Failed to save task: {str(e)}", exc_info=True)

class AgentManager:
    """Manages multiple agent instances"""
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
    
    def get_or_create_agent(self, user_id: str, model: str = "gpt-4o") -> Agent:
        """Get existing agent or create new one for user"""
        agent_id = f"{user_id}_{model}"
        
        if agent_id not in self.agents:
            self.agents[agent_id] = Agent(agent_id, user_id, model)
        
        return self.agents[agent_id]
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get specific agent by ID"""
        return self.agents.get(agent_id)
    
    async def execute_agentic_task(self, user_id: str, user_input: str, 
                                 model: str = "gpt-4o", context: Dict[str, Any] = None) -> AgentTask:
        """Execute an agentic task for a user"""
        try:
            agent = self.get_or_create_agent(user_id, model)
            return await agent.execute_task(user_input, context)
        except Exception as e:
            logger.error(f"Failed to execute agentic task: {e}", exc_info=True)
            # Return a failed task instead of letting the exception bubble up
            failed_task = AgentTask(
                task_id=str(uuid.uuid4()),
                user_input=user_input,
                context=context or {},
                status=AgentStatus.ERROR,
                steps=[],
                error=str(e),
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            return failed_task

# Global agent manager instance
agent_manager = AgentManager()
