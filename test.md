# Improved method of creating vectorstores using kmeans


import os 
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
import fitz
from tqdm import tqdm
import logging
import time
from typing import List, Dict
import numpy as np
import re
import hashlib
from datetime import datetime
import json

# Setup logging with more detailed configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vectorstore_creation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup Azure variables
api_key = os.environ.get("AZURE_OPENAI_KEY")
endpoint = os.environ.get("AZURE_EMBEDDING_ENDPOINT")

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
        self.document_processor = DocumentProcessor()

    def create_batched_vectorstore(self, 
                                 documents: List[Document], 
                                 batch_size: int = 50,
                                 retry_delay: int = 5,
                                 max_retries: int = 3) -> FAISS:
        """Create a FAISS vectorstore with enhanced batch processing."""
        vectorstore = None
        total_batches = len(documents) // batch_size + (1 if len(documents) % batch_size else 0)
        
        for i in tqdm(range(0, len(documents), batch_size), desc="Processing batches", total=total_batches):
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

    def process_directory(self, input_dir: str, output_dir: str):
        """Process all PDFs in directory with enhanced text splitting and embedding."""
        
        # Create text splitter with optimal settings
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ". ", " ", ""],
            chunk_size=3000,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False
        )
        
        # Walk through input directory
        for root, dirs, files in os.walk(input_dir):
            pdf_files = [f for f in files if f.lower().endswith('.pdf')]
            if not pdf_files:
                continue
                
            rel_path = os.path.relpath(root, input_dir)
            current_output_dir = os.path.join(output_dir, rel_path)
            os.makedirs(current_output_dir, exist_ok=True)
            
            logger.info(f"\nProcessing directory: {rel_path}")
            
            # Initialize processing statistics
            stats = {
                'total_pdfs': len(pdf_files),
                'processed_pdfs': 0,
                'total_pages': 0,
                'total_chunks': 0,
                'start_time': time.time()
            }
            
            all_documents = []
            for pdf_file in tqdm(pdf_files, desc="Loading PDFs"):
                file_path = os.path.join(root, pdf_file)
                documents = self.document_processor.process_pdf(file_path)
                
                if documents:
                    # Split documents with overlap
                    split_docs = text_splitter.split_documents(documents)
                    
                    # Update statistics
                    stats['processed_pdfs'] += 1
                    stats['total_pages'] += len(documents)
                    stats['total_chunks'] += len(split_docs)
                    
                    all_documents.extend(split_docs)
                    
                    if len(all_documents) >= 250:
                        self._process_document_batch(all_documents, current_output_dir)
                        all_documents = []
            
            # Process remaining documents
            if all_documents:
                self._process_document_batch(all_documents, current_output_dir)
            
            # Save processing statistics
            stats['end_time'] = time.time()
            stats['processing_time'] = stats['end_time'] - stats['start_time']
            self._save_processing_stats(current_output_dir, stats)
            
            # Save enhanced source document list
            self._save_source_list(current_output_dir, root, pdf_files)

    def _process_document_batch(self, documents: List[Document], output_dir: str):
        """Process a batch of documents and update/create vectorstore."""
        try:
            if not os.path.exists(os.path.join(output_dir, 'index.faiss')):
                vectorstore = self.create_batched_vectorstore(documents)  # Remove embeddings parameter
                vectorstore.save_local(output_dir)
            else:
                existing_vectorstore = FAISS.load_local(output_dir, self.embeddings, allow_dangerous_deserialization=True)
                new_vectorstore = self.create_batched_vectorstore(documents)  # Remove embeddings parameter
                existing_vectorstore.merge_from(new_vectorstore)
                existing_vectorstore.save_local(output_dir)
        except Exception as e:
            logger.error(f"Error processing batch: {str(e)}")

    def _save_processing_stats(self, output_dir: str, stats: Dict):
        """Save processing statistics to a JSON file."""
        stats_file = os.path.join(output_dir, "processing_stats.json")
        try:
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Saved processing statistics to {stats_file}")
        except Exception as e:
            logger.error(f"Error saving processing statistics: {str(e)}")

    def _save_source_list(self, output_dir: str, root_dir: str, pdf_files: List[str]):
        """Save enhanced source document list with metadata."""
        sources_file = os.path.join(output_dir, "sources.txt")
        try:
            with open(sources_file, 'w', encoding='utf-8') as f:
                for pdf_file in sorted(pdf_files):
                    file_path = os.path.join(root_dir, pdf_file)
                    file_size = os.path.getsize(file_path)
                    modified_time = time.ctime(os.path.getmtime(file_path))
                    f.write(f"{pdf_file}\t{file_size}\t{modified_time}\n")
            logger.info(f"Saved enhanced source list with {len(pdf_files)} documents")
        except Exception as e:
            logger.error(f"Error saving sources list: {str(e)}")

def main():
    # Define input and output directories
    input_dir = r"C:\Users\aaa\DNA-AI\AI-TIHKNOWLEDGEBOT\input_documents\Personal_Lines"
    output_dir = r"C:\Users\aaa\DNA-AI\AI-TIHKNOWLEDGEBOT\faiss_index\Personal_Lines"
    
    logger.info("Starting document processing")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    
    try:
        # Create embeddings object with optimal settings
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment='text-embedding-3-large',
            api_key=api_key,
            azure_endpoint=endpoint,
            chunk_size=3000
        )
        
        # Create vectorstore creator instance
        creator = VectorstoreCreator(embeddings)
        
        # Process directory
        creator.process_directory(input_dir, output_dir)
        
        logger.info("Processing completed successfully!")
        
    except Exception as e:
        logger.error(f"An error occurred during processing: {str(e)}")
        raise

if __name__ == "__main__":
    main()