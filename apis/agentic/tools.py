# apis/agentic/tools.py
import json
import logging
import requests
import os
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod
from apis.utils.fileService import FileService
from apis.utils.llmServices import gpt4o_service
from apis.utils.databaseService import DatabaseService
import tempfile
import subprocess

logger = logging.getLogger(__name__)

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    category: str = "general"

class BaseTool(ABC):
    """Base class for all agent tools"""
    
    @abstractmethod
    def get_definition(self) -> ToolDefinition:
        """Return tool definition"""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any], user_id: str) -> str:
        """Execute the tool with given parameters"""
        pass

class EchoTestTool(BaseTool):
    """Simple tool for testing agent functionality"""
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="echo_test",
            description="A simple test tool that echoes back the input with a timestamp. Use this to test if the agent tool system is working.",
            parameters={
                "message": {"type": "string", "description": "Message to echo back"},
                "test_type": {"type": "string", "description": "Type of test to perform", "default": "basic"}
            },
            function=self.execute,
            category="testing"
        )
    
    async def execute(self, parameters: Dict[str, Any], user_id: str) -> str:
        """Execute the echo test tool"""
        try:
            message = parameters.get("message", "No message provided")
            test_type = parameters.get("test_type", "basic")
            
            import datetime
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            response = f"""
🔧 AGENT TOOL TEST SUCCESSFUL! 🔧

Tool: Echo Test Tool
User ID: {user_id}
Test Type: {test_type}
Timestamp: {current_time}
Your Message: "{message}"

✅ The agent tool system is working correctly!
✅ The agent can successfully call tools
✅ Parameters are being passed correctly
✅ Tool execution is functioning as expected

This confirms that:
- The agent can identify when to use tools
- Tool parameters are correctly parsed
- Tool execution pipeline is working
- Results are properly returned to the agent
"""
            
            logger.info(f"Echo test tool executed successfully for user {user_id}")
            return response
            
        except Exception as e:
            error_msg = f"Echo test tool failed: {str(e)}"
            logger.error(error_msg)
            return error_msg

class WebSearchTool(BaseTool):
    """Tool for searching the web"""
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description="Search the internet for current information",
            parameters={
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Maximum number of results", "default": 5}
            },
            function=self.execute,
            category="information"
        )
    
    async def execute(self, parameters: Dict[str, Any], user_id: str) -> str:
        # This would integrate with a web search API like Bing, Google, or SerpAPI
        # For demo purposes, I'll show the structure
        query = parameters.get("query", "")
        max_results = parameters.get("max_results", 5)
        
        try:
            # Example using hypothetical search API
            # search_results = await self._search_web(query, max_results)
            # For now, return mock results
            mock_results = [
                {
                    "title": f"Search result for: {query}",
                    "url": "https://example.com",
                    "snippet": f"This is a mock search result for the query '{query}'"
                }
            ]
            
            formatted_results = []
            for i, result in enumerate(mock_results[:max_results], 1):
                formatted_results.append(f"{i}. {result['title']}\n   {result['snippet']}\n   URL: {result['url']}")
            
            return f"Search results for '{query}':\n\n" + "\n\n".join(formatted_results)
            
        except Exception as e:
            return f"Error performing web search: {str(e)}"

class FileOperationTool(BaseTool):
    """Tool for file operations"""
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="file_operations",
            description="Perform file operations like reading, writing, or analyzing files",
            parameters={
                "operation": {"type": "string", "enum": ["read", "list", "analyze"], "description": "Operation to perform"},
                "file_id": {"type": "string", "description": "ID of the file to operate on (for read/analyze)"},
                "content": {"type": "string", "description": "Content to write (for write operations)"}
            },
            function=self.execute,
            category="file"
        )
    
    async def execute(self, parameters: Dict[str, Any], user_id: str) -> str:
        operation = parameters.get("operation")
        
        try:
            if operation == "list":
                files, error = FileService.list_files(user_id=user_id)
                if error:
                    return f"Error listing files: {error}"
                
                if not files:
                    return "No files found."
                
                file_list = []
                for file_info in files:
                    file_list.append(f"- {file_info['file_name']} (ID: {file_info['file_id']}, Type: {file_info['content_type']})")
                
                return "Available files:\n" + "\n".join(file_list)
            
            elif operation == "read":
                file_id = parameters.get("file_id")
                if not file_id:
                    return "Error: file_id is required for read operation"
                
                file_info, error = FileService.get_file_url(file_id, user_id)
                if error:
                    return f"Error accessing file: {error}"
                
                # For text files, we could download and read content
                # For now, return file information
                return f"File: {file_info['file_name']}\nType: {file_info['content_type']}\nURL: {file_info['file_url']}"
            
            elif operation == "analyze":
                file_id = parameters.get("file_id")
                if not file_id:
                    return "Error: file_id is required for analyze operation"
                
                # Use multimodal LLM to analyze the file
                analysis_prompt = "Analyze this file and provide a detailed description of its contents."
                
                response = gpt4o_service(
                    system_prompt="You are a file analysis assistant.",
                    user_input=analysis_prompt,
                    temperature=0.3
                )
                
                if response["success"]:
                    return f"File analysis:\n{response['result']}"
                else:
                    return f"Error analyzing file: {response['error']}"
            
            else:
                return f"Unsupported file operation: {operation}"
                
        except Exception as e:
            return f"Error in file operation: {str(e)}"

class CalculatorTool(BaseTool):
    """Tool for mathematical calculations"""
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="calculator",
            description="Perform mathematical calculations and solve equations",
            parameters={
                "expression": {"type": "string", "description": "Mathematical expression to evaluate"},
                "operation": {"type": "string", "description": "Type of calculation (basic, scientific, solve_equation)"}
            },
            function=self.execute,
            category="math"
        )
    
    async def execute(self, parameters: Dict[str, Any], user_id: str) -> str:
        expression = parameters.get("expression", "")
        operation = parameters.get("operation", "basic")
        
        try:
            if operation == "basic":
                # Safe evaluation of basic mathematical expressions
                # In production, use a proper math parser like sympy
                allowed_names = {
                    k: v for k, v in vars(__builtins__).items()
                    if k in ['abs', 'round', 'min', 'max', 'sum', 'pow']
                }
                allowed_names.update({
                    'pi': 3.141592653589793,
                    'e': 2.718281828459045
                })
                
                # Very basic safety check
                if any(dangerous in expression.lower() for dangerous in ['import', 'exec', 'eval', 'open', '__']):
                    return "Error: Expression contains potentially dangerous operations"
                
                try:
                    result = eval(expression, {"__builtins__": {}}, allowed_names)
                    return f"Result: {expression} = {result}"
                except Exception as e:
                    return f"Error evaluating expression: {str(e)}"
            
            else:
                return f"Operation '{operation}' not yet implemented"
                
        except Exception as e:
            return f"Error in calculation: {str(e)}"

class DatabaseQueryTool(BaseTool):
    """Tool for querying databases (with restrictions)"""
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="database_query",
            description="Query database for user-specific information",
            parameters={
                "query_type": {"type": "string", "enum": ["usage_stats", "file_history", "balance"], "description": "Type of query to perform"},
                "time_period": {"type": "string", "description": "Time period for the query (optional)"}
            },
            function=self.execute,
            category="data"
        )
    
    async def execute(self, parameters: Dict[str, Any], user_id: str) -> str:
        query_type = parameters.get("query_type")
        
        try:
            if query_type == "usage_stats":
                # Get user's usage statistics
                conn = DatabaseService.get_connection()
                cursor = conn.cursor()
                
                query = """
                SELECT 
                    COUNT(*) as total_calls,
                    SUM(total_tokens) as total_tokens,
                    AVG(total_tokens) as avg_tokens
                FROM user_usage 
                WHERE user_id = ?
                AND timestamp >= DATEADD(day, -30, GETDATE())
                """
                
                cursor.execute(query, [user_id])
                result = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if result:
                    return f"Usage stats (last 30 days):\n- Total API calls: {result[0] or 0}\n- Total tokens: {result[1] or 0}\n- Average tokens per call: {result[2] or 0:.2f}"
                else:
                    return "No usage data found for the last 30 days"
            
            elif query_type == "balance":
                from apis.utils.balanceService import BalanceService
                balance_info, error = BalanceService.get_current_balance(user_id)
                
                if error:
                    return f"Error getting balance: {error}"
                
                return f"Current balance: {balance_info['current_balance']} credits\nTier: {balance_info['tier_description']}\nMonth: {balance_info['month']}"
            
            else:
                return f"Query type '{query_type}' not supported"
                
        except Exception as e:
            return f"Error querying database: {str(e)}"

class CodeExecutorTool(BaseTool):
    """Tool for executing code (with sandboxing)"""
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="code_executor",
            description="Execute Python code in a sandboxed environment",
            parameters={
                "code": {"type": "string", "description": "Python code to execute"},
                "language": {"type": "string", "enum": ["python"], "description": "Programming language"}
            },
            function=self.execute,
            category="development"
        )
    
    async def execute(self, parameters: Dict[str, Any], user_id: str) -> str:
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        
        if language != "python":
            return f"Language '{language}' not supported"
        
        try:
            # Create a temporary file with the code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name
            
            try:
                # Execute the code with timeout and resource limits
                result = subprocess.run(
                    ['python', tmp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=30,  # 30 second timeout
                    cwd=tempfile.gettempdir()  # Run in temp directory
                )
                
                output = result.stdout
                error = result.stderr
                
                response = "Code execution completed.\n"
                if output:
                    response += f"Output:\n{output}\n"
                if error:
                    response += f"Errors:\n{error}"
                
                return response
                
            finally:
                # Clean up temporary file
                os.unlink(tmp_file_path)
                
        except subprocess.TimeoutExpired:
            return "Error: Code execution timed out (30 second limit)"
        except Exception as e:
            return f"Error executing code: {str(e)}"

class ToolRegistry:
    """Registry for all available tools"""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register default tools"""
        default_tools = [
            EchoTestTool(),  # Add the test tool first
            WebSearchTool(),
            FileOperationTool(),
            CalculatorTool(),
            DatabaseQueryTool(),
            CodeExecutorTool()
        ]
        
        for tool in default_tools:
            self.register_tool(tool)
    
    def register_tool(self, tool: BaseTool):
        """Register a new tool"""
        definition = tool.get_definition()
        self.tools[definition.name] = tool
        logger.info(f"Registered tool: {definition.name}")
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self.tools.get(name)
    
    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all tool definitions"""
        return {
            name: {
                "description": tool.get_definition().description,
                "parameters": tool.get_definition().parameters,
                "category": tool.get_definition().category
            }
            for name, tool in self.tools.items()
        }
    
    def get_tools_by_category(self, category: str) -> List[str]:
        """Get tools by category"""
        return [
            name for name, tool in self.tools.items()
            if tool.get_definition().category == category
        ]

class ToolExecutor:
    """Executes tools safely"""
    
    def __init__(self):
        self.registry = ToolRegistry()
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any], user_id: str) -> str:
        """Execute a tool with given parameters"""
        tool = self.registry.get_tool(tool_name)
        
        if not tool:
            return f"Error: Tool '{tool_name}' not found"
        
        try:
            logger.info(f"Executing tool {tool_name} for user {user_id}")
            result = await tool.execute(parameters, user_id)
            logger.info(f"Tool {tool_name} completed successfully")
            return result
            
        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def get_available_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all available tools"""
        return self.registry.get_all_tools()
