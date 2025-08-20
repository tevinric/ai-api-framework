# Complete Guide to the Agentic API System

This comprehensive tutorial covers everything you need to know about using, customizing, and extending the agentic API system.

## Table of Contents

1. [Getting Started](#getting-started)
2. [API Endpoints Deep Dive](#api-endpoints-deep-dive)
3. [Working with Tools](#working-with-tools)
4. [Creating Custom Tools](#creating-custom-tools)
5. [MCP Server Integration](#mcp-server-integration)
6. [Business Agent Templates](#business-agent-templates)
7. [Multi-Agent Workflows](#multi-agent-workflows)
8. [Advanced Customization](#advanced-customization)
9. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

Before using the agentic API system, ensure you have:

1. **Valid API Token**: Obtain from `/token/get_token` endpoint
2. **Proper Permissions**: Your user needs access to agent endpoints
3. **Azure OpenAI Setup**: Environment variables configured
4. **Database Schema**: All agent tables created

### Basic Authentication

All endpoints require the `X-Token` header:

```bash
curl -H "X-Token: your_api_token_here" \
     -H "Content-Type: application/json" \
     https://your-api.com/agents/list
```

---

## API Endpoints Deep Dive

### 1. Create Agent

**Endpoint**: `POST /agents/create`  
**Cost**: 1 AI Credit  
**Purpose**: Create a new AI agent with custom instructions and tools

#### Request Format

```json
{
  "name": "My Business Assistant",
  "instructions": "You are a helpful business assistant specialized in project management. Always be professional and concise.",
  "tools": ["web_search", "calculator", "send_email"],
  "model": "gpt-4o",
  "temperature": 0.7,
  "metadata": {
    "department": "Operations",
    "created_for": "Project Management"
  }
}
```

#### Response Format

```json
{
  "response": "200",
  "agent_id": "asst_abc123def456",
  "message": "Agent created successfully",
  "model": "gpt-4o"
}
```

#### Complete Example

```python
import requests

# Create a specialized data analysis agent
payload = {
    "name": "Data Analysis Specialist",
    "instructions": """You are an expert data analyst. Your responsibilities include:
    - Analyzing datasets and identifying trends
    - Creating visualizations and reports
    - Providing actionable insights
    - Explaining complex data in simple terms
    
    Always provide data-driven recommendations with clear reasoning.""",
    "tools": ["data_analysis", "calculator", "document_generator", "web_search"],
    "model": "gpt-4o",
    "temperature": 0.5,
    "metadata": {
        "specialization": "business_intelligence",
        "department": "analytics"
    }
}

response = requests.post(
    'https://your-api.com/agents/create',
    headers={
        'X-Token': 'your_token_here',
        'Content-Type': 'application/json'
    },
    json=payload
)

print(f"Agent ID: {response.json()['agent_id']}")
```

### 2. Execute Agent (Async)

**Endpoint**: `POST /agents/execute`  
**Cost**: 5 AI Credits  
**Purpose**: Execute an agent task asynchronously (KONG-compatible)

#### Request Format

```json
{
  "agent_id": "asst_abc123def456",
  "message": "Analyze our Q3 sales performance and identify growth opportunities",
  "thread_id": "thread_xyz789abc123",
  "tools": ["data_analysis", "web_search", "document_generator"],
  "context": {
    "company": "TechCorp",
    "quarter": "Q3_2024",
    "focus_areas": ["revenue", "customer_acquisition"]
  },
  "webhook_url": "https://your-app.com/webhook/agent-complete"
}
```

#### Response Format

```json
{
  "response": "200",
  "job_id": "job_xyz789abc123",
  "message": "Agent execution started",
  "status_url": "/agents/status/job_xyz789abc123",
  "model": "agent_execution",
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "total_tokens": 0
}
```

#### Complete Example

```python
import requests
import time

def execute_agent_with_polling(agent_id, message, tools=None, max_wait=300):
    """Execute agent and poll for completion"""
    
    # Start execution
    payload = {
        "agent_id": agent_id,
        "message": message,
        "tools": tools or ["web_search", "document_generator"],
        "context": {
            "execution_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "priority": "high"
        }
    }
    
    response = requests.post(
        'https://your-api.com/agents/execute',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=payload
    )
    
    if response.status_code != 200:
        raise Exception(f"Execution failed: {response.text}")
    
    job_id = response.json()['job_id']
    print(f"Job started: {job_id}")
    
    # Poll for completion
    start_time = time.time()
    while time.time() - start_time < max_wait:
        status_response = requests.get(
            f'https://your-api.com/agents/status/{job_id}',
            headers={'X-Token': 'your_token_here'}
        )
        
        status_data = status_response.json()
        print(f"Status: {status_data['status']}")
        
        if status_data['status'] == 'completed':
            return status_data['result']
        elif status_data['status'] == 'failed':
            raise Exception(f"Agent execution failed: {status_data.get('error_message')}")
        
        time.sleep(5)  # Wait 5 seconds before next check
    
    raise Exception("Agent execution timed out")

# Usage example
result = execute_agent_with_polling(
    agent_id="asst_abc123def456",
    message="Create a comprehensive market analysis report for our new product launch",
    tools=["web_search", "data_analysis", "document_generator"]
)

print("Agent Result:", result)
```

### 3. Check Job Status

**Endpoint**: `GET /agents/status/{job_id}`  
**Cost**: Free  
**Purpose**: Monitor async agent execution progress

#### Response Formats

**Running Job:**
```json
{
  "response": "200",
  "job_id": "job_xyz789abc123",
  "status": "processing",
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z",
  "completed_at": null,
  "error_message": null,
  "elapsed_seconds": 25,
  "estimated_remaining": 30
}
```

**Completed Job:**
```json
{
  "response": "200",
  "job_id": "job_xyz789abc123",
  "status": "completed",
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z",
  "completed_at": "2024-01-15T10:31:30Z",
  "result": {
    "run_id": "run_def456ghi789",
    "thread_id": "thread_xyz789abc123",
    "response": "Based on my analysis of Q3 sales data, I've identified three key growth opportunities...",
    "usage": {
      "prompt_tokens": 1250,
      "completion_tokens": 850,
      "total_tokens": 2100
    },
    "completed_at": "2024-01-15T10:31:30Z"
  }
}
```

### 4. List Agents

**Endpoint**: `GET /agents/list`  
**Cost**: Free  
**Purpose**: List all agents available to the user

#### Query Parameters

- `include_shared` (boolean): Include shared agents from other users

#### Example Usage

```python
import requests

# List only user's agents
response = requests.get(
    'https://your-api.com/agents/list',
    headers={'X-Token': 'your_token_here'}
)

agents = response.json()['agents']

# List including shared agents
response_with_shared = requests.get(
    'https://your-api.com/agents/list?include_shared=true',
    headers={'X-Token': 'your_token_here'}
)

all_agents = response_with_shared.json()['agents']

# Print agent summary
for agent in agents:
    print(f"Agent: {agent['name']}")
    print(f"  ID: {agent['agent_id']}")
    print(f"  Model: {agent['model']}")
    print(f"  Tools: {len(agent['tools'])}")
    print(f"  Owner: {'Yes' if agent['is_owner'] else 'No'}")
    print()
```

### 5. Create Custom Agent

**Endpoint**: `POST /agents/custom/create`  
**Cost**: 2 AI Credits  
**Purpose**: Create agents using business templates as foundation

#### Request Format

```json
{
  "name": "Senior Financial Analyst",
  "description": "Specialized in SaaS financial metrics and growth analysis",
  "instructions": "Focus specifically on SaaS metrics like MRR, ARR, churn rates, and customer acquisition costs. Provide detailed analysis with actionable recommendations.",
  "tools": ["data_analysis", "calculator", "document_generator", "web_search"],
  "model": "gpt-4o",
  "temperature": 0.4,
  "base_template": "financial_analyst"
}
```

#### Complete Example

```python
import requests

def create_specialized_agent(template_id, customizations):
    """Create a custom agent based on a template"""
    
    # First, get available templates to understand the base
    templates_response = requests.get(
        'https://your-api.com/agents/templates',
        headers={'X-Token': 'your_token_here'}
    )
    
    templates = templates_response.json()['templates']
    base_template = next((t for t in templates if t['id'] == template_id), None)
    
    if not base_template:
        raise Exception(f"Template {template_id} not found")
    
    print(f"Using template: {base_template['name']}")
    print(f"Default tools: {base_template['default_tools']}")
    
    # Create custom agent
    payload = {
        "base_template": template_id,
        **customizations
    }
    
    response = requests.post(
        'https://your-api.com/agents/custom/create',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=payload
    )
    
    if response.status_code == 200:
        return response.json()['agent_id']
    else:
        raise Exception(f"Failed to create agent: {response.text}")

# Create a specialized HR agent
hr_agent_id = create_specialized_agent(
    template_id="hr_business_partner",
    customizations={
        "name": "Technical Recruiting Specialist",
        "description": "Specialized in technical talent acquisition and engineering team building",
        "instructions": """You are a technical recruiting specialist with deep knowledge of:
        - Software engineering roles and requirements
        - Technical interview processes
        - Compensation benchmarking for tech roles
        - Engineering team structures and scaling
        
        Always provide data-driven insights and specific recommendations for technical hiring.""",
        "tools": ["web_search", "data_analysis", "document_generator", "calendar_manager"],
        "temperature": 0.6
    }
)

print(f"Created specialized HR agent: {hr_agent_id}")
```

### 6. Get Agent Templates

**Endpoint**: `GET /agents/templates`  
**Cost**: Free  
**Purpose**: Get available business agent templates

#### Response Format

```json
{
  "response": "200",
  "templates": [
    {
      "id": "executive_assistant",
      "name": "Executive Assistant",
      "role": "executive_assistant",
      "description": "Comprehensive executive support for scheduling, communication, and task management",
      "default_tools": ["calendar_manager", "send_email", "task_manager", "document_generator"],
      "model": "gpt-4o",
      "temperature": 0.6
    }
  ]
}
```

### 7. Create Workflow

**Endpoint**: `POST /agents/workflow/create`  
**Cost**: 3 AI Credits  
**Purpose**: Create multi-agent workflows for complex business processes

#### Request Format

```json
{
  "name": "Product Launch Workflow",
  "description": "Complete product launch process with market research, analysis, and planning",
  "flow_type": "sequential",
  "agents": [
    {
      "agent_id": "asst_research123",
      "role": "Market Research"
    },
    {
      "agent_id": "asst_analyst456", 
      "role": "Data Analysis"
    },
    {
      "agent_id": "asst_marketing789",
      "role": "Marketing Strategy"
    }
  ]
}
```

### 8. Get Available Tools

**Endpoint**: `GET /agents/tools`  
**Cost**: Free  
**Purpose**: List tools available to the user

#### Query Parameters

- `categories` (array): Filter by tool categories (e.g., "analytics", "communication")

#### Example Usage

```python
import requests

# Get all available tools
response = requests.get(
    'https://your-api.com/agents/tools',
    headers={'X-Token': 'your_token_here'}
)

tools = response.json()['tools']

# Get only analytics tools
analytics_response = requests.get(
    'https://your-api.com/agents/tools?categories=analytics&categories=math',
    headers={'X-Token': 'your_token_here'}
)

analytics_tools = analytics_response.json()['tools']

# Print tool information
for tool in tools:
    print(f"Tool: {tool['name']}")
    print(f"  Category: {tool['category']}")
    print(f"  Description: {tool['description']}")
    print(f"  Parameters: {list(tool['parameters_schema'].get('properties', {}).keys())}")
    print()
```

---

## Working with Tools

### Understanding the Tool System

The agent system includes a comprehensive tool registry that provides business-focused capabilities:

#### Available Tools

1. **web_search**: Internet search capabilities
2. **database_query**: Query user-specific data
3. **calculator**: Mathematical calculations
4. **send_email**: Email notifications
5. **data_analysis**: Data processing and insights
6. **document_generator**: Create business documents
7. **calendar_manager**: Schedule management
8. **task_manager**: Task tracking and management

### Tool Usage in Agent Instructions

When creating agents, you can specify which tools they should use and how:

```python
instructions = """You are a business analyst. When analyzing data:

1. Use the 'data_analysis' tool to process datasets and identify trends
2. Use the 'calculator' tool for complex calculations
3. Use the 'web_search' tool to gather market intelligence
4. Use the 'document_generator' tool to create professional reports

Always explain your methodology and cite your sources."""

payload = {
    "name": "Business Analyst Pro",
    "instructions": instructions,
    "tools": ["data_analysis", "calculator", "web_search", "document_generator"],
    "model": "gpt-4o"
}
```

### Tool Permissions

Tools are controlled by user permissions. To check what tools you have access to:

```python
import requests

# Check available tools
response = requests.get(
    'https://your-api.com/agents/tools',
    headers={'X-Token': 'your_token_here'}
)

available_tools = [tool['name'] for tool in response.json()['tools']]
print("Available tools:", available_tools)

# Try to create agent with unauthorized tool
try:
    response = requests.post(
        'https://your-api.com/agents/create',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json={
            "name": "Test Agent",
            "instructions": "Test agent",
            "tools": ["unauthorized_tool"]  # This will fail
        }
    )
    print(response.json())
except Exception as e:
    print(f"Error: {e}")
```

---

## Creating Custom Tools via API

The system now provides complete API endpoints for creating, managing, and testing custom tools dynamically. This allows users to extend agent capabilities without database access.

### Tool Management API Endpoints

#### Available Endpoints:
- `POST /agents/tools/create` - Create custom tools (2 credits)
- `GET /agents/tools/list` - List custom tools (free)
- `GET /agents/tools/<tool_name>` - Get tool details (free)
- `PUT /agents/tools/<tool_name>` - Update custom tools (1 credit)
- `DELETE /agents/tools/<tool_name>` - Delete custom tools (free)
- `POST /agents/tools/<tool_name>/test` - Test tool execution (0.5 credits)
- `POST /agents/tools/<tool_name>/share` - Share tools with users (free)

### Creating Tools via API

#### Method 1: Function-Based Tools

Create tools using Python code that executes in a secure environment:

```python
import requests

def create_expense_calculator_tool():
    """Create a custom function-based tool for expense calculations"""
    
    tool_config = {
        "name": "expense_calculator",
        "description": "Calculate business expenses with tax implications and detailed breakdown",
        "category": "finance",
        "tool_type": "function",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "expenses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "number", "description": "Expense amount"},
                            "category": {"type": "string", "description": "Expense category"},
                            "tax_deductible": {"type": "boolean", "description": "Is this expense tax deductible?"},
                            "date": {"type": "string", "description": "Expense date (YYYY-MM-DD)"}
                        },
                        "required": ["amount", "category"]
                    },
                    "description": "List of expense items"
                },
                "tax_rate": {
                    "type": "number",
                    "default": 0.25,
                    "description": "Tax rate for deduction calculations"
                }
            },
            "required": ["expenses"]
        },
        "implementation": {
            "code": '''
def expense_calculator(parameters, context):
    """Calculate total expenses with tax implications"""
    
    expenses = parameters.get('expenses', [])
    tax_rate = parameters.get('tax_rate', 0.25)
    
    total_expenses = 0
    total_deductible = 0
    expense_breakdown = {}
    monthly_breakdown = {}
    
    for expense in expenses:
        amount = expense.get('amount', 0)
        category = expense.get('category', 'other')
        is_deductible = expense.get('tax_deductible', False)
        date = expense.get('date', '2024-01-01')
        
        total_expenses += amount
        
        if is_deductible:
            total_deductible += amount
        
        # Category breakdown
        if category in expense_breakdown:
            expense_breakdown[category] += amount
        else:
            expense_breakdown[category] = amount
        
        # Monthly breakdown
        month = date[:7]  # Extract YYYY-MM
        if month in monthly_breakdown:
            monthly_breakdown[month] += amount
        else:
            monthly_breakdown[month] = amount
    
    # Calculate tax savings
    tax_savings = total_deductible * tax_rate
    net_cost = total_expenses - tax_savings
    
    # Generate insights
    insights = []
    if total_deductible / total_expenses > 0.5:
        insights.append("High deductible ratio - good tax optimization")
    if total_expenses > 10000:
        insights.append("Large expense total - consider budget review")
    
    return {
        "total_expenses": round(total_expenses, 2),
        "total_deductible": round(total_deductible, 2),
        "tax_savings": round(tax_savings, 2),
        "net_cost": round(net_cost, 2),
        "expense_breakdown": expense_breakdown,
        "monthly_breakdown": monthly_breakdown,
        "tax_rate_used": tax_rate,
        "deductible_percentage": round((total_deductible / total_expenses * 100), 1) if total_expenses > 0 else 0,
        "insights": insights,
        "summary": f"Total: ${total_expenses:.2f}, Tax savings: ${tax_savings:.2f}, Net cost: ${net_cost:.2f}"
    }
            ''',
            "function_name": "expense_calculator"
        },
        "requires_auth": False,
        "max_execution_time_ms": 10000,
        "is_shared": False
    }
    
    response = requests.post(
        'https://your-api.com/agents/tools/create',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=tool_config
    )
    
    if response.status_code == 200:
        result = response.json()
        tool_name = result['tool_name']
        print(f"✅ Created function tool: {tool_name}")
        print(f"   Tool ID: {result['tool_id']}")
        return tool_name
    else:
        print(f"❌ Failed to create tool: {response.text}")
        return None

# Create the expense calculator tool
expense_tool = create_expense_calculator_tool()
```

#### Method 2: API Endpoint Tools

Create tools that call external APIs:

```python
def create_weather_api_tool():
    """Create a tool that calls weather APIs"""
    
    tool_config = {
        "name": "weather_lookup",
        "description": "Get current weather information and forecasts for any location",
        "category": "information",
        "tool_type": "api_endpoint",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name, coordinates, or airport code"
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial", "kelvin"],
                    "default": "metric",
                    "description": "Temperature units"
                },
                "include_forecast": {
                    "type": "boolean",
                    "default": false,
                    "description": "Include 5-day forecast"
                }
            },
            "required": ["location"]
        },
        "implementation": {
            "url": "https://api.openweathermap.org/data/2.5/weather",
            "method": "GET",
            "headers": {
                "Content-Type": "application/json"
            },
            "auth": {
                "type": "api_key",
                "key_name": "appid",
                "api_key": "your_openweather_api_key"
            }
        },
        "requires_auth": True,
        "max_execution_time_ms": 15000,
        "is_shared": True
    }
    
    response = requests.post(
        'https://your-api.com/agents/tools/create',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=tool_config
    )
    
    if response.status_code == 200:
        tool_name = response.json()['tool_name']
        print(f"✅ Created API endpoint tool: {tool_name}")
        return tool_name
    else:
        print(f"❌ Failed to create tool: {response.text}")
        return None

weather_tool = create_weather_api_tool()
```

#### Method 3: Webhook Tools

Create tools that trigger webhooks for external processing:

```python
def create_slack_notification_tool():
    """Create a webhook-based tool for Slack notifications"""
    
    tool_config = {
        "name": "slack_notification",
        "description": "Send formatted notifications to Slack channels with priority handling",
        "category": "communication",
        "tool_type": "webhook",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Slack channel name (with #) or user ID"
                },
                "message": {
                    "type": "string",
                    "description": "Message content to send"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "default": "medium",
                    "description": "Message priority level"
                },
                "include_timestamp": {
                    "type": "boolean",
                    "default": true,
                    "description": "Include timestamp in message"
                },
                "mention_users": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of user IDs to mention"
                }
            },
            "required": ["channel", "message"]
        },
        "implementation": {
            "webhook_url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
            "method": "POST",
            "headers": {
                "Content-Type": "application/json"
            },
            "callback_required": False
        },
        "max_execution_time_ms": 5000,
        "is_shared": True
    }
    
    response = requests.post(
        'https://your-api.com/agents/tools/create',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=tool_config
    )
    
    if response.status_code == 200:
        tool_name = response.json()['tool_name']
        print(f"✅ Created webhook tool: {tool_name}")
        return tool_name
    else:
        print(f"❌ Failed to create tool: {response.text}")
        return None

slack_tool = create_slack_notification_tool()
```

### Testing Custom Tools

Always test your tools before using them with agents:

```python
def test_custom_tool(tool_name, test_parameters):
    """Test a custom tool with sample parameters"""
    
    test_request = {
        "parameters": test_parameters,
        "context": {
            "test_mode": True,
            "user_notes": "Testing tool functionality"
        }
    }
    
    response = requests.post(
        f'https://your-api.com/agents/tools/{tool_name}/test',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=test_request
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Tool test successful!")
        print(f"   Execution time: {result['execution_time_ms']}ms")
        print(f"   Result preview: {str(result['result'])[:200]}...")
        return result
    else:
        print(f"❌ Tool test failed: {response.text}")
        return None

# Test the expense calculator with sample data
expense_test = test_custom_tool(
    "expense_calculator",
    {
        "expenses": [
            {"amount": 1200, "category": "software", "tax_deductible": True, "date": "2024-01-15"},
            {"amount": 800, "category": "meals", "tax_deductible": False, "date": "2024-01-16"},
            {"amount": 2500, "category": "equipment", "tax_deductible": True, "date": "2024-01-20"}
        ],
        "tax_rate": 0.28
    }
)

# Test Slack notification
slack_test = test_custom_tool(
    "slack_notification",
    {
        "channel": "#general",
        "message": "Test notification from agent system",
        "priority": "medium",
        "include_timestamp": True
    }
)
```

### Managing Custom Tools

#### List Your Tools

```python
def list_my_custom_tools():
    """List all custom tools created by the user"""
    
    response = requests.get(
        'https://your-api.com/agents/tools/list?created_by_me=true',
        headers={'X-Token': 'your_token_here'}
    )
    
    if response.status_code == 200:
        data = response.json()
        tools = data['tools']
        print(f"📋 Found {data['count']} custom tools:")
        
        for tool in tools:
            print(f"\n  🔧 {tool['tool_name']}")
            print(f"     📝 {tool['description']}")
            print(f"     🏷️  Category: {tool['category']}")
            print(f"     ⚙️  Type: {tool['tool_type']}")
            print(f"     📅 Created: {tool['created_at']}")
            print(f"     🌐 Shared: {'Yes' if tool['is_shared'] else 'No'}")
            if tool.get('usage_stats'):
                print(f"     📊 Used {tool['usage_stats']['usage_count']} times")
        
        return tools
    else:
        print(f"❌ Failed to list tools: {response.text}")
        return []

my_tools = list_my_custom_tools()
```

#### Get Detailed Tool Information

```python
def get_tool_details(tool_name):
    """Get comprehensive details about a specific tool"""
    
    response = requests.get(
        f'https://your-api.com/agents/tools/{tool_name}',
        headers={'X-Token': 'your_token_here'}
    )
    
    if response.status_code == 200:
        tool = response.json()['tool']
        
        print(f"🔧 Tool Details: {tool['tool_name']}")
        print(f"   📝 Description: {tool['description']}")
        print(f"   🏷️  Category: {tool['category']}")
        print(f"   ⚙️  Type: {tool['tool_type']}")
        print(f"   ⏱️  Max execution time: {tool['max_execution_time_ms']}ms")
        print(f"   🔒 Requires auth: {tool['requires_auth']}")
        print(f"   👤 Owner: {tool.get('creator_name', 'Unknown')}")
        print(f"   📅 Created: {tool['created_at']}")
        
        # Usage statistics
        usage = tool.get('usage_stats', {})
        if usage.get('usage_count', 0) > 0:
            print(f"\n   📊 Usage Statistics:")
            print(f"      🔄 Times used: {usage['usage_count']}")
            print(f"      🕒 Last used: {usage.get('last_used', 'Never')}")
            print(f"      ⚡ Avg execution: {usage.get('avg_execution_time_ms', 0):.1f}ms")
        
        # Parameters schema
        schema = tool.get('parameters_schema', {})
        if schema.get('properties'):
            print(f"\n   📋 Parameters:")
            for param, config in schema['properties'].items():
                required = "✅" if param in schema.get('required', []) else "⚪"
                print(f"      {required} {param}: {config.get('description', 'No description')}")
        
        return tool
    else:
        print(f"❌ Failed to get tool details: {response.text}")
        return None

# Get details for expense calculator
expense_details = get_tool_details("expense_calculator")
```

#### Update Tool Configuration

```python
def update_tool_configuration(tool_name, updates):
    """Update a custom tool's configuration"""
    
    response = requests.put(
        f'https://your-api.com/agents/tools/{tool_name}',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=updates
    )
    
    if response.status_code == 200:
        print(f"✅ Tool {tool_name} updated successfully")
        return True
    else:
        print(f"❌ Failed to update tool: {response.text}")
        return False

# Example: Update tool description and sharing settings
update_success = update_tool_configuration(
    "expense_calculator",
    {
        "description": "Advanced expense calculator with tax optimization and monthly breakdown analysis",
        "is_shared": True,  # Share with other users
        "max_execution_time_ms": 15000  # Increase timeout for complex calculations
    }
)

# Example: Update parameters schema to add new field
schema_update = update_tool_configuration(
    "expense_calculator",
    {
        "parameters_schema": {
            "type": "object",
            "properties": {
                "expenses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "number", "description": "Expense amount"},
                            "category": {"type": "string", "description": "Expense category"},
                            "tax_deductible": {"type": "boolean", "description": "Is this expense tax deductible?"},
                            "date": {"type": "string", "description": "Expense date (YYYY-MM-DD)"},
                            "vendor": {"type": "string", "description": "Vendor name (optional)"}  # New field
                        },
                        "required": ["amount", "category"]
                    }
                },
                "tax_rate": {"type": "number", "default": 0.25},
                "currency": {"type": "string", "default": "USD", "description": "Currency code"}  # New field
            },
            "required": ["expenses"]
        }
    }
)
```

#### Share Tools with Team Members

```python
def share_tool_with_team(tool_name, user_ids):
    """Share a tool with specific team members"""
    
    share_request = {
        "user_ids": user_ids,
        "grant_access": True
    }
    
    response = requests.post(
        f'https://your-api.com/agents/tools/{tool_name}/share',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=share_request
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ {result['message']}")
        return True
    else:
        print(f"❌ Failed to share tool: {response.text}")
        return False

# Share expense calculator with finance team
finance_team_ids = [
    "user-uuid-finance-manager",
    "user-uuid-accountant-1",
    "user-uuid-accountant-2"
]

share_success = share_tool_with_team("expense_calculator", finance_team_ids)

# Revoke access from specific users
revoke_success = requests.post(
    f'https://your-api.com/agents/tools/expense_calculator/share',
    headers={
        'X-Token': 'your_token_here',
        'Content-Type': 'application/json'
    },
    json={
        "user_ids": ["user-uuid-to-revoke"],
        "grant_access": False  # Revoke access
    }
).status_code == 200
```

### Complex Tool Examples

#### CRM Integration Tool

```python
def create_comprehensive_crm_tool():
    """Create a full-featured CRM integration tool"""
    
    crm_tool_config = {
        "name": "crm_customer_manager",
        "description": "Comprehensive CRM integration for customer management, opportunity tracking, and interaction logging",
        "category": "sales",
        "tool_type": "function",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "get_customer", "update_customer", "search_customers",
                        "log_interaction", "get_opportunities", "create_opportunity",
                        "get_activity_history", "generate_customer_report"
                    ],
                    "description": "CRM action to perform"
                },
                "customer_id": {
                    "type": "string", 
                    "description": "Customer ID for customer-specific actions"
                },
                "search_query": {
                    "type": "string",
                    "description": "Search query for customer search"
                },
                "data": {
                    "type": "object",
                    "description": "Action-specific data payload"
                },
                "filters": {
                    "type": "object",
                    "description": "Filters for search and list operations"
                }
            },
            "required": ["action"]
        },
        "implementation": {
            "code": '''
def crm_customer_manager(parameters, context):
    """Comprehensive CRM management functionality"""
    import json
    from datetime import datetime, timedelta
    
    action = parameters.get('action')
    customer_id = parameters.get('customer_id')
    search_query = parameters.get('search_query', '')
    data = parameters.get('data', {})
    filters = parameters.get('filters', {})
    user_id = context.get('user_id')
    
    # Mock database for demonstration (replace with real CRM API)
    customers_db = {
        "cust_001": {
            "id": "cust_001", "name": "Acme Corp", "email": "contact@acme.com",
            "phone": "+1-555-0123", "status": "active", "tier": "enterprise",
            "ltv": 150000, "last_contact": "2024-01-15", "industry": "technology",
            "employees": 500, "annual_revenue": 50000000
        },
        "cust_002": {
            "id": "cust_002", "name": "Beta LLC", "email": "info@beta.com",
            "phone": "+1-555-0456", "status": "active", "tier": "business",
            "ltv": 75000, "last_contact": "2024-01-10", "industry": "manufacturing",
            "employees": 150, "annual_revenue": 10000000
        }
    }
    
    opportunities_db = [
        {"id": "opp_001", "customer_id": "cust_001", "name": "Q2 License Renewal", 
         "value": 45000, "probability": 90, "stage": "negotiation", "close_date": "2024-02-28"},
        {"id": "opp_002", "customer_id": "cust_001", "name": "Additional Modules", 
         "value": 25000, "probability": 65, "stage": "proposal", "close_date": "2024-03-15"},
        {"id": "opp_003", "customer_id": "cust_002", "name": "Integration Services", 
         "value": 15000, "probability": 80, "stage": "qualified", "close_date": "2024-02-20"}
    ]
    
    try:
        if action == "get_customer":
            if not customer_id or customer_id not in customers_db:
                return {"error": "Customer not found", "customer_id": customer_id}
            
            customer = customers_db[customer_id]
            
            # Get related opportunities
            customer_opps = [opp for opp in opportunities_db if opp["customer_id"] == customer_id]
            pipeline_value = sum(opp["value"] * opp["probability"] / 100 for opp in customer_opps)
            
            return {
                "success": True,
                "customer": customer,
                "opportunities": customer_opps,
                "pipeline_value": round(pipeline_value, 2),
                "summary": f"{customer['name']} - {customer['tier']} tier, LTV: ${customer['ltv']:,}, Pipeline: ${pipeline_value:,.2f}"
            }
        
        elif action == "search_customers":
            if not search_query:
                return {"error": "Search query is required"}
            
            query_lower = search_query.lower()
            matching_customers = []
            
            for cust in customers_db.values():
                if (query_lower in cust["name"].lower() or 
                    query_lower in cust["email"].lower() or
                    query_lower in cust.get("industry", "").lower()):
                    matching_customers.append(cust)
            
            return {
                "success": True,
                "customers": matching_customers,
                "count": len(matching_customers),
                "query": search_query
            }
        
        elif action == "log_interaction":
            if not customer_id:
                return {"error": "customer_id is required for logging interactions"}
            
            interaction = {
                "id": f"int_{customer_id}_{int(datetime.utcnow().timestamp())}",
                "customer_id": customer_id,
                "type": data.get("type", "call"),
                "subject": data.get("subject", ""),
                "notes": data.get("notes", ""),
                "outcome": data.get("outcome", "completed"),
                "duration": data.get("duration", 0),
                "next_action": data.get("next_action", ""),
                "logged_by": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return {
                "success": True,
                "interaction": interaction,
                "message": f"Logged {interaction['type']} interaction for {customer_id}"
            }
        
        elif action == "get_opportunities":
            customer_opps = opportunities_db
            
            if customer_id:
                customer_opps = [opp for opp in opportunities_db if opp["customer_id"] == customer_id]
            
            # Apply filters
            if filters.get("stage"):
                customer_opps = [opp for opp in customer_opps if opp["stage"] == filters["stage"]]
            if filters.get("min_value"):
                customer_opps = [opp for opp in customer_opps if opp["value"] >= filters["min_value"]]
            
            total_value = sum(opp["value"] for opp in customer_opps)
            weighted_value = sum(opp["value"] * opp["probability"] / 100 for opp in customer_opps)
            
            return {
                "success": True,
                "opportunities": customer_opps,
                "count": len(customer_opps),
                "total_value": total_value,
                "weighted_value": round(weighted_value, 2),
                "summary": f"Found {len(customer_opps)} opportunities worth ${total_value:,} (weighted: ${weighted_value:,.2f})"
            }
        
        elif action == "generate_customer_report":
            if not customer_id or customer_id not in customers_db:
                return {"error": "Customer not found for report generation"}
            
            customer = customers_db[customer_id]
            customer_opps = [opp for opp in opportunities_db if opp["customer_id"] == customer_id]
            
            report = {
                "customer_overview": customer,
                "opportunity_summary": {
                    "active_opportunities": len(customer_opps),
                    "total_pipeline": sum(opp["value"] for opp in customer_opps),
                    "weighted_pipeline": sum(opp["value"] * opp["probability"] / 100 for opp in customer_opps),
                    "opportunities_by_stage": {}
                },
                "recommendations": [],
                "next_actions": [],
                "generated_at": datetime.utcnow().isoformat()
            }
            
            # Opportunities by stage
            for opp in customer_opps:
                stage = opp["stage"]
                if stage not in report["opportunity_summary"]["opportunities_by_stage"]:
                    report["opportunity_summary"]["opportunities_by_stage"][stage] = 0
                report["opportunity_summary"]["opportunities_by_stage"][stage] += opp["value"]
            
            # Generate recommendations
            if len(customer_opps) > 0:
                avg_probability = sum(opp["probability"] for opp in customer_opps) / len(customer_opps)
                if avg_probability < 70:
                    report["recommendations"].append("Focus on improving opportunity win rates")
            
            if customer["tier"] == "enterprise" and len(customer_opps) < 2:
                report["recommendations"].append("Identify additional expansion opportunities")
            
            return {
                "success": True,
                "report": report,
                "customer_name": customer["name"]
            }
        
        else:
            return {"error": f"Unsupported action: {action}"}
    
    except Exception as e:
        return {"error": f"CRM operation failed: {str(e)}"}
            ''',
            "function_name": "crm_customer_manager"
        },
        "requires_auth": True,
        "max_execution_time_ms": 25000,
        "is_shared": True
    }
    
    response = requests.post(
        'https://your-api.com/agents/tools/create',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=crm_tool_config
    )
    
    if response.status_code == 200:
        tool_name = response.json()['tool_name']
        print(f"✅ Created comprehensive CRM tool: {tool_name}")
        
        # Test the tool with various actions
        test_cases = [
            {"action": "get_customer", "customer_id": "cust_001"},
            {"action": "search_customers", "search_query": "technology"},
            {"action": "get_opportunities", "filters": {"stage": "negotiation"}},
            {"action": "generate_customer_report", "customer_id": "cust_001"}
        ]
        
        for test_case in test_cases:
            print(f"\n🧪 Testing: {test_case['action']}")
            test_result = test_custom_tool(tool_name, test_case)
            if test_result:
                print(f"   ✅ Success - Execution time: {test_result['execution_time_ms']}ms")
        
        return tool_name
    else:
        print(f"❌ Failed to create CRM tool: {response.text}")
        return None

# Create the comprehensive CRM tool
crm_tool = create_comprehensive_crm_tool()
```

### Using Pre-built Tool Templates

The system includes pre-built templates for common tool patterns:

```python
# Available templates: "http_request", "data_processor", "text_analyzer"

def create_tool_from_template(template_name, customizations):
    """Create a tool using a pre-built template"""
    
    # Get the template from the system
    from apis.agents.dynamic_tool_executor import get_tool_template
    template = get_tool_template(template_name)
    
    if not template:
        print(f"❌ Template {template_name} not found")
        available_templates = ["http_request", "data_processor", "text_analyzer"]
        print(f"Available templates: {available_templates}")
        return None
    
    # Merge template with customizations
    tool_config = {**template, **customizations}
    
    response = requests.post(
        'https://your-api.com/agents/tools/create',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=tool_config
    )
    
    if response.status_code == 200:
        tool_name = response.json()['tool_name']
        print(f"✅ Created tool from template: {tool_name}")
        return tool_name
    else:
        print(f"❌ Failed to create tool: {response.text}")
        return None

# Create HTTP client for company APIs
company_api_tool = create_tool_from_template(
    "http_request",
    {
        "name": "company_api_client",
        "description": "Client for internal company REST APIs with authentication",
        "category": "integration"
    }
)

# Create sales data processor
sales_processor_tool = create_tool_from_template(
    "data_processor",
    {
        "name": "sales_data_processor",
        "description": "Process sales data, calculate metrics, and generate insights",
        "category": "sales"
    }
)

# Create content analyzer
content_analyzer_tool = create_tool_from_template(
    "text_analyzer", 
    {
        "name": "content_analyzer",
        "description": "Analyze marketing content for keywords, sentiment, and readability",
        "category": "marketing"
    }
)
```

### Best Practices for Tool Creation

#### 1. Security Considerations

```python
# ✅ Good: Safe parameter validation
def safe_tool_implementation(parameters, context):
    # Validate all inputs
    required_fields = ['field1', 'field2']
    for field in required_fields:
        if field not in parameters:
            return {"error": f"Missing required field: {field}"}
    
    # Sanitize string inputs
    clean_text = parameters.get('text', '').strip()[:1000]  # Limit length
    
    # Use safe operations
    return {"result": clean_text.upper()}

# ❌ Bad: Dangerous operations
def unsafe_tool_implementation(parameters, context):
    # Don't use eval, exec, or dynamic imports
    # Don't access file system
    # Don't make unlimited external requests
    pass
```

#### 2. Error Handling

```python
def robust_tool_implementation(parameters, context):
    """Tool with proper error handling"""
    try:
        # Main logic here
        result = perform_operation(parameters)
        
        return {
            "success": True,
            "result": result,
            "metadata": {
                "processed_at": datetime.utcnow().isoformat(),
                "version": "1.0"
            }
        }
    
    except ValueError as e:
        return {
            "success": False,
            "error": f"Invalid input: {str(e)}",
            "error_type": "validation_error"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Operation failed: {str(e)}",
            "error_type": "execution_error"
        }
```

#### 3. Performance Optimization

```python
def optimized_tool_implementation(parameters, context):
    """Optimized tool implementation"""
    
    # Early validation
    if not parameters.get('data'):
        return {"error": "No data provided"}
    
    # Limit processing size
    data = parameters['data'][:1000]  # Process max 1000 items
    
    # Use efficient algorithms
    result = process_data_efficiently(data)
    
    # Return structured response
    return {
        "success": True,
        "result": result,
        "items_processed": len(data),
        "processing_time": "fast"  # Could include actual timing
    }
```

### Understanding Tool Structure

Tools in the system are defined by the `ToolDefinition` class:

```python
@dataclass
class ToolDefinition:
    name: str                           # Unique tool name
    type: ToolType                      # FUNCTION, MCP_SERVER, API_ENDPOINT
    description: str                    # Tool description
    parameters_schema: Dict[str, Any]   # JSON schema for parameters
    function: Optional[Callable] = None # Implementation function
    endpoint_url: Optional[str] = None  # For API endpoints
    mcp_config: Optional[Dict] = None   # For MCP servers
    requires_auth: bool = False         # Authorization required
    max_execution_time_ms: int = 30000  # Timeout limit
    category: str = "general"           # Tool category
```

### Step 1: Create Tool Implementation

Create a new file `apis/agents/custom_tools/my_custom_tools.py`:

```python
"""
Custom Business Tools
"""

import requests
import json
import pandas as pd
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

async def crm_integration_tool(params: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Integrate with CRM system to fetch customer data
    """
    try:
        action = params.get("action")
        customer_id = params.get("customer_id")
        user_id = context.get("user_id")
        
        # Your CRM API integration here
        crm_api_key = os.getenv("CRM_API_KEY")
        
        if action == "get_customer":
            # Example CRM API call
            response = requests.get(
                f"https://your-crm.com/api/customers/{customer_id}",
                headers={
                    "Authorization": f"Bearer {crm_api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                customer_data = response.json()
                return {
                    "status": "success",
                    "customer": customer_data,
                    "last_interaction": customer_data.get("last_contact"),
                    "total_value": customer_data.get("lifetime_value")
                }
            else:
                return {"status": "error", "message": "Customer not found"}
                
        elif action == "list_opportunities":
            # List sales opportunities
            response = requests.get(
                f"https://your-crm.com/api/opportunities",
                headers={"Authorization": f"Bearer {crm_api_key}"},
                params={"customer_id": customer_id, "status": "open"}
            )
            
            opportunities = response.json()
            return {
                "status": "success",
                "opportunities": opportunities,
                "total_value": sum(opp.get("value", 0) for opp in opportunities)
            }
            
    except Exception as e:
        logger.error(f"CRM integration error: {str(e)}")
        return {"status": "error", "message": str(e)}

async def financial_reporting_tool(params: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Generate financial reports and analysis
    """
    try:
        report_type = params.get("report_type")
        period = params.get("period", "monthly")
        metrics = params.get("metrics", ["revenue", "expenses", "profit"])
        
        # Connect to your financial system
        # This is a mock implementation
        financial_data = {
            "revenue": 150000,
            "expenses": 120000,
            "profit": 30000,
            "growth_rate": 15.5,
            "period": period
        }
        
        if report_type == "summary":
            return {
                "status": "success",
                "report_type": "Financial Summary",
                "period": period,
                "metrics": {k: v for k, v in financial_data.items() if k in metrics},
                "insights": [
                    "Revenue growth is strong at 15.5%",
                    "Profit margins are healthy at 20%",
                    "Expenses are well controlled"
                ]
            }
            
        elif report_type == "trend_analysis":
            # Mock trend data
            trend_data = {
                "revenue_trend": [140000, 145000, 150000],
                "months": ["Jan", "Feb", "Mar"],
                "growth_percentage": [4.2, 3.4, 3.4]
            }
            return {
                "status": "success",
                "report_type": "Trend Analysis",
                "data": trend_data,
                "recommendation": "Maintain current growth trajectory"
            }
            
    except Exception as e:
        logger.error(f"Financial reporting error: {str(e)}")
        return {"status": "error", "message": str(e)}

async def inventory_management_tool(params: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Manage inventory operations
    """
    try:
        action = params.get("action")
        product_id = params.get("product_id")
        
        # Mock inventory system integration
        if action == "check_stock":
            inventory_data = {
                "product_id": product_id,
                "current_stock": 150,
                "reserved": 25,
                "available": 125,
                "reorder_point": 50,
                "status": "in_stock"
            }
            
            if inventory_data["available"] < inventory_data["reorder_point"]:
                inventory_data["status"] = "low_stock"
                inventory_data["action_needed"] = "reorder_required"
            
            return {
                "status": "success",
                "inventory": inventory_data
            }
            
        elif action == "forecast_demand":
            # Mock demand forecasting
            forecast_data = {
                "product_id": product_id,
                "current_stock": 150,
                "predicted_demand_30_days": 80,
                "predicted_stockout_date": "2024-02-15",
                "recommended_order_quantity": 200
            }
            
            return {
                "status": "success",
                "forecast": forecast_data,
                "recommendations": [
                    "Order 200 units within next 10 days",
                    "Consider bulk discount opportunities",
                    "Monitor seasonal trends"
                ]
            }
            
    except Exception as e:
        logger.error(f"Inventory management error: {str(e)}")
        return {"status": "error", "message": str(e)}
```

### Step 2: Register Custom Tools

Create `apis/agents/custom_tools/__init__.py`:

```python
"""
Custom Tools Registration
"""

from apis.agents.tool_registry import tool_registry, ToolDefinition, ToolType
from .my_custom_tools import (
    crm_integration_tool,
    financial_reporting_tool, 
    inventory_management_tool
)

def register_custom_tools():
    """Register all custom tools with the tool registry"""
    
    # CRM Integration Tool
    crm_tool = ToolDefinition(
        name="crm_integration",
        type=ToolType.FUNCTION,
        description="Integrate with CRM system to manage customer data and opportunities",
        parameters_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_customer", "list_opportunities", "create_lead"],
                    "description": "CRM action to perform"
                },
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID for CRM operations"
                },
                "data": {
                    "type": "object",
                    "description": "Additional data for CRM operations"
                }
            },
            "required": ["action"]
        },
        function=crm_integration_tool,
        category="sales",
        requires_auth=True,
        max_execution_time_ms=15000
    )
    
    # Financial Reporting Tool
    financial_tool = ToolDefinition(
        name="financial_reporting",
        type=ToolType.FUNCTION,
        description="Generate financial reports and analysis",
        parameters_schema={
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": ["summary", "trend_analysis", "variance_report", "forecast"],
                    "description": "Type of financial report to generate"
                },
                "period": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly", "quarterly", "yearly"],
                    "default": "monthly",
                    "description": "Reporting period"
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Financial metrics to include in report"
                }
            },
            "required": ["report_type"]
        },
        function=financial_reporting_tool,
        category="finance",
        requires_auth=True,
        max_execution_time_ms=30000
    )
    
    # Inventory Management Tool
    inventory_tool = ToolDefinition(
        name="inventory_management",
        type=ToolType.FUNCTION,
        description="Manage inventory operations and forecasting",
        parameters_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["check_stock", "forecast_demand", "reorder_analysis"],
                    "description": "Inventory action to perform"
                },
                "product_id": {
                    "type": "string",
                    "description": "Product ID for inventory operations"
                },
                "parameters": {
                    "type": "object",
                    "description": "Additional parameters for inventory operations"
                }
            },
            "required": ["action", "product_id"]
        },
        function=inventory_management_tool,
        category="operations",
        requires_auth=True,
        max_execution_time_ms=20000
    )
    
    # Register all tools
    tool_registry.register_tool(crm_tool)
    tool_registry.register_tool(financial_tool)
    tool_registry.register_tool(inventory_tool)
    
    print("Custom tools registered successfully!")

# Auto-register when module is imported
register_custom_tools()
```

### Step 3: Update Tool Registry Initialization

Modify `apis/agents/tool_registry.py` to include custom tools:

```python
# Add to the __init__ method of ToolRegistry class
def __init__(self):
    self.tools: Dict[str, ToolDefinition] = {}
    self.mcp_servers: Dict[str, Dict[str, Any]] = {}
    self._load_builtin_tools()
    self._load_custom_tools()
    
    # Load custom tools from custom_tools package
    try:
        from apis.agents.custom_tools import register_custom_tools
        # Custom tools are auto-registered when imported
    except ImportError:
        logger.info("No custom tools package found")
```

### Step 4: Grant Tool Access to Users

Add the tools to the database and grant user access:

```sql
-- Add custom tools to the database
INSERT INTO agent_tools (tool_name, description, category, parameters_schema, max_execution_time_ms) VALUES
('crm_integration', 'Integrate with CRM system', 'sales', 
 '{"type": "object", "properties": {"action": {"type": "string", "enum": ["get_customer", "list_opportunities"]}}}',
 15000),
('financial_reporting', 'Generate financial reports', 'finance',
 '{"type": "object", "properties": {"report_type": {"type": "string", "enum": ["summary", "trend_analysis"]}}}',
 30000),
('inventory_management', 'Manage inventory operations', 'operations',
 '{"type": "object", "properties": {"action": {"type": "string", "enum": ["check_stock", "forecast_demand"]}}}',
 20000);

-- Grant access to specific users
INSERT INTO user_tool_access (user_id, tool_name, is_enabled) 
SELECT u.id, 'crm_integration', 1 
FROM users u 
WHERE u.scope IN (0, 1); -- Admin and business users

INSERT INTO user_tool_access (user_id, tool_name, is_enabled) 
SELECT u.id, 'financial_reporting', 1 
FROM users u 
WHERE u.scope IN (0, 1);

INSERT INTO user_tool_access (user_id, tool_name, is_enabled) 
SELECT u.id, 'inventory_management', 1 
FROM users u 
WHERE u.scope IN (0, 1);
```

### Step 5: Use Custom Tools in Agents

```python
import requests

# Create agent with custom tools
payload = {
    "name": "Sales Operations Manager",
    "instructions": """You are a sales operations manager with access to CRM and financial systems. 
    
    Your capabilities include:
    - Managing customer relationships through CRM integration
    - Generating financial reports and analysis
    - Providing sales forecasting and insights
    
    Always provide data-driven recommendations and actionable insights.""",
    "tools": ["crm_integration", "financial_reporting", "data_analysis", "document_generator"],
    "model": "gpt-4o",
    "temperature": 0.6
}

response = requests.post(
    'https://your-api.com/agents/create',
    headers={
        'X-Token': 'your_token_here',
        'Content-Type': 'application/json'
    },
    json=payload
)

agent_id = response.json()['agent_id']

# Execute with custom tools
execution_payload = {
    "agent_id": agent_id,
    "message": "Generate a comprehensive sales report for customer ID 12345 including their opportunities and financial performance",
    "tools": ["crm_integration", "financial_reporting"],
    "context": {
        "customer_focus": "high_value_clients",
        "report_urgency": "high"
    }
}

execution_response = requests.post(
    'https://your-api.com/agents/execute',
    headers={
        'X-Token': 'your_token_here',
        'Content-Type': 'application/json'
    },
    json=execution_payload
)

print(f"Job ID: {execution_response.json()['job_id']}")
```

---

## MCP Server Integration

### What is MCP?

Model Context Protocol (MCP) is a standard for connecting AI agents to external tools and data sources. The system is designed to support MCP servers for extensible tool integration.

### MCP Server Configuration

#### Step 1: Register MCP Server

```python
from apis.agents.tool_registry import tool_registry

# Register an MCP server
tool_registry.register_mcp_server(
    name="business_intelligence_server",
    url="https://mcp.your-company.com/bi",
    api_key="your_mcp_api_key",
    capabilities=["data_query", "report_generation", "visualization"]
)
```

#### Step 2: Database Configuration

```sql
-- Add MCP server to database
INSERT INTO mcp_servers (id, name, url, api_key, capabilities, is_enabled)
VALUES (
    NEWID(),
    'business_intelligence_server',
    'https://mcp.your-company.com/bi',
    'encrypted_api_key_here',
    '["data_query", "report_generation", "visualization"]',
    1
);
```

#### Step 3: Create MCP Tool Implementation

Create `apis/agents/mcp_tools.py`:

```python
"""
MCP Server Tool Implementations
"""

import requests
import json
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class MCPToolExecutor:
    def __init__(self, server_config):
        self.server_url = server_config['url']
        self.api_key = server_config.get('api_key')
        self.capabilities = server_config.get('capabilities', [])
    
    async def execute_mcp_tool(self, tool_name: str, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool via MCP server"""
        try:
            # MCP protocol request
            mcp_request = {
                "jsonrpc": "2.0",
                "id": context.get("correlation_id", "default"),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": parameters
                }
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            # Make MCP request
            response = requests.post(
                f"{self.server_url}/mcp",
                headers=headers,
                json=mcp_request,
                timeout=30
            )
            
            if response.status_code == 200:
                mcp_response = response.json()
                
                if "result" in mcp_response:
                    return {
                        "success": True,
                        "result": mcp_response["result"],
                        "mcp_server": self.server_url
                    }
                elif "error" in mcp_response:
                    return {
                        "success": False,
                        "error": mcp_response["error"]["message"],
                        "mcp_server": self.server_url
                    }
            else:
                return {
                    "success": False,
                    "error": f"MCP server returned {response.status_code}",
                    "mcp_server": self.server_url
                }
                
        except Exception as e:
            logger.error(f"MCP tool execution error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "mcp_server": self.server_url
            }
    
    async def discover_tools(self) -> list:
        """Discover available tools from MCP server"""
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "id": "discover",
                "method": "tools/list",
                "params": {}
            }
            
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = requests.post(
                f"{self.server_url}/mcp",
                headers=headers,
                json=mcp_request,
                timeout=10
            )
            
            if response.status_code == 200:
                mcp_response = response.json()
                if "result" in mcp_response:
                    return mcp_response["result"].get("tools", [])
            
            return []
            
        except Exception as e:
            logger.error(f"MCP tool discovery error: {str(e)}")
            return []

# Global MCP executors
mcp_executors = {}

def get_mcp_executor(server_name: str):
    """Get MCP executor for a server"""
    if server_name not in mcp_executors:
        # Load from database
        try:
            from apis.utils.databaseService import DatabaseService
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT url, api_key, capabilities FROM mcp_servers WHERE name = ? AND is_enabled = 1",
                [server_name]
            )
            
            server_data = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if server_data:
                server_config = {
                    'url': server_data[0],
                    'api_key': server_data[1],
                    'capabilities': json.loads(server_data[2]) if server_data[2] else []
                }
                mcp_executors[server_name] = MCPToolExecutor(server_config)
            
        except Exception as e:
            logger.error(f"Error loading MCP server config: {str(e)}")
    
    return mcp_executors.get(server_name)
```

#### Step 4: Update Tool Registry for MCP

Update `apis/agents/tool_registry.py` to support MCP tools:

```python
# Add to ToolRegistry class

def _execute_mcp_tool(self, tool: ToolDefinition, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool via MCP server"""
    try:
        from .mcp_tools import get_mcp_executor
        
        mcp_config = tool.mcp_config
        server_name = mcp_config.get('server_name')
        
        executor = get_mcp_executor(server_name)
        if not executor:
            return {"error": f"MCP server {server_name} not available"}
        
        # Execute via MCP
        result = asyncio.run(executor.execute_mcp_tool(tool.name, parameters, context))
        return result
        
    except Exception as e:
        logger.error(f"MCP tool execution error: {str(e)}")
        return {"error": str(e)}

def register_mcp_tool(self, server_name: str, tool_info: Dict[str, Any]):
    """Register a tool from an MCP server"""
    tool_def = ToolDefinition(
        name=tool_info['name'],
        type=ToolType.MCP_SERVER,
        description=tool_info.get('description', ''),
        parameters_schema=tool_info.get('inputSchema', {}),
        mcp_config={
            'server_name': server_name,
            'tool_name': tool_info['name']
        },
        category='mcp',
        max_execution_time_ms=30000
    )
    
    self.register_tool(tool_def)
    logger.info(f"Registered MCP tool: {tool_info['name']} from {server_name}")

async def discover_mcp_tools(self, server_name: str):
    """Discover and register tools from an MCP server"""
    from .mcp_tools import get_mcp_executor
    
    executor = get_mcp_executor(server_name)
    if not executor:
        logger.error(f"MCP server {server_name} not available")
        return
    
    tools = await executor.discover_tools()
    
    for tool_info in tools:
        self.register_mcp_tool(server_name, tool_info)
    
    logger.info(f"Discovered and registered {len(tools)} tools from {server_name}")
```

#### Step 5: Using MCP Tools

```python
import requests
import asyncio

async def setup_mcp_integration():
    """Set up MCP server integration"""
    
    # Register MCP server
    from apis.agents.tool_registry import tool_registry
    
    # Discover tools from MCP server
    await tool_registry.discover_mcp_tools("business_intelligence_server")
    
    # List newly available tools
    response = requests.get(
        'https://your-api.com/agents/tools?categories=mcp',
        headers={'X-Token': 'your_token_here'}
    )
    
    mcp_tools = response.json()['tools']
    print(f"Available MCP tools: {[t['name'] for t in mcp_tools]}")
    
    # Create agent with MCP tools
    agent_payload = {
        "name": "Business Intelligence Agent",
        "instructions": "You have access to business intelligence tools via MCP servers. Use these to generate comprehensive reports and insights.",
        "tools": [tool['name'] for tool in mcp_tools[:3]], # Use first 3 MCP tools
        "model": "gpt-4o"
    }
    
    agent_response = requests.post(
        'https://your-api.com/agents/create',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=agent_payload
    )
    
    return agent_response.json()['agent_id']

# Run MCP setup
# agent_id = asyncio.run(setup_mcp_integration())
```

---

## Business Agent Templates

### Understanding Templates

Business agent templates provide pre-configured agents for common business roles. Each template includes:

- **Specialized Instructions**: Role-specific behavior and expertise
- **Default Tools**: Relevant tools for the business function
- **Optimized Parameters**: Temperature and model settings
- **Use Case Examples**: Common scenarios and applications

### Available Templates

#### 1. Executive Assistant

**Best For**: C-level support, administrative tasks, scheduling

```python
# Create executive assistant
payload = {
    "name": "Senior Executive Assistant",
    "base_template": "executive_assistant",
    "instructions": "Additionally focus on board meeting preparation and stakeholder communication",
    "tools": ["calendar_manager", "send_email", "task_manager", "document_generator"]
}
```

**Common Use Cases**:
- Schedule complex multi-stakeholder meetings
- Draft executive communications
- Prepare meeting agendas and materials
- Coordinate travel and events
- Manage task prioritization

#### 2. Financial Analyst

**Best For**: Financial modeling, investment analysis, reporting

```python
# Create specialized financial analyst
payload = {
    "name": "SaaS Financial Analyst",
    "base_template": "financial_analyst", 
    "instructions": "Specialize in SaaS metrics: MRR, ARR, churn, CAC, LTV. Focus on subscription business models.",
    "tools": ["data_analysis", "calculator", "document_generator", "web_search"]
}
```

**Common Use Cases**:
- Build DCF and valuation models
- Analyze financial statements
- Create investor presentations
- Monitor KPIs and metrics
- Conduct market analysis

#### 3. Marketing Strategist

**Best For**: Campaign planning, market research, content strategy

```python
# Create digital marketing specialist
payload = {
    "name": "Digital Marketing Strategist",
    "base_template": "marketing_strategist",
    "instructions": "Focus on digital channels: SEO, SEM, social media, email marketing. Emphasize data-driven decision making.",
    "tools": ["web_search", "data_analysis", "document_generator", "send_email"]
}
```

**Template Customization Example**:

```python
import requests

def create_specialized_marketing_agent():
    """Create a specialized marketing agent with custom focus areas"""
    
    # Get base template first
    templates_response = requests.get(
        'https://your-api.com/agents/templates',
        headers={'X-Token': 'your_token_here'}
    )
    
    templates = templates_response.json()['templates']
    marketing_template = next(t for t in templates if t['id'] == 'marketing_strategist')
    
    print("Base Marketing Template:")
    print(f"- Default tools: {marketing_template['default_tools']}")
    print(f"- Temperature: {marketing_template['temperature']}")
    
    # Create customized agent
    custom_agent = {
        "name": "B2B SaaS Marketing Director",
        "base_template": "marketing_strategist",
        "description": "Specialized in B2B SaaS marketing with focus on product-led growth",
        "instructions": f"""
        {marketing_template.get('description', '')}
        
        Additional specializations:
        - B2B SaaS marketing strategies and tactics
        - Product-led growth (PLG) methodologies
        - Account-based marketing (ABM) campaigns
        - Customer success marketing and retention
        - Freemium and trial conversion optimization
        
        Key metrics to track:
        - Monthly Recurring Revenue (MRR) growth
        - Customer Acquisition Cost (CAC) 
        - Customer Lifetime Value (CLV)
        - Product adoption rates
        - User activation and engagement
        
        Always provide specific, measurable recommendations with clear success metrics.
        """,
        "tools": ["web_search", "data_analysis", "document_generator", "send_email", "crm_integration"],
        "temperature": 0.7
    }
    
    response = requests.post(
        'https://your-api.com/agents/custom/create',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=custom_agent
    )
    
    if response.status_code == 200:
        agent_id = response.json()['agent_id']
        print(f"Created specialized marketing agent: {agent_id}")
        return agent_id
    else:
        print(f"Error creating agent: {response.text}")
        return None

# Create the agent
agent_id = create_specialized_marketing_agent()

# Test with a specific task
if agent_id:
    test_execution = {
        "agent_id": agent_id,
        "message": """
        Develop a comprehensive go-to-market strategy for our new AI-powered analytics feature. 
        Target audience is mid-market B2B companies. 
        Budget: $50K for first quarter.
        Include pricing recommendations, channel strategy, and success metrics.
        """,
        "tools": ["web_search", "data_analysis", "document_generator"],
        "context": {
            "company_stage": "Series_B",
            "current_arr": "5M",
            "target_market": "mid_market_b2b"
        }
    }
    
    response = requests.post(
        'https://your-api.com/agents/execute',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=test_execution
    )
    
    print(f"Execution started: {response.json()['job_id']}")
```

### Template Inheritance and Customization

Templates support inheritance, allowing you to build upon existing templates:

```python
def create_template_hierarchy():
    """Demonstrate template inheritance"""
    
    # Level 1: Base business consultant
    base_consultant = {
        "name": "Management Consultant", 
        "base_template": "business_consultant",
        "instructions": "Focus on strategic planning and organizational transformation"
    }
    
    # Level 2: Specialized consultant (inherits from base)  
    tech_consultant = {
        "name": "Technology Consultant",
        "base_template": "business_consultant", 
        "instructions": """
        Specialized management consultant focusing on:
        - Digital transformation initiatives
        - Technology strategy and roadmaps
        - IT organizational design
        - Vendor selection and management
        - Agile transformation
        """,
        "tools": ["web_search", "data_analysis", "document_generator", "calculator"]
    }
    
    # Level 3: Highly specialized (could inherit from tech consultant if supported)
    ai_consultant = {
        "name": "AI Strategy Consultant",
        "base_template": "business_consultant",
        "instructions": """
        Highly specialized consultant focusing on AI adoption:
        - AI readiness assessments
        - Machine learning use case identification
        - AI ethics and governance frameworks
        - Data strategy for AI initiatives
        - AI team building and capability development
        
        Always consider:
        - Business value and ROI of AI initiatives
        - Technical feasibility and requirements
        - Change management and adoption challenges
        - Ethical implications and risk mitigation
        """,
        "tools": ["web_search", "data_analysis", "document_generator"],
        "temperature": 0.5
    }
    
    # Create agents at each level
    agents = {}
    for config in [base_consultant, tech_consultant, ai_consultant]:
        response = requests.post(
            'https://your-api.com/agents/custom/create',
            headers={'X-Token': 'your_token_here', 'Content-Type': 'application/json'},
            json=config
        )
        agents[config['name']] = response.json()['agent_id']
    
    return agents

consultant_agents = create_template_hierarchy()
print("Created consultant hierarchy:", consultant_agents)
```

---

## Multi-Agent Workflows

### Understanding Workflows

Multi-agent workflows allow you to chain multiple agents together for complex business processes. The system supports three flow types:

1. **Sequential**: Agents execute in order, output feeds into next agent
2. **Parallel**: Agents execute simultaneously, results are combined
3. **Conditional**: Agent selection based on conditions and results

### Sequential Workflows

**Best For**: Process-driven tasks with clear dependencies

```python
def create_product_launch_workflow():
    """Create a sequential product launch workflow"""
    
    # Step 1: Create the agents we'll need
    agents = {}
    
    # Market Research Agent
    research_agent = {
        "name": "Market Research Specialist",
        "base_template": "researcher",
        "instructions": "Conduct thorough market research including competitor analysis, market size, and customer needs assessment.",
        "tools": ["web_search", "data_analysis", "document_generator"]
    }
    
    # Product Strategy Agent  
    strategy_agent = {
        "name": "Product Strategy Manager",
        "base_template": "product_manager",
        "instructions": "Develop product positioning, pricing strategy, and feature prioritization based on market research.",
        "tools": ["data_analysis", "calculator", "document_generator"]
    }
    
    # Marketing Campaign Agent
    marketing_agent = {
        "name": "Launch Marketing Manager", 
        "base_template": "marketing_strategist",
        "instructions": "Create comprehensive launch marketing campaign including channels, messaging, and timeline.",
        "tools": ["web_search", "document_generator", "send_email", "calendar_manager"]
    }
    
    # Create each agent
    for agent_config in [research_agent, strategy_agent, marketing_agent]:
        response = requests.post(
            'https://your-api.com/agents/custom/create',
            headers={'X-Token': 'your_token_here', 'Content-Type': 'application/json'},
            json=agent_config
        )
        agents[agent_config['name']] = response.json()['agent_id']
    
    # Step 2: Create the workflow
    workflow_config = {
        "name": "Product Launch Workflow",
        "description": "Complete product launch process from research to marketing execution",
        "flow_type": "sequential",
        "agents": [
            {
                "agent_id": agents["Market Research Specialist"],
                "role": "Market Research",
                "description": "Conduct market analysis and competitor research"
            },
            {
                "agent_id": agents["Product Strategy Manager"], 
                "role": "Product Strategy",
                "description": "Develop positioning and pricing strategy"
            },
            {
                "agent_id": agents["Launch Marketing Manager"],
                "role": "Marketing Campaign",
                "description": "Create launch marketing campaign"
            }
        ]
    }
    
    response = requests.post(
        'https://your-api.com/agents/workflow/create',
        headers={'X-Token': 'your_token_here', 'Content-Type': 'application/json'},
        json=workflow_config
    )
    
    workflow_id = response.json()['workflow_id']
    print(f"Created product launch workflow: {workflow_id}")
    
    return workflow_id, agents

# Create and execute workflow
workflow_id, agents = create_product_launch_workflow()

# Execute the workflow
execution_request = {
    "workflow_id": workflow_id,
    "initial_input": """
    Product: AI-powered customer service chatbot
    Target Market: Small to medium businesses (SMBs) 
    Launch Timeline: Q2 2024
    Budget: $100K marketing budget
    
    Please conduct a complete analysis and develop a comprehensive launch strategy.
    """,
    "context": {
        "product_category": "AI_SaaS",
        "target_segment": "SMB",
        "competitive_landscape": "crowded",
        "differentiator": "industry_specific_training"
    }
}

workflow_response = requests.post(
    'https://your-api.com/agents/workflow/execute',
    headers={'X-Token': 'your_token_here', 'Content-Type': 'application/json'},
    json=execution_request
)

print(f"Workflow execution started: {workflow_response.json()['job_id']}")
```

### Parallel Workflows

**Best For**: Independent analysis tasks that can be combined

```python
def create_due_diligence_workflow():
    """Create parallel due diligence workflow for M&A analysis"""
    
    # Create specialized agents for parallel analysis
    agents_config = [
        {
            "name": "Financial Due Diligence Agent",
            "base_template": "financial_analyst",
            "instructions": "Conduct comprehensive financial due diligence including financial statement analysis, cash flow modeling, and valuation.",
            "tools": ["data_analysis", "calculator", "document_generator"]
        },
        {
            "name": "Market Due Diligence Agent", 
            "base_template": "marketing_strategist",
            "instructions": "Analyze market position, competitive landscape, customer base, and growth opportunities.",
            "tools": ["web_search", "data_analysis", "document_generator"]
        },
        {
            "name": "Technology Due Diligence Agent",
            "base_template": "business_consultant", 
            "instructions": "Evaluate technology stack, IP portfolio, development processes, and technical risks.",
            "tools": ["web_search", "data_analysis", "document_generator"]
        },
        {
            "name": "Legal Due Diligence Agent",
            "base_template": "legal_advisor",
            "instructions": "Review legal structure, contracts, compliance issues, and potential liabilities.",
            "tools": ["document_generator", "web_search", "database_query"]
        }
    ]
    
    # Create agents
    agents = {}
    for config in agents_config:
        response = requests.post(
            'https://your-api.com/agents/custom/create',
            headers={'X-Token': 'your_token_here', 'Content-Type': 'application/json'},
            json=config
        )
        agents[config['name']] = response.json()['agent_id']
    
    # Create parallel workflow
    workflow_config = {
        "name": "M&A Due Diligence Workflow",
        "description": "Parallel due diligence analysis covering financial, market, technology, and legal aspects",
        "flow_type": "parallel",
        "agents": [
            {"agent_id": agents["Financial Due Diligence Agent"], "role": "Financial Analysis"},
            {"agent_id": agents["Market Due Diligence Agent"], "role": "Market Analysis"}, 
            {"agent_id": agents["Technology Due Diligence Agent"], "role": "Technology Assessment"},
            {"agent_id": agents["Legal Due Diligence Agent"], "role": "Legal Review"}
        ]
    }
    
    response = requests.post(
        'https://your-api.com/agents/workflow/create',
        headers={'X-Token': 'your_token_here', 'Content-Type': 'application/json'},
        json=workflow_config
    )
    
    return response.json()['workflow_id']

workflow_id = create_due_diligence_workflow()
print(f"Due diligence workflow created: {workflow_id}")
```

### Conditional Workflows

**Best For**: Decision-driven processes with branching logic

```python
def create_customer_support_workflow():
    """Create conditional workflow for customer support escalation"""
    
    # Create agents for different support scenarios
    agents_config = [
        {
            "name": "L1 Support Agent",
            "base_template": "customer_service",
            "instructions": "Handle basic customer inquiries and technical issues. Escalate complex issues appropriately.",
            "tools": ["database_query", "send_email", "task_manager"]
        },
        {
            "name": "Technical Support Specialist",
            "base_template": "customer_service", 
            "instructions": "Handle complex technical issues and provide detailed troubleshooting guidance.",
            "tools": ["database_query", "document_generator", "send_email"]
        },
        {
            "name": "Account Manager",
            "base_template": "sales_director",
            "instructions": "Handle high-value customer issues and relationship management concerns.",
            "tools": ["crm_integration", "send_email", "calendar_manager"]
        }
    ]
    
    # Create agents
    agents = {}
    for config in agents_config:
        response = requests.post(
            'https://your-api.com/agents/custom/create',
            headers={'X-Token': 'your_token_here', 'Content-Type': 'application/json'},
            json=config
        )
        agents[config['name']] = response.json()['agent_id']
    
    # Create conditional workflow
    workflow_config = {
        "name": "Customer Support Escalation Workflow",
        "description": "Route customer issues to appropriate agents based on complexity and customer tier",
        "flow_type": "conditional",
        "agents": [
            {
                "agent_id": agents["L1 Support Agent"],
                "role": "Initial Triage",
                "conditions": ["issue_type == 'general'", "customer_tier == 'standard'"]
            },
            {
                "agent_id": agents["Technical Support Specialist"],
                "role": "Technical Resolution", 
                "conditions": ["issue_type == 'technical'", "complexity == 'high'"]
            },
            {
                "agent_id": agents["Account Manager"],
                "role": "VIP Handling",
                "conditions": ["customer_tier == 'enterprise'", "priority == 'high'"]
            }
        ]
    }
    
    response = requests.post(
        'https://your-api.com/agents/workflow/create',
        headers={'X-Token': 'your_token_here', 'Content-Type': 'application/json'},
        json=workflow_config
    )
    
    return response.json()['workflow_id']
```

### Workflow Monitoring and Management

```python
def monitor_workflow_execution(job_id, max_wait=600):
    """Monitor workflow execution with detailed progress tracking"""
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        # Get job status
        response = requests.get(
            f'https://your-api.com/agents/status/{job_id}',
            headers={'X-Token': 'your_token_here'}
        )
        
        status_data = response.json()
        print(f"Workflow Status: {status_data['status']}")
        
        if status_data['status'] == 'completed':
            result = status_data.get('result', {})
            workflow_results = result.get('workflow_results', [])
            
            print("\n=== Workflow Results ===")
            for step in workflow_results:
                print(f"Step {step['step']}: {step['role']}")
                print(f"Agent: {step['agent_id']}")
                print(f"Output: {step['output'][:200]}...")
                print()
            
            return workflow_results
            
        elif status_data['status'] == 'failed':
            print(f"Workflow failed: {status_data.get('error_message')}")
            return None
        
        # Show progress if available
        if 'elapsed_seconds' in status_data:
            print(f"  Elapsed: {status_data['elapsed_seconds']}s")
            if 'estimated_remaining' in status_data:
                print(f"  Estimated remaining: {status_data['estimated_remaining']}s")
        
        time.sleep(10)  # Check every 10 seconds
    
    print("Workflow monitoring timed out")
    return None

# Example usage
# workflow_results = monitor_workflow_execution(job_id)
```

---

## Advanced Customization

### Creating Industry-Specific Agent Packs

```python
def create_healthcare_agent_pack():
    """Create a complete set of agents for healthcare organizations"""
    
    healthcare_agents = {
        "Clinical Research Manager": {
            "base_template": "product_manager",
            "instructions": """
            Specialized in clinical research and regulatory compliance:
            - Protocol development and study design
            - Regulatory submission management (FDA, EMA)
            - Clinical data analysis and reporting
            - Site management and monitoring
            - Adverse event tracking and reporting
            
            Always ensure compliance with GCP, HIPAA, and relevant regulations.
            """,
            "tools": ["data_analysis", "document_generator", "task_manager", "calendar_manager"]
        },
        
        "Healthcare Operations Director": {
            "base_template": "operations_manager",
            "instructions": """
            Focus on healthcare operations optimization:
            - Patient flow and capacity planning
            - Quality improvement initiatives
            - Regulatory compliance monitoring
            - Staff scheduling and resource allocation
            - Revenue cycle optimization
            
            Prioritize patient safety and care quality in all recommendations.
            """,
            "tools": ["data_analysis", "task_manager", "document_generator", "calendar_manager"]
        },
        
        "Medical Affairs Specialist": {
            "base_template": "business_consultant",
            "instructions": """
            Medical affairs and scientific communication expert:
            - Scientific publication strategy
            - KOL engagement and management
            - Medical education program development
            - Advisory board management
            - Post-market surveillance analysis
            
            Maintain scientific integrity and evidence-based recommendations.
            """,
            "tools": ["web_search", "document_generator", "send_email", "calendar_manager"]
        }
    }
    
    # Create all healthcare agents
    created_agents = {}
    for name, config in healthcare_agents.items():
        response = requests.post(
            'https://your-api.com/agents/custom/create',
            headers={'X-Token': 'your_token_here', 'Content-Type': 'application/json'},
            json={"name": name, **config}
        )
        created_agents[name] = response.json()['agent_id']
        print(f"Created {name}: {created_agents[name]}")
    
    return created_agents

def create_fintech_agent_pack():
    """Create agents specialized for fintech companies"""
    
    fintech_agents = {
        "Risk Management Director": {
            "base_template": "financial_analyst",
            "instructions": """
            Specialized in fintech risk management:
            - Credit risk modeling and assessment
            - Operational risk identification and mitigation
            - Regulatory compliance (PCI DSS, SOX, Basel III)
            - Fraud detection and prevention strategies
            - Stress testing and scenario analysis
            
            Always prioritize regulatory compliance and risk mitigation.
            """,
            "tools": ["data_analysis", "calculator", "document_generator", "web_search"]
        },
        
        "Product Compliance Officer": {
            "base_template": "legal_advisor",
            "instructions": """
            Financial services compliance specialist:
            - Product regulatory review and approval
            - Consumer protection law compliance
            - Anti-money laundering (AML) program oversight
            - Privacy and data protection (CCPA, GDPR)
            - Financial product disclosure requirements
            
            Ensure all recommendations meet regulatory standards.
            """,
            "tools": ["web_search", "document_generator", "database_query"]
        },
        
        "Customer Success Manager": {
            "base_template": "customer_service", 
            "instructions": """
            Fintech customer success specialization:
            - Financial product onboarding optimization
            - Customer financial health monitoring
            - Churn prediction and prevention
            - Product adoption and engagement strategies
            - Regulatory communication and transparency
            
            Focus on customer financial wellbeing and product value realization.
            """,
            "tools": ["crm_integration", "data_analysis", "send_email", "task_manager"]
        }
    }
    
    # Create fintech agents
    created_agents = {}
    for name, config in fintech_agents.items():
        response = requests.post(
            'https://your-api.com/agents/custom/create',
            headers={'X-Token': 'your_token_here', 'Content-Type': 'application/json'},
            json={"name": name, **config}
        )
        created_agents[name] = response.json()['agent_id']
    
    return created_agents

# Create industry packs
healthcare_agents = create_healthcare_agent_pack()
fintech_agents = create_fintech_agent_pack()
```

### Advanced Agent Configuration

```python
class AdvancedAgentBuilder:
    """Advanced agent configuration builder"""
    
    def __init__(self, token):
        self.token = token
        self.headers = {
            'X-Token': token,
            'Content-Type': 'application/json'
        }
    
    def create_multi_model_agent(self, name, tasks_config):
        """Create agent that uses different models for different tasks"""
        
        # Create multiple specialized agents
        agents = {}
        
        for task_name, task_config in tasks_config.items():
            agent_config = {
                "name": f"{name} - {task_name}",
                "instructions": task_config['instructions'],
                "tools": task_config.get('tools', []),
                "model": task_config.get('model', 'gpt-4o'),
                "temperature": task_config.get('temperature', 0.7),
                "metadata": {
                    "parent_agent": name,
                    "task_specialization": task_name
                }
            }
            
            response = requests.post(
                'https://your-api.com/agents/create',
                headers=self.headers,
                json=agent_config
            )
            
            agents[task_name] = response.json()['agent_id']
        
        # Create orchestration workflow
        workflow_config = {
            "name": f"{name} Multi-Model Workflow",
            "description": f"Orchestrated workflow for {name} with specialized models",
            "flow_type": "conditional",
            "agents": [
                {
                    "agent_id": agent_id,
                    "role": task_name,
                    "conditions": [f"task_type == '{task_name}'"]
                }
                for task_name, agent_id in agents.items()
            ]
        }
        
        workflow_response = requests.post(
            'https://your-api.com/agents/workflow/create',
            headers=self.headers,
            json=workflow_config
        )
        
        return {
            "agents": agents,
            "workflow_id": workflow_response.json()['workflow_id']
        }
    
    def create_learning_agent(self, name, base_config, feedback_system=True):
        """Create agent with learning capabilities through feedback"""
        
        enhanced_config = {
            **base_config,
            "name": name,
            "instructions": f"""
            {base_config.get('instructions', '')}
            
            LEARNING AND IMPROVEMENT:
            - Pay attention to user feedback and adjust approaches accordingly
            - Track successful strategies and apply them to similar situations
            - Learn from mistakes and avoid repeating them
            - Continuously improve based on outcomes and feedback
            
            FEEDBACK INTEGRATION:
            - Always ask for feedback on important recommendations
            - Incorporate feedback into future responses
            - Maintain context of what works well for each user
            """,
            "metadata": {
                "learning_enabled": True,
                "feedback_system": feedback_system,
                "adaptation_level": "high"
            }
        }
        
        response = requests.post(
            'https://your-api.com/agents/custom/create',
            headers=self.headers,
            json=enhanced_config
        )
        
        return response.json()['agent_id']

# Example usage
builder = AdvancedAgentBuilder('your_token_here')

# Create multi-model content agent
content_agent_config = {
    "creative_writing": {
        "instructions": "Focus on creative, engaging content with high creativity",
        "model": "gpt-4o",
        "temperature": 0.9,
        "tools": ["web_search", "document_generator"]
    },
    "technical_writing": {
        "instructions": "Create precise, accurate technical documentation",
        "model": "gpt-4o",  
        "temperature": 0.3,
        "tools": ["web_search", "document_generator", "data_analysis"]
    },
    "data_analysis": {
        "instructions": "Analyze data and generate insights with statistical rigor",
        "model": "gpt-4o",
        "temperature": 0.2,
        "tools": ["data_analysis", "calculator", "document_generator"]
    }
}

multi_model_agent = builder.create_multi_model_agent(
    "Advanced Content Specialist",
    content_agent_config
)

print(f"Created multi-model agent with workflow: {multi_model_agent['workflow_id']}")
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Agent Creation Fails

**Problem**: Agent creation returns 400 or 500 errors

**Solutions**:

```python
def diagnose_agent_creation_issue():
    """Diagnose common agent creation problems"""
    
    # Check 1: Verify token and permissions
    try:
        response = requests.get(
            'https://your-api.com/agents/tools',
            headers={'X-Token': 'your_token_here'}
        )
        
        if response.status_code == 401:
            print("❌ Token issue: Invalid or expired token")
            return
        elif response.status_code == 403:
            print("❌ Permission issue: User doesn't have access to agent endpoints")
            return
        else:
            available_tools = [tool['name'] for tool in response.json()['tools']]
            print(f"✅ Token valid. Available tools: {available_tools}")
    except Exception as e:
        print(f"❌ Connection issue: {str(e)}")
        return
    
    # Check 2: Validate agent configuration
    test_config = {
        "name": "Test Agent",
        "instructions": "You are a helpful assistant",
        "tools": ["web_search"],  # Use only basic tools
        "model": "gpt-4o"
    }
    
    response = requests.post(
        'https://your-api.com/agents/create',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=test_config
    )
    
    if response.status_code == 200:
        print("✅ Basic agent creation works")
        agent_id = response.json()['agent_id']
        print(f"   Test agent created: {agent_id}")
    else:
        print(f"❌ Agent creation failed: {response.status_code}")
        print(f"   Error: {response.text}")
    
    # Check 3: Azure OpenAI configuration
    try:
        from apis.utils.config import get_azure_openai_config
        config = get_azure_openai_config()
        
        required_keys = ['api_key', 'endpoint', 'api_version']
        for key in required_keys:
            if config.get(key):
                print(f"✅ {key} configured")
            else:
                print(f"❌ {key} missing")
    except Exception as e:
        print(f"❌ Configuration error: {str(e)}")

# Run diagnosis
diagnose_agent_creation_issue()
```

#### 2. Agent Execution Timeouts

**Problem**: Agent executions time out or never complete

**Solutions**:

```python
def troubleshoot_execution_timeouts():
    """Troubleshoot agent execution timeout issues"""
    
    # Check job processor status
    response = requests.get(
        'https://your-api.com/jobs/status/recent',
        headers={'X-Token': 'your_token_here'}
    )
    
    if response.status_code == 200:
        recent_jobs = response.json().get('jobs', [])
        
        failed_jobs = [job for job in recent_jobs if job['status'] == 'failed']
        timeout_jobs = [job for job in recent_jobs if 'timeout' in job.get('error_message', '').lower()]
        
        print(f"Recent jobs: {len(recent_jobs)}")
        print(f"Failed jobs: {len(failed_jobs)}")
        print(f"Timeout jobs: {len(timeout_jobs)}")
        
        if timeout_jobs:
            print("\nTimeout job details:")
            for job in timeout_jobs[:3]:
                print(f"  Job {job['id']}: {job.get('error_message', 'No error message')}")
    
    # Test with simple execution
    print("\nTesting simple execution...")
    
    # Get a basic agent
    agents_response = requests.get(
        'https://your-api.com/agents/list',
        headers={'X-Token': 'your_token_here'}
    )
    
    if agents_response.status_code == 200:
        agents = agents_response.json()['agents']
        if agents:
            test_agent_id = agents[0]['agent_id']
            
            # Simple execution test
            test_execution = {
                "agent_id": test_agent_id,
                "message": "Hello, please respond with a simple greeting.",
                "tools": []  # No tools to minimize complexity
            }
            
            exec_response = requests.post(
                'https://your-api.com/agents/execute',
                headers={
                    'X-Token': 'your_token_here',
                    'Content-Type': 'application/json'
                },
                json=test_execution
            )
            
            if exec_response.status_code == 200:
                job_id = exec_response.json()['job_id']
                print(f"✅ Test execution started: {job_id}")
                
                # Monitor for completion
                for i in range(12):  # Check for 2 minutes
                    time.sleep(10)
                    
                    status_response = requests.get(
                        f'https://your-api.com/agents/status/{job_id}',
                        headers={'X-Token': 'your_token_here'}
                    )
                    
                    if status_response.status_code == 200:
                        status = status_response.json()['status']
                        print(f"   Status check {i+1}: {status}")
                        
                        if status == 'completed':
                            print("✅ Test execution completed successfully")
                            break
                        elif status == 'failed':
                            error = status_response.json().get('error_message', 'Unknown error')
                            print(f"❌ Test execution failed: {error}")
                            break
                else:
                    print("❌ Test execution timed out")
            else:
                print(f"❌ Test execution failed to start: {exec_response.text}")

troubleshoot_execution_timeouts()
```

#### 3. Tool Permission Issues

**Problem**: Agents can't access requested tools

**Solutions**:

```python
def fix_tool_permissions(user_id, required_tools):
    """Fix tool permission issues for a user"""
    
    # Check current permissions
    current_tools_response = requests.get(
        'https://your-api.com/agents/tools',
        headers={'X-Token': 'your_token_here'}
    )
    
    if current_tools_response.status_code == 200:
        current_tools = [tool['name'] for tool in current_tools_response.json()['tools']]
        print(f"Current tools: {current_tools}")
        
        missing_tools = [tool for tool in required_tools if tool not in current_tools]
        
        if missing_tools:
            print(f"Missing tools: {missing_tools}")
            
            # Generate SQL to grant access (admin would need to run this)
            print("\nSQL to grant tool access:")
            for tool in missing_tools:
                print(f"""
INSERT INTO user_tool_access (id, user_id, tool_name, is_enabled, granted_at)
VALUES (NEWID(), '{user_id}', '{tool}', 1, GETUTCDATE());
                """)
        else:
            print("✅ All required tools are available")
    else:
        print(f"❌ Failed to check tools: {current_tools_response.text}")

# Example usage
fix_tool_permissions('user-uuid-here', ['data_analysis', 'web_search', 'send_email'])
```

#### 4. Database Connection Issues

**Problem**: Database-related operations fail

**Solutions**:

```python
def test_database_connectivity():
    """Test database connectivity and schema"""
    
    try:
        from apis.utils.databaseService import DatabaseService
        
        # Test basic connection
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        # Test agent tables exist
        tables_to_check = [
            'agent_configurations',
            'agent_threads', 
            'agent_runs',
            'custom_agents',
            'agent_workflows'
        ]
        
        for table in tables_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"✅ Table {table}: {count} records")
            except Exception as e:
                print(f"❌ Table {table}: {str(e)}")
        
        # Test endpoints table has agent endpoints
        cursor.execute("SELECT COUNT(*) FROM endpoints WHERE endpoint_path LIKE '/agents%'")
        agent_endpoints = cursor.fetchone()[0]
        print(f"Agent endpoints in database: {agent_endpoints}")
        
        if agent_endpoints == 0:
            print("⚠️  No agent endpoints found. Run agent SQL scripts.")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database connectivity error: {str(e)}")
        print("   Check database configuration and ensure SQL scripts are run")

test_database_connectivity()
```

### Performance Optimization

#### 1. Reduce Agent Response Time

```python
def optimize_agent_performance():
    """Best practices for optimal agent performance"""
    
    optimization_tips = {
        "Instructions": [
            "Keep instructions concise and specific",
            "Avoid overly complex or contradictory requirements", 
            "Use clear, actionable language",
            "Limit instruction length to under 2000 characters"
        ],
        "Tools": [
            "Only include necessary tools for the task",
            "Prefer specialized tools over generic ones",
            "Limit tools to 5 or fewer per agent",
            "Test tool combinations for compatibility"
        ],
        "Model Selection": [
            "Use gpt-4o-mini for simple tasks to reduce costs",
            "Use gpt-4o for complex reasoning and analysis", 
            "Adjust temperature based on creativity needs",
            "Consider model-specific strengths"
        ],
        "Async Execution": [
            "Always use async execution for production",
            "Implement proper status polling with exponential backoff",
            "Use webhook notifications when possible",
            "Handle timeout scenarios gracefully"
        ]
    }
    
    for category, tips in optimization_tips.items():
        print(f"\n{category}:")
        for tip in tips:
            print(f"  • {tip}")
    
    # Example optimized agent configuration
    optimized_config = {
        "name": "Optimized Business Analyst",
        "instructions": """Analyze business data and provide actionable insights. 
        Focus on key metrics, trends, and specific recommendations. 
        Be concise and data-driven.""",
        "tools": ["data_analysis", "calculator"],  # Minimal necessary tools
        "model": "gpt-4o",
        "temperature": 0.5  # Balanced for accuracy and creativity
    }
    
    return optimized_config

optimized_config = optimize_agent_performance()
```

#### 2. Monitor System Performance

```python
def monitor_system_performance():
    """Monitor agent system performance metrics"""
    
    import time
    
    # Test response times
    start_time = time.time()
    
    response = requests.get(
        'https://your-api.com/agents/templates',
        headers={'X-Token': 'your_token_here'}
    )
    
    template_time = time.time() - start_time
    print(f"Template retrieval: {template_time:.2f}s")
    
    # Test agent creation time
    start_time = time.time()
    
    test_agent = {
        "name": "Performance Test Agent",
        "instructions": "Simple test agent",
        "tools": ["web_search"],
        "model": "gpt-4o"
    }
    
    response = requests.post(
        'https://your-api.com/agents/create',
        headers={
            'X-Token': 'your_token_here',
            'Content-Type': 'application/json'
        },
        json=test_agent
    )
    
    creation_time = time.time() - start_time
    print(f"Agent creation: {creation_time:.2f}s")
    
    if response.status_code == 200:
        agent_id = response.json()['agent_id']
        
        # Test execution startup time
        start_time = time.time()
        
        exec_response = requests.post(
            'https://your-api.com/agents/execute',
            headers={
                'X-Token': 'your_token_here',
                'Content-Type': 'application/json'
            },
            json={
                "agent_id": agent_id,
                "message": "Say hello",
                "tools": []
            }
        )
        
        execution_startup_time = time.time() - start_time
        print(f"Execution startup: {execution_startup_time:.2f}s")
        
        if exec_response.status_code == 200:
            job_id = exec_response.json()['job_id']
            print(f"Created performance test job: {job_id}")

monitor_system_performance()
```

---

## Conclusion

This comprehensive tutorial covers all aspects of the agentic API system, from basic usage to advanced customization. The system provides:

- **Enterprise-grade AI agents** with OpenAI SDK integration
- **Business-focused tools** for productivity and automation  
- **Flexible customization** through templates and custom agents
- **Scalable architecture** with async execution and workflows
- **Comprehensive monitoring** and usage tracking

### Next Steps

1. **Start Simple**: Begin with pre-built templates for common use cases
2. **Customize Gradually**: Extend templates with custom instructions and tools
3. **Build Workflows**: Combine multiple agents for complex business processes
4. **Monitor and Optimize**: Use analytics to improve agent performance
5. **Scale Up**: Add custom tools and MCP server integrations as needed

The agentic API system is designed to grow with your organization's AI automation needs, providing a solid foundation for business productivity enhancement.