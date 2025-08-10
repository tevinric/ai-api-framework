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
    max_retries=0,
    api_version="2024-02-01",
    # NO max retries for final deployment
)
    return client
###### FOURTH 
def fourth_openai_client():
    client = AzureOpenAI(
    azure_endpoint=DEPLOYMENTS["openai"]["fourth"]["api_endpoint"],
    api_key=DEPLOYMENTS["openai"]["fourth"]["api_key"],
    max_retries=0,
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
fourth_openai_client = fourth_openai_client() # Placeholder for fourth region client if needed


# DALLE3
def dalle3_service(prompt, size="1024x1024", quality="standard", style="vivid", deployment="dall-e-3"):
    """DALLE-3 image generation service function with failover logic
    
    Args:
        prompt (str): Text prompt describing the image to generate
        size (str): Output image size (1024x1024, 1792x1024, 1024x1792)
        quality (str): Image quality (standard, hd)
        style (str): Image generation style (vivid, natural)
        deployment (str): The DALLE-3 model deployment to use (dall-e-3, dalle3-hd)
    
    Returns:
        dict: Response containing success status, image data, and metadata
    """
    
    # DALLE-3 client configurations with failover
    dalle3_clients = [
        {
            "name": "primary", # EUS - Only primary client available
            "client": tertiary_openai_client,
            "deployment": deployment
        },
        # {
        #     "name": "secondary", 
        #     "client": secondary_openai_client,
        #     "deployment": deployment
        # },
        # {
        #     "name": "tertiary",
        #     "client": tertiary_openai_client, 
        #     "deployment": deployment
        # }
    ]
    
    last_error = None
    
    for client_config in dalle3_clients:
        try:
            logger.info(f"Attempting DALLE-3 image generation using {client_config['name']} client with quality: {quality}")
            
            # Make request to DALLE-3
            response = client_config['client'].images.generate(
                model=client_config['deployment'],
                prompt=prompt,
                n=1,  # Generate 1 image
                size=size,
                quality=quality,
                style=style,
                response_format="b64_json"  # Get base64 encoded image data
            )
            
            # Extract response data
            b64_image = response.data[0].b64_json
            prompt_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') and hasattr(response.usage, 'prompt_tokens') else 0
            
            logger.info(f"DALLE-3 image generation successful using {client_config['name']} client")
            
            return {
                "success": True,
                "b64_image": b64_image,
                "prompt_tokens": prompt_tokens,
                "model": client_config['deployment'],
                "client_used": client_config['name'],
                "quality": quality
            }
            
        except Exception as e:
            last_error = e
            logger.warning(f"DALLE-3 API error with {client_config['name']} client: {str(e)}")
            
            # If this is not the last client, continue to next one
            if client_config['name'] != "tertiary":
                logger.info(f"Trying next client...")
                continue
    
    # All clients failed, return error
    logger.error(f"All DALLE-3 clients failed. Final error: {str(last_error)}")
    return {
        "success": False,
        "error": str(last_error)
    }