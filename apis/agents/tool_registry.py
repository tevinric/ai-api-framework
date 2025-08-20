"""
Tool Registry for Agent System
Manages tools and MCP server connections for agents
"""

from typing import Dict, List, Optional, Any, Callable
import json
import logging
from dataclasses import dataclass
from enum import Enum
import importlib
import inspect
from apis.utils.databaseService import DatabaseService

logger = logging.getLogger(__name__)

class ToolType(Enum):
    """Types of tools available to agents"""
    FUNCTION = "function"
    MCP_SERVER = "mcp_server"
    API_ENDPOINT = "api_endpoint"
    CODE_INTERPRETER = "code_interpreter"
    FILE_SEARCH = "file_search"
    RETRIEVAL = "retrieval"

@dataclass
class ToolDefinition:
    """Definition of a tool available to agents"""
    name: str
    type: ToolType
    description: str
    parameters_schema: Dict[str, Any]
    function: Optional[Callable] = None
    endpoint_url: Optional[str] = None
    mcp_config: Optional[Dict[str, Any]] = None
    requires_auth: bool = False
    max_execution_time_ms: int = 30000
    category: str = "general"
    
    def to_openai_function(self) -> Dict[str, Any]:
        """Convert to OpenAI function format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }

class ToolRegistry:
    """Registry for managing agent tools and MCP servers"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.mcp_servers: Dict[str, Dict[str, Any]] = {}
        self._load_builtin_tools()
        self._load_custom_tools()
        
    def _load_builtin_tools(self):
        """Load built-in tools"""
        
        # Web Search Tool
        self.register_tool(ToolDefinition(
            name="web_search",
            type=ToolType.FUNCTION,
            description="Search the web for current information",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 5
                    }
                },
                "required": ["query"]
            },
            function=self._web_search_impl,
            category="information"
        ))
        
        # Database Query Tool
        self.register_tool(ToolDefinition(
            name="database_query",
            type=ToolType.FUNCTION,
            description="Query database for user-specific information",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["usage_stats", "file_history", "balance", "agent_history"],
                        "description": "Type of query to execute"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional filters for the query"
                    }
                },
                "required": ["query_type"]
            },
            function=self._database_query_impl,
            category="data",
            requires_auth=True
        ))
        
        # Calculator Tool
        self.register_tool(ToolDefinition(
            name="calculator",
            type=ToolType.FUNCTION,
            description="Perform mathematical calculations",
            parameters_schema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate"
                    }
                },
                "required": ["expression"]
            },
            function=self._calculator_impl,
            category="math"
        ))
        
        # Email Tool
        self.register_tool(ToolDefinition(
            name="send_email",
            type=ToolType.FUNCTION,
            description="Send an email notification",
            parameters_schema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content"
                    },
                    "attachments": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File IDs to attach"
                    }
                },
                "required": ["to", "subject", "body"]
            },
            function=self._send_email_impl,
            category="communication",
            requires_auth=True
        ))
        
        # Data Analysis Tool
        self.register_tool(ToolDefinition(
            name="data_analysis",
            type=ToolType.FUNCTION,
            description="Analyze data and generate insights",
            parameters_schema={
                "type": "object",
                "properties": {
                    "data_source": {
                        "type": "string",
                        "description": "File ID or data source"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["summary", "correlation", "trend", "anomaly"],
                        "description": "Type of analysis to perform"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Analysis-specific parameters"
                    }
                },
                "required": ["data_source", "analysis_type"]
            },
            function=self._data_analysis_impl,
            category="analytics",
            max_execution_time_ms=60000
        ))
        
        # Document Generator Tool
        self.register_tool(ToolDefinition(
            name="document_generator",
            type=ToolType.FUNCTION,
            description="Generate documents from templates",
            parameters_schema={
                "type": "object",
                "properties": {
                    "template_type": {
                        "type": "string",
                        "enum": ["report", "proposal", "invoice", "contract", "presentation"],
                        "description": "Type of document to generate"
                    },
                    "data": {
                        "type": "object",
                        "description": "Data to populate the template"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["pdf", "docx", "xlsx", "pptx"],
                        "description": "Output format",
                        "default": "pdf"
                    }
                },
                "required": ["template_type", "data"]
            },
            function=self._document_generator_impl,
            category="productivity"
        ))
        
        # Calendar Integration Tool
        self.register_tool(ToolDefinition(
            name="calendar_manager",
            type=ToolType.FUNCTION,
            description="Manage calendar events and scheduling",
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "update", "delete", "search", "check_availability"],
                        "description": "Calendar action to perform"
                    },
                    "event_data": {
                        "type": "object",
                        "description": "Event details"
                    }
                },
                "required": ["action"]
            },
            function=self._calendar_manager_impl,
            category="productivity",
            requires_auth=True
        ))
        
        # Task Management Tool
        self.register_tool(ToolDefinition(
            name="task_manager",
            type=ToolType.FUNCTION,
            description="Create and manage tasks and to-do lists",
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "update", "complete", "list", "prioritize"],
                        "description": "Task action to perform"
                    },
                    "task_data": {
                        "type": "object",
                        "description": "Task details"
                    }
                },
                "required": ["action"]
            },
            function=self._task_manager_impl,
            category="productivity"
        ))
    
    def _load_custom_tools(self):
        """Load custom tools from database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT tool_name, description, category, parameters_schema, 
                       requires_auth, max_execution_time_ms, tool_type, config
                FROM custom_tools WHERE is_enabled = 1
            """)
            
            tools = cursor.fetchall()
            for tool in tools:
                tool_def = ToolDefinition(
                    name=tool[0],
                    type=ToolType(tool[6]) if tool[6] else ToolType.FUNCTION,
                    description=tool[1],
                    category=tool[2],
                    parameters_schema=json.loads(tool[3]) if tool[3] else {},
                    requires_auth=bool(tool[4]),
                    max_execution_time_ms=tool[5] or 30000
                )
                
                # Load additional config for MCP servers
                if tool[6] == ToolType.MCP_SERVER.value and tool[7]:
                    tool_def.mcp_config = json.loads(tool[7])
                
                self.register_tool(tool_def)
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error loading custom tools: {str(e)}")
    
    def register_tool(self, tool: ToolDefinition):
        """Register a tool in the registry"""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def register_mcp_server(
        self,
        name: str,
        url: str,
        api_key: Optional[str] = None,
        capabilities: List[str] = None
    ):
        """Register an MCP server"""
        self.mcp_servers[name] = {
            "url": url,
            "api_key": api_key,
            "capabilities": capabilities or [],
            "tools": []
        }
        
        # Discover tools from MCP server
        self._discover_mcp_tools(name)
        
    def _discover_mcp_tools(self, server_name: str):
        """Discover available tools from an MCP server"""
        try:
            server = self.mcp_servers[server_name]
            # TODO: Implement MCP protocol to discover tools
            # This would make a request to the MCP server to get available tools
            logger.info(f"Discovering tools from MCP server: {server_name}")
            
        except Exception as e:
            logger.error(f"Error discovering MCP tools: {str(e)}")
    
    def get_tools_for_user(
        self,
        user_id: str,
        categories: Optional[List[str]] = None
    ) -> List[ToolDefinition]:
        """Get tools available to a specific user"""
        available_tools = []
        
        try:
            # Get user's tool permissions from database
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT tool_name FROM user_tool_access 
                WHERE user_id = ? AND is_enabled = 1
            """, [user_id])
            
            allowed_tools = {row[0] for row in cursor.fetchall()}
            cursor.close()
            conn.close()
            
            # Filter tools based on permissions and categories
            for tool_name, tool in self.tools.items():
                if tool_name in allowed_tools:
                    if not categories or tool.category in categories:
                        available_tools.append(tool)
            
        except Exception as e:
            logger.error(f"Error getting user tools: {str(e)}")
        
        return available_tools
    
    def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool with given parameters"""
        if tool_name not in self.tools:
            return {"error": f"Tool {tool_name} not found"}
        
        tool = self.tools[tool_name]
        
        try:
            if tool.type == ToolType.FUNCTION and tool.function:
                result = tool.function(parameters, context)
                return {"success": True, "result": result}
            
            elif tool.type == ToolType.MCP_SERVER:
                return self._execute_mcp_tool(tool, parameters, context)
            
            elif tool.type == ToolType.API_ENDPOINT:
                return self._execute_api_tool(tool, parameters, context)
            
            else:
                return {"error": f"Tool type {tool.type} not implemented"}
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {"error": str(e)}
    
    # Tool Implementation Methods
    async def _web_search_impl(self, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Implementation of web search tool"""
        # TODO: Implement actual web search using Bing API or similar
        query = params.get("query")
        max_results = params.get("max_results", 5)
        
        # Placeholder implementation
        return {
            "results": [
                {
                    "title": f"Result for: {query}",
                    "snippet": "This is a placeholder search result",
                    "url": "https://example.com"
                }
            ]
        }
    
    async def _database_query_impl(self, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Implementation of database query tool"""
        query_type = params.get("query_type")
        user_id = context.get("user_id")
        
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        if query_type == "usage_stats":
            cursor.execute("""
                SELECT COUNT(*) as total_requests, 
                       SUM(total_tokens) as total_tokens,
                       AVG(total_tokens) as avg_tokens
                FROM user_usage 
                WHERE user_id = ?
            """, [user_id])
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return {
                "total_requests": result[0],
                "total_tokens": result[1],
                "avg_tokens": result[2]
            }
        
        # Add other query types as needed
        return {"error": f"Query type {query_type} not implemented"}
    
    async def _calculator_impl(self, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Implementation of calculator tool"""
        expression = params.get("expression")
        
        try:
            # Safe evaluation of mathematical expressions
            import ast
            import operator as op
            
            # Supported operators
            operators = {
                ast.Add: op.add,
                ast.Sub: op.sub,
                ast.Mult: op.mul,
                ast.Div: op.truediv,
                ast.Pow: op.pow,
                ast.USub: op.neg
            }
            
            def eval_expr(expr):
                return eval(compile(ast.parse(expr, mode='eval'), '', 'eval'))
            
            result = eval_expr(expression)
            return {"result": result, "expression": expression}
            
        except Exception as e:
            return {"error": f"Failed to evaluate expression: {str(e)}"}
    
    async def _send_email_impl(self, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Implementation of email sending tool"""
        # TODO: Implement actual email sending
        return {
            "status": "queued",
            "message": f"Email to {params['to']} queued for sending"
        }
    
    async def _data_analysis_impl(self, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Implementation of data analysis tool"""
        # TODO: Implement actual data analysis
        return {
            "analysis_type": params["analysis_type"],
            "status": "completed",
            "insights": ["Placeholder insight 1", "Placeholder insight 2"]
        }
    
    async def _document_generator_impl(self, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Implementation of document generation tool"""
        # TODO: Implement actual document generation
        return {
            "document_id": "doc_" + str(uuid.uuid4()),
            "format": params.get("format", "pdf"),
            "status": "generated"
        }
    
    async def _calendar_manager_impl(self, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Implementation of calendar management tool"""
        # TODO: Implement actual calendar integration
        action = params.get("action")
        return {
            "action": action,
            "status": "completed",
            "message": f"Calendar action {action} completed"
        }
    
    async def _task_manager_impl(self, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Implementation of task management tool"""
        # TODO: Implement actual task management
        action = params.get("action")
        return {
            "action": action,
            "status": "completed",
            "task_id": "task_" + str(uuid.uuid4())
        }
    
    def _execute_mcp_tool(
        self,
        tool: ToolDefinition,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool via MCP server"""
        # TODO: Implement MCP protocol execution
        return {"error": "MCP execution not yet implemented"}
    
    def _execute_api_tool(
        self,
        tool: ToolDefinition,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool via API endpoint"""
        # TODO: Implement API endpoint execution
        return {"error": "API execution not yet implemented"}

# Global registry instance
tool_registry = ToolRegistry()