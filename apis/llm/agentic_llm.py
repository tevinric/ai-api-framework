# apis/llm/agentic_llm.py
from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
import logging
import pytz
from datetime import datetime
from apis.agentic.agent_core import agent_manager
import asyncio
import json

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from apis.utils.config import create_api_response

def agentic_llm_route():
    """
    Consumes 5 AI credits per call
    
    Agentic LLM endpoint that can plan, use tools, and iterate to complete complex tasks.

    ---
    tags:
      - LLM
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: X-Correlation-ID
        in: header
        type: string
        required: false
        description: Unique identifier for tracking requests across multiple systems
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - user_input
          properties:
            system_prompt:
              type: string
              description: System prompt to control agent behavior
              default: "You are a helpful AI agent capable of reasoning, planning, and using tools."
            user_input:
              type: string
              description: Task or question for the agent to complete
            model:
              type: string
              enum: ["gpt-4o", "deepseek-v3"]
              default: "gpt-4o"
              description: LLM model to use for reasoning
            max_iterations:
              type: integer
              minimum: 1
              maximum: 20
              default: 10
              description: Maximum number of reasoning iterations
            context_id:
              type: string
              description: ID of a context file to use as additional knowledge (optional)
            agent_config:
              type: object
              properties:
                tools_enabled:
                  type: array
                  items:
                    type: string
                  description: List of tools the agent can use
                planning_enabled:
                  type: boolean
                  default: true
                  description: Whether to use task planning
              description: Agent configuration options
    produces:
      - application/json
    responses:
      200:
        description: Successful agent response
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            message:
              type: string
              example: "I've completed the task by searching for information and analyzing the results..."
            task_id:
              type: string
              example: "task-123-456-789"
              description: Unique ID for this agent task
            agent_id:
              type: string
              example: "agent-user123-gpt4o"
              description: ID of the agent that processed the task
            user_id:
              type: string
              example: "user123"
            user_name:
              type: string
              example: "John Doe"
            user_email:
              type: string
              example: "john.doe@example.com"
            model:
              type: string
              example: "gpt-4o"
            execution_details:
              type: object
              properties:
                status:
                  type: string
                  example: "completed"
                steps_executed:
                  type: integer
                  example: 3
                tools_used:
                  type: array
                  items:
                    type: string
                  example: ["web_search", "calculator"]
                execution_time:
                  type: number
                  example: 45.2
                  description: Time taken in seconds
            context_used:
              type: string
              example: "ctx-123"
              description: ID of the context file that was used (if any)
      400:
        description: Bad request
        schema:
          type: object
          properties:
            response:
              type: string
              example: "400"
            message:
              type: string
              example: "Missing required fields: user_input"
      401:
        description: Authentication error
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Authentication Error"
            message:
              type: string
              example: "Token has expired"
      500:
        description: Server error
        schema:
          type: object
          properties:
            response:
              type: string
              example: "500"
            message:
              type: string
              example: "Internal server error occurred during agent execution"
    """
    # Get token from X-Token header
    token = request.headers.get('X-Token')
    if not token:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing X-Token header"
        }, 401)
    
    # Validate token from database
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token - not found in database"
        }, 401)
    
    # Store token ID and user ID in g for logging and balance check
    g.token_id = token_details["id"]
    g.user_id = token_details["user_id"]
    
    # Check if token is expired
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Validate token with Microsoft Graph
    is_valid = TokenService.validate_token(token)
    if not is_valid:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token is no longer valid with provider"
        }, 401)
        
    # Get user details
    user_id = token_details["user_id"]
    user_details = DatabaseService.get_user_by_id(user_id)
    if not user_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "User associated with token not found"
        }, 401)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "response": "400",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['user_input']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "response": "400",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Extract parameters with defaults
    user_input = data.get('user_input', '')
    model = data.get('model', 'gpt-4o')
    max_iterations = int(data.get('max_iterations', 10))
    context_id = data.get('context_id')
    agent_config = data.get('agent_config', {})
    
    # Validate model
    if model not in ['gpt-4o', 'deepseek-v3']:
        return create_api_response({
            "response": "400",
            "message": "Model must be 'gpt-4o' or 'deepseek-v3'"
        }, 400)
    
    # Validate max_iterations
    if not (1 <= max_iterations <= 20):
        return create_api_response({
            "response": "400",
            "message": "max_iterations must be between 1 and 20"
        }, 400)
    
    try:
        # Log API usage
        logger.info(f"Agentic LLM API called by user: {user_id}")
        
        # Apply context if provided
        context_data = {}
        context_used = None
        if context_id:
            from apis.llm.context_helper import apply_context_if_provided
            # We'll pass context to the agent rather than modifying system prompt
            from apis.llm.context_integration import apply_context_to_system_prompt
            _, error = apply_context_to_system_prompt("", context_id, g.user_id)
            if not error:
                context_used = context_id
                # Add context to agent execution context
                context_data['context_id'] = context_id
        
        # Prepare execution context
        execution_context = {
            'max_iterations': max_iterations,
            'agent_config': agent_config,
            **context_data
        }
        
        # Execute agentic task
        start_time = datetime.utcnow()
        
        # Create event loop for async execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            task_result = loop.run_until_complete(
                agent_manager.execute_agentic_task(
                    user_id=user_id,
                    user_input=user_input,
                    model=model,
                    context=execution_context
                )
            )
        finally:
            loop.close()
        
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()
        
        # Check if task completed successfully
        if task_result.status.value == "error":
            logger.error(f"Agentic task failed: {task_result.error}")
            return create_api_response({
                "response": "500",
                "message": f"Agent execution failed: {task_result.error}"
            }, 500)
        
        # Extract tools used and token usage
        tools_used = []
        for step in task_result.steps:
            if step.get('tool') and step['tool'] not in tools_used:
                tools_used.append(step['tool'])
        
        # Get token usage from task context
        token_usage = task_result.context.get('token_usage', {})
        
        # Prepare successful response with token usage for track_usage middleware
        response_data = {
            "response": "200",
            "message": task_result.result or "Task completed successfully",
            "task_id": task_result.task_id,
            "agent_id": f"{user_id}_{model}",
            "user_id": user_details["id"],
            "user_name": user_details["user_name"],
            "user_email": user_details["user_email"],
            "model": token_usage.get('model', model),
            
            # Token usage data for track_usage middleware
            "prompt_tokens": token_usage.get('prompt_tokens', 0),
            "completion_tokens": token_usage.get('completion_tokens', 0),
            "total_tokens": token_usage.get('total_tokens', 0),
            "cached_tokens": token_usage.get('cached_tokens', 0),
            
            "execution_details": {
                "status": task_result.status.value,
                "steps_executed": len(task_result.steps),
                "tools_used": tools_used,
                "execution_time": execution_time,
                "llm_calls": token_usage.get('llm_calls', 0)
            }
        }
        
        # Include context usage info if context was used
        if context_used:
            response_data["context_used"] = context_used
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Agentic LLM API error: {str(e)}")
        return create_api_response({
            "response": "500",
            "message": f"Internal server error: {str(e)}"
        }, 500)

def get_agent_task_status_route():
    """
    Get the status of a specific agent task
    
    ---
    tags:
      - LLM
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: task_id
        in: path
        type: string
        required: true
        description: Task ID to query
    produces:
      - application/json
    responses:
      200:
        description: Task status information
        schema:
          type: object
          properties:
            task_id:
              type: string
            status:
              type: string
            result:
              type: string
            steps:
              type: array
            execution_time:
              type: number
    """
    task_id = request.view_args.get('task_id')
    
    try:
        # Validate authentication (simplified for demo)
        token = request.headers.get('X-Token')
        if not token:
            return create_api_response({
                "error": "Authentication Error",
                "message": "Missing X-Token header"
            }, 401)
        
        # Get task from database
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT task_input, status, steps, result, error, created_at, completed_at
        FROM agent_tasks
        WHERE id = ? AND user_id = (
            SELECT user_id FROM token_transactions WHERE token_value = ?
        )
        """
        
        cursor.execute(query, [task_id, token])
        task_data = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not task_data:
            return create_api_response({
                "error": "Not Found",
                "message": "Task not found or access denied"
            }, 404)
        
        # Calculate execution time
        execution_time = None
        if task_data[5] and task_data[6]:  # created_at and completed_at
            execution_time = (task_data[6] - task_data[5]).total_seconds()
        
        response_data = {
            "task_id": task_id,
            "task_input": task_data[0],
            "status": task_data[1],
            "steps": json.loads(task_data[2]) if task_data[2] else [],
            "result": task_data[3],
            "error": task_data[4],
            "created_at": task_data[5].isoformat() if task_data[5] else None,
            "completed_at": task_data[6].isoformat() if task_data[6] else None,
            "execution_time": execution_time
        }
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"Get task status error: {str(e)}")
        return create_api_response({
            "response": "500",
            "message": str(e)
        }, 500)

def list_agent_tasks_route():
    """
    List recent agent tasks for the authenticated user
    
    ---
    tags:
      - LLM
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: limit
        in: query
        type: integer
        default: 10
        description: Maximum number of tasks to return
      - name: status
        in: query
        type: string
        description: Filter by task status
    produces:
      - application/json
    responses:
      200:
        description: List of tasks
        schema:
          type: object
          properties:
            tasks:
              type: array
              items:
                type: object
    """
    try:
        # Validate authentication
        token = request.headers.get('X-Token')
        if not token:
            return create_api_response({
                "error": "Authentication Error",
                "message": "Missing X-Token header"
            }, 401)
        
        # Get query parameters
        limit = int(request.args.get('limit', 10))
        status_filter = request.args.get('status')
        
        # Get tasks from database
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        base_query = """
        SELECT id, task_input, status, result, created_at, completed_at
        FROM agent_tasks
        WHERE user_id = (
            SELECT user_id FROM token_transactions WHERE token_value = ?
        )
        """
        
        params = [token]
        
        if status_filter:
            base_query += " AND status = ?"
            params.append(status_filter)
        
        base_query += " ORDER BY created_at DESC"
        
        if limit:
            base_query += f" OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY"
        
        cursor.execute(base_query, params)
        tasks = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Format response
        task_list = []
        for task in tasks:
            execution_time = None
            if task[4] and task[5]:  # created_at and completed_at
                execution_time = (task[5] - task[4]).total_seconds()
            
            task_list.append({
                "task_id": task[0],
                "task_input": task[1][:100] + "..." if len(task[1]) > 100 else task[1],
                "status": task[2],
                "result_preview": (task[3][:200] + "...") if task[3] and len(task[3]) > 200 else task[3],
                "created_at": task[4].isoformat() if task[4] else None,
                "completed_at": task[5].isoformat() if task[5] else None,
                "execution_time": execution_time
            })
        
        return create_api_response({
            "tasks": task_list,
            "total_returned": len(task_list)
        }, 200)
        
    except Exception as e:
        logger.error(f"List tasks error: {str(e)}")
        return create_api_response({
            "response": "500",
            "message": str(e)
        }, 500)

def register_agentic_llm(app):
    """Register agentic LLM routes with the Flask app"""
    from apis.utils.logMiddleware import api_logger
    from apis.utils.balanceMiddleware import check_balance
    from apis.utils.usageMiddleware import track_usage
    from apis.utils.rbacMiddleware import check_endpoint_access
    
    # Main agentic endpoint
    app.route('/llm/agentic', methods=['POST'])(
        track_usage(api_logger(check_endpoint_access(check_balance(agentic_llm_route))))
    )
    
    # Task status endpoint
    app.route('/llm/agentic/tasks/<task_id>', methods=['GET'])(
        api_logger(get_agent_task_status_route)
    )
    
    # List tasks endpoint
    app.route('/llm/agentic/tasks', methods=['GET'])(
        api_logger(list_agent_tasks_route)
    )
