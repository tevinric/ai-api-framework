"""
Tool Management API Routes
API endpoints for creating, managing, and configuring custom tools
"""

from flask import Blueprint, jsonify, request, g
from apis.utils.tokenService import TokenService
from apis.utils.balanceMiddleware import check_balance
from apis.utils.usageMiddleware import track_usage
from apis.utils.rbacMiddleware import check_endpoint_access
from apis.utils.databaseService import DatabaseService
from apis.agents.tool_registry import tool_registry, ToolDefinition, ToolType
from apis.agents.dynamic_tool_executor import DynamicToolExecutor
import logging
import json
import uuid
from datetime import datetime
import importlib
import inspect
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Create Blueprint
tools_bp = Blueprint('tools_management', __name__, url_prefix='/agents/tools')

# Token service instance
token_service = TokenService()

@tools_bp.route('/create', methods=['POST'])
@check_endpoint_access
@check_balance
@track_usage
def create_custom_tool():
    """
    Create a custom tool
    Consumes 2 AI credits
    
    ---
    tags:
      - Tools Management
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
            - tool_type
            - implementation
          properties:
            name:
              type: string
              description: Unique tool name (alphanumeric and underscores only)
            description:
              type: string
              description: Tool description for agents
            category:
              type: string
              default: "custom"
              description: Tool category
            tool_type:
              type: string
              enum: ["function", "api_endpoint", "webhook"]
              description: Type of tool implementation
            parameters_schema:
              type: object
              description: JSON schema for tool parameters
            implementation:
              type: object
              description: Tool implementation details (varies by type)
            requires_auth:
              type: boolean
              default: false
              description: Whether tool requires special authorization
            max_execution_time_ms:
              type: integer
              default: 30000
              description: Maximum execution time in milliseconds
            is_shared:
              type: boolean
              default: false
              description: Whether tool can be shared with other users
    responses:
      200:
        description: Tool created successfully
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            tool_name:
              type: string
              example: "my_custom_tool"
            message:
              type: string
              example: "Custom tool created successfully"
      400:
        description: Bad request - invalid tool configuration
      401:
        description: Unauthorized
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'description', 'tool_type', 'implementation']
        missing_fields = [f for f in required_fields if not data.get(f)]
        if missing_fields:
            return jsonify({
                'response': '400',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Validate tool name (alphanumeric and underscores only)
        tool_name = data['name']
        if not tool_name.replace('_', '').isalnum():
            return jsonify({
                'response': '400',
                'message': 'Tool name must contain only alphanumeric characters and underscores'
            }), 400
        
        # Check if tool name already exists
        if tool_name in tool_registry.tools:
            return jsonify({
                'response': '400',
                'message': f'Tool {tool_name} already exists'
            }), 400
        
        user_id = g.get('user_id')
        tool_type = data['tool_type']
        implementation = data['implementation']
        
        # Validate implementation based on tool type
        validation_result = _validate_tool_implementation(tool_type, implementation)
        if not validation_result['valid']:
            return jsonify({
                'response': '400',
                'message': f'Invalid implementation: {validation_result["message"]}'
            }), 400
        
        # Create tool configuration
        tool_config = {
            'name': tool_name,
            'description': data['description'],
            'category': data.get('category', 'custom'),
            'tool_type': tool_type,
            'parameters_schema': data.get('parameters_schema', {}),
            'implementation': implementation,
            'requires_auth': data.get('requires_auth', False),
            'max_execution_time_ms': data.get('max_execution_time_ms', 30000),
            'is_shared': data.get('is_shared', False),
            'created_by': user_id,
            'is_enabled': True
        }
        
        # Store in database
        tool_id = _store_custom_tool(tool_config)
        
        if not tool_id:
            return jsonify({
                'response': '500',
                'message': 'Failed to store custom tool'
            }), 500
        
        # Register tool in runtime registry
        tool_def = _create_tool_definition(tool_config)
        tool_registry.register_tool(tool_def)
        
        # Grant access to creator
        _grant_tool_access(user_id, tool_name)
        
        logger.info(f"Created custom tool {tool_name} by user {user_id}")
        
        return jsonify({
            'response': '200',
            'tool_name': tool_name,
            'tool_id': tool_id,
            'message': 'Custom tool created successfully',
            'model': 'tool_creation'
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating custom tool: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

@tools_bp.route('/list', methods=['GET'])
@check_endpoint_access
def list_custom_tools():
    """
    List custom tools created by or accessible to the user
    
    ---
    tags:
      - Tools Management
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: category
        in: query
        type: string
        description: Filter by category
      - name: created_by_me
        in: query
        type: boolean
        default: false
        description: Show only tools created by the user
      - name: shared_only
        in: query
        type: boolean
        default: false
        description: Show only shared tools
    responses:
      200:
        description: List of custom tools
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
                  tool_name:
                    type: string
                  description:
                    type: string
                  category:
                    type: string
                  tool_type:
                    type: string
                  parameters_schema:
                    type: object
                  is_shared:
                    type: boolean
                  created_by:
                    type: string
                  created_at:
                    type: string
                  is_owner:
                    type: boolean
    """
    try:
        user_id = g.get('user_id')
        category = request.args.get('category')
        created_by_me = request.args.get('created_by_me', 'false').lower() == 'true'
        shared_only = request.args.get('shared_only', 'false').lower() == 'true'
        
        # Get tools from database
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT ct.tool_name, ct.description, ct.category, ct.tool_type,
               ct.parameters_schema, ct.is_shared, ct.created_by, ct.created_at,
               ct.requires_auth, ct.max_execution_time_ms, ct.is_enabled,
               u.user_name as creator_name
        FROM custom_tools ct
        LEFT JOIN users u ON ct.created_by = u.id
        WHERE ct.is_enabled = 1
        """
        
        params = []
        
        # Apply filters
        if created_by_me:
            query += " AND ct.created_by = ?"
            params.append(user_id)
        elif shared_only:
            query += " AND ct.is_shared = 1 AND ct.created_by != ?"
            params.append(user_id)
        else:
            # Show tools created by user or shared tools they have access to
            query += """ AND (ct.created_by = ? OR 
                           (ct.is_shared = 1 AND EXISTS (
                               SELECT 1 FROM user_tool_access uta 
                               WHERE uta.user_id = ? AND uta.tool_name = ct.tool_name AND uta.is_enabled = 1
                           )))"""
            params.extend([user_id, user_id])
        
        if category:
            query += " AND ct.category = ?"
            params.append(category)
        
        query += " ORDER BY ct.created_at DESC"
        
        cursor.execute(query, params)
        tools_data = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Format response
        tools_list = []
        for tool_data in tools_data:
            tool_info = {
                'tool_name': tool_data[0],
                'description': tool_data[1],
                'category': tool_data[2],
                'tool_type': tool_data[3],
                'parameters_schema': json.loads(tool_data[4]) if tool_data[4] else {},
                'is_shared': bool(tool_data[5]),
                'created_by': tool_data[6],
                'created_at': tool_data[7].isoformat() if tool_data[7] else None,
                'requires_auth': bool(tool_data[8]),
                'max_execution_time_ms': tool_data[9],
                'creator_name': tool_data[11],
                'is_owner': tool_data[6] == user_id
            }
            tools_list.append(tool_info)
        
        return jsonify({
            'response': '200',
            'tools': tools_list,
            'count': len(tools_list)
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing custom tools: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

@tools_bp.route('/<tool_name>', methods=['GET'])
@check_endpoint_access
def get_tool_details(tool_name):
    """
    Get detailed information about a specific tool
    
    ---
    tags:
      - Tools Management
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: tool_name
        in: path
        type: string
        required: true
        description: Name of the tool to retrieve
    responses:
      200:
        description: Tool details
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            tool:
              type: object
              properties:
                tool_name:
                  type: string
                description:
                  type: string
                category:
                  type: string
                tool_type:
                  type: string
                parameters_schema:
                  type: object
                implementation:
                  type: object
                usage_stats:
                  type: object
      404:
        description: Tool not found
    """
    try:
        user_id = g.get('user_id')
        
        # Get tool details from database
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT ct.tool_name, ct.description, ct.category, ct.tool_type,
               ct.parameters_schema, ct.implementation, ct.is_shared, 
               ct.created_by, ct.created_at, ct.requires_auth, 
               ct.max_execution_time_ms, ct.is_enabled,
               u.user_name as creator_name
        FROM custom_tools ct
        LEFT JOIN users u ON ct.created_by = u.id
        WHERE ct.tool_name = ? AND ct.is_enabled = 1
        """
        
        cursor.execute(query, [tool_name])
        tool_data = cursor.fetchone()
        
        if not tool_data:
            cursor.close()
            conn.close()
            return jsonify({
                'response': '404',
                'message': f'Tool {tool_name} not found'
            }), 404
        
        # Check access permissions
        is_owner = tool_data[7] == user_id
        is_shared = bool(tool_data[6])
        
        if not is_owner and not is_shared:
            # Check if user has explicit access
            cursor.execute("""
                SELECT COUNT(*) FROM user_tool_access 
                WHERE user_id = ? AND tool_name = ? AND is_enabled = 1
            """, [user_id, tool_name])
            
            has_access = cursor.fetchone()[0] > 0
            if not has_access:
                cursor.close()
                conn.close()
                return jsonify({
                    'response': '403',
                    'message': 'Access denied to this tool'
                }), 403
        
        # Get usage statistics
        cursor.execute("""
            SELECT COUNT(*) as usage_count,
                   MAX(started_at) as last_used,
                   AVG(execution_time_ms) as avg_execution_time
            FROM tool_executions
            WHERE tool_name = ?
        """, [tool_name])
        
        usage_stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Format response
        tool_info = {
            'tool_name': tool_data[0],
            'description': tool_data[1],
            'category': tool_data[2],
            'tool_type': tool_data[3],
            'parameters_schema': json.loads(tool_data[4]) if tool_data[4] else {},
            'implementation': json.loads(tool_data[5]) if tool_data[5] and is_owner else None,
            'is_shared': bool(tool_data[6]),
            'created_by': tool_data[7],
            'created_at': tool_data[8].isoformat() if tool_data[8] else None,
            'requires_auth': bool(tool_data[9]),
            'max_execution_time_ms': tool_data[10],
            'creator_name': tool_data[12],
            'is_owner': is_owner,
            'usage_stats': {
                'usage_count': usage_stats[0] if usage_stats else 0,
                'last_used': usage_stats[1].isoformat() if usage_stats and usage_stats[1] else None,
                'avg_execution_time_ms': float(usage_stats[2]) if usage_stats and usage_stats[2] else 0
            }
        }
        
        return jsonify({
            'response': '200',
            'tool': tool_info
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting tool details: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

@tools_bp.route('/<tool_name>', methods=['PUT'])
@check_endpoint_access
@check_balance
@track_usage
def update_custom_tool(tool_name):
    """
    Update a custom tool (only by owner)
    Consumes 1 AI credit
    
    ---
    tags:
      - Tools Management
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: tool_name
        in: path
        type: string
        required: true
        description: Name of the tool to update
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            description:
              type: string
              description: Updated tool description
            parameters_schema:
              type: object
              description: Updated parameters schema
            implementation:
              type: object
              description: Updated implementation details
            is_shared:
              type: boolean
              description: Whether tool should be shared
            max_execution_time_ms:
              type: integer
              description: Updated execution timeout
    responses:
      200:
        description: Tool updated successfully
      403:
        description: Not authorized to update this tool
      404:
        description: Tool not found
    """
    try:
        data = request.get_json()
        user_id = g.get('user_id')
        
        # Check tool ownership
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT created_by, tool_type FROM custom_tools 
            WHERE tool_name = ? AND is_enabled = 1
        """, [tool_name])
        
        tool_data = cursor.fetchone()
        
        if not tool_data:
            cursor.close()
            conn.close()
            return jsonify({
                'response': '404',
                'message': f'Tool {tool_name} not found'
            }), 404
        
        if tool_data[0] != user_id:
            cursor.close()
            conn.close()
            return jsonify({
                'response': '403',
                'message': 'Only tool owner can update the tool'
            }), 403
        
        # Prepare update fields
        update_fields = []
        update_params = []
        
        if 'description' in data:
            update_fields.append('description = ?')
            update_params.append(data['description'])
        
        if 'parameters_schema' in data:
            update_fields.append('parameters_schema = ?')
            update_params.append(json.dumps(data['parameters_schema']))
        
        if 'implementation' in data:
            # Validate implementation
            tool_type = tool_data[1]
            validation_result = _validate_tool_implementation(tool_type, data['implementation'])
            if not validation_result['valid']:
                cursor.close()
                conn.close()
                return jsonify({
                    'response': '400',
                    'message': f'Invalid implementation: {validation_result["message"]}'
                }), 400
            
            update_fields.append('implementation = ?')
            update_params.append(json.dumps(data['implementation']))
        
        if 'is_shared' in data:
            update_fields.append('is_shared = ?')
            update_params.append(data['is_shared'])
        
        if 'max_execution_time_ms' in data:
            update_fields.append('max_execution_time_ms = ?')
            update_params.append(data['max_execution_time_ms'])
        
        if not update_fields:
            cursor.close()
            conn.close()
            return jsonify({
                'response': '400',
                'message': 'No fields to update'
            }), 400
        
        # Add modified timestamp
        update_fields.append('modified_at = GETUTCDATE()')
        
        # Execute update
        query = f"UPDATE custom_tools SET {', '.join(update_fields)} WHERE tool_name = ?"
        update_params.append(tool_name)
        
        cursor.execute(query, update_params)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Update runtime registry
        _reload_tool_in_registry(tool_name)
        
        logger.info(f"Updated custom tool {tool_name} by user {user_id}")
        
        return jsonify({
            'response': '200',
            'message': 'Tool updated successfully',
            'model': 'tool_update'
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating custom tool: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

@tools_bp.route('/<tool_name>', methods=['DELETE'])
@check_endpoint_access
@track_usage
def delete_custom_tool(tool_name):
    """
    Delete a custom tool (only by owner)
    
    ---
    tags:
      - Tools Management
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: tool_name
        in: path
        type: string
        required: true
        description: Name of the tool to delete
    responses:
      200:
        description: Tool deleted successfully
      403:
        description: Not authorized to delete this tool
      404:
        description: Tool not found
    """
    try:
        user_id = g.get('user_id')
        
        # Check tool ownership
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT created_by FROM custom_tools 
            WHERE tool_name = ? AND is_enabled = 1
        """, [tool_name])
        
        tool_data = cursor.fetchone()
        
        if not tool_data:
            cursor.close()
            conn.close()
            return jsonify({
                'response': '404',
                'message': f'Tool {tool_name} not found'
            }), 404
        
        if tool_data[0] != user_id:
            cursor.close()
            conn.close()
            return jsonify({
                'response': '403',
                'message': 'Only tool owner can delete the tool'
            }), 403
        
        # Soft delete (disable) the tool
        cursor.execute("""
            UPDATE custom_tools 
            SET is_enabled = 0, modified_at = GETUTCDATE()
            WHERE tool_name = ?
        """, [tool_name])
        
        # Remove from user access table
        cursor.execute("""
            DELETE FROM user_tool_access WHERE tool_name = ?
        """, [tool_name])
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Remove from runtime registry
        if tool_name in tool_registry.tools:
            del tool_registry.tools[tool_name]
        
        logger.info(f"Deleted custom tool {tool_name} by user {user_id}")
        
        return jsonify({
            'response': '200',
            'message': 'Tool deleted successfully',
            'model': 'tool_deletion'
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting custom tool: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

@tools_bp.route('/<tool_name>/test', methods=['POST'])
@check_endpoint_access
@check_balance
@track_usage
def test_custom_tool(tool_name):
    """
    Test a custom tool with provided parameters
    Consumes 0.5 AI credits
    
    ---
    tags:
      - Tools Management
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: tool_name
        in: path
        type: string
        required: true
        description: Name of the tool to test
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - parameters
          properties:
            parameters:
              type: object
              description: Parameters to pass to the tool
            context:
              type: object
              description: Additional context for tool execution
    responses:
      200:
        description: Tool test results
        schema:
          type: object
          properties:
            response:
              type: string
              example: "200"
            result:
              type: object
              description: Tool execution result
            execution_time_ms:
              type: integer
              description: Execution time in milliseconds
      400:
        description: Invalid parameters or tool configuration
    """
    try:
        data = request.get_json()
        user_id = g.get('user_id')
        
        if 'parameters' not in data:
            return jsonify({
                'response': '400',
                'message': 'Missing required field: parameters'
            }), 400
        
        # Check if user has access to the tool
        user_tools = tool_registry.get_tools_for_user(user_id)
        user_tool_names = {tool.name for tool in user_tools}
        
        if tool_name not in user_tool_names:
            return jsonify({
                'response': '403',
                'message': f'Access denied to tool {tool_name}'
            }), 403
        
        # Get tool definition
        if tool_name not in tool_registry.tools:
            return jsonify({
                'response': '404',
                'message': f'Tool {tool_name} not found in registry'
            }), 404
        
        # Execute tool
        context = data.get('context', {})
        context['user_id'] = user_id
        context['test_mode'] = True
        
        start_time = datetime.utcnow()
        result = tool_registry.execute_tool(tool_name, data['parameters'], context)
        end_time = datetime.utcnow()
        
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Log test execution
        _log_tool_test_execution(user_id, tool_name, data['parameters'], result, execution_time_ms)
        
        return jsonify({
            'response': '200',
            'result': result,
            'execution_time_ms': execution_time_ms,
            'timestamp': end_time.isoformat(),
            'model': 'tool_test'
        }), 200
        
    except Exception as e:
        logger.error(f"Error testing tool {tool_name}: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Tool test failed: {str(e)}'
        }), 500

@tools_bp.route('/<tool_name>/share', methods=['POST'])
@check_endpoint_access
@track_usage
def share_tool_with_users(tool_name):
    """
    Share a custom tool with specific users
    
    ---
    tags:
      - Tools Management
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: tool_name
        in: path
        type: string
        required: true
        description: Name of the tool to share
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - user_ids
          properties:
            user_ids:
              type: array
              items:
                type: string
              description: List of user IDs to share the tool with
            grant_access:
              type: boolean
              default: true
              description: Whether to grant (true) or revoke (false) access
    responses:
      200:
        description: Tool sharing updated
      403:
        description: Not authorized to share this tool
      404:
        description: Tool not found
    """
    try:
        data = request.get_json()
        user_id = g.get('user_id')
        
        if 'user_ids' not in data:
            return jsonify({
                'response': '400',
                'message': 'Missing required field: user_ids'
            }), 400
        
        # Check tool ownership
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT created_by FROM custom_tools 
            WHERE tool_name = ? AND is_enabled = 1
        """, [tool_name])
        
        tool_data = cursor.fetchone()
        
        if not tool_data:
            cursor.close()
            conn.close()
            return jsonify({
                'response': '404',
                'message': f'Tool {tool_name} not found'
            }), 404
        
        if tool_data[0] != user_id:
            cursor.close()
            conn.close()
            return jsonify({
                'response': '403',
                'message': 'Only tool owner can share the tool'
            }), 403
        
        user_ids = data['user_ids']
        grant_access = data.get('grant_access', True)
        
        # Validate user IDs exist
        if user_ids:
            placeholders = ','.join(['?' for _ in user_ids])
            cursor.execute(f"SELECT id FROM users WHERE id IN ({placeholders})", user_ids)
            valid_users = [row[0] for row in cursor.fetchall()]
            
            invalid_users = set(user_ids) - set(valid_users)
            if invalid_users:
                cursor.close()
                conn.close()
                return jsonify({
                    'response': '400',
                    'message': f'Invalid user IDs: {list(invalid_users)}'
                }), 400
        
        # Update tool access
        success_count = 0
        for target_user_id in user_ids:
            if grant_access:
                # Grant access
                cursor.execute("""
                    INSERT INTO user_tool_access (id, user_id, tool_name, is_enabled, granted_at, granted_by)
                    VALUES (NEWID(), ?, ?, 1, GETUTCDATE(), ?)
                    ON DUPLICATE KEY UPDATE is_enabled = 1, granted_at = GETUTCDATE(), granted_by = ?
                """, [target_user_id, tool_name, user_id, user_id])
            else:
                # Revoke access
                cursor.execute("""
                    UPDATE user_tool_access 
                    SET is_enabled = 0
                    WHERE user_id = ? AND tool_name = ?
                """, [target_user_id, tool_name])
            
            success_count += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        action = "granted" if grant_access else "revoked"
        logger.info(f"Tool {tool_name} access {action} for {success_count} users by {user_id}")
        
        return jsonify({
            'response': '200',
            'message': f'Tool access {action} for {success_count} users',
            'model': 'tool_sharing'
        }), 200
        
    except Exception as e:
        logger.error(f"Error sharing tool {tool_name}: {str(e)}")
        return jsonify({
            'response': '500',
            'message': f'Internal server error: {str(e)}'
        }), 500

# Helper functions

def _validate_tool_implementation(tool_type: str, implementation: Dict[str, Any]) -> Dict[str, Any]:
    """Validate tool implementation based on type"""
    
    if tool_type == 'function':
        required_fields = ['code', 'function_name']
        
        for field in required_fields:
            if field not in implementation:
                return {'valid': False, 'message': f'Missing required field: {field}'}
        
        # Basic code validation
        code = implementation['code']
        function_name = implementation['function_name']
        
        if not isinstance(code, str) or len(code.strip()) == 0:
            return {'valid': False, 'message': 'Code cannot be empty'}
        
        if not function_name.replace('_', '').isalnum():
            return {'valid': False, 'message': 'Function name must be alphanumeric with underscores'}
        
        # Check if function is defined in code
        if f"def {function_name}" not in code:
            return {'valid': False, 'message': f'Function {function_name} not found in code'}
        
        return {'valid': True, 'message': 'Valid function implementation'}
    
    elif tool_type == 'api_endpoint':
        required_fields = ['url', 'method']
        
        for field in required_fields:
            if field not in implementation:
                return {'valid': False, 'message': f'Missing required field: {field}'}
        
        url = implementation['url']
        method = implementation['method'].upper()
        
        if not url.startswith(('http://', 'https://')):
            return {'valid': False, 'message': 'URL must start with http:// or https://'}
        
        if method not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
            return {'valid': False, 'message': 'Invalid HTTP method'}
        
        return {'valid': True, 'message': 'Valid API endpoint implementation'}
    
    elif tool_type == 'webhook':
        required_fields = ['webhook_url']
        
        for field in required_fields:
            if field not in implementation:
                return {'valid': False, 'message': f'Missing required field: {field}'}
        
        webhook_url = implementation['webhook_url']
        
        if not webhook_url.startswith(('http://', 'https://')):
            return {'valid': False, 'message': 'Webhook URL must start with http:// or https://'}
        
        return {'valid': True, 'message': 'Valid webhook implementation'}
    
    else:
        return {'valid': False, 'message': f'Unsupported tool type: {tool_type}'}

def _store_custom_tool(tool_config: Dict[str, Any]) -> str:
    """Store custom tool in database"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        tool_id = str(uuid.uuid4())
        
        query = """
        INSERT INTO custom_tools (
            id, tool_name, description, category, tool_type,
            parameters_schema, implementation, requires_auth,
            max_execution_time_ms, is_shared, created_by,
            is_enabled, created_at, modified_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, GETUTCDATE(), GETUTCDATE()
        )
        """
        
        cursor.execute(query, [
            tool_id,
            tool_config['name'],
            tool_config['description'],
            tool_config['category'],
            tool_config['tool_type'],
            json.dumps(tool_config['parameters_schema']),
            json.dumps(tool_config['implementation']),
            tool_config['requires_auth'],
            tool_config['max_execution_time_ms'],
            tool_config['is_shared'],
            tool_config['created_by']
        ])
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return tool_id
        
    except Exception as e:
        logger.error(f"Error storing custom tool: {str(e)}")
        return None

def _create_tool_definition(tool_config: Dict[str, Any]) -> ToolDefinition:
    """Create ToolDefinition from tool configuration"""
    
    tool_type_map = {
        'function': ToolType.FUNCTION,
        'api_endpoint': ToolType.API_ENDPOINT,
        'webhook': ToolType.API_ENDPOINT  # Treat webhooks as API endpoints
    }
    
    # Create dynamic executor function
    executor = DynamicToolExecutor(tool_config)
    
    return ToolDefinition(
        name=tool_config['name'],
        type=tool_type_map.get(tool_config['tool_type'], ToolType.FUNCTION),
        description=tool_config['description'],
        parameters_schema=tool_config['parameters_schema'],
        function=executor.execute,
        category=tool_config['category'],
        requires_auth=tool_config['requires_auth'],
        max_execution_time_ms=tool_config['max_execution_time_ms']
    )

def _grant_tool_access(user_id: str, tool_name: str):
    """Grant tool access to user"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_tool_access (id, user_id, tool_name, is_enabled, granted_at)
            VALUES (NEWID(), ?, ?, 1, GETUTCDATE())
        """, [user_id, tool_name])
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error granting tool access: {str(e)}")

def _reload_tool_in_registry(tool_name: str):
    """Reload tool in runtime registry from database"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT tool_name, description, category, tool_type,
                   parameters_schema, implementation, requires_auth,
                   max_execution_time_ms
            FROM custom_tools
            WHERE tool_name = ? AND is_enabled = 1
        """, [tool_name])
        
        tool_data = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if tool_data:
            tool_config = {
                'name': tool_data[0],
                'description': tool_data[1],
                'category': tool_data[2],
                'tool_type': tool_data[3],
                'parameters_schema': json.loads(tool_data[4]) if tool_data[4] else {},
                'implementation': json.loads(tool_data[5]) if tool_data[5] else {},
                'requires_auth': bool(tool_data[6]),
                'max_execution_time_ms': tool_data[7]
            }
            
            tool_def = _create_tool_definition(tool_config)
            tool_registry.register_tool(tool_def)
            
    except Exception as e:
        logger.error(f"Error reloading tool in registry: {str(e)}")

def _log_tool_test_execution(user_id: str, tool_name: str, parameters: Dict, result: Dict, execution_time_ms: int):
    """Log tool test execution"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tool_executions (
                id, task_id, tool_name, parameters, result, 
                execution_time_ms, started_at, completed_at
            ) VALUES (
                NEWID(), ?, ?, ?, ?, ?, GETUTCDATE(), GETUTCDATE()
            )
        """, [
            f"test_{user_id}",  # Use test task ID
            tool_name,
            json.dumps(parameters),
            json.dumps(result),
            execution_time_ms
        ])
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error logging tool test execution: {str(e)}")