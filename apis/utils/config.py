import os 
from openai import AzureOpenAI

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
        
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_ENDPOINT = os.environ.get("OPENAI_API_ENDPOINT")

DEEPSEEK_API_KEY=os.environ.get("DEEPSEEK_API_KEY")
LLAMA_API_KEY=os.environ.get("LLAMA_API_KEY")

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

# def get_openai_client():
#     """Get Azure OpenAI client with appropriate configuration"""
#     api_key = os.environ.get("AZURE_OPENAI_API_KEY")
#     azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
#     api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2023-07-01-preview")
    
#     if not api_key or not azure_endpoint:
#         logger.error("Azure OpenAI API key or endpoint not configured")
#         raise ValueError("Azure OpenAI API key and endpoint must be set in environment variables")
    
#     return AzureOpenAI(
#         api_key=api_key,  
#         api_version=api_version,
#         azure_endpoint=azure_endpoint
#     )

def get_azure_blob_client():
    """Get Azure Blob Storage client"""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        logger.error("Azure Storage connection string not found in environment variables")
        raise ValueError("Azure Storage connection string not found in environment variables")
    
    return BlobServiceClient.from_connection_string(connection_string)

# Azure Blob Storage configuration
FILE_UPLOADS_CONTAINER = os.environ.get("FILE_UPLOADS_CONTAINER")
IMAGE_GENERATION_CONTAINER = os.environ.get("IMAGE_GENERATION_CONTAINER")
STORAGE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT")

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
    Save image data to Azure Blob Storage and return the URL
    
    Args:
        image_data (bytes): The binary image data
        image_name (str): The name to give the image file in blob storage
        container_name (str): The container name to use
        
    Returns:
        str: The public URL to access the image
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
        
        # Generate the public URL for the blob
        blob_url = f"{BASE_BLOB_URL}/{image_name}"
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
    List all images in the blob container
    
    Args:
        container_name (str): The container name
        max_results (int): Maximum number of results to return
        
    Returns:
        list: List of image names and URLs
    """
    try:
        # Get blob service client
        blob_service_client = get_azure_blob_client()
        
        # Get container client
        container_client = blob_service_client.get_container_client(container_name)
        
        # List blobs
        blobs = container_client.list_blobs(max_results=max_results)
        
        # Create a list of image details
        image_list = []
        for blob in blobs:
            image_list.append({
                'name': blob.name,
                'url': f"{BASE_BLOB_URL}/{blob.name}",
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
