# Agentic API System

A comprehensive AI agent ecosystem built with the OpenAI Agents SDK, designed for business productivity and automation.

## 🚀 Features

### Core Agent Capabilities
- **OpenAI Agents SDK Integration**: Full compatibility with OpenAI's assistant APIs
- **Azure OpenAI Backend**: Enterprise-grade AI with Azure's security and compliance
- **Async Execution**: KONG gateway-compatible async processing (under 60s timeout)
- **Usage Tracking**: Complete token usage monitoring and cost management
- **Tool Integration**: Extensible tool registry with business-focused tools
- **MCP Server Support**: Model Context Protocol server integration (future)

### Business-Focused Agents
- **Executive Assistant**: Calendar management, email drafting, task coordination
- **Financial Analyst**: Financial modeling, analysis, and reporting
- **Marketing Strategist**: Campaign planning, market research, content strategy
- **Operations Manager**: Process optimization, workflow management
- **HR Business Partner**: Talent management, organizational development
- **Sales Director**: Pipeline management, customer relationship building
- **Product Manager**: Roadmap planning, feature prioritization
- **Business Consultant**: Strategic analysis, transformation guidance
- **Legal Advisor**: Contract review, compliance support

### Advanced Features
- **Custom Agent Creation**: User-defined agents with template inheritance
- **Multi-Agent Workflows**: Sequential, parallel, and conditional agent chaining
- **Tool Registry**: Pluggable tool system with security controls
- **Template System**: Pre-built business agent templates
- **Real-time Status**: Job status tracking and webhook notifications

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Flask API     │────│  Agent Manager   │────│  Azure OpenAI   │
│   Routes        │    │                  │    │    Agents       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │
         │              ┌──────────────────┐    ┌─────────────────┐
         │              │ Async Executor   │────│  Job Service    │
         │              │                  │    │                 │
         │              └──────────────────┘    └─────────────────┘
         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Agent           │────│  Tool Registry   │────│  Business       │
│ Orchestrator    │    │                  │    │  Templates      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Database Schema

The system uses several key tables:
- `agent_configurations`: Store agent definitions and settings
- `agent_threads`: Conversation thread management
- `agent_runs`: Execution tracking and results
- `custom_agents`: User-created agent definitions
- `agent_workflows`: Multi-agent workflow configurations
- `custom_tools`: User-defined tool registry
- `user_tool_access`: Permission management

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- SQL Server database
- Azure OpenAI account
- Flask application setup

### Environment Variables
```bash
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Database Configuration
DB_SERVER=your_server
DB_DATABASE=your_database
DB_USERNAME=your_username
DB_PASSWORD=your_password

# Optional: KONG Configuration
KONG_TIMEOUT=60
```

### Installation Steps

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Database Schema**
   ```bash
   # Run the SQL initialization scripts
   sqlcmd -S your_server -d your_database -i sql_init/agentic_init.sql
   sqlcmd -S your_server -d your_database -i sql_init/agent_tables_extended.sql
   ```

3. **Run Tests**
   ```bash
   python test_agents.py
   ```

4. **Start the Application**
   ```bash
   python app.py
   ```

## 📚 API Documentation

### Core Endpoints

#### Create Agent
```http
POST /agents/create
```
Creates a new AI agent with specified instructions and tools.

**Request Body:**
```json
{
  "name": "My Business Assistant",
  "instructions": "You are a helpful business assistant...",
  "tools": ["web_search", "calculator", "send_email"],
  "model": "gpt-4o",
  "temperature": 0.7
}
```

#### Execute Agent (Async)
```http
POST /agents/execute
```
Executes an agent task asynchronously to comply with KONG timeout limits.

**Request Body:**
```json
{
  "agent_id": "asst_abc123",
  "message": "Analyze the Q3 sales data",
  "thread_id": "thread_xyz789", // optional
  "tools": ["data_analysis", "document_generator"],
  "webhook_url": "https://your-app.com/webhook" // optional
}
```

#### Check Job Status
```http
GET /agents/status/{job_id}
```
Returns the status and results of an async agent execution.

#### Create Custom Agent
```http
POST /agents/custom/create
```
Creates a custom agent using business templates as a foundation.

**Request Body:**
```json
{
  "name": "Sales Analytics Assistant",
  "description": "Analyzes sales performance and trends",
  "instructions": "Focus on identifying growth opportunities...",
  "base_template": "sales_director",
  "tools": ["data_analysis", "web_search"],
  "model": "gpt-4o"
}
```

#### Create Workflow
```http
POST /agents/workflow/create
```
Creates a multi-agent workflow for complex business processes.

### Available Tools

The system includes several business-focused tools:

- **web_search**: Internet search capabilities
- **database_query**: Query user-specific data
- **calculator**: Mathematical calculations
- **send_email**: Email notifications
- **data_analysis**: Data processing and insights
- **document_generator**: Create business documents
- **calendar_manager**: Schedule management
- **task_manager**: Task tracking and management

## 🎯 Usage Examples

### Example 1: Financial Analysis Agent

```python
# Create a financial analyst agent
response = requests.post('/agents/custom/create', json={
    "name": "Financial Analyst",
    "base_template": "financial_analyst",
    "instructions": "Focus on SaaS metrics and growth analysis"
})

agent_id = response.json()['agent_id']

# Execute analysis
job_response = requests.post('/agents/execute', json={
    "agent_id": agent_id,
    "message": "Analyze our MRR growth and churn rates for Q4",
    "tools": ["data_analysis", "calculator", "document_generator"]
})

job_id = job_response.json()['job_id']

# Check status
status = requests.get(f'/agents/status/{job_id}')
```

### Example 2: Multi-Agent Workflow

```python
# Create a market research workflow
workflow_response = requests.post('/agents/workflow/create', json={
    "name": "Market Research Workflow",
    "description": "Complete market analysis process",
    "flow_type": "sequential",
    "agents": [
        {"agent_id": "research_agent_id", "role": "Data Collection"},
        {"agent_id": "analyst_agent_id", "role": "Analysis"},
        {"agent_id": "writer_agent_id", "role": "Report Generation"}
    ]
})
```

### Example 3: Executive Dashboard Agent

```python
# Create executive assistant for daily briefings
response = requests.post('/agents/custom/create', json={
    "name": "Executive Briefing Assistant",
    "base_template": "executive_assistant", 
    "instructions": """
    Prepare daily executive briefings including:
    - Key metrics and KPIs
    - Priority tasks and meetings
    - Important market updates
    - Risk alerts and opportunities
    """,
    "tools": ["database_query", "web_search", "document_generator", "calendar_manager"]
})
```

## 🔧 Customization

### Creating Custom Tools

Add new tools to the registry:

```python
from apis.agents.tool_registry import tool_registry, ToolDefinition, ToolType

# Define custom tool
custom_tool = ToolDefinition(
    name="custom_analytics",
    type=ToolType.FUNCTION,
    description="Perform custom business analytics",
    parameters_schema={
        "type": "object",
        "properties": {
            "metric": {"type": "string"},
            "timeframe": {"type": "string"}
        }
    },
    function=custom_analytics_impl,
    category="analytics"
)

# Register the tool
tool_registry.register_tool(custom_tool)
```

### Creating Custom Agent Templates

Extend the business templates:

```python
from apis.agents.agent_orchestrator import agent_orchestrator

# Add new template
new_template = AgentTemplate(
    name="Custom Role",
    role=AgentRole.CUSTOM,
    description="Specialized business role",
    instructions="Your custom instructions...",
    default_tools=["tool1", "tool2"],
    model="gpt-4o"
)

agent_orchestrator.templates["custom_role"] = new_template
```

## 📊 Monitoring and Analytics

The system provides comprehensive analytics:

- **Agent Usage Metrics**: Track agent performance and adoption
- **Token Consumption**: Monitor costs and usage patterns  
- **Tool Usage Analytics**: Understand which tools are most valuable
- **Business Impact Metrics**: Measure productivity improvements

Access analytics through:
- Database views: `agent_usage_analytics`, `tool_usage_analytics`
- Stored procedures: `GetAgentAnalytics`, `GetAgentStatistics`
- API endpoints: `/agents/analytics/*`

## 🔒 Security & Compliance

### Security Features
- **RBAC Integration**: Role-based access control for all endpoints
- **Token Usage Tracking**: Complete audit trail of all API calls
- **Tool Permissions**: Granular control over tool access per user
- **Data Isolation**: User data segregation and privacy protection

### Compliance
- **Audit Logging**: Comprehensive logging of all agent interactions
- **Data Retention**: Configurable data retention policies
- **Privacy Controls**: GDPR-compliant data handling
- **Cost Management**: Built-in spending controls and alerts

## 🚀 Deployment

### Production Considerations

1. **Environment Setup**
   - Use environment-specific configuration
   - Set up proper logging and monitoring
   - Configure database connection pooling

2. **Scaling**
   - Consider horizontal scaling for async executors
   - Implement Redis for job queue management
   - Use load balancers for high availability

3. **Security**
   - Enable HTTPS for all endpoints
   - Implement API rate limiting
   - Use Azure Key Vault for secrets management

4. **Monitoring**
   - Set up Application Insights
   - Monitor token consumption and costs
   - Track agent performance metrics

## 🤝 Support

For technical support and questions:

1. Review the API documentation at `/apidocs/`
2. Check the test results with `python test_agents.py`
3. Review logs for debugging information
4. Consult the business templates for use case examples

## 📈 Future Roadmap

- **MCP Server Integration**: Full Model Context Protocol support
- **Advanced Workflows**: Conditional and parallel execution
- **Real-time Collaboration**: Multiple users working with same agents
- **Voice Integration**: Speech-to-text and text-to-speech capabilities
- **Mobile SDK**: Native mobile app integration
- **Advanced Analytics**: Machine learning-powered insights

---

Built with ❤️ for business productivity and AI automation.