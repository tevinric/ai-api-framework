import os 
from openai import AzureOpenAI
from flask import jsonify, request, g, make_response

# MICROSOFT ENTRA CONFIGURATION 
class Config:
    CLIENT_ID = os.environ.get("ENTRA_APP_CLIENT_ID")
    CLIENT_SECRET = os.environ.get("ENTRA_APP_CLIENT_SECRET")
    TENANT_ID = os.environ.get("ENTRA_APP_TENANT_ID")
    

    # SET THE MS GRAPH API SCOPES
    GRAPH_SCOPES = [
        "https://graph.microsoft.com/.default" # REQUESTS ALL CONFIGURED PERMISSIONS ON THE APP REGISTRATION
    ]
    
    @staticmethod
    def validate():
        missing = []
        for attr in ['CLIENT_ID', 'CLIENT_SECRET', 'TENANT_ID']:
            if not getattr(Config, attr):
                missing.append(attr)
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
 

# DEPOLYMENT CONFIGURATION FOR ALL MODELS WITH DIFFERENT DEPLOYMENTS
DEPLOYMENTS = {
    "openai": {
        "primary": {
            #ZAR DEPLOYMENT
            "api_key": os.environ.get("OPENAI_API_KEY"),
            "api_endpoint": os.environ.get("OPENAI_API_ENDPOINT")
        },
        "secondary": {
            #WEST EUROPE DEPLOYMENT
            "api_key": os.environ.get("OPENAI_API_KEY_SECONDARY"),
            "api_endpoint": os.environ.get("OPENAI_API_ENDPOINT_SECONDARY")
        },
        "tertiary": {
            #EAST US DEPLOYMENT
            "api_key": os.environ.get("OPENAI_API_KEY_TERTIARY"),
            "api_endpoint": os.environ.get("OPENAI_API_ENDPOINT_TERTIARY")
        },
        "fourth": {
            #EAST US 2 REGION DEPLOYMENT
            "api_key": os.environ.get("OPENAI_API_KEY_FOURTH"),
            "api_endpoint": os.environ.get("OPENAI_API_ENDPOINT_FOURTH")
        }
    }
}


 
        
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_ENDPOINT = os.environ.get("OPENAI_API_ENDPOINT")

DEEPSEEK_API_KEY=os.environ.get("DEEPSEEK_API_KEY")
LLAMA_API_KEY=os.environ.get("LLAMA_API_KEY")
DEEPSEEK_V3_API_KEY= OPENAI_API_KEY
O3_MINI_API_KEY = OPENAI_API_KEY


STABLE_DIFFUSION_API_KEY = os.environ.get("STABLE_DIFFUSION_API_KEY")

def get_openai_client():
    client = AzureOpenAI(
    azure_endpoint=OPENAI_API_ENDPOINT,
    api_key=OPENAI_API_KEY,
    api_version="2024-02-01",
)
    return client

# apis/utils/config.py

import os
import logging
from azure.storage.blob import BlobServiceClient, ContentSettings
from openai import AzureOpenAI
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

# Configure logging
logger = logging.getLogger(__name__)

# Azure Blob Storage configuration
FILE_UPLOADS_CONTAINER = os.environ.get("FILE_UPLOADS_CONTAINER")
IMAGE_GENERATION_CONTAINER = os.environ.get("IMAGE_GENERATION_CONTAINER")
STORAGE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT")

# NEW: Alias domain configuration for security
BLOB_ALIAS_DOMAIN = os.environ.get("BLOB_ALIAS_DOMAIN")  # e.g., "files.yourdomain.com"

def get_aliased_blob_url(container_name, blob_name):
    """
    Generate aliased blob URL instead of direct Azure blob URL
    
    Args:
        container_name (str): The container name
        blob_name (str): The blob name
        
    Returns:
        str: Aliased URL if alias domain is configured, otherwise direct URL
    """
    # Add logging to debug
    logger.info(f"BLOB_ALIAS_DOMAIN: {BLOB_ALIAS_DOMAIN}")
    logger.info(f"STORAGE_ACCOUNT: {STORAGE_ACCOUNT}")
    
    if BLOB_ALIAS_DOMAIN:
        # Use alias domain
        aliased_url = f"https://{BLOB_ALIAS_DOMAIN}/{container_name}/{blob_name}"
        logger.info(f"Generated aliased URL: {aliased_url}")
        return aliased_url
    else:
        # Fallback to direct URL if alias not configured
        direct_url = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{container_name}/{blob_name}"
        logger.warning(f"No BLOB_ALIAS_DOMAIN configured, using direct URL: {direct_url}")
        return direct_url

def convert_direct_url_to_aliased(direct_url):
    """
    Convert direct Azure blob URL to aliased URL
    
    Args:
        direct_url (str): Direct Azure blob URL
        
    Returns:
        str: Aliased URL if alias domain is configured, otherwise original URL
    """
    if not BLOB_ALIAS_DOMAIN or not direct_url:
        return direct_url
    
    try:
        # Extract container and blob name from direct URL
        # Format: https://storageaccount.blob.core.windows.net/container/blob
        if f"{STORAGE_ACCOUNT}.blob.core.windows.net" in direct_url:
            # Split the URL to extract container and blob path
            url_parts = direct_url.split(f"{STORAGE_ACCOUNT}.blob.core.windows.net/", 1)
            if len(url_parts) == 2:
                container_and_blob = url_parts[1]
                # Split on first '/' to separate container from blob path
                if '/' in container_and_blob:
                    container_name, blob_path = container_and_blob.split('/', 1)
                    return f"https://{BLOB_ALIAS_DOMAIN}/{container_name}/{blob_path}"
        
        # If we can't parse it, return original URL
        return direct_url
    except Exception as e:
        logger.warning(f"Error converting URL to alias: {str(e)}")
        return direct_url

def get_azure_blob_client():
    """Get Azure Blob Storage client"""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        logger.error("Azure Storage connection string not found in environment variables")
        raise ValueError("Azure Storage connection string not found in environment variables")
    
    return BlobServiceClient.from_connection_string(connection_string)

def ensure_container_exists(container_name=IMAGE_GENERATION_CONTAINER):
    """
    Ensures that the specified blob container exists.
    Creates it with public access if it doesn't exist.
    """
    try:
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(container_name)
        
        # Check if container exists
        try:
            container_client.get_container_properties()
            logger.info(f"Container {container_name} already exists")
        except ResourceNotFoundError:
            # Create container with public access
            container_client.create_container(public_access="blob")
            logger.info(f"Container {container_name} created successfully with public access")
        
        return True
    except Exception as e:
        logger.error(f"Error ensuring container exists: {str(e)}")
        raise

def save_image_to_blob(image_data, image_name, container_name=IMAGE_GENERATION_CONTAINER):
    """
    Save image data to Azure Blob Storage and return the aliased URL
    
    Args:
        image_data (bytes): The binary image data
        image_name (str): The name to give the image file in blob storage
        container_name (str): The container name to use
        
    Returns:
        str: The aliased URL to access the image
    """
    try:
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        
        # Get container client
        container_client = blob_service_client.get_container_client(container_name)
        
        # Ensure container exists (will create if it doesn't)
        ensure_container_exists(container_name)
        
        # Set content settings for the blob (image)
        content_settings = ContentSettings(content_type='image/png')
        
        # Upload image to blob
        blob_client = container_client.get_blob_client(image_name)
        blob_client.upload_blob(image_data, overwrite=True, content_settings=content_settings)
        
        # Generate the aliased URL for the blob
        blob_url = get_aliased_blob_url(container_name, image_name)
        logger.info(f"Image saved successfully to {blob_url}")
        
        return blob_url
    
    except Exception as e:
        logger.error(f"Error saving image to blob storage: {str(e)}")
        raise Exception(f"Failed to save generated image: {str(e)}")

def delete_image_from_blob(image_name, container_name=IMAGE_GENERATION_CONTAINER):
    """
    Delete an image from Azure Blob Storage
    
    Args:
        image_name (str): The name of the image file in blob storage
        container_name (str): The container name
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        
        # Get container client
        container_client = blob_service_client.get_container_client(container_name)
        
        # Delete the blob
        blob_client = container_client.get_blob_client(image_name)
        blob_client.delete_blob()
        
        logger.info(f"Image {image_name} deleted successfully")
        return True
    
    except ResourceNotFoundError:
        logger.warning(f"Image {image_name} not found in container {container_name}")
        return False
    except Exception as e:
        logger.error(f"Error deleting image from blob storage: {str(e)}")
        return False

def list_blob_images(container_name=IMAGE_GENERATION_CONTAINER, max_results=100):
    """
    List all images in the blob container with aliased URLs
    
    Args:
        container_name (str): The container name
        max_results (int): Maximum number of results to return
        
    Returns:
        list: List of image names and aliased URLs
    """
    try:
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        
        # Get container client
        container_client = blob_service_client.get_container_client(container_name)
        
        # List blobs
        blobs = container_client.list_blobs(max_results=max_results)
        
        # Create a list of image details with aliased URLs
        image_list = []
        for blob in blobs:
            image_list.append({
                'name': blob.name,
                'url': get_aliased_blob_url(container_name, blob.name),
                'created_on': blob.creation_time,
                'size': blob.size
            })
        
        return image_list
    
    except Exception as e:
        logger.error(f"Error listing images in blob storage: {str(e)}")
        raise

def get_document_intelligence_config():
    """Get the Document Intelligence configuration"""
    return {
        'endpoint': os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"),
        'api_key': os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    }


def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    
    # Add correlation ID to response if available in g context
    correlation_id = getattr(g, 'correlation_id', None)
    if correlation_id:
        response.headers['X-Correlation-ID'] = correlation_id
        
    return response

def get_azure_openai_config():
    """
    Get Azure OpenAI configuration for agents
    
    Returns:
        Dictionary with Azure OpenAI configuration
    """
    return {
        'api_key': OPENAI_API_KEY,
        'endpoint': OPENAI_API_ENDPOINT,
        'api_version': os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
        'deployment_name': os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    }
