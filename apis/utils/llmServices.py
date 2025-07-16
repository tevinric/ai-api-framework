import logging
from openai import AzureOpenAI
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from apis.utils.config import (
    get_openai_client, 
    DEEPSEEK_API_KEY, 
    DEEPSEEK_V3_API_KEY, 
    LLAMA_API_KEY,
    O3_MINI_API_KEY,
    DEPLOYMENTS
    
)
import os
import tempfile
import base64
from apis.utils.fileService import FileService
import requests

# Configure logging
logger = logging.getLogger(__name__)



## CREATE THE CLIENTS FOR CONNECTING TO MODELS
### OPENAI
###### PRIMARY
def primary_openai_client():
    client = AzureOpenAI(
    azure_endpoint=DEPLOYMENTS["openai"]["primary"]["api_endpoint"],
    api_key=DEPLOYMENTS["openai"]["primary"]["api_key"],
    max_retries=0,
    api_version="2024-02-01",
)
    return client
###### SECONDARY
def secondary_openai_client():
    client = AzureOpenAI(
    azure_endpoint=DEPLOYMENTS["openai"]["secondary"]["api_endpoint"],
    api_key=DEPLOYMENTS["openai"]["secondary"]["api_key"],
    max_retries=0,
    api_version="2024-02-01",
)
    return client
###### TERTIARY
def tertiary_openai_client():
    client = AzureOpenAI(
    azure_endpoint=DEPLOYMENTS["openai"]["tertiary"]["api_endpoint"],
    api_key=DEPLOYMENTS["openai"]["tertiary"]["api_key"],
    api_version="2024-02-01",
    # NO max retries for final deployment
)
    return client

### INFERENCE CLIENTS


# Initialize CLIENTS
### OPENAI
primary_openai_client = primary_openai_client()
secondary_openai_client = secondary_openai_client()
tertiary_openai_client = tertiary_openai_client()


# For GPT-4o and GPT-4o-mini, only allow image formats
ALLOWED_IMAGE_EXTENSIONS = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg'
}

def deepseek_r1_service(system_prompt, user_input, temperature=0.5, json_output=False, max_tokens=2048):
    """DeepSeek-R1 LLM service function for chain of thought and deep reasoning with failover logic"""
    
    # DeepSeek-R1 client configurations with failover
    deepseek_clients = [
        {
            "name": "primary",
            "endpoint": os.environ.get("INFERENCE_ENDPOINT_PRIMARY"),
            "api_key": os.environ.get("INFERENCE_API_KEY_PRIMARY"),
            "model": "DeepSeek-R1-0528"
        },
        {
            "name": "secondary", 
            "endpoint": os.environ.get("INFERENCE_ENDPOINT_SECONDARY"),
            "api_key": os.environ.get("INFERENCE_API_KEY_SECONDARY"),
            "model": "DeepSeek-R1-0528"
        }
    ]
    
    last_error = None
    
    for client_config in deepseek_clients:
        try:
            logger.info(f"Attempting DeepSeek-R1 request using {client_config['name']} client")
            
            # Initialize Azure Inference client for this endpoint
            client = ChatCompletionsClient(
                endpoint=client_config['endpoint'],
                credential=AzureKeyCredential(client_config['api_key']),
                api_version="2024-05-01-preview"
            )
            
            # Prepare messages for the model using the new message types
            messages = []
            
            # Add system message if provided
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            
            # Add user message
            messages.append(UserMessage(content=user_input))
            
            # Prepare payload
            payload = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "model": client_config['model']
            }
            
            # Add response format if JSON output is requested
            if json_output:
                payload["response_format"] = {"type": "json_object"}
            
            # Make request to LLM
            response = client.complete(**payload)
            
            # Extract response data
            result = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            model_name = client_config['model']
            cached_tokens = 0  # Default to 0 as this model doesn't support cached tokens
            
            logger.info(f"DeepSeek-R1 request successful using {client_config['name']} client")
            
            return {
                "success": True,
                "result": result,
                "model": model_name,
                "client_used": client_config['name'],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cached_tokens": cached_tokens
            }
            
        except Exception as e:
            last_error = e
            logger.warning(f"DeepSeek-R1 API error with {client_config['name']} client: {str(e)}")
            
            # If this is not the last client, continue to next one
            if client_config['name'] != "tertiary":
                logger.info(f"Trying next client...")
                continue
    
    # All clients failed, return error
    logger.error(f"All DeepSeek-R1 clients failed. Final error: {str(last_error)}")
    return {
        "success": False,
        "error": str(last_error)
    }



    """OpenAI GPT-4o LLM service function for text completion and content generation with failover logic"""
    # Fixed deployment model
    DEPLOYMENT = 'gpt-4o'
    
    # List of clients to try in order
    clients = [
        ("primary", primary_openai_client),
        ("secondary", secondary_openai_client), 
        ("tertiary", tertiary_openai_client)
    ]
    
    last_error = None
    
    for client_name, client in clients:
        try:
            logger.info(f"Attempting GPT-4o request using {client_name} client")
            
            # Make request to LLM
            response = client.chat.completions.create(
                model=DEPLOYMENT,
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
            
            logger.info(f"GPT-4o request successful using {client_name} client")
            
            return {
                "success": True,
                "result": result,
                "model": DEPLOYMENT,
                "client_used": client_name,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cached_tokens": cached_tokens
            }
            
        except Exception as e:
            last_error = e
            logger.warning(f"GPT-4o API error with {client_name} client: {str(e)}")
            
            # If this is not the last client, continue to next one
            if client_name != "tertiary":
                logger.info(f"Trying next client...")
                continue
    
    # All clients failed, return error
    logger.error(f"All GPT-4o clients failed. Final error: {str(last_error)}")
    return {
        "success": False,
        "error": str(last_error)
    }

    """OpenAI GPT-4o-mini LLM service function for everyday text completion tasks"""
    try:
        # Fixed deployment model
        DEPLOYMENT = 'gpt-4o-mini'
        
        # Make request to LLM
        response = openai_client.chat.completions.create(
            model=DEPLOYMENT,
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
            "model": DEPLOYMENT,
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

def deepseek_v3_service(system_prompt, user_input, temperature=0.7, json_output=False, max_tokens=1000):
    """DeepSeek-V3-0324 LLM service function for general task completion with failover logic"""
    
    # DeepSeek-V3-0324 client configurations with failover
    deepseek_clients = [
        {
            "name": "primary",
            "endpoint": os.environ.get("INFERENCE_ENDPOINT_PRIMARY"),
            "api_key": os.environ.get("INFERENCE_API_KEY_PRIMARY"),
            "model": "DeepSeek-V3-0324"
        },
        {
            "name": "secondary", 
            "endpoint": os.environ.get("INFERENCE_ENDPOINT_SECONDARY"),
            "api_key": os.environ.get("INFERENCE_API_KEY_SECONDARY"),
            "model": "DeepSeek-V3-0324"
        }
    ]
    
    last_error = None
    
    for client_config in deepseek_clients:
        try:
            logger.info(f"Attempting DeepSeek-V3-0324 request using {client_config['name']} client")
            
            # Initialize Azure Inference client for this endpoint
            client = ChatCompletionsClient(
                endpoint=client_config['endpoint'],
                credential=AzureKeyCredential(client_config['api_key']),
                api_version="2024-05-01-preview"
            )
            
            # Prepare messages for the model using the new message types
            messages = []
            
            # Add system message if provided
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            
            # Add user message
            messages.append(UserMessage(content=user_input))
            
            # Prepare payload
            payload = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "model": client_config['model']
            }
            
            # Add response format if JSON output is requested
            if json_output:
                payload["response_format"] = {"type": "json_object"}
            
            # Make request to LLM
            response = client.complete(**payload)
            
            # Extract response data
            result = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            model_name = client_config['model']
            cached_tokens = 0  # Default to 0 as this model doesn't support cached tokens
            
            logger.info(f"DeepSeek-V3-0324 request successful using {client_config['name']} client")
            
            return {
                "success": True,
                "result": result,
                "model": model_name,
                "client_used": client_config['name'],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cached_tokens": cached_tokens
            }
            
        except Exception as e:
            last_error = e
            logger.warning(f"DeepSeek-V3-0324 API error with {client_config['name']} client: {str(e)}")
            
            # If this is not the last client, continue to next one
            if client_config['name'] != "tertiary":
                logger.info(f"Trying next client...")
                continue
    
    # All clients failed, return error
    logger.error(f"All DeepSeek-V3-0324 clients failed. Final error: {str(last_error)}")
    return {
        "success": False,
        "error": str(last_error)
    }

def o1_mini_service(system_prompt, user_input, temperature=0.5, json_output=False):
    """OpenAI O1-mini LLM service function for complex tasks requiring reasoning"""
    try:
        # Fixed deployment model
        DEPLOYMENT = 'o1-mini'
        
        # o1-mini doesn't support 'system' role, so include system prompt in user message
        combined_input = f"{system_prompt}\n\nProvided text: {user_input}"
        
        # Make request to LLM
        response = openai_client.chat.completions.create(
            model=DEPLOYMENT,
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
            "model": DEPLOYMENT,
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

def o3_mini_service(system_prompt, user_input, max_completion_tokens=100000, reasoning_effort="medium", json_output=False):
    """O3-Mini LLM service function with variable reasoning effort"""
    try:
        # Fixed deployment information
        ENDPOINT = "https://ai-coe-services-dev.openai.azure.com/"
        DEPLOYMENT = "o3-mini"
        API_VERSION = "2024-12-01-preview"
        
        # Initialize Azure OpenAI client
        client = AzureOpenAI(
            azure_endpoint=ENDPOINT,
            api_key=O3_MINI_API_KEY,
            api_version=API_VERSION,
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
            model=DEPLOYMENT,
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
        model_name = DEPLOYMENT
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

def llama_service(system_prompt, user_input, temperature=0.7, json_output=False, max_tokens=2048, top_p=0.1, presence_penalty=0, frequency_penalty=0):
    """Meta Llama LLM service function for text generation with failover logic"""
    
    # Debug: Check environment variables
    primary_endpoint = os.environ.get("INFERENCE_ENDPOINT_PRIMARY")
    primary_key = os.environ.get("INFERENCE_API_KEY_PRIMARY")
    secondary_endpoint = os.environ.get("INFERENCE_ENDPOINT_SECONDARY") 
    secondary_key = os.environ.get("INFERENCE_API_KEY_SECONDARY")
    
    logger.info(f"Primary endpoint: {primary_endpoint}")
    logger.info(f"Secondary endpoint: {secondary_endpoint}")
    logger.info(f"Primary key exists: {bool(primary_key)}")
    logger.info(f"Secondary key exists: {bool(secondary_key)}")
    
    # Llama client configurations with failover
    llama_clients = [
        {
            "name": "primary",
            "endpoint": primary_endpoint,
            "api_key": primary_key,
            "model": "Meta-Llama-3.1-405B-Instruct"
        },
        {
            "name": "secondary", 
            "endpoint": secondary_endpoint,
            "api_key": secondary_key,
            "model": "Meta-Llama-3.1-405B-Instruct"
        }
    ]
    
    last_error = None
    
    for client_config in llama_clients:
        # Skip if endpoint or key is missing
        if not client_config['endpoint'] or not client_config['api_key']:
            logger.warning(f"Skipping {client_config['name']} client - missing endpoint or API key")
            continue
            
        try:
            logger.info(f"Attempting Llama request using {client_config['name']} client")
            logger.info(f"Endpoint: {client_config['endpoint']}")
            
            # Initialize Azure Inference client for this endpoint
            client = ChatCompletionsClient(
                endpoint=client_config['endpoint'],
                credential=AzureKeyCredential(client_config['api_key']),
                api_version="2024-05-01-preview"
            )
            
            # Prepare messages for the model using the correct message types
            messages = []
            
            # Add system message if provided
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            
            # Add user message
            messages.append(UserMessage(content=user_input))
            
            # Log the request details for debugging
            logger.info(f"Making request with model: {client_config['model']}")
            logger.info(f"Temperature: {temperature}, Max tokens: {max_tokens}")
            
            # Make request to LLM using individual parameters
            response = client.complete(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                model=client_config['model']
            )
            
            # Extract response data
            result = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            model_name = client_config['model']
            cached_tokens = response.usage.cached_tokens if hasattr(response.usage, 'cached_tokens') else 0
            
            logger.info(f"Llama request successful using {client_config['name']} client")
            
            return {
                "success": True,
                "result": result,
                "model": model_name,
                "client_used": client_config['name'],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cached_tokens": cached_tokens
            }
            
        except Exception as e:
            last_error = e
            error_message = str(e)
            logger.error(f"Llama API error with {client_config['name']} client: {error_message}")
            
            # Enhanced error logging
            if "Internal Server Error" in error_message:
                logger.error(f"Model service unavailable at endpoint: {client_config['endpoint']}")
                logger.error(f"This could indicate: 1) Endpoint is down, 2) Model not deployed, 3) Authentication issue")
            elif "401" in error_message or "Unauthorized" in error_message:
                logger.error(f"Authentication failed - check API key for {client_config['name']}")
            elif "404" in error_message:
                logger.error(f"Endpoint not found - check endpoint URL for {client_config['name']}")
            
            # If this is not the last client, continue to next one
            if client_config['name'] != "secondary":
                logger.info(f"Trying next client...")
                continue
    
    # All clients failed, return error
    logger.error(f"All Llama clients failed. Final error: {str(last_error)}")
    return {
        "success": False,
        "error": f"All Llama model endpoints are unavailable. Last error: {str(last_error)}"
    }

def gpt4o_service(system_prompt, user_input, temperature=0.5, json_output=False, file_ids=None, user_id=None):
    """OpenAI GPT-4o LLM service function for multimodal content generation with image file support"""
    # Fixed deployment model
    DEPLOYMENT = 'gpt-4o'
    temp_files = []  # Keep track of temporary files for cleanup
    
    # List of clients to try in order
    clients = [
        ("primary", primary_openai_client),
        ("secondary", secondary_openai_client), 
        ("tertiary", tertiary_openai_client)
    ]
    
    last_error = None
    
    try:
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
        
        # Try each client in sequence
        for client_name, client in clients:
            try:
                logger.info(f"Attempting GPT-4o multimodal request using {client_name} client")
                
                # Make the API call
                response = client.chat.completions.create(
                    model=DEPLOYMENT,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=4000,  # Add reasonable limit
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
                
                logger.info(f"GPT-4o multimodal request successful using {client_name} client")
                
                return {
                    "success": True,
                    "result": result,
                    "model": DEPLOYMENT,
                    "client_used": client_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cached_tokens": cached_tokens,
                    "files_processed": total_files_processed,
                    "file_processing_details": file_stats
                }
                
            except Exception as e:
                last_error = e
                
                # FUTURE work - overwrite the last_error message to show the user a more graceful error message
                
                
                logger.warning(f"GPT-4o multimodal API error with {client_name} client: {str(e)}")
                
                # If this is not the last client, continue to next one
                if client_name != "tertiary":
                    logger.info(f"Trying next client...")
                    continue
        
        # All clients failed, return error
        logger.error(f"All GPT-4o multimodal clients failed. Final error: {str(last_error)}")
        return {
            "success": False,
            "error": str(last_error)
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
        
def gpt4o_mini_service(system_prompt, user_input, temperature=0.5, json_output=False, file_ids=None, user_id=None):
    """OpenAI GPT-4o-mini LLM service function for multimodal content generation with image file support"""
    # Fixed deployment model
    DEPLOYMENT = 'gpt-4o-mini'
    temp_files = []  # Keep track of temporary files for cleanup
    
    # List of clients to try in order
    clients = [
        ("primary", primary_openai_client),
        ("secondary", secondary_openai_client), 
        ("tertiary", tertiary_openai_client)
    ]
    
    last_error = None
    
    try:
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
        
        # Try each client in sequence
        for client_name, client in clients:
            try:
                logger.info(f"Attempting GPT-4o-mini multimodal request using {client_name} client")
                
                # Make the API call
                response = client.chat.completions.create(
                    model=DEPLOYMENT,
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
                
                logger.info(f"GPT-4o-mini multimodal request successful using {client_name} client")
                
                return {
                    "success": True,
                    "result": result,
                    "model": DEPLOYMENT,
                    "client_used": client_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cached_tokens": cached_tokens,
                    "files_processed": total_files_processed,
                    "file_processing_details": file_stats
                }
                
            except Exception as e:
                last_error = e
                
                # FUTURE work - overwrite the last_error message to show the user a more graceful error message
                
                
                logger.warning(f"GPT-4o-mini multimodal API error with {client_name} client: {str(e)}")
                
                # If this is not the last client, continue to next one
                if client_name != "tertiary":
                    logger.info(f"Trying next client...")
                    continue
        
        # All clients failed, return error
        logger.error(f"All GPT-4o-mini multimodal clients failed. Final error: {str(last_error)}")
        return {
            "success": False,
            "error": str(last_error)
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

def gpt41_service(system_prompt, user_input, temperature=0.5, json_output=False, file_ids=None, user_id=None):
    """OpenAI GPT-4.1 LLM service function for multimodal content generation with image file support"""
    # Fixed deployment model
    DEPLOYMENT = 'gpt-4.1'
    temp_files = []  # Keep track of temporary files for cleanup
    
    # List of clients to try in order
    clients = [
        ("primary", primary_openai_client),
        ("secondary", secondary_openai_client), 
        ("tertiary", tertiary_openai_client)
    ]
    
    last_error = None
    
    try:
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
        
        # GPT-4.1 context window is approximately 128k tokens
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
        
        # Try each client in sequence
        for client_name, client in clients:
            try:
                logger.info(f"Attempting GPT-4.1 multimodal request using {client_name} client")
                
                # Make the API call
                response = client.chat.completions.create(
                    model=DEPLOYMENT,
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
                
                logger.info(f"GPT-4.1 multimodal request successful using {client_name} client")
                
                return {
                    "success": True,
                    "result": result,
                    "model": DEPLOYMENT,
                    "client_used": client_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cached_tokens": cached_tokens,
                    "files_processed": total_files_processed,
                    "file_processing_details": file_stats
                }
                
            except Exception as e:
                last_error = e
                
                # FUTURE work - overwrite the last_error message to show the user a more graceful error message
                
                
                logger.warning(f"GPT-4.1 multimodal API error with {client_name} client: {str(e)}")
                
                # If this is not the last client, continue to next one
                if client_name != "tertiary":
                    logger.info(f"Trying next client...")
                    continue
        
        # All clients failed, return error
        logger.error(f"All GPT-4.1 multimodal clients failed. Final error: {str(last_error)}")
        return {
            "success": False,
            "error": str(last_error)
        }
        
    except Exception as e:
        # Clean up temporary files in case of error
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass
                
        logger.error(f"GPT-4.1 Multimodal API error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def gpt41_mini_service(system_prompt, user_input, temperature=0.5, json_output=False, file_ids=None, user_id=None):
    """OpenAI GPT-4.1-mini LLM service function for multimodal content generation with image file support"""
    # Fixed deployment model
    DEPLOYMENT = 'gpt-4.1-mini'
    temp_files = []  # Keep track of temporary files for cleanup
    
    # List of clients to try in order
    clients = [
        ("primary", primary_openai_client),
        ("secondary", secondary_openai_client), 
        ("tertiary", tertiary_openai_client)
    ]
    
    last_error = None
    
    try:
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
        
        # GPT-4.1-mini context window is approximately 128k tokens, but be more conservative
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
        
        # Try each client in sequence
        for client_name, client in clients:
            try:
                logger.info(f"Attempting GPT-4.1-mini multimodal request using {client_name} client")
                
                # Make the API call
                response = client.chat.completions.create(
                    model=DEPLOYMENT,
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
                
                logger.info(f"GPT-4.1-mini multimodal request successful using {client_name} client")
                
                return {
                    "success": True,
                    "result": result,
                    "model": DEPLOYMENT,
                    "client_used": client_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cached_tokens": cached_tokens,
                    "files_processed": total_files_processed,
                    "file_processing_details": file_stats
                }
                
            except Exception as e:
                last_error = e
                
                # FUTURE work - overwrite the last_error message to show the user a more graceful error message
                
                
                logger.warning(f"GPT-4.1-mini multimodal API error with {client_name} client: {str(e)}")
                
                # If this is not the last client, continue to next one
                if client_name != "tertiary":
                    logger.info(f"Trying next client...")
                    continue
        
        # All clients failed, return error
        logger.error(f"All GPT-4.1-mini multimodal clients failed. Final error: {str(last_error)}")
        return {
            "success": False,
            "error": str(last_error)
        }
        
    except Exception as e:
        # Clean up temporary files in case of error
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass
                
        logger.error(f"GPT-4.1-mini Multimodal API error: {str(e)}")
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