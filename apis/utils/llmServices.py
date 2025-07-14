import logging
from openai import AzureOpenAI, RateLimitError, APIError  # Added specific error imports
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from apis.utils.config import (
    get_openai_client, 
    DEEPSEEK_API_KEY, 
    DEEPSEEK_V3_API_KEY, 
    LLAMA_API_KEY,
    O3_MINI_API_KEY
)
import os
import tempfile
import base64
from apis.utils.fileService import FileService
import requests

# Configure logging
logger = logging.getLogger(__name__)

# For GPT-4o and GPT-4o-mini, only allow image formats
ALLOWED_IMAGE_EXTENSIONS = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg'
}

def get_azure_openai_client(deployment_config=None):
    """
    Get Azure OpenAI client with deployment configuration support and fast-fail setup.
    
    Args:
        deployment_config (dict, optional): Deployment configuration with endpoint, api_key, etc.
        
    Returns:
        AzureOpenAI: Configured client with fast-fail settings
    """
    if deployment_config:
        return AzureOpenAI(
            azure_endpoint=deployment_config.get("endpoint"),
            api_key=deployment_config.get("api_key"),
            api_version=deployment_config.get("api_version", "2024-02-01"),
            timeout=30,  # 30 second timeout for fast failover
            max_retries=0  # Disable automatic retries for immediate failover
        )
    else:
        # Fallback to default client with fast-fail settings
        from apis.utils.config import get_openai_client_fast_fail
        return get_openai_client_fast_fail()

def get_azure_inference_client(deployment_config):
    """
    Get Azure AI Inference client with deployment configuration.
    
    Args:
        deployment_config (dict): Deployment configuration with endpoint and api_key
        
    Returns:
        ChatCompletionsClient: Configured client
    """
    return ChatCompletionsClient(
        endpoint=deployment_config.get("endpoint"),
        credential=AzureKeyCredential(deployment_config.get("api_key"))
    )

def deepseek_r1_service(system_prompt, user_input, temperature=0.5, json_output=False, max_tokens=2048, deployment_config=None):
    """DeepSeek-R1 LLM service function for chain of thought and deep reasoning with failover support"""
    try:
        # Use deployment config if provided, otherwise use default
        if deployment_config:
            endpoint = deployment_config.get("endpoint")
            api_key = deployment_config.get("api_key")
        else:
            # Fallback to original configuration
            endpoint = 'https://deepseek-r1-aiapi.eastus.models.ai.azure.com'
            api_key = DEEPSEEK_API_KEY
        
        # Initialize Azure Inference client
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
        
        # Prepare messages for the model
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user message
        messages.append({"role": "user", "content": user_input})
        
        # Prepare payload
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        # Add response format if JSON output is requested
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        
        # Make request to LLM
        response = client.complete(payload)
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name = response.model if hasattr(response, 'model') else "deepseek-r1-aiapi"
        cached_tokens = 0  # Default to 0 as this model doesn't support cached tokens
        
        return {
            "success": True,
            "result": result,
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"DeepSeek-R1 API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def deepseek_v3_service(system_prompt, user_input, temperature=0.7, json_output=False, max_tokens=1000, deployment_config=None):
    """DeepSeek-V3 LLM service function for general task completion with failover support"""
    try:
        # Use deployment config if provided, otherwise use default
        if deployment_config:
            endpoint = deployment_config.get("endpoint")
            api_key = deployment_config.get("api_key")
            model_name = deployment_config.get("model_name", "DeepSeek-V3")
        else:
            # Fallback to original configuration
            endpoint = 'https://ai-coe-services-dev.services.ai.azure.com/models'
            api_key = DEEPSEEK_V3_API_KEY
            model_name = 'DeepSeek-V3'
        
        # Initialize Azure Inference client
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
        
        # Prepare messages for the model
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user message
        messages.append({"role": "user", "content": user_input})
        
        # Prepare payload
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "model": model_name
        }
        
        # Add response format if JSON output is requested
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        
        # Make request to LLM
        response = client.complete(payload)
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name_response = response.model if hasattr(response, 'model') else model_name
        cached_tokens = 0  # Default to 0 as this model doesn't support cached tokens
        
        return {
            "success": True,
            "result": result,
            "model": model_name_response,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"DeepSeek-V3 API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def gpt4o_service(system_prompt, user_input, temperature=0.5, json_output=False, deployment_config=None):
    """OpenAI GPT-4o LLM service function for text completion and content generation with fast-fail failover support"""
    try:
        # Use deployment config if provided, otherwise use default
        if deployment_config:
            client = get_azure_openai_client(deployment_config)
            deployment_name = deployment_config.get("deployment", "gpt-4o")
        else:
            # Fallback to original configuration with fast-fail settings
            client = get_azure_openai_client()
            deployment_name = 'gpt-4o'
        
        try:
            # Make request to LLM with fast-fail settings
            response = client.chat.completions.create(
                model=deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Provided text: {user_input}"}
                ],
                temperature=temperature,
                response_format={"type": "json_object"} if json_output else {"type": "text"},
                timeout=30  # 30 second timeout for fast failover
            )
            
        except RateLimitError as e:
            # Immediately return rate limit error for failover
            logger.warning(f"GPT-4o rate limit hit: {str(e)}")
            return {
                "success": False,
                "error": f"429 Rate limit exceeded: {str(e)}"
            }
        except APIError as e:
            # Handle other API errors that might be rate/quota related
            error_str = str(e).lower()
            if "429" in error_str or "rate limit" in error_str or "quota" in error_str or "too many requests" in error_str:
                logger.warning(f"GPT-4o quota/rate error: {str(e)}")
                return {
                    "success": False,
                    "error": f"429 Rate limit or quota exceeded: {str(e)}"
                }
            else:
                logger.error(f"GPT-4o API error: {str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        return {
            "success": True,
            "result": result,
            "model": deployment_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"GPT-4o API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def gpt4o_mini_service(system_prompt, user_input, temperature=0.5, json_output=False, deployment_config=None):
    """OpenAI GPT-4o-mini LLM service function for everyday text completion tasks with failover support"""
    try:
        # Use deployment config if provided, otherwise use default
        if deployment_config:
            client = get_azure_openai_client(deployment_config)
            deployment_name = deployment_config.get("deployment", "gpt-4o-mini")
        else:
            # Fallback to original configuration
            client = get_openai_client()
            deployment_name = 'gpt-4o-mini'
        
        # Make request to LLM
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Provided text: {user_input}"}
            ],
            temperature=temperature,
            response_format={"type": "json_object"} if json_output else {"type": "text"}
        )
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        return {
            "success": True,
            "result": result,
            "model": deployment_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"GPT-4o-mini API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def o1_mini_service(system_prompt, user_input, temperature=0.5, json_output=False, deployment_config=None):
    """OpenAI O1-mini LLM service function for complex tasks requiring reasoning with failover support"""
    try:
        # Use deployment config if provided, otherwise use default
        if deployment_config:
            client = get_azure_openai_client(deployment_config)
            deployment_name = deployment_config.get("deployment", "o1-mini")
        else:
            # Fallback to original configuration
            client = get_openai_client()
            deployment_name = 'o1-mini'
        
        # o1-mini doesn't support 'system' role, so include system prompt in user message
        combined_input = f"{system_prompt}\n\nProvided text: {user_input}"
        
        # Make request to LLM
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "user", "content": combined_input}
            ],
            response_format={"type": "json_object"} if json_output else {"type": "text"}
        )
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        return {
            "success": True,
            "result": result,
            "model": deployment_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"O1-mini API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def o3_mini_service(system_prompt, user_input, max_completion_tokens=100000, reasoning_effort="medium", json_output=False, deployment_config=None):
    """O3-Mini LLM service function with variable reasoning effort and failover support"""
    try:
        # Use deployment config if provided, otherwise use default
        if deployment_config:
            endpoint = deployment_config.get("endpoint")
            api_key = deployment_config.get("api_key")
            api_version = deployment_config.get("api_version", "2024-12-01-preview")
            deployment_name = deployment_config.get("deployment", "o3-mini")
        else:
            # Fallback to original configuration
            endpoint = "https://ai-coe-services-dev.openai.azure.com/"
            api_key = O3_MINI_API_KEY
            api_version = "2024-12-01-preview"
            deployment_name = "o3-mini"
        
        # Initialize Azure OpenAI client
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        
        # Prepare messages for the model
        chat_prompt = [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "text",
                        "text": system_prompt
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_input
                    }
                ]
            }
        ]
        
        # Prepare additional parameters
        additional_params = {
            "max_completion_tokens": max_completion_tokens,
            "reasoning_effort": reasoning_effort
        }
        
        # Add response format if JSON output is requested
        if json_output:
            additional_params["response_format"] = {"type": "json_object"}
        
        # Make request to LLM
        completion = client.chat.completions.create(
            model=deployment_name,
            messages=chat_prompt,
            **additional_params,
            stop=None,
            stream=False
        )
        
        # Extract response data
        result = completion.choices[0].message.content
        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
        total_tokens = prompt_tokens + completion_tokens
        model_name = deployment_name
        cached_tokens = completion.usage.cached_tokens if hasattr(completion.usage, 'cached_tokens') else 0
        
        return {
            "success": True,
            "result": result,
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"O3-Mini API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def llama_service(system_prompt, user_input, temperature=0.8, json_output=False, max_tokens=2048, top_p=0.1, presence_penalty=0, frequency_penalty=0, deployment_config=None):
    """Meta Llama LLM service function for text generation with failover support"""
    try:
        # Use deployment config if provided, otherwise use default
        if deployment_config:
            endpoint = deployment_config.get("endpoint")
            api_key = deployment_config.get("api_key")
        else:
            # Fallback to original configuration
            endpoint = 'https://Meta-Llama-3-1-405B-aiapis.eastus.models.ai.azure.com'
            api_key = LLAMA_API_KEY
        
        # Initialize Azure Inference client
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
        
        # Prepare messages for the model
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user message
        messages.append({"role": "user", "content": user_input})
        
        # Prepare payload
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty
        }
        
        # Add response format if JSON output is requested
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        
        # Make request to LLM
        response = client.complete(payload)
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name = "llama-3-1-405b"
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        return {
            "success": True,
            "result": result,
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens
        }
        
    except Exception as e:
        logger.error(f"Llama API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# Helper functions for image validation
def is_image_file_for_multimodal(filename, content_type):
    """Check if the file is a supported image for GPT-4o/4o-mini multimodal"""
    # Check by filename extension
    if '.' in filename:
        ext = filename.rsplit('.', 1)[1].lower()
        if ext in ALLOWED_IMAGE_EXTENSIONS:
            return True
    
    # Check by content type
    if content_type and content_type.startswith('image/'):
        # Extract format from MIME type
        if content_type in ALLOWED_IMAGE_EXTENSIONS.values():
            return True
    
    return False

def gpt4o_multimodal_service(system_prompt, user_input, temperature=0.5, json_output=False, file_ids=None, user_id=None, deployment_config=None):
    """OpenAI GPT-4o LLM service function for multimodal content generation with image file support and fast-fail failover"""
    try:
        # Use deployment config if provided, otherwise use default
        if deployment_config:
            client = get_azure_openai_client(deployment_config)
            deployment_name = deployment_config.get("deployment", "gpt-4o")
        else:
            # Fallback to original configuration with fast-fail settings
            client = get_azure_openai_client()
            deployment_name = 'gpt-4o'
        
        temp_files = []  # Keep track of temporary files for cleanup
        
        # Track file processing statistics
        file_stats = {
            "images_processed": 0
        }
        
        # Prepare message content
        message_content = []
        
        # First add the user's input text
        message_content.append({
            "type": "text", 
            "text": user_input
        })
        
        # Process file_ids if any
        if file_ids and isinstance(file_ids, list) and len(file_ids) > 0:
            unsupported_files = []
            
            for file_id in file_ids:
                # Get file details using FileService
                file_info, error = FileService.get_file_url(file_id, user_id)
                
                if error:
                    logger.error(f"Error retrieving file {file_id}: {error}")
                    continue
                
                # Check if we have the necessary file information
                if not file_info or 'file_url' not in file_info or 'content_type' not in file_info:
                    logger.error(f"Incomplete file information for file {file_id}")
                    continue
                
                file_url = file_info['file_url']
                content_type = file_info['content_type']
                file_name = file_info.get('file_name', f"file_{file_id}")
                
                # Check if file is a supported image format
                if not is_image_file_for_multimodal(file_name, content_type):
                    unsupported_files.append(file_name)
                    logger.warning(f"Unsupported file format: {file_name} ({content_type})")
                    continue
                
                try:
                    # Create a temporary file to store the downloaded content
                    fd, temp_path = tempfile.mkstemp(suffix=f'.{file_name.rsplit(".", 1)[1].lower()}' if '.' in file_name else '')
                    temp_files.append(temp_path)
                    
                    # Download the file from Azure Blob Storage
                    response = requests.get(file_url)
                    response.raise_for_status()
                    
                    with os.fdopen(fd, 'wb') as tmp:
                        tmp.write(response.content)
                    
                    # Process as image
                    file_stats["images_processed"] += 1
                    
                    with open(temp_path, 'rb') as img_file:
                        base64_image = base64.b64encode(img_file.read()).decode('utf-8')
                    
                    # Add as image content
                    message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{base64_image}"
                        }
                    })
                        
                except requests.RequestException as e:
                    logger.error(f"Error downloading file {file_id}: {str(e)}")
                    message_content.append({
                        "type": "text",
                        "text": f"\n\nFailed to download file {file_name}: {str(e)}"
                    })
                except Exception as e:
                    logger.error(f"Error processing file {file_id}: {str(e)}")
                    message_content.append({
                        "type": "text",
                        "text": f"\n\nError processing file {file_name}: {str(e)}"
                    })
            
            # Add information about unsupported files
            if unsupported_files:
                unsupported_message = f"\n\nNote: The following files were not processed as they are not supported image formats (only PNG, JPG, JPEG are supported): {', '.join(unsupported_files)}"
                message_content.append({
                    "type": "text",
                    "text": unsupported_message
                })
        
        # Estimate token usage for context window check
        # Simple heuristic: each image ≈ 765 tokens, text ≈ 1 token per 4 characters
        estimated_tokens = 0
        text_tokens = len(user_input + system_prompt) // 4
        image_tokens = file_stats["images_processed"] * 765  # OpenAI's estimate for image tokens
        estimated_tokens = text_tokens + image_tokens
        
        # GPT-4o context window is approximately 128k tokens
        MAX_CONTEXT_TOKENS = 120000  # Conservative limit
        
        if estimated_tokens > MAX_CONTEXT_TOKENS:
            return {
                "success": False,
                "error": f"Request exceeds context window limit. Estimated {estimated_tokens} tokens, but maximum is {MAX_CONTEXT_TOKENS}. Please reduce the number of images or shorten your text prompt."
            }
        
        # Create the chat completion request
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_content}
        ]
        
        try:
            # Make the API call with fast-fail settings
            response = client.chat.completions.create(
                model=deployment_name,
                messages=messages,
                temperature=temperature,
                max_tokens=4000,  # Add reasonable limit
                response_format={"type": "json_object"} if json_output else {"type": "text"},
                timeout=30  # 30 second timeout for fast failover
            )
            
        except RateLimitError as e:
            # Immediately return rate limit error for failover
            logger.warning(f"GPT-4o Multimodal rate limit hit: {str(e)}")
            return {
                "success": False,
                "error": f"429 Rate limit exceeded: {str(e)}"
            }
        except APIError as e:
            # Handle other API errors that might be rate/quota related
            error_str = str(e).lower()
            if "429" in error_str or "rate limit" in error_str or "quota" in error_str or "too many requests" in error_str:
                logger.warning(f"GPT-4o Multimodal quota/rate error: {str(e)}")
                return {
                    "success": False,
                    "error": f"429 Rate limit or quota exceeded: {str(e)}"
                }
            else:
                logger.error(f"GPT-4o Multimodal API error: {str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        # Total files processed
        total_files_processed = file_stats["images_processed"]
        
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except Exception as e:
                logger.error(f"Error removing temporary file {temp_file}: {str(e)}")
        
        return {
            "success": True,
            "result": result,
            "model": deployment_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "files_processed": total_files_processed,
            "file_processing_details": file_stats
        }
        
    except Exception as e:
        # Clean up temporary files in case of error
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass
                
        logger.error(f"GPT-4o Multimodal API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def gpt4o_mini_multimodal_service(system_prompt, user_input, temperature=0.5, json_output=False, file_ids=None, user_id=None, deployment_config=None):
    """OpenAI GPT-4o-mini LLM service function for multimodal content generation with image file support and failover"""
    try:
        # Use deployment config if provided, otherwise use default
        if deployment_config:
            client = get_azure_openai_client(deployment_config)
            deployment_name = deployment_config.get("deployment", "gpt-4o-mini")
        else:
            # Fallback to original configuration
            client = get_openai_client()
            deployment_name = 'gpt-4o-mini'
        
        temp_files = []  # Keep track of temporary files for cleanup
        
        # Track file processing statistics
        file_stats = {
            "images_processed": 0
        }
        
        # Prepare message content
        message_content = []
        
        # First add the user's input text
        message_content.append({
            "type": "text", 
            "text": user_input
        })
        
        # Process file_ids if any
        if file_ids and isinstance(file_ids, list) and len(file_ids) > 0:
            unsupported_files = []
            
            for file_id in file_ids:
                # Get file details using FileService
                file_info, error = FileService.get_file_url(file_id, user_id)
                
                if error:
                    logger.error(f"Error retrieving file {file_id}: {error}")
                    continue
                
                # Check if we have the necessary file information
                if not file_info or 'file_url' not in file_info or 'content_type' not in file_info:
                    logger.error(f"Incomplete file information for file {file_id}")
                    continue
                
                file_url = file_info['file_url']
                content_type = file_info['content_type']
                file_name = file_info.get('file_name', f"file_{file_id}")
                
                # Check if file is a supported image format
                if not is_image_file_for_multimodal(file_name, content_type):
                    unsupported_files.append(file_name)
                    logger.warning(f"Unsupported file format: {file_name} ({content_type})")
                    continue
                
                try:
                    # Create a temporary file to store the downloaded content
                    fd, temp_path = tempfile.mkstemp(suffix=f'.{file_name.rsplit(".", 1)[1].lower()}' if '.' in file_name else '')
                    temp_files.append(temp_path)
                    
                    # Download the file from Azure Blob Storage
                    response = requests.get(file_url)
                    response.raise_for_status()
                    
                    with os.fdopen(fd, 'wb') as tmp:
                        tmp.write(response.content)
                    
                    # Process as image
                    file_stats["images_processed"] += 1
                    
                    with open(temp_path, 'rb') as img_file:
                        base64_image = base64.b64encode(img_file.read()).decode('utf-8')
                    
                    # Add as image content
                    message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{base64_image}"
                        }
                    })
                        
                except requests.RequestException as e:
                    logger.error(f"Error downloading file {file_id}: {str(e)}")
                    message_content.append({
                        "type": "text",
                        "text": f"\n\nFailed to download file {file_name}: {str(e)}"
                    })
                except Exception as e:
                    logger.error(f"Error processing file {file_id}: {str(e)}")
                    message_content.append({
                        "type": "text",
                        "text": f"\n\nError processing file {file_name}: {str(e)}"
                    })
            
            # Add information about unsupported files
            if unsupported_files:
                unsupported_message = f"\n\nNote: The following files were not processed as they are not supported image formats (only PNG, JPG, JPEG are supported): {', '.join(unsupported_files)}"
                message_content.append({
                    "type": "text",
                    "text": unsupported_message
                })
        
        # Estimate token usage for context window check
        # Simple heuristic: each image ≈ 765 tokens, text ≈ 1 token per 4 characters
        estimated_tokens = 0
        text_tokens = len(user_input + system_prompt) // 4
        image_tokens = file_stats["images_processed"] * 765  # OpenAI's estimate for image tokens
        estimated_tokens = text_tokens + image_tokens
        
        # GPT-4o-mini context window is approximately 128k tokens, but be more conservative
        MAX_CONTEXT_TOKENS = 100000  # Conservative limit for mini model
        
        if estimated_tokens > MAX_CONTEXT_TOKENS:
            return {
                "success": False,
                "error": f"Request exceeds context window limit. Estimated {estimated_tokens} tokens, but maximum is {MAX_CONTEXT_TOKENS}. Please reduce the number of images or shorten your text prompt."
            }
        
        # Create the chat completion request
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_content}
        ]
        
        # Make the API call
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"} if json_output else {"type": "text"}
        )
        
        # Extract response data
        result = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
        
        # Total files processed
        total_files_processed = file_stats["images_processed"]
        
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except Exception as e:
                logger.error(f"Error removing temporary file {temp_file}: {str(e)}")
        
        return {
            "success": True,
            "result": result,
            "model": deployment_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "files_processed": total_files_processed,
            "file_processing_details": file_stats
        }
        
    except Exception as e:
        # Clean up temporary files in case of error
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass
                
        logger.error(f"GPT-4o-mini Multimodal API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
