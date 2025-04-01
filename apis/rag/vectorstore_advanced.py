import re
import hashlib
import json
import time
from typing import List, Dict
import fitz  # PyMuPDF
from langchain_core.documents import Document

class TextProcessor:
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text content."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep meaningful punctuation
        text = re.sub(r'[^\w\s.,!?;:()\-\']', ' ', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        # Convert to lowercase for consistency
        text = text.lower().strip()
        return text

    @staticmethod
    def generate_content_hash(content: str) -> str:
        """Generate a hash of the content for deduplication."""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

class DocumentProcessor:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.processed_hashes = set()

    def preprocess_document(self, content: str, metadata: Dict) -> Document:
        """Preprocess document content with enhanced cleaning and metadata."""
        # Clean the content
        cleaned_content = self.text_processor.clean_text(content)
        
        # Generate content hash
        content_hash = self.text_processor.generate_content_hash(cleaned_content)
        
        # Update metadata
        metadata.update({
            'preprocessed': True,
            'content_length': len(cleaned_content),
            'content_hash': content_hash,
            'processing_timestamp': datetime.now().isoformat(),
            'chunk_id': hashlib.md5(f"{metadata.get('source', '')}-{metadata.get('page', '')}-{content_hash}".encode()).hexdigest()
        })
        
        return Document(
            page_content=cleaned_content,
            metadata=metadata
        )

    def process_pdf(self, file_path: str) -> List[Document]:
        """Process a single PDF file with enhanced text extraction."""
        documents = []
        filename = os.path.basename(file_path)
        
        try:
            reader = fitz.open(file_path)
            logger.info(f'Processing {filename} - Pages: {reader.page_count}')
            
            file_metadata = {
                "source": filename,
                "file_path": file_path,
                "total_pages": reader.page_count,
                "file_size": os.path.getsize(file_path),
                "last_modified": time.ctime(os.path.getmtime(file_path))
            }
            
            for page_num in range(reader.page_count):
                page = reader[page_num]
                
                # Extract text with better formatting
                blocks = page.get_text("blocks")
                text_blocks = []
                
                for block in blocks:
                    # Skip empty blocks or those with only whitespace
                    if not block[4].strip():
                        continue
                    text_blocks.append(block[4])
                
                # Join blocks with proper spacing
                plain_text = "\n".join(text_blocks)
                
                # Skip if content is too short or mostly whitespace
                if len(plain_text.strip()) < 10:
                    continue
                
                # Create document metadata
                page_metadata = {
                    **file_metadata,
                    "page": page_num + 1,
                    "block_count": len(blocks)
                }
                
                # Create preprocessed document
                doc = self.preprocess_document(plain_text, page_metadata)
                
                # Check for duplicate content
                if doc.metadata['content_hash'] not in self.processed_hashes:
                    documents.append(doc)
                    self.processed_hashes.add(doc.metadata['content_hash'])
            
            reader.close()
            return documents
        
        except Exception as e:
            logger.error(f"Error processing {filename}: {str(e)}")
            return []

class VectorstoreCreator:
    def __init__(self, embeddings):
        self.embeddings = embeddings

    def create_batched_vectorstore(self, 
                               documents: List[Document], 
                               batch_size: int = 50,
                               retry_delay: int = 5,
                               max_retries: int = 3) -> FAISS:
        """Create a FAISS vectorstore with enhanced batch processing."""
        vectorstore = None
        total_batches = len(documents) // batch_size + (1 if len(documents) % batch_size else 0)
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Create new vectorstore for batch
                    batch_vectorstore = FAISS.from_documents(
                        batch, 
                        self.embeddings,
                        normalize_L2=True
                    )
                    
                    # Merge with existing vectorstore if it exists
                    if vectorstore is None:
                        vectorstore = batch_vectorstore
                    else:
                        vectorstore.merge_from(batch_vectorstore)
                    
                    break
                    
                except Exception as e:
                    retry_count += 1
                    logger.warning(f"Batch processing failed (attempt {retry_count}/{max_retries}): {str(e)}")
                    
                    if retry_count < max_retries:
                        logger.info(f"Waiting {retry_delay} seconds before retrying...")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Failed to process batch after {max_retries} attempts")
                        raise
        
        return vectorstore

def create_advanced_vectorstore_route():
    """
    Create an advanced FAISS vectorstore from files with enhanced processing
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
              default: 3000
              description: Size of text chunks for splitting documents
            chunk_overlap:
              type: integer
              default: 200
              description: Overlap between chunks
            batch_size:
              type: integer
              default: 50
              description: Number of documents to process in each batch
            max_retries:
              type: integer
              default: 3
              description: Maximum number of retries for batch processing
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
              example: "Advanced vectorstore created successfully"
            vectorstore_id:
              type: string
              example: "12345678-1234-1234-1234-123456789012"
            path:
              type: string
              example: "user123-12345678-1234-1234-1234-123456789012"
            file_count:
              type: integer
              example: 3
            documents_processed:
              type: integer
              example: 42
            chunks_processed:
              type: integer
              example: 120
            processing_stats:
              type: object
              description: Detailed processing statistics
      400:
        description: Bad request
      401:
        description: Authentication error
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
    if 'file_ids' not in data or not data['file_ids']:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: file_ids must be an array with at least one file ID"
        }, 400)
    
    # Extract parameters with defaults
    file_ids = data.get('file_ids', [])
    vectorstore_name = data.get('vectorstore_name', f"advanced-vs-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    chunk_size = int(data.get('chunk_size', 3000))
    chunk_overlap = int(data.get('chunk_overlap', 200))
    batch_size = int(data.get('batch_size', 50))
    max_retries = int(data.get('max_retries', 3))
    
    # Ensure file_ids is a list
    if not isinstance(file_ids, list):
        file_ids = [file_ids]
    
    try:
        # Create a temporary working directory
        temp_dir = tempfile.mkdtemp()
        local_files = []
        
        # Ensure container exists
        ensure_container_exists(VECTORSTORE_CONTAINER)
        
        # Initialize processing statistics
        processing_stats = {
            'start_time': time.time(),
            'total_files': len(file_ids),
            'processed_files': 0,
            'total_pages': 0,
            'total_documents': 0,
            'total_chunks': 0,
            'duplicates_removed': 0,
            'files_details': []
        }
        
        # Initialize document processor
        doc_processor = DocumentProcessor()
        
        # Process each file
        all_documents = []
        files_processed = 0
        
        for file_id in file_ids:
            try:
                # Get file URL from the file ID
                file_url_endpoint = f"{request.url_root.rstrip('/')}/file/url?file_id={file_id}"
                headers = {"X-Token": token}
                
                file_url_response = requests.get(
                    file_url_endpoint,
                    headers=headers
                )
                
                if file_url_response.status_code != 200:
                    logger.error(f"Error retrieving file URL: Status {file_url_response.status_code}")
                    continue
                
                file_info = file_url_response.json()
                file_url = file_info.get("file_url")
                file_name = file_info.get("file_name")
                
                if not file_url or not file_name:
                    logger.error(f"Missing file_url or file_name in response")
                    continue
                
                # Download the file
                file_response = requests.get(file_url, stream=True)
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
                
                # Process the file - use enhanced PDF processing for PDFs
                file_documents = []
                if file_name.lower().endswith('.pdf'):
                    file_documents = doc_processor.process_pdf(local_file_path)
                else:
                    # For non-PDF files, create a basic document
                    with open(local_file_path, 'r', errors='ignore') as f:
                        content = f.read()
                    
                    metadata = {
                        "source": file_name,
                        "file_id": file_id,
                        "file_path": local_file_path,
                        "file_size": os.path.getsize(local_file_path),
                        "last_modified": time.ctime(os.path.getmtime(local_file_path))
                    }
                    
                    # Preprocess the document
                    doc = doc_processor.preprocess_document(content, metadata)
                    
                    # Add if not a duplicate
                    if doc.metadata['content_hash'] not in doc_processor.processed_hashes:
                        file_documents.append(doc)
                        doc_processor.processed_hashes.add(doc.metadata['content_hash'])
                
                # Update statistics
                if file_documents:
                    file_stats = {
                        "file_name": file_name,
                        "file_id": file_id,
                        "documents_extracted": len(file_documents),
                        "file_size": os.path.getsize(local_file_path),
                        "content_hashes": [doc.metadata['content_hash'] for doc in file_documents]
                    }
                    processing_stats['files_details'].append(file_stats)
                    
                    all_documents.extend(file_documents)
                    processing_stats['total_documents'] += len(file_documents)
                    
                    if file_name.lower().endswith('.pdf'):
                        # For PDFs, count pages
                        processing_stats['total_pages'] += file_documents[-1].metadata.get('total_pages', 0) if file_documents else 0
                    
                    files_processed += 1
                    processing_stats['processed_files'] += 1
                
                logger.info(f"Processed file {file_name}, extracted {len(file_documents)} documents")
                
            except Exception as e:
                logger.error(f"Error processing file ID {file_id}: {str(e)}")
                continue
        
        if not all_documents:
            return create_api_response({
                "error": "Processing Error",
                "message": "No documents were successfully processed from the provided files"
            }, 400)
        
        # Create text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ". ", " ", ""],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )
        
        # Split documents
        chunks = text_splitter.split_documents(all_documents)
        logger.info(f"Split {len(all_documents)} documents into {len(chunks)} chunks")
        
        # Update statistics
        processing_stats['total_chunks'] = len(chunks)
        processing_stats['duplicates_removed'] = len(doc_processor.processed_hashes) - processing_stats['total_documents']
        
        # Generate vectorstore ID
        vectorstore_id = str(uuid.uuid4())
        vectorstore_path = f"{user_id}-{vectorstore_id}"
        
        # Initialize embeddings
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
            api_key=os.environ.get("OPENAI_API_KEY"),
            azure_endpoint=os.environ.get("OPENAI_API_ENDPOINT"),
            chunk_size=chunk_size
        )
        
        # Create vectorstore creator
        creator = VectorstoreCreator(embeddings)
        
        # Create FAISS index with batch processing
        vectorstore = creator.create_batched_vectorstore(
            chunks, 
            batch_size=batch_size,
            max_retries=max_retries
        )
        
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
        
        # Update final statistics
        processing_stats['end_time'] = time.time()
        processing_stats['processing_time_seconds'] = processing_stats['end_time'] - processing_stats['start_time']
        
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
                processing_stats
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()), ?)
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
                chunk_overlap,
                json.dumps(processing_stats)
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
            "message": "Advanced vectorstore created successfully",
            "vectorstore_id": vectorstore_id,
            "path": vectorstore_path,
            "name": vectorstore_name,
            "file_count": files_processed,
            "document_count": len(all_documents),
            "chunk_count": len(chunks),
            "processing_stats": processing_stats
        }, 200)
        
    except Exception as e:
        logger.error(f"Error creating advanced vectorstore: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error creating advanced vectorstore: {str(e)}"
        }, 500)
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {str(e)}")

def register_advanced_vectorstore_routes(app):
    """Register advanced vectorstore routes with the Flask app"""
    app.route('/rag/vectorstore/document/advanced', methods=['POST'])(api_logger(check_balance(create_advanced_vectorstore_route)))
