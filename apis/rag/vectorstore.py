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
# Import FileService directly
from apis.utils.fileService import FileService

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define container for vectorstores
VECTORSTORE_CONTAINER = "vectorstores"
STORAGE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT")
BASE_BLOB_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{VECTORSTORE_CONTAINER}"

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

def detect_file_type(file_path):
    """Detect file type and return appropriate loader"""
    file_extension = os.path.splitext(file_path)[1].lower()
    
    if file_extension == '.pdf':
        return PyPDFLoader(file_path)
    elif file_extension == '.docx':
        return Docx2txtLoader(file_path)
    elif file_extension == '.txt':
        return TextLoader(file_path)
    elif file_extension == '.csv':
        return CSVLoader(file_path)
    elif file_extension in ['.xlsx', '.xls']:
        return UnstructuredExcelLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

def process_file(file_path, metadata=None):
    """Process a file and return documents"""
    try:
        # Detect file type and get appropriate loader
        loader = detect_file_type(file_path)
        
        # Load documents
        documents = loader.load()
        
        # Add metadata if provided
        if metadata:
            for doc in documents:
                doc.metadata.update(metadata)
        
        return documents
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {str(e)}")
        raise

def create_vectorstore_route():
    """
    Create a FAISS vectorstore from files
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
            - file_ids
          properties:
            file_ids:
              type: array
              items:
                type: string
              description: Array of file IDs to process (uploaded via /file endpoint)
            vectorstore_name:
              type: string
              description: Optional name for the vectorstore
            chunk_size:
              type: integer
              default: 1000
              description: Size of text chunks for splitting documents
            chunk_overlap:
              type: integer
              default: 200
              description: Overlap between chunks
    produces:
      - application/json
    responses:
      200:
        description: Vectorstore created successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Vectorstore created successfully"
            vectorstore_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
            path:
              type: string
              example: "user123-12345678-1234-1234-1234-123456789012"
            name:
              type: string
              example: "My Vectorstore"
            file_count:
              type: integer
              example: 3
            files_uploaded:
              type: integer
              example: 3
            document_count:
              type: integer
              example: 42
            chunk_count:
              type: integer
              example: 120
            embedded_tokens:
              type: integer
              example: 65000
            embedding_model:
              type: string
              example: "text-embedding-3-large"
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
              example: "Missing required field: file_ids"
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
              example: "File not found"
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
              example: "Error creating vectorstore"
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
    if 'file_ids' not in data or not data['file_ids']:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: file_ids must be an array with at least one file ID"
        }, 400)
    
    # Extract parameters with defaults
    file_ids = data.get('file_ids', [])
    vectorstore_name = data.get('vectorstore_name', f"vectorstore-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    chunk_size = int(data.get('chunk_size', 1000))
    chunk_overlap = int(data.get('chunk_overlap', 200))
    
    # Ensure file_ids is a list
    if not isinstance(file_ids, list):
        file_ids = [file_ids]
    
    try:
        # Create a temporary working directory
        temp_dir = tempfile.mkdtemp()
        local_files = []
        
        # Ensure container exists
        ensure_container_exists(VECTORSTORE_CONTAINER)
        
        # Process each file
        all_documents = []
        files_processed = 0
        embedding_model = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
        
        # Get a database connection to access file data directly
        conn = DatabaseService.get_connection()
        
        for file_id in file_ids:
            try:
                # Directly query the database for file information
                cursor = conn.cursor()
                query = """
                SELECT id, user_id, original_filename, blob_name, blob_url, content_type
                FROM file_uploads
                WHERE id = ?
                """
                cursor.execute(query, [file_id])
                file_record = cursor.fetchone()
                cursor.close()
                
                if not file_record:
                    logger.error(f"File record not found for ID {file_id}")
                    continue
                
                file_name = file_record[2]
                blob_url = file_record[4]
                
                # Download the file using the blob_url
                import requests
                file_response = requests.get(blob_url, stream=True)
                if file_response.status_code != 200:
                    logger.error(f"Failed to download file: Status {file_response.status_code}")
                    continue
                
                # Save to temporary location
                local_file_path = os.path.join(temp_dir, file_name)
                with open(local_file_path, 'wb') as f:
                    for chunk in file_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                local_files.append(local_file_path)
                
                # Process the file
                metadata = {
                    "source": file_name,
                    "file_id": file_id
                }
                
                docs = process_file(local_file_path, metadata)
                all_documents.extend(docs)
                files_processed += 1
                
                logger.info(f"Processed file {file_name}, extracted {len(docs)} documents")
                
            except Exception as e:
                logger.error(f"Error processing file ID {file_id}: {str(e)}")
                continue
                
        # Close the connection when done
        conn.close()
        
        if not all_documents:
            return create_api_response({
                "error": "Processing Error",
                "message": "No documents were successfully processed from the provided files"
            }, 400)
        
        # Create text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # Split documents
        chunks = text_splitter.split_documents(all_documents)
        logger.info(f"Split {len(all_documents)} documents into {len(chunks)} chunks")
        
        # Generate vectorstore ID
        vectorstore_id = str(uuid.uuid4())
        vectorstore_path = f"{user_id}-{vectorstore_id}"
        
        # Initialize embeddings
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=embedding_model,
            api_key=os.environ.get("OPENAI_API_KEY"),
            azure_endpoint=os.environ.get("OPENAI_API_ENDPOINT")
        )
        
        # Estimate token count (approximately 4 tokens per word)
        total_text = " ".join([chunk.page_content for chunk in chunks])
        words = total_text.split()
        estimated_tokens = len(words) * 4  # Rough estimation
        
        # Create FAISS index
        vectorstore = FAISS.from_documents(chunks, embeddings)
        
        # Create a temporary path to save the vectorstore
        temp_vs_path = os.path.join(temp_dir, "vectorstore")
        vectorstore.save_local(temp_vs_path)
        
        # Upload to Azure Blob Storage
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(VECTORSTORE_CONTAINER)
        
        # Upload each file in the vectorstore directory
        for root, dirs, files in os.walk(temp_vs_path):
            for file in files:
                local_file_path = os.path.join(root, file)
                # Get relative path from temp_vs_path
                rel_path = os.path.relpath(local_file_path, temp_vs_path)
                # Construct blob path
                blob_path = f"{vectorstore_path}/{rel_path}"
                
                # Upload blob
                with open(local_file_path, "rb") as data:
                    container_client.upload_blob(name=blob_path, data=data, overwrite=True)
        
        # Store metadata in database
        conn = None
        cursor = None
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Insert vectorstore metadata
            query = """
            INSERT INTO vectorstores (
                id, 
                user_id, 
                name, 
                path, 
                file_count,
                document_count,
                chunk_count,
                chunk_size,
                chunk_overlap,
                created_at,
                last_accessed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()), DATEADD(HOUR, 2, GETUTCDATE()))
            """
            
            cursor.execute(query, [
                vectorstore_id,
                user_id,
                vectorstore_name,
                vectorstore_path,
                files_processed,
                len(all_documents),
                len(chunks),
                chunk_size,
                chunk_overlap
            ])
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error storing vectorstore metadata: {str(e)}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        # Return success response
        return create_api_response({
            "message": "Vectorstore created successfully",
            "vectorstore_id": vectorstore_id,
            "path": vectorstore_path,
            "name": vectorstore_name,
            "file_count": files_processed,
            "files_uploaded": files_processed,
            "document_count": len(all_documents),
            "chunk_count": len(chunks),
            "embedded_tokens": estimated_tokens,
            "embedding_model": embedding_model
        }, 200)
        
    except Exception as e:
        logger.error(f"Error creating vectorstore: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error creating vectorstore: {str(e)}"
        }, 500)
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {str(e)}")
            
def delete_vectorstore_route():
    """
    Delete a FAISS vectorstore
    ---
    tags:
      - RAG
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: vectorstore_id
        in: query
        type: string
        required: true
        description: ID of the vectorstore to delete
    produces:
      - application/json
    responses:
      200:
        description: Vectorstore deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Vectorstore deleted successfully"
            vectorstore_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
            name:
              type: string
              example: "My Vectorstore"
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
              example: "Missing required parameter: vectorstore_id"
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
              example: "You don't have permission to delete this vectorstore"
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
              example: "Error deleting vectorstore"
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
    
    # Get vectorstore_id from query parameter
    vectorstore_id = request.args.get('vectorstore_id')
    if not vectorstore_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required parameter: vectorstore_id"
        }, 400)
    
    try:
        # Check if vectorstore exists and belongs to the user
        conn = None
        cursor = None
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Get vectorstore info
            query = """
            SELECT id, user_id, path, name 
            FROM vectorstores 
            WHERE id = ?
            """
            
            cursor.execute(query, [vectorstore_id])
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
                    "message": "You don't have permission to delete this vectorstore"
                }, 403)
            
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
        
        # Delete from Azure Blob Storage
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(VECTORSTORE_CONTAINER)
        
        # Delete all blobs with the vectorstore path prefix
        blobs = container_client.list_blobs(name_starts_with=vectorstore_path)
        for blob in blobs:
            container_client.delete_blob(blob)
        
        # Delete from database
        conn = None
        cursor = None
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Delete vectorstore record
            query = """
            DELETE FROM vectorstores
            WHERE id = ?
            """
            
            cursor.execute(query, [vectorstore_id])
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error deleting vectorstore record: {str(e)}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error deleting vectorstore record: {str(e)}"
            }, 500)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        # Return success response
        return create_api_response({
            "message": "Vectorstore deleted successfully",
            "vectorstore_id": vectorstore_id,
            "name": vectorstore_name
        }, 200)
        
    except Exception as e:
        logger.error(f"Error deleting vectorstore: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error deleting vectorstore: {str(e)}"
        }, 500)

def load_vectorstore_route():
    """
    Load a FAISS vectorstore and return its metadata
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
          properties:
            vectorstore_id:
              type: string
              description: ID of the vectorstore to load
    produces:
      - application/json
    responses:
      200:
        description: Vectorstore information retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Vectorstore loaded successfully"
            vectorstore_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
            path:
              type: string
              example: "user123-12345678-1234-1234-1234-123456789012"
            name:
              type: string
              example: "My Vectorstore"
            file_count:
              type: integer
              example: 3
            document_count:
              type: integer
              example: 42
            chunk_count:
              type: integer
              example: 120
            created_at:
              type: string
              format: date-time
              example: "2023-06-01T10:30:45.123456+02:00"
            last_accessed:
              type: string
              format: date-time
              example: "2023-06-02T14:22:33.123456+02:00"
            embedding_model:
              type: string
              example: "text-embedding-3-large"
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
              example: "Missing required field: vectorstore_id"
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
              example: "Error loading vectorstore"
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
    if 'vectorstore_id' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: vectorstore_id"
        }, 400)
    
    vectorstore_id = data.get('vectorstore_id')
    
    try:
        # Check if vectorstore exists and user has access
        conn = None
        cursor = None
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Get vectorstore info
            query = """
            SELECT id, user_id, path, name, file_count, document_count, 
                   chunk_count, created_at, last_accessed
            FROM vectorstores 
            WHERE id = ?
            """
            
            cursor.execute(query, [vectorstore_id])
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
            file_count = vectorstore_info[4]
            document_count = vectorstore_info[5]
            chunk_count = vectorstore_info[6]
            created_at = vectorstore_info[7].isoformat() if vectorstore_info[7] else None
            last_accessed = vectorstore_info[8].isoformat() if vectorstore_info[8] else None
            
            # Update the last_accessed timestamp
            update_query = """
            UPDATE vectorstores
            SET last_accessed = DATEADD(HOUR, 2, GETUTCDATE())
            WHERE id = ?
            """
            
            cursor.execute(update_query, [vectorstore_id])
            conn.commit()
            
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
            
            # Test loading the vectorstore to ensure it's valid
            try:
                # Initialize embeddings
                embedding_model = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
                embeddings = AzureOpenAIEmbeddings(
                    azure_deployment=embedding_model,
                    api_key=os.environ.get("OPENAI_API_KEY"),
                    azure_endpoint=os.environ.get("OPENAI_API_ENDPOINT")
                )
                
                # Load the vectorstore
                FAISS.load_local(
                    local_vs_path,
                    embeddings,
                    allow_dangerous_deserialization=True
                )
                
                logger.info(f"Successfully loaded vectorstore {vectorstore_id}")
            except Exception as e:
                logger.error(f"Error loading vectorstore from disk: {str(e)}")
                return create_api_response({
                      "error": "Server Error",
                      "message": f"Error loading vectorstore: {str(e)}"
                  }, 500)
            
            # Return success response with vectorstore info
            return create_api_response({
                "message": "Vectorstore loaded successfully",
                "vectorstore_id": vectorstore_id,
                "path": vectorstore_path,
                "name": vectorstore_name,
                "file_count": file_count,
                "document_count": document_count,
                "chunk_count": chunk_count,
                "created_at": created_at,
                "last_accessed": last_accessed,
                "embedding_model": embedding_model
            }, 200)
            
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
        logger.error(f"Error in load_vectorstore_route: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error loading vectorstore: {str(e)}"
        }, 500)

def list_vectorstores_route():
    """
    List all vectorstores available to the user
    ---
    tags:
      - RAG
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
    produces:
      - application/json
    responses:
      200:
        description: Vectorstores list retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Vectorstores retrieved successfully"
            vectorstores:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                    example: "12345678-1234-1234-1234-123456789012"
                  name:
                    type: string
                    example: "My Vectorstore"
                  path:
                    type: string
                    example: "user123-12345678-1234-1234-1234-123456789012"
                  file_count:
                    type: integer
                    example: 3
                  document_count:
                    type: integer
                    example: 42
                  chunk_count:
                    type: integer
                    example: 120
                  created_at:
                    type: string
                    format: date-time
                    example: "2023-06-01T10:30:45.123456+02:00"
                  last_accessed:
                    type: string
                    format: date-time
                    example: "2023-06-02T14:22:33.123456+02:00"
                  owner_id:
                    type: string
                    example: "98765432-9876-9876-9876-987654321098"
            count:
              type: integer
              example: 3
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
              example: "Error retrieving vectorstores"
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
    
    try:
        # Get vectorstores for the user
        conn = None
        cursor = None
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # For admin users, get all vectorstores
            if user_details.get("scope", 1) == 0:
                query = """
                SELECT id, name, path, file_count, document_count, chunk_count, 
                       created_at, user_id, last_accessed
                FROM vectorstores 
                ORDER BY created_at DESC
                """
                cursor.execute(query)
            else:
                # For regular users, only get their vectorstores
                query = """
                SELECT id, name, path, file_count, document_count, chunk_count, 
                       created_at, user_id, last_accessed
                FROM vectorstores 
                WHERE user_id = ?
                ORDER BY created_at DESC
                """
                cursor.execute(query, [user_id])
            
            result = cursor.fetchall()
            
            # Format vectorstores
            vectorstores = []
            for row in result:
                vectorstores.append({
                    "id": row[0],
                    "name": row[1],
                    "path": row[2],
                    "file_count": row[3],
                    "document_count": row[4],
                    "chunk_count": row[5],
                    "created_at": row[6].isoformat() if row[6] else None,
                    "owner_id": row[7],
                    "last_accessed": row[8].isoformat() if row[8] else None
                })
            
            return create_api_response({
                "message": "Vectorstores retrieved successfully",
                "vectorstores": vectorstores,
                "count": len(vectorstores)
            }, 200)
            
        except Exception as e:
            logger.error(f"Error retrieving vectorstores: {str(e)}")
            return create_api_response({
                "error": "Server Error",
                "message": f"Error retrieving vectorstores: {str(e)}"
            }, 500)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    except Exception as e:
        logger.error(f"Error in list_vectorstores_route: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving vectorstores: {str(e)}"
        }, 500)

def create_vectorstore_from_string_route():
    """
    Create a FAISS vectorstore directly from a text string
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
            - content
          properties:
            content:
              type: string
              description: Text content to create vectorstore from
            content_source:
              type: string
              description: Source identifier for the content (e.g. "API Response", "Manual Input")
              default: "User Input"
            vectorstore_name:
              type: string
              description: Optional name for the vectorstore
            chunk_size:
              type: integer
              default: 500
              description: Size of text chunks for splitting documents (smaller default for strings)
            chunk_overlap:
              type: integer
              default: 100
              description: Overlap between chunks
            metadata:
              type: object
              description: Additional metadata to store with the content
    produces:
      - application/json
    responses:
      200:
        description: Vectorstore created successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Vectorstore created successfully from string content"
            vectorstore_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
            path:
              type: string
              example: "user123-12345678-1234-1234-1234-123456789012"
            name:
              type: string
              example: "My String Vectorstore"
            content_length:
              type: integer
              example: 5000
            chunk_count:
              type: integer
              example: 12
            content_source:
              type: string
              example: "User Input"
            embedded_tokens:
              type: integer
              example: 1200
            embedding_model:
              type: string
              example: "text-embedding-3-large"
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
              example: "Missing required field: content"
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
              example: "Error creating vectorstore"
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
    if 'content' not in data or not data['content']:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: content must be a non-empty string"
        }, 400)
    
    # Extract parameters with defaults optimized for string content
    content = data.get('content')
    content_source = data.get('content_source', 'User Input')
    vectorstore_name = data.get('vectorstore_name', f"string-vs-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    
    # Use smaller chunk sizes for string content by default
    chunk_size = int(data.get('chunk_size', 500))
    chunk_overlap = int(data.get('chunk_overlap', 100))
    
    # Get additional metadata
    metadata = data.get('metadata', {})
    
    # Add source to metadata
    metadata['source'] = content_source
    
    try:
        # Create a temporary working directory
        temp_dir = tempfile.mkdtemp()
        
        # Ensure container exists
        ensure_container_exists(VECTORSTORE_CONTAINER)
        
        # Create Document object from string
        from langchain_core.documents import Document
        
        doc = Document(
            page_content=content,
            metadata=metadata
        )
        
        # Create text splitter
        # For string input, RecursiveCharacterTextSplitter works well with smaller chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Split document into chunks
        chunks = text_splitter.split_documents([doc])
        
        # If content is very small, don't chunk it
        if not chunks and content.strip():
            chunks = [doc]
        
        logger.info(f"Split content into {len(chunks)} chunks")
        
        if not chunks:
            return create_api_response({
                "error": "Processing Error",
                "message": "Content was empty or could not be processed into chunks"
            }, 400)
        
        # Generate vectorstore ID
        vectorstore_id = str(uuid.uuid4())
        vectorstore_path = f"{user_id}-{vectorstore_id}"
        
        # Estimate token count (approximately 4 tokens per word)
        words = content.split()
        estimated_tokens = len(words) * 4  # Rough estimation
        
        # Initialize embeddings
        embedding_model = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=embedding_model,
            api_key=os.environ.get("OPENAI_API_KEY"),
            azure_endpoint=os.environ.get("OPENAI_API_ENDPOINT")
        )
        
        # Create FAISS index
        vectorstore = FAISS.from_documents(chunks, embeddings)
        
        # Create a temporary path to save the vectorstore
        temp_vs_path = os.path.join(temp_dir, "vectorstore")
        vectorstore.save_local(temp_vs_path)
        
        # Upload to Azure Blob Storage
        blob_service_client = get_azure_blob_client()
        container_client = blob_service_client.get_container_client(VECTORSTORE_CONTAINER)
        
        # Upload each file in the vectorstore directory
        for root, dirs, files in os.walk(temp_vs_path):
            for file in files:
                local_file_path = os.path.join(root, file)
                # Get relative path from temp_vs_path
                rel_path = os.path.relpath(local_file_path, temp_vs_path)
                # Construct blob path
                blob_path = f"{vectorstore_path}/{rel_path}"
                
                # Upload blob
                with open(local_file_path, "rb") as data_file:
                    container_client.upload_blob(name=blob_path, data=data_file, overwrite=True)
        
        # Store metadata in database
        conn = None
        cursor = None
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Insert vectorstore metadata
            query = """
            INSERT INTO vectorstores (
                id, 
                user_id, 
                name, 
                path, 
                file_count,
                document_count,
                chunk_count,
                chunk_size,
                chunk_overlap,
                created_at,
                last_accessed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()), DATEADD(HOUR, 2, GETUTCDATE()))
            """
            
            cursor.execute(query, [
                vectorstore_id,
                user_id,
                vectorstore_name,
                vectorstore_path,
                1,  # file_count (virtual file)
                1,  # document_count (one string input)
                len(chunks),
                chunk_size,
                chunk_overlap
            ])
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error storing vectorstore metadata: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        # Return success response
        return create_api_response({
            "message": "Vectorstore created successfully from string content",
            "vectorstore_id": vectorstore_id,
            "path": vectorstore_path,
            "name": vectorstore_name,
            "content_length": len(content),
            "chunk_count": len(chunks),
            "content_source": content_source,
            "embedded_tokens": estimated_tokens,
            "embedding_model": embedding_model
        }, 200)
        
    except Exception as e:
        logger.error(f"Error creating vectorstore from string: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error creating vectorstore: {str(e)}"
        }, 500)
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {str(e)}")

def register_vectorstore_routes(app):
    """Register vectorstore routes with the Flask app"""
    app.route('/rag/vectorstore/document', methods=['POST'])(api_logger(check_balance(create_vectorstore_route)))
    app.route('/rag/vectorstore/string', methods=['POST'])(api_logger(check_balance(create_vectorstore_from_string_route)))
    app.route('/rag/vectorstore/load', methods=['POST'])(api_logger(check_balance(load_vectorstore_route)))
    app.route('/rag/vectorstore', methods=['DELETE'])(api_logger(check_balance(delete_vectorstore_route)))
    app.route('/rag/vectorstore/list', methods=['GET'])(api_logger(check_balance(list_vectorstores_route)))
