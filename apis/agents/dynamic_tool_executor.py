"""
Dynamic Tool Executor
Handles execution of custom tools created via API
"""

import json
import logging
import requests
import importlib
import tempfile
import sys
import os
import subprocess
import time
from typing import Dict, Any, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

class DynamicToolExecutor:
    """Executes custom tools dynamically based on their configuration"""
    
    def __init__(self, tool_config: Dict[str, Any]):
        self.tool_config = tool_config
        self.tool_name = tool_config['name']
        self.tool_type = tool_config['tool_type']
        self.implementation = tool_config['implementation']
        self.max_execution_time = tool_config.get('max_execution_time_ms', 30000) / 1000.0
        
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute the tool based on its type"""
        
        try:
            if self.tool_type == 'function':
                return await self._execute_function_tool(parameters, context)
            elif self.tool_type == 'api_endpoint':
                return await self._execute_api_tool(parameters, context)
            elif self.tool_type == 'webhook':
                return await self._execute_webhook_tool(parameters, context)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported tool type: {self.tool_type}"
                }
                
        except Exception as e:
            logger.error(f"Error executing tool {self.tool_name}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": self.tool_name
            }
    
    async def _execute_function_tool(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute a Python function tool"""
        
        try:
            code = self.implementation['code']
            function_name = self.implementation['function_name']
            
            # Create a safe execution environment
            safe_globals = {
                '__builtins__': {
                    # Safe built-ins only
                    'len': len,
                    'str': str,
                    'int': int,
                    'float': float,
                    'bool': bool,
                    'dict': dict,
                    'list': list,
                    'tuple': tuple,
                    'set': set,
                    'abs': abs,
                    'max': max,
                    'min': min,
                    'sum': sum,
                    'round': round,
                    'sorted': sorted,
                    'enumerate': enumerate,
                    'zip': zip,
                    'range': range,
                    'map': map,
                    'filter': filter,
                    'json': json,
                    'datetime': datetime,
                    'requests': requests,  # Allow HTTP requests
                    'print': print,  # For debugging
                },
                # Add useful modules
                'json': json,
                'datetime': datetime,
                'time': time,
                'requests': requests,
                'logger': logger,
                # Tool-specific context
                'parameters': parameters,
                'context': context,
                'tool_name': self.tool_name
            }
            
            # Execute the code in safe environment
            exec(code, safe_globals)
            
            # Get the function and execute it
            if function_name in safe_globals:
                func = safe_globals[function_name]
                
                # Call the function with parameters and context
                if callable(func):
                    result = func(parameters, context)
                    
                    return {
                        "success": True,
                        "result": result,
                        "tool_name": self.tool_name,
                        "execution_type": "function"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"'{function_name}' is not callable"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Function '{function_name}' not found in code"
                }
                
        except Exception as e:
            logger.error(f"Error executing function tool: {str(e)}")
            return {
                "success": False,
                "error": f"Function execution error: {str(e)}"
            }
    
    async def _execute_api_tool(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute an API endpoint tool"""
        
        try:
            url = self.implementation['url']
            method = self.implementation['method'].upper()
            headers = self.implementation.get('headers', {})
            auth = self.implementation.get('auth', {})
            
            # Prepare request parameters
            request_params = {
                'url': url,
                'method': method,
                'timeout': self.max_execution_time,
                'headers': headers
            }
            
            # Add authentication if specified
            if auth.get('type') == 'bearer':
                request_params['headers']['Authorization'] = f"Bearer {auth['token']}"
            elif auth.get('type') == 'api_key':
                key_name = auth.get('key_name', 'X-API-Key')
                request_params['headers'][key_name] = auth['api_key']
            elif auth.get('type') == 'basic':
                request_params['auth'] = (auth['username'], auth['password'])
            
            # Handle different HTTP methods
            if method in ['POST', 'PUT', 'PATCH']:
                content_type = headers.get('Content-Type', 'application/json')
                
                if content_type == 'application/json':
                    request_params['json'] = parameters
                elif content_type == 'application/x-www-form-urlencoded':
                    request_params['data'] = parameters
                else:
                    request_params['data'] = parameters
                    
            elif method == 'GET':
                request_params['params'] = parameters
            
            # Make the request
            response = requests.request(**request_params)
            
            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = response.text
            
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "data": response_data,
                "headers": dict(response.headers),
                "tool_name": self.tool_name,
                "execution_type": "api_endpoint"
            }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "API request timed out",
                "tool_name": self.tool_name
            }
        except Exception as e:
            logger.error(f"Error executing API tool: {str(e)}")
            return {
                "success": False,
                "error": f"API request error: {str(e)}"
            }
    
    async def _execute_webhook_tool(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute a webhook tool"""
        
        try:
            webhook_url = self.implementation['webhook_url']
            method = self.implementation.get('method', 'POST').upper()
            headers = self.implementation.get('headers', {'Content-Type': 'application/json'})
            
            # Prepare webhook payload
            webhook_payload = {
                'tool_name': self.tool_name,
                'parameters': parameters,
                'context': {
                    'user_id': context.get('user_id'),
                    'timestamp': datetime.utcnow().isoformat(),
                    'execution_id': context.get('correlation_id', 'unknown')
                },
                'callback_required': self.implementation.get('callback_required', False)
            }
            
            # Send webhook
            response = requests.post(
                webhook_url,
                json=webhook_payload,
                headers=headers,
                timeout=self.max_execution_time
            )
            
            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = response.text
            
            return {
                "success": response.status_code < 400,
                "webhook_status": response.status_code,
                "response": response_data,
                "tool_name": self.tool_name,
                "execution_type": "webhook"
            }
            
        except Exception as e:
            logger.error(f"Error executing webhook tool: {str(e)}")
            return {
                "success": False,
                "error": f"Webhook error: {str(e)}"
            }

class ToolCodeValidator:
    """Validates and sanitizes tool code for security"""
    
    FORBIDDEN_IMPORTS = [
        'os', 'sys', 'subprocess', 'importlib', 'exec', 'eval',
        'open', 'file', '__import__', 'compile', 'globals', 'locals',
        'vars', 'dir', 'help', 'input', 'raw_input'
    ]
    
    FORBIDDEN_FUNCTIONS = [
        'exec', 'eval', 'compile', '__import__', 'getattr', 'setattr',
        'delattr', 'hasattr', 'globals', 'locals', 'vars'
    ]
    
    @classmethod
    def validate_code(cls, code: str) -> Dict[str, Any]:
        """Validate tool code for security issues"""
        
        issues = []
        
        # Check for forbidden imports
        for forbidden in cls.FORBIDDEN_IMPORTS:
            if f'import {forbidden}' in code or f'from {forbidden}' in code:
                issues.append(f"Forbidden import: {forbidden}")
        
        # Check for forbidden functions
        for forbidden in cls.FORBIDDEN_FUNCTIONS:
            if forbidden in code:
                issues.append(f"Forbidden function: {forbidden}")
        
        # Check for file operations
        if any(term in code for term in ['open(', 'file(', 'with open']):
            issues.append("File operations are not allowed")
        
        # Check for system operations
        if any(term in code for term in ['os.', 'sys.', 'subprocess']):
            issues.append("System operations are not allowed")
        
        # Check code length (prevent extremely large code)
        if len(code) > 10000:  # 10KB limit
            issues.append("Code is too large (max 10KB)")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }

# Pre-built tool templates for common use cases
TOOL_TEMPLATES = {
    "http_request": {
        "name": "HTTP Request Tool",
        "description": "Make HTTP requests to external APIs",
        "tool_type": "function",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target URL"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                "headers": {"type": "object", "description": "Request headers"},
                "data": {"type": "object", "description": "Request data"}
            },
            "required": ["url"]
        },
        "implementation": {
            "code": '''
def http_request_tool(parameters, context):
    """Make HTTP requests with error handling"""
    import requests
    import json
    
    url = parameters.get('url')
    method = parameters.get('method', 'GET').upper()
    headers = parameters.get('headers', {})
    data = parameters.get('data')
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=30)
        elif method == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=30)
        elif method == 'PUT':
            response = requests.put(url, json=data, headers=headers, timeout=30)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=30)
        
        try:
            result_data = response.json()
        except:
            result_data = response.text
        
        return {
            "status_code": response.status_code,
            "success": response.status_code < 400,
            "data": result_data,
            "headers": dict(response.headers)
        }
        
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}
            ''',
            "function_name": "http_request_tool"
        }
    },
    
    "data_processor": {
        "name": "Data Processing Tool",
        "description": "Process and transform data",
        "tool_type": "function",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "data": {"type": "array", "description": "Data to process"},
                "operation": {"type": "string", "enum": ["sum", "average", "filter", "transform"]},
                "criteria": {"type": "object", "description": "Processing criteria"}
            },
            "required": ["data", "operation"]
        },
        "implementation": {
            "code": '''
def data_processor_tool(parameters, context):
    """Process data with various operations"""
    
    data = parameters.get('data', [])
    operation = parameters.get('operation')
    criteria = parameters.get('criteria', {})
    
    try:
        if operation == 'sum':
            if all(isinstance(x, (int, float)) for x in data):
                return {"result": sum(data), "count": len(data)}
            else:
                return {"error": "Sum operation requires numeric data"}
        
        elif operation == 'average':
            if all(isinstance(x, (int, float)) for x in data):
                avg = sum(data) / len(data) if data else 0
                return {"result": avg, "count": len(data)}
            else:
                return {"error": "Average operation requires numeric data"}
        
        elif operation == 'filter':
            filter_key = criteria.get('key')
            filter_value = criteria.get('value')
            
            if filter_key and filter_value is not None:
                filtered = [item for item in data if isinstance(item, dict) and item.get(filter_key) == filter_value]
                return {"result": filtered, "count": len(filtered)}
            else:
                return {"error": "Filter operation requires key and value in criteria"}
        
        elif operation == 'transform':
            transform_func = criteria.get('function')
            
            if transform_func == 'uppercase' and all(isinstance(x, str) for x in data):
                return {"result": [x.upper() for x in data]}
            elif transform_func == 'lowercase' and all(isinstance(x, str) for x in data):
                return {"result": [x.lower() for x in data]}
            else:
                return {"error": "Unsupported transform function"}
        
        else:
            return {"error": f"Unsupported operation: {operation}"}
            
    except Exception as e:
        return {"error": str(e)}
            ''',
            "function_name": "data_processor_tool"
        }
    },
    
    "text_analyzer": {
        "name": "Text Analysis Tool",
        "description": "Analyze text for various properties",
        "tool_type": "function",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to analyze"},
                "analysis_type": {"type": "string", "enum": ["word_count", "sentiment", "keywords", "summary"]}
            },
            "required": ["text", "analysis_type"]
        },
        "implementation": {
            "code": '''
def text_analyzer_tool(parameters, context):
    """Analyze text properties"""
    
    text = parameters.get('text', '')
    analysis_type = parameters.get('analysis_type')
    
    try:
        if analysis_type == 'word_count':
            words = text.split()
            chars = len(text)
            chars_no_spaces = len(text.replace(' ', ''))
            sentences = len([s for s in text.split('.') if s.strip()])
            
            return {
                "word_count": len(words),
                "character_count": chars,
                "character_count_no_spaces": chars_no_spaces,
                "sentence_count": sentences,
                "average_word_length": sum(len(word) for word in words) / len(words) if words else 0
            }
        
        elif analysis_type == 'keywords':
            words = text.lower().split()
            word_freq = {}
            
            # Simple word frequency (excluding common words)
            common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'can', 'may', 'might', 'must', 'shall'}
            
            for word in words:
                clean_word = ''.join(c for c in word if c.isalnum()).lower()
                if clean_word and len(clean_word) > 2 and clean_word not in common_words:
                    word_freq[clean_word] = word_freq.get(clean_word, 0) + 1
            
            # Get top keywords
            top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "top_keywords": [{"word": word, "frequency": freq} for word, freq in top_keywords],
                "total_unique_words": len(word_freq)
            }
        
        elif analysis_type == 'summary':
            sentences = [s.strip() for s in text.split('.') if s.strip()]
            words = text.split()
            
            # Simple extractive summary (first and longest sentences)
            if len(sentences) > 2:
                first_sentence = sentences[0]
                longest_sentence = max(sentences, key=len)
                summary = f"{first_sentence}. {longest_sentence}." if first_sentence != longest_sentence else first_sentence
            else:
                summary = text[:200] + "..." if len(text) > 200 else text
            
            return {
                "summary": summary,
                "original_length": len(text),
                "summary_length": len(summary),
                "compression_ratio": len(summary) / len(text) if text else 0
            }
        
        else:
            return {"error": f"Unsupported analysis type: {analysis_type}"}
            
    except Exception as e:
        return {"error": str(e)}
            ''',
            "function_name": "text_analyzer_tool"
        }
    }
}

def get_tool_template(template_name: str) -> Dict[str, Any]:
    """Get a pre-built tool template"""
    return TOOL_TEMPLATES.get(template_name)