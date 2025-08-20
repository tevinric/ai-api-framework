"""
Agent API Routes
Main API endpoints for agent functionality with usage tracking
"""

from flask import Blueprint, jsonify, request, g
from apis.utils.tokenService import TokenService
from apis.utils.balanceMiddleware import check_balance
from apis.utils.usageMiddleware import track_usage
from apis.utils.rbacMiddleware import check_rbac
from apis.agents.agent_manager import AgentManager
from apis.agents.async_executor import async_executor
from apis.agents.agent_orchestrator import agent_orchestrator
from apis.agents.tool_registry import tool_registry
import logging
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)

# Create Blueprint
agents_bp = Blueprint('agents', __name__, url_prefix='/agents')

# Token service instance
token_service = TokenService()

def async_route(f):
    """Decorator to run async functions in Flask routes"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    return wrapper

# Create Agent Endpoint
@agents_bp.route('/create', methods=['POST'])
@check_rbac(endpoint_name='agents_create')
@check_balance(cost=1.0)
@track_usage
@async_route
async def create_agent():
    """
    Create a new agent
    Consumes 1 AI credit
    
    ---
    tags:
      - Agents
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
            - instructions
          properties:
            name:
              type: string
              description: Name of the agent
            instructions:
              type: string
              description: Instructions for the agent's behavior
            tools:
              type: array
              items:
                type: string
              description: List of tool names the agent can use
            model:
              type: string
              default: "gpt-4o"
              description: Model to use for the agent
            temperature:
              type: number
              default: 0.7
              description: Temperature for agent responses
            metadata:
              type: object
              description: Additional metadata for the agent
    responses:
      200:
        description: Agent created successfully
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            agent_id:
              type: string
              example: "asst_abc123"
            message:
              type: string
              example: "Agent created successfully"
      400:
        description: Bad request
      401:
        description: Unauthorized
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('instructions'):
            return jsonify({
                'response': '400',
                'message': 'Missing required fields: name and instructions'
            }), 400
        
        # Get user ID from token
        user_id = g.get('user_id')
        
        # Get tools configuration
        tools = data.get('tools', [])
        if tools:
            # Validate user has access to requested tools
            user_tools = tool_registry.get_tools_for_user(user_id)
            available_tool_names = {tool.name for tool in user_tools}
            
            invalid_tools = set(tools) - available_tool_names
            if invalid_tools:
                return jsonify({
                    'response': '400',
                    'message': f'Invalid or unauthorized tools: {list(invalid_tools)}'
                }), 400
            
            # Convert to OpenAI format
            tools_config = [
                tool.to_openai_function()
                for tool in user_tools
                if tool.name in tools
            ]
        else:
            tools_config = None
        
        # Create agent
        agent_manager = AgentManager()
        agent_id, error = await agent_manager.create_agent(
            user_id=user_id,
            name=data['name'],
            instructions=data['instructions'],
            tools=tools_config,
            model=data.get('model', 'gpt-4o'),
            metadata=data.get('metadata'),
            temperature=data.get('temperature', 0.7)
        )
        
        if error:
            return jsonify({
                'response': '500',
                'message': error
            }), 500
        
        return jsonify({
            'response': '200',
            'agent_id': agent_id,
            'message': 'Agent created successfully',
            'model': data.get('model', 'gpt-4o')
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating agent: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

# Execute Agent Endpoint (Async)
@agents_bp.route('/execute', methods=['POST'])
@check_rbac(endpoint_name='agents_execute')
@check_balance(cost=5.0)
@track_usage
@async_route
async def execute_agent():
    """
    Execute an agent asynchronously
    Consumes 5 AI credits
    
    ---
    tags:
      - Agents
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - agent_id
            - message
          properties:
            agent_id:
              type: string
              description: ID of the agent to execute
            message:
              type: string
              description: Message to send to the agent
            thread_id:
              type: string
              description: Existing thread ID (optional)
            tools:
              type: array
              items:
                type: string
              description: Tools to enable for this execution
            context:
              type: object
              description: Additional context for the agent
            webhook_url:
              type: string
              description: URL to receive completion webhook
    responses:
      200:
        description: Agent execution started
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            job_id:
              type: string
              example: "job_xyz789"
            message:
              type: string
              example: "Agent execution started"
            status_url:
              type: string
              example: "/agents/status/job_xyz789"
      400:
        description: Bad request
      401:
        description: Unauthorized
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('agent_id') or not data.get('message'):
            return jsonify({
                'response': '400',
                'message': 'Missing required fields: agent_id and message'
            }), 400
        
        # Get user ID from token
        user_id = g.get('user_id')
        
        # Submit agent task for async execution
        job_id, error = await async_executor.submit_agent_task(
            user_id=user_id,
            agent_id=data['agent_id'],
            message=data['message'],
            thread_id=data.get('thread_id'),
            tools=data.get('tools'),
            context=data.get('context'),
            webhook_url=data.get('webhook_url')
        )
        
        if error:
            return jsonify({
                'response': '400',
                'message': error
            }), 400
        
        # Track usage - will be updated when job completes
        return jsonify({
            'response': '200',
            'job_id': job_id,
            'message': 'Agent execution started',
            'status_url': f'/agents/status/{job_id}',
            'model': 'agent_execution',
            'prompt_tokens': 0,  # Will be updated when job completes
            'completion_tokens': 0,
            'total_tokens': 0
        }), 200
        
    except Exception as e:
        logger.error(f"Error executing agent: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

# Get Job Status Endpoint
@agents_bp.route('/status/<job_id>', methods=['GET'])
@check_rbac(endpoint_name='agents_status')
@async_route
async def get_job_status(job_id):
    """
    Get the status of an agent execution job
    
    ---
    tags:
      - Agents
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: job_id
        in: path
        type: string
        required: true
        description: Job ID to check status for
    responses:
      200:
        description: Job status retrieved
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            job_id:
              type: string
            status:
              type: string
              enum: [pending, processing, completed, failed, cancelled]
            result:
              type: object
              description: Result data if completed
            error_message:
              type: string
              description: Error message if failed
      404:
        description: Job not found
      401:
        description: Unauthorized
    """
    try:
        # Get user ID from token
        user_id = g.get('user_id')
        
        # Get job status
        status_info, error = await async_executor.get_agent_job_status(
            user_id=user_id,
            job_id=job_id
        )
        
        if error:
            return jsonify({
                'response': '404',
                'message': error
            }), 404
        
        return jsonify({
            'response': '200',
            **status_info
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

# List Agents Endpoint
@agents_bp.route('/list', methods=['GET'])
@check_rbac(endpoint_name='agents_list')
@async_route
async def list_agents():
    """
    List all agents available to the user
    
    ---
    tags:
      - Agents
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: include_shared
        in: query
        type: boolean
        default: false
        description: Include shared agents
    responses:
      200:
        description: List of agents
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            agents:
              type: array
              items:
                type: object
                properties:
                  agent_id:
                    type: string
                  name:
                    type: string
                  instructions:
                    type: string
                  model:
                    type: string
                  created_at:
                    type: string
                  is_shared:
                    type: boolean
                  is_owner:
                    type: boolean
      401:
        description: Unauthorized
    """
    try:
        # Get user ID from token
        user_id = g.get('user_id')
        include_shared = request.args.get('include_shared', 'false').lower() == 'true'
        
        # Get agents list
        agent_manager = AgentManager()
        agents_list, error = await agent_manager.list_user_agents(
            user_id=user_id,
            include_shared=include_shared
        )
        
        if error:
            return jsonify({
                'response': '500',
                'message': error
            }), 500
        
        return jsonify({
            'response': '200',
            'agents': agents_list
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing agents: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

# Create Custom Agent Endpoint
@agents_bp.route('/custom/create', methods=['POST'])
@check_rbac(endpoint_name='agents_custom_create')
@check_balance(cost=2.0)
@track_usage
@async_route
async def create_custom_agent():
    """
    Create a custom agent with template support
    Consumes 2 AI credits
    
    ---
    tags:
      - Agents
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
            - description
            - instructions
          properties:
            name:
              type: string
              description: Name of the custom agent
            description:
              type: string
              description: Description of the agent's purpose
            instructions:
              type: string
              description: Custom instructions for the agent
            tools:
              type: array
              items:
                type: string
              description: Tools the agent can use
            model:
              type: string
              default: "gpt-4o"
            temperature:
              type: number
              default: 0.7
            base_template:
              type: string
              description: Base template to extend from
    responses:
      200:
        description: Custom agent created
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            agent_id:
              type: string
            message:
              type: string
      400:
        description: Bad request
      401:
        description: Unauthorized
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'description', 'instructions']
        missing_fields = [f for f in required_fields if not data.get(f)]
        if missing_fields:
            return jsonify({
                'response': '400',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Get user ID from token
        user_id = g.get('user_id')
        
        # Create custom agent
        agent_id, error = await agent_orchestrator.create_custom_agent(
            user_id=user_id,
            name=data['name'],
            description=data['description'],
            instructions=data['instructions'],
            tools=data.get('tools', []),
            model=data.get('model', 'gpt-4o'),
            temperature=data.get('temperature', 0.7),
            base_template=data.get('base_template')
        )
        
        if error:
            return jsonify({
                'response': '400',
                'message': error
            }), 400
        
        return jsonify({
            'response': '200',
            'agent_id': agent_id,
            'message': 'Custom agent created successfully',
            'model': data.get('model', 'gpt-4o')
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating custom agent: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

# Get Agent Templates Endpoint
@agents_bp.route('/templates', methods=['GET'])
@check_rbac(endpoint_name='agents_templates')
def get_agent_templates():
    """
    Get available agent templates
    
    ---
    tags:
      - Agents
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
    responses:
      200:
        description: List of templates
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            templates:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                  name:
                    type: string
                  role:
                    type: string
                  description:
                    type: string
                  default_tools:
                    type: array
                    items:
                      type: string
      401:
        description: Unauthorized
    """
    try:
        templates = agent_orchestrator.get_available_templates()
        
        return jsonify({
            'response': '200',
            'templates': templates
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting templates: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

# Create Workflow Endpoint
@agents_bp.route('/workflow/create', methods=['POST'])
@check_rbac(endpoint_name='agents_workflow_create')
@check_balance(cost=3.0)
@track_usage
@async_route
async def create_workflow():
    """
    Create a multi-agent workflow
    Consumes 3 AI credits
    
    ---
    tags:
      - Agents
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
            - description
            - agents
          properties:
            name:
              type: string
              description: Name of the workflow
            description:
              type: string
              description: Description of the workflow
            agents:
              type: array
              items:
                type: object
                properties:
                  agent_id:
                    type: string
                  role:
                    type: string
              description: List of agents in the workflow
            flow_type:
              type: string
              enum: [sequential, parallel, conditional]
              default: sequential
    responses:
      200:
        description: Workflow created
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            workflow_id:
              type: string
            message:
              type: string
      400:
        description: Bad request
      401:
        description: Unauthorized
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'description', 'agents']
        missing_fields = [f for f in required_fields if not data.get(f)]
        if missing_fields:
            return jsonify({
                'response': '400',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Get user ID from token
        user_id = g.get('user_id')
        
        # Create workflow
        workflow_id, error = await agent_orchestrator.create_agent_workflow(
            user_id=user_id,
            name=data['name'],
            description=data['description'],
            agents=data['agents'],
            flow_type=data.get('flow_type', 'sequential')
        )
        
        if error:
            return jsonify({
                'response': '400',
                'message': error
            }), 400
        
        return jsonify({
            'response': '200',
            'workflow_id': workflow_id,
            'message': 'Workflow created successfully',
            'model': 'workflow'
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating workflow: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

# Get Available Tools Endpoint
@agents_bp.route('/tools', methods=['GET'])
@check_rbac(endpoint_name='agents_tools')
def get_available_tools():
    """
    Get tools available to the user
    
    ---
    tags:
      - Agents
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: categories
        in: query
        type: array
        items:
          type: string
        description: Filter by categories
    responses:
      200:
        description: List of available tools
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            tools:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  description:
                    type: string
                  category:
                    type: string
                  parameters_schema:
                    type: object
      401:
        description: Unauthorized
    """
    try:
        # Get user ID from token
        user_id = g.get('user_id')
        
        # Get categories filter
        categories = request.args.getlist('categories')
        
        # Get available tools
        tools = tool_registry.get_tools_for_user(
            user_id=user_id,
            categories=categories if categories else None
        )
        
        # Format response
        tools_list = [
            {
                'name': tool.name,
                'description': tool.description,
                'category': tool.category,
                'parameters_schema': tool.parameters_schema
            }
            for tool in tools
        ]
        
        return jsonify({
            'response': '200',
            'tools': tools_list
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting tools: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500