from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.utils.config import get_azure_blob_client, ensure_container_exists
import logging
import pytz
import os
import uuid
import tempfile
import shutil
from datetime import datetime
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    CSVLoader,
    UnstructuredExcelLoader
)
# Import LLM services directly
from apis.utils.llmServices import (
    gpt4o_service,
    gpt4o_mini_service,
    deepseek_r1_service,
    deepseek_v3_service,
    o1_mini_service,
    o3_mini_service,
    llama_service
)

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define container for vectorstores
VECTORSTORE_CONTAINER = "vectorstores"
STORAGE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT")
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{VECTORSTORE_CONTAINER}"

# Define available LLM models and their services
LLM_SERVICES = {
    'gpt-4o': gpt4o_service,
    'gpt-4o-mini': gpt4o_mini_service,
    'deepseek-r1': deepseek_r1_service,
    'deepseek-v3': deepseek_v3_service,
    'o1-mini': o1_mini_service,
    'o3-mini': o3_mini_service,
    'llama-3': llama_service,
}

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def update_vectorstore_access_timestamp(vectorstore_id):
    """Update the last_accessed timestamp for a vectorstore"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        # Update the last_accessed timestamp
        query = """
        UPDATE vectorstores
        SET last_accessed = DATEADD(HOUR, 2, GETUTCDATE())
        WHERE id = ?
        """
        
        cursor.execute(query, [vectorstore_id])
        conn.commit()
        
        cursor.close()
        conn.close()
        
        logger.info(f"Updated last_accessed timestamp for vectorstore {vectorstore_id}")
    except Exception as e:
        logger.error(f"Error updating last_accessed timestamp: {str(e)}")

def consume_git_policies_route():
    """
    Consume the Git policies vectorstore with a query - RAG-based conversational assistant
    ---
    tags:
      - RAG
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - query
          properties:
            query:
              type: string
              description: User query to answer using the git policies vectorstore
            system_prompt:
              type: string
              description: Custom system prompt to guide model behavior (optional)
            include_sources:
              type: boolean
              default: false 
              description: Whether to include source documents in the response
    produces:
      - application/json
    responses:
      200:
        description: Query answered successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Query processed successfully"
            answer:
              type: string
              example: "Based on the context, the answer to your question is..."
            model_used:
              type: string
              example: "gpt-4o"
            vectorstore_id:
              type: string
              example: "abc123456789"
            prompt_tokens:
              type: integer
              example: 125
            completion_tokens:
              type: integer
              example: 84
            total_tokens:
              type: integer
              example: 209
            sources:
              type: array
              items:
                type: string
              example: ["document1.pdf", "document2.docx"]
              description: Source documents used for the answer (only included if include_sources is true)
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Bad Request"
            message:
              type: string
              example: "Missing required field: query"
      401:
        description: Authentication error
      403:
        description: Forbidden
      404:
        description: Not found
      500:
        description: Server error
    """
    # Get token from X-Token header
    token = request.headers.get('X-Token')
    if not token:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing X-Token header"
        }, 401)
    
    # Validate token from database
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token - not found in database"
        }, 401)
    
    # Store token ID and user ID in g for logging and balance check
    g.token_id = token_details["id"]
    g.user_id = token_details["user_id"]
    
    # Check if token is expired
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    
    # Ensure expiration_time is timezone-aware
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get user details
    user_id = token_details["user_id"]
    user_details = DatabaseService.get_user_by_id(user_id)
    if not user_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "User associated with token not found"
        }, 401)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    if 'query' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: query"
        }, 400)
    
    # Extract parameters
    query = data.get('query')
    system_prompt = data.get('system_prompt', None)
    include_sources = data.get('include_sources', False)
    model = data.get('model', 'gpt-4o')  # Default to gpt-4o
    temperature = float(data.get('temperature', 0.15))
    
    # Validate model
    if model not in LLM_SERVICES:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Invalid model. Must be one of: {', '.join(LLM_SERVICES.keys())}"
        }, 400)
    
    # Set hardcoded parameters for git policies
    vectorstore_id = "f5e57660-79a7-4742-a240-c0fa6fc81b0d"
    
    try:
        # Check if vectorstore exists and user has access
        conn = None
        cursor = None
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Get vectorstore info
            query_db = """
            SELECT id, user_id, path, name
            FROM vectorstores 
            WHERE id = ?
            """
            
            cursor.execute(query_db, [vectorstore_id])
            vectorstore_info = cursor.fetchone()
            
            if not vectorstore_info:
                return create_api_response({
                    "error": "Not Found",
                    "message": f"Git policies vectorstore with ID {vectorstore_id} not found"
                }, 404)
            
            # Check if vectorstore belongs to user (or if admin)
            vs_user_id = vectorstore_info[1]
            if vs_user_id != user_id and user_details.get("scope", 1) != 0:  # Not owner and not admin
                return create_api_response({
                    "error": "Forbidden",
                    "message": "You don't have permission to access this vectorstore"
                }, 403)
            
            # Extract vectorstore info
            vectorstore_path = vectorstore_info[2]
            vectorstore_name = vectorstore_info[3]
            
        except Exception as e:
            logger.error(f"Error checking vectorstore: {str(e)}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error checking vectorstore: {str(e)}"
            }, 500)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        # Create temporary directory to download vectorstore
        temp_dir = tempfile.mkdtemp()
        local_vs_path = os.path.join(temp_dir, "vectorstore")
        os.makedirs(local_vs_path)
        
        try:
            # Download vectorstore from blob storage
            blob_service_client = get_azure_blob_client()
            container_client = blob_service_client.get_container_client(VECTORSTORE_CONTAINER)
            
            # Download all blobs with the vectorstore path prefix
            blobs = list(container_client.list_blobs(name_starts_with=vectorstore_path))
            if not blobs:
                return create_api_response({
                    "error": "Not Found",
                    "message": f"Git policies vectorstore files not found in storage for ID {vectorstore_id}"
                }, 404)
            
            # Download each blob
            for blob in blobs:
                # Get relative path from vectorstore_path
                rel_path = blob.name[len(vectorstore_path) + 1:] if blob.name.startswith(vectorstore_path + "/") else blob.name
                # Construct local path
                local_blob_path = os.path.join(local_vs_path, rel_path)
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(local_blob_path), exist_ok=True)
                
                # Download blob
                blob_client = container_client.get_blob_client(blob.name)
                with open(local_blob_path, "wb") as download_file:
                    download_file.write(blob_client.download_blob().readall())
            
            # Load the vectorstore
            try:
                # Initialize embeddings
                embeddings = AzureOpenAIEmbeddings(
                    azure_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
                    api_key=os.environ.get("OPENAI_API_KEY"),
                    azure_endpoint=os.environ.get("OPENAI_API_ENDPOINT")
                )
                
                # Load the vectorstore
                vectorstore = FAISS.load_local(
                    local_vs_path,
                    embeddings,
                    allow_dangerous_deserialization=True
                )
                
                logger.info(f"Successfully loaded git policies vectorstore {vectorstore_id}")
                
                # Perform vector search to get relevant documents
                docs = vectorstore.similarity_search(query, k=4)
                
                # Prepare context from retrieved documents
                context = "\n\n".join([doc.page_content for doc in docs])
                
                # Set default system prompt if not provided
                if not system_prompt:
                    system_prompt = """You are a Git policy assistant that answers questions based on the company's git policies and guidelines.
                    When answering, use only information from the provided context.
                    If the context doesn't contain the answer, say you don't know based on the available information.
                    Format your answers in a clear, concise manner and provide examples where appropriate.
                    Always maintain a helpful, informative tone."""
                
                # Prepare request for the LLM model
                user_input = f"Context: {context}\n\nQuestion: {query}\n\nAnswer the question based on the context provided."
                
                # Use LLM service directly instead of making an API call
                llm_service = LLM_SERVICES[model]
                
                # Special handling for o3-mini which uses different parameters
                if model == 'o3-mini':
                    service_response = llm_service(
                        system_prompt=system_prompt,
                        user_input=user_input,
                        reasoning_effort="medium" if temperature > 0.5 else "high"
                    )
                else:
                    service_response = llm_service(
                        system_prompt=system_prompt,
                        user_input=user_input,
                        temperature=temperature
                    )
                
                if not service_response["success"]:
                    logger.error(f"Error from LLM service: {service_response['error']}")
                    return create_api_response({
                        "error": "Server Error",
                        "message": f"Error from LLM service: {service_response['error']}"
                    }, 500)
                
                # Extract the response data
                answer = service_response["result"]
                
                # Extract token usage
                prompt_tokens = service_response.get("prompt_tokens", 0)
                completion_tokens = service_response.get("completion_tokens", 0)
                total_tokens = service_response.get("total_tokens", 0)
                cached_tokens = service_response.get("cached_tokens", 0)
                
                # Update the last_accessed timestamp
                update_vectorstore_access_timestamp(vectorstore_id)
                
                # Create the response
                response_data = {
                    "message": "Query processed successfully",
                    "answer": answer,
                    "model_used": model,
                    "vectorstore_id": vectorstore_id,
                    "vectorstore_name": vectorstore_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cached_tokens": cached_tokens
                }
                
                # Add source documents if requested
                if include_sources:
                    sources = []
                    for doc in docs:
                        if 'source' in doc.metadata:
                            sources.append(doc.metadata['source'])
                    response_data["sources"] = list(set(sources))  # Remove duplicates
                
                return create_api_response(response_data, 200)
                
            except Exception as e:
                logger.error(f"Error processing query with git policies vectorstore: {str(e)}")
                return create_api_response({
                    "error": "Server Error",
                    "message": f"Error processing query: {str(e)}"
                }, 500)
            
        except Exception as e:
            logger.error(f"Error loading git policies vectorstore from storage: {str(e)}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error loading git policies vectorstore: {str(e)}"
            }, 500)
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.error(f"Error cleaning up temporary directory: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in consume_git_policies_route: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing query: {str(e)}"
        }, 500)

def consume_vectorstore_route():
    """
    Consume a vectorstore with a query - RAG-based conversational assistant
    ---
    tags:
      - RAG
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - vectorstore_id
            - query
          properties:
            vectorstore_id:
              type: string
              description: ID of the vectorstore to use
            query:
              type: string
              description: User query to answer using the vectorstore
            model:
              type: string
              enum: [gpt-4o-mini, gpt-4o]
              default: gpt-4o-mini
              description: LLM model to use for generating the answer
            system_prompt:
              type: string
              description: Custom system prompt to guide model behavior (optional)
            temperature:
              type: number
              format: float
              minimum: 0
              maximum: 1
              default: 0.5
              description: Controls randomness (0=focused, 1=creative)
            include_sources:
              type: boolean
              default: false
              description: Whether to include source documents in the response
    produces:
      - application/json
    responses:
      200:
        description: Query answered successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Query processed successfully"
            answer:
              type: string
              example: "Based on the context, the answer to your question is..."
            model_used:
              type: string
              example: "gpt-4o-mini"
            vectorstore_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
            prompt_tokens:
              type: integer
              example: 125
            completion_tokens:
              type: integer
              example: 84
            total_tokens:
              type: integer
              example: 209
            sources:
              type: array
              items:
                type: string
              example: ["document1.pdf", "document2.docx"]
              description: Source documents used for the answer (only included if include_sources is true)
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Bad Request"
            message:
              type: string
              example: "Missing required field: vectorstore_id or query"
      401:
        description: Authentication error
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Authentication Error"
            message:
              type: string
              example: "Token has expired"
      403:
        description: Forbidden
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Forbidden"
            message:
              type: string
              example: "You don't have permission to access this vectorstore"
      404:
        description: Not found
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Not Found"
            message:
              type: string
              example: "Vectorstore not found"
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Server Error"
            message:
              type: string
              example: "Error processing query"
    """
    # Get token from X-Token header
    token = request.headers.get('X-Token')
    if not token:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing X-Token header"
        }, 401)
    
    # Validate token from database
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token - not found in database"
        }, 401)
    
    # Store token ID and user ID in g for logging and balance check
    g.token_id = token_details["id"]
    g.user_id = token_details["user_id"]
    
    # Check if token is expired
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    
    # Ensure expiration_time is timezone-aware
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Get user details
    user_id = token_details["user_id"]
    user_details = DatabaseService.get_user_by_id(user_id)
    if not user_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "User associated with token not found"
        }, 401)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    required_fields = ['vectorstore_id', 'query']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Extract parameters
    vectorstore_id = data.get('vectorstore_id')
    query = data.get('query')
    model = data.get('model', 'gpt-4o-mini')  # Default to gpt-4o-mini
    system_prompt = data.get('system_prompt', None)
    temperature = float(data.get('temperature', 0.5))
    include_sources = data.get('include_sources', False)
    
    # Validate model
    if model not in LLM_SERVICES:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Invalid model. Must be one of: {', '.join(LLM_SERVICES.keys())}"
        }, 400)
    
    # Validate temperature
    if not (0 <= temperature <= 1):
        return create_api_response({
            "error": "Bad Request",
            "message": "Temperature must be between 0 and 1"
        }, 400)
    
    try:
        # Check if vectorstore exists and user has access
        conn = None
        cursor = None
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Get vectorstore info
            query_db = """
            SELECT id, user_id, path, name
            FROM vectorstores 
            WHERE id = ?
            """
            
            cursor.execute(query_db, [vectorstore_id])
            vectorstore_info = cursor.fetchone()
            
            if not vectorstore_info:
                return create_api_response({
                    "error": "Not Found",
                    "message": f"Vectorstore with ID {vectorstore_id} not found"
                }, 404)
            
            # Check if vectorstore belongs to user (or if admin)
            vs_user_id = vectorstore_info[1]
            if vs_user_id != user_id and user_details.get("scope", 1) != 0:  # Not owner and not admin
                return create_api_response({
                    "error": "Forbidden",
                    "message": "You don't have permission to access this vectorstore"
                }, 403)
            
            # Extract vectorstore info
            vectorstore_path = vectorstore_info[2]
            vectorstore_name = vectorstore_info[3]
            
        except Exception as e:
            logger.error(f"Error checking vectorstore: {str(e)}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error checking vectorstore: {str(e)}"
            }, 500)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        # Create temporary directory to download vectorstore
        temp_dir = tempfile.mkdtemp()
        local_vs_path = os.path.join(temp_dir, "vectorstore")
        os.makedirs(local_vs_path)
        
        try:
            # Download vectorstore from blob storage
            blob_service_client = get_azure_blob_client()
            container_client = blob_service_client.get_container_client(VECTORSTORE_CONTAINER)
            
            # Download all blobs with the vectorstore path prefix
            blobs = list(container_client.list_blobs(name_starts_with=vectorstore_path))
            if not blobs:
                return create_api_response({
                    "error": "Not Found",
                    "message": f"Vectorstore files not found in storage for ID {vectorstore_id}"
                }, 404)
            
            # Download each blob
            for blob in blobs:
                # Get relative path from vectorstore_path
                rel_path = blob.name[len(vectorstore_path) + 1:] if blob.name.startswith(vectorstore_path + "/") else blob.name
                # Construct local path
                local_blob_path = os.path.join(local_vs_path, rel_path)
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(local_blob_path), exist_ok=True)
                
                # Download blob
                blob_client = container_client.get_blob_client(blob.name)
                with open(local_blob_path, "wb") as download_file:
                    download_file.write(blob_client.download_blob().readall())
            
            # Load the vectorstore
            try:
                # Initialize embeddings
                embeddings = AzureOpenAIEmbeddings(
                    azure_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
                    api_key=os.environ.get("OPENAI_API_KEY"),
                    azure_endpoint=os.environ.get("OPENAI_API_ENDPOINT")
                )
                
                # Load the vectorstore
                vectorstore = FAISS.load_local(
                    local_vs_path,
                    embeddings,
                    allow_dangerous_deserialization=True
                )
                
                logger.info(f"Successfully loaded vectorstore {vectorstore_id}")
                
                # Perform vector search to get relevant documents
                docs = vectorstore.similarity_search(query, k=4)
                
                # Prepare context from retrieved documents
                context = "\n\n".join([doc.page_content for doc in docs])
                
                # Set default system prompt if not provided
                if not system_prompt:
                    system_prompt = """You are a helpful AI assistant that answers questions based on the provided context. 
                    When answering, use only information from the provided context.
                    If the context doesn't contain the answer, say you don't know based on the available information.
                    Always maintain a helpful, informative tone."""
                
                # Prepare user input for the LLM model
                user_input = f"Context: {context}\n\nQuestion: {query}\n\nAnswer the question based on the context provided."
                
                # Use LLM service directly instead of making an API call
                llm_service = LLM_SERVICES[model]
                
                # Special handling for o3-mini which uses different parameters
                if model == 'o3-mini':
                    service_response = llm_service(
                        system_prompt=system_prompt,
                        user_input=user_input,
                        reasoning_effort="medium" if temperature > 0.5 else "high"
                    )
                else:
                    service_response = llm_service(
                        system_prompt=system_prompt,
                        user_input=user_input,
                        temperature=temperature
                    )
                
                if not service_response["success"]:
                    logger.error(f"Error from LLM service: {service_response['error']}")
                    return create_api_response({
                        "error": "Server Error",
                        "message": f"Error from LLM service: {service_response['error']}"
                    }, 500)
                
                # Extract the response data
                answer = service_response["result"]
                
                # Extract token usage
                prompt_tokens = service_response.get("prompt_tokens", 0)
                completion_tokens = service_response.get("completion_tokens", 0)
                total_tokens = service_response.get("total_tokens", 0)
                cached_tokens = service_response.get("cached_tokens", 0)
                
                # Update the last_accessed timestamp
                update_vectorstore_access_timestamp(vectorstore_id)
                
                # Create the response
                response_data = {
                    "message": "Query processed successfully",
                    "answer": answer,
                    "model_used": model,
                    "vectorstore_id": vectorstore_id,
                    "vectorstore_name": vectorstore_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cached_tokens": cached_tokens
                }
                
                # Add source documents if requested
                if include_sources:
                    sources = []
                    for doc in docs:
                        if 'source' in doc.metadata:
                            sources.append(doc.metadata['source'])
                    response_data["sources"] = list(set(sources))  # Remove duplicates
                
                return create_api_response(response_data, 200)
                
            except Exception as e:
                logger.error(f"Error processing query with vectorstore: {str(e)}")
                return create_api_response({
                    "error": "Server Error",
                    "message": f"Error processing query: {str(e)}"
                }, 500)
            
        except Exception as e:
            logger.error(f"Error loading vectorstore from storage: {str(e)}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error loading vectorstore: {str(e)}"
            }, 500)
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.error(f"Error cleaning up temporary directory: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in consume_vectorstore_route: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing query: {str(e)}"
        }, 500)


def register_consume_vectorstore_routes(app):
  from apis.utils.usageMiddleware import track_usage
  app.route('/rag/vectorstore/consume', methods=['POST'])(track_usage(api_logger(check_balance(consume_vectorstore_route))))
  app.route('/rag/vectorstore/consume/git_policies', methods=['POST'])(track_usage(api_logger(check_balance(consume_git_policies_route))))
