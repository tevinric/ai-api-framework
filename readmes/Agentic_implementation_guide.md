# Agentic LLM Integration Guide

## Overview

This guide shows how to transform your existing LLM middleware into an agentic system capable of:

- **Planning and Reasoning**: Breaking down complex tasks into executable steps
- **Tool Usage**: Accessing external tools for web search, file operations, calculations, etc.
- **Memory**: Maintaining conversation context across multiple interactions
- **Iteration**: Refining responses through multiple reasoning cycles
- **Self-reflection**: Evaluating and improving its own outputs

## Architecture Components

### 1. Core Agent System (`apis/agentic/agent_core.py`)
- **Agent**: Main orchestrator that plans, executes, and manages tasks
- **AgentManager**: Manages multiple agent instances per user
- **AgentTask**: Represents a complete task execution with status tracking

### 2. Tool System (`apis/agentic/tools.py`)
- **ToolRegistry**: Manages available tools and their definitions
- **ToolExecutor**: Safely executes tools with proper error handling
- **BaseTool**: Abstract base class for creating new tools

**Available Tools:**
- `web_search`: Internet search capabilities
- `file_operations`: File reading, listing, and analysis
- `calculator`: Mathematical calculations
- `database_query`: User-specific data queries
- `code_executor`: Sandboxed Python code execution

### 3. Memory Management (`apis/agentic/memory.py`)
- **ConversationMemory**: Persistent conversation history
- **Message**: Individual conversation messages with metadata
- Automatic database persistence and retrieval

### 4. Task Planning (`apis/agentic/planner.py`)
- **TaskPlanner**: Analyzes tasks and creates execution plans
- **TaskType**: Categorizes different types of tasks
- **TaskStep**: Individual steps with dependencies and priorities

## Integration Steps

### 1. Database Setup

Run the SQL schema from `agentic_database_schema.sql` to create required tables:

```sql
-- Core tables
- agent_tasks: Stores task executions
- agent_memory: Conversation history
- tool_executions: Tool usage logs
- agent_configurations: User agent settings
- agent_tools: Available tools registry
- user_tool_access: Tool permissions per user
```

### 2. Install Dependencies

Add to your `requirements.txt`:
```
asyncio  # For async agent execution
```

### 3. Register New Endpoints

In your main Flask app file:

```python
from apis.llm.agentic_llm import register_agentic_llm

# Register agentic endpoints
register_agentic_llm(app)
```

### 4. Add Endpoint Configurations

Update your endpoints table:
```sql
INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
VALUES (NEWID(), '/llm/agentic', 'Agentic LLM', 5.0, 'Agentic LLM with planning and tools', 1);
```

### 5. Configure User Access

Grant users access to agentic features and tools:

```sql
-- Grant endpoint access
INSERT INTO user_endpoint_access (id, user_id, endpoint_id, created_by)
SELECT NEWID(), user_id, endpoint_id, admin_user_id
FROM users u, endpoints e 
WHERE e.endpoint_path = '/llm/agentic';

-- Grant tool access (all tools to all users)
INSERT INTO user_tool_access (user_id, tool_name)
SELECT u.id, t.tool_name
FROM users u
CROSS JOIN agent_tools t
WHERE t.is_enabled = 1;
```

## API Usage Examples

### 1. Basic Agentic Task

```bash
POST /llm/agentic
Content-Type: application/json
X-Token: your-auth-token

{
  "user_input": "Find information about climate change impacts in 2024 and summarize the key findings",
  "model": "gpt-4o",
  "max_iterations": 10,
  "agent_config": {
    "tools_enabled": ["web_search", "calculator"],
    "planning_enabled": true
  }
}
```

**Response:**
```json
{
  "response": "200",
  "message": "Based on my research, here are the key climate change impacts in 2024...",
  "task_id": "task-123-456-789",
  "agent_id": "agent-user123-gpt4o",
  "execution_details": {
    "status": "completed",
    "steps_executed": 3,
    "tools_used": ["web_search"],
    "execution_time": 45.2
  }
}
```

### 2. File Analysis Task

```bash
POST /llm/agentic
Content-Type: application/json
X-Token: your-auth-token

{
  "user_input": "Analyze my uploaded data files and provide insights about trends",
  "model": "gpt-4o",
  "agent_config": {
    "tools_enabled": ["file_operations", "calculator"]
  }
}
```

### 3. Complex Problem Solving

```bash
POST /llm/agentic
Content-Type: application/json
X-Token: your-auth-token

{
  "user_input": "Create a Python script to calculate compound interest, test it with sample data, and explain how it works",
  "model": "gpt-4o",
  "agent_config": {
    "tools_enabled": ["code_executor", "calculator"]
  }
}
```

### 4. Check Task Status

```bash
GET /llm/agentic/tasks/task-123-456-789
X-Token: your-auth-token
```

### 5. List User Tasks

```bash
GET /llm/agentic/tasks?limit=10&status=completed
X-Token: your-auth-token
```

## Extending the System

### Adding New Tools

1. Create a new tool class inheriting from `BaseTool`:

```python
class MyCustomTool(BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="my_tool",
            description="Description of what this tool does",
            parameters={"param1": {"type": "string"}},
            function=self.execute,
            category="custom"
        )
    
    async def execute(self, parameters: Dict[str, Any], user_id: str) -> str:
        # Tool implementation
        return "Tool result"
```

2. Register the tool:

```python
tool_registry = ToolRegistry()
tool_registry.register_tool(MyCustomTool())
```

3. Add to database:

```sql
INSERT INTO agent_tools (tool_name, description, category, parameters_schema)
VALUES ('my_tool', 'Description', 'custom', '{"type": "object", "properties": {...}}');
```

### Modifying Existing Endpoints

You can add agentic capabilities to existing endpoints by modifying them to check for an `agentic_mode` parameter:

```python
def enhanced_gpt4o_route():
    data = request.get_json()
    agentic_mode = data.get('agentic_mode', False)
    
    if agentic_mode:
        # Use agentic execution
        task_result = await agent_manager.execute_agentic_task(
            user_id=user_id,
            user_input=data['user_input'],
            model="gpt-4o"
        )
        return create_api_response({
            "response": "200",
            "message": task_result.result,
            "agentic_execution": True
        }, 200)
    else:
        # Use standard execution
        return gpt4o_service(...)
```

## Configuration Options

### Agent Configuration

Users can customize agent behavior:

```json
{
  "agent_config": {
    "tools_enabled": ["web_search", "calculator"],
    "planning_enabled": true,
    "max_iterations": 15,
    "system_prompt": "You are a research assistant focused on accuracy."
  }
}
```

### Tool Permissions

Admins can control tool access per user:

```sql
-- Grant specific tool access
INSERT INTO user_tool_access (user_id, tool_name, granted_by)
VALUES ('user-id', 'code_executor', 'admin-id');

-- Revoke tool access
UPDATE user_tool_access 
SET is_enabled = 0 
WHERE user_id = 'user-id' AND tool_name = 'code_executor';
```

## Monitoring and Analytics

### Task Analytics

```sql
-- Get user task statistics
EXEC GetAgentStatistics @UserId = 'user-id', @DaysBack = 30;

-- View most used tools
SELECT * FROM tool_usage_analytics;

-- View user performance
SELECT * FROM agent_analytics;
```

### Performance Monitoring

Track execution metrics:
- Average task completion time
- Tool success rates
- Most common failure points
- Resource usage patterns

## Security Considerations

1. **Tool Sandboxing**: Code execution and file operations are sandboxed
2. **User Permissions**: Fine-grained control over tool access
3. **Resource Limits**: Execution timeouts and iteration limits
4. **Data Isolation**: Users can only access their own data
5. **Input Validation**: All tool parameters are validated

## Cost Management

Agentic tasks consume more credits due to:
- Multiple LLM calls for planning and execution
- Tool usage overhead
- Extended execution time

Default cost: 5 credits per agentic task (configurable in endpoints table)

## Best Practices

1. **Start Simple**: Begin with basic tools and gradually add complexity
2. **Monitor Usage**: Track tool usage and execution patterns
3. **Set Limits**: Use reasonable iteration and execution limits
4. **User Education**: Provide examples of effective agentic prompts
5. **Error Handling**: Implement robust error handling and user feedback
6. **Performance**: Monitor execution times and optimize slow tools

## Troubleshooting

### Common Issues

1. **Task Timeouts**: Increase `max_execution_time_ms` for tools
2. **Memory Issues**: Implement memory cleanup procedures
3. **Tool Failures**: Check tool logs in `tool_executions` table
4. **Permission Errors**: Verify user tool access in `user_tool_access`

### Debugging

Enable debug logging:
```python
import logging
logging.getLogger('apis.agentic').setLevel(logging.DEBUG)
```

Check task status:
```sql
SELECT * FROM agent_tasks WHERE status = 'error' ORDER BY created_at DESC;
```

## Future Enhancements

Potential improvements:
- **Multi-agent collaboration**: Multiple agents working together
- **Custom tool creation**: User-defined tools
- **Advanced planning**: More sophisticated task decomposition
- **Learning**: Agents that improve based on past executions
- **Integration**: Connect with external APIs and services
