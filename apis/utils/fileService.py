from apis.utils.config import get_azure_blob_client, ensure_container_exists, get_aliased_blob_url
import uuid
import os
import logging
from apis.utils.databaseService import DatabaseService
from flask import g
from datetime import datetime
import pytz
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContentSettings

# Configure logging
logger = logging.getLogger(__name__)

# Define container for file uploads
FILE_UPLOAD_CONTAINER = os.environ.get("AZURE_STORAGE_UPLOAD_CONTAINER", "file-uploads")

class FileService:
    @staticmethod
    def upload_file(file_obj, user_id, container_name=FILE_UPLOAD_CONTAINER):
        """
        Upload a file to Azure Blob Storage and store metadata in database
        
        Args:
            file_obj: Flask file object from request.files
            user_id: ID of the user uploading the file
            container_name (str): The container to upload to
            
        Returns:
            tuple: (file_info, None) or (None, error_message)
                file_info is a dict with file_id, file_name, content_type
        """
        try:
            # Ensure container exists
            ensure_container_exists(container_name)
            
            # Get blob service client
            blob_service_client = get_azure_blob_client()
            container_client = blob_service_client.get_container_client(container_name)
            
            # Generate unique ID for the file
            file_id = str(uuid.uuid4())
            original_filename = file_obj.filename
            
            # Create a blob name using the file_id to ensure uniqueness
            # Keep original extension if any
            _, file_extension = os.path.splitext(original_filename)
            blob_name = f"{file_id}{file_extension}"
            
            # Upload the file to blob storage
            blob_client = container_client.get_blob_client(blob_name)
            file_content = file_obj.read()  # Read file content
            
            content_settings = None
            if file_obj.content_type:
                content_settings = ContentSettings(content_type=file_obj.content_type)
            
            blob_client.upload_blob(file_content, overwrite=True, content_settings=content_settings)
            
            # Generate aliased URL to the blob
            blob_url = get_aliased_blob_url(container_name, blob_name)
            
            # Store file info in database
            db_conn = None
            cursor = None
            try:
                db_conn = DatabaseService.get_connection()
                cursor = db_conn.cursor()
                
                insert_query = """
                INSERT INTO file_uploads (
                    id, 
                    user_id, 
                    original_filename, 
                    blob_name, 
                    blob_url, 
                    content_type, 
                    file_size, 
                    upload_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()))
                """
                
                cursor.execute(insert_query, [
                    file_id,
                    user_id,
                    original_filename,
                    blob_name,
                    blob_url,  # This is now the aliased URL
                    file_obj.content_type or 'application/octet-stream',
                    len(file_content)  # File size in bytes
                ])
                
                db_conn.commit()
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except:
                        pass
                if db_conn:
                    try:
                        db_conn.close()
                    except:
                        pass
            
            # Return file info
            file_info = {
                "file_name": original_filename,
                "file_id": file_id,
                "content_type": file_obj.content_type or 'application/octet-stream'
            }
            
            logger.info(f"File uploaded: {original_filename} with ID {file_id} by user {user_id}")
            return file_info, None
            
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            return None, str(e)
    
    @staticmethod
    def get_file_url(file_id, user_id=None):
        """
        Get access URL for a previously uploaded file
        
        Args:
            file_id (str): ID of the file to retrieve
            user_id (str, optional): ID of the user requesting the file
            
        Returns:
            tuple: (file_info, None) or (None, error_message)
                file_info is a dict with file_name, file_url, content_type, upload_date
        """
        db_conn = None
        cursor = None
        
        try:
            db_conn = DatabaseService.get_connection()
            cursor = db_conn.cursor()
            
            query = """
            SELECT id, user_id, original_filename, blob_url, content_type, upload_date
            FROM file_uploads
            WHERE id = ?
            """
            
            cursor.execute(query, [file_id])
            file_info = cursor.fetchone()
            
            if not file_info:
                return None, f"File with ID {file_id} not found"
            
            # If user_id is provided, check permissions
            if user_id:
                # Get user scope from database
                user_scope_query = """
                SELECT scope FROM users WHERE id = ?
                """
                cursor.execute(user_scope_query, [user_id])
                user_scope_result = cursor.fetchone()
                user_scope = user_scope_result[0] if user_scope_result else 1  # Default to regular user if not found
            
                # Check if user has access to this file (admin or file owner)
                # Admins (scope=0) can access any file
                if user_scope != 0 and str(file_info[1]) != user_id:
                    return None, "You don't have permission to access this file"
            
            # Return file info with URL (already aliased from database)
            result = {
                "file_name": file_info[2],
                "file_url": file_info[3],  # This is already the aliased URL from DB
                "content_type": file_info[4],
                "upload_date": file_info[5].isoformat() if file_info[5] else None
            }
            
            return result, None
        
        except Exception as e:
            logger.error(f"Error retrieving file URL: {str(e)}")
            return None, str(e)
            
        finally:
            # Ensure cursor and connection are closed even if an exception occurs
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            
            if db_conn:
                try:
                    db_conn.close()
                except:
                    pass
    
    @staticmethod
    def delete_file(file_id, user_id=None, container_name=FILE_UPLOAD_CONTAINER):
        """
        Delete a file from Azure Blob Storage and remove from database
        
        Args:
            file_id (str): ID of the file to delete
            user_id (str, optional): ID of the user deleting the file
            container_name (str): Container name where the file is stored
            
        Returns:
            tuple: (success, message)
                success is a boolean indicating if the operation was successful
                message is a string with details
        """
        db_conn = None
        cursor = None
        
        try:
            db_conn = DatabaseService.get_connection()
            cursor = db_conn.cursor()
            
            query = """
            SELECT id, user_id, blob_name
            FROM file_uploads
            WHERE id = ?
            """
            
            cursor.execute(query, [file_id])
            file_info = cursor.fetchone()
            
            if not file_info:
                return False, f"File with ID {file_id} not found"
            
            # If user_id is provided, check permissions
            if user_id:
                # Get user scope from database
                user_scope_query = """
                SELECT scope FROM users WHERE id = ?
                """
                cursor.execute(user_scope_query, [user_id])
                user_scope_result = cursor.fetchone()
                user_scope = user_scope_result[0] if user_scope_result else 1  # Default to regular user if not found
                
                # Check if user has permission to delete this file (admin or file owner)
                # Admins (scope=0) can delete any file
                if user_scope != 0 and str(file_info[1]) != user_id:
                    return False, "You don't have permission to delete this file"
            
            # Delete from blob storage
            blob_name = file_info[2]
            blob_service_client = get_azure_blob_client()
            container_client = blob_service_client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            
            # Try to delete the blob (may already be deleted)
            try:
                blob_client.delete_blob()
            except Exception as e:
                logger.warning(f"Error deleting blob {blob_name}, may already be deleted: {str(e)}")
            
            # Delete from database
            delete_query = """
            DELETE FROM file_uploads
            WHERE id = ?
            """
            
            cursor.execute(delete_query, [file_id])
            db_conn.commit()
            
            logger.info(f"File {file_id} deleted by user {user_id}")
            
            return True, "File deleted successfully"
        
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False, str(e)
        
        finally:
            # Ensure cursor and connection are closed even if an exception occurs
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            
            if db_conn:
                try:
                    db_conn.close()
                except:
                    pass
    
    @staticmethod
    def list_files(user_id=None, is_admin=False):
        """
        List files uploaded by a user or all files for admin
        
        Args:
            user_id (str, optional): ID of the user whose files to list
            is_admin (bool): Whether the requesting user is an admin
            
        Returns:
            tuple: (files, None) or (None, error_message)
                files is a list of file info dicts
        """
        try:
            # Query database for files
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            if is_admin:
                # Admin can see all files
                query = """
                SELECT
                    fu.id,
                    fu.user_id,
                    fu.original_filename,
                    fu.blob_name,
                    fu.blob_url,
                    fu.content_type,
                    fu.file_size,
                    fu.upload_date,
                    u.user_name,
                    u.common_name
                FROM
                    file_uploads fu
                LEFT JOIN
                    users u ON fu.user_id = u.id
                ORDER BY
                    fu.upload_date DESC
                """
                cursor.execute(query)
            else:
                # Regular user can only see their own files
                query = """
                SELECT
                    id,
                    user_id,
                    original_filename,
                    blob_name,
                    blob_url,
                    content_type,
                    file_size,
                    upload_date
                FROM
                    file_uploads
                WHERE
                    user_id = ?
                ORDER BY
                    upload_date DESC
                """
                cursor.execute(query, [user_id])
            
            files = []
            for row in cursor.fetchall():
                file_info = {
                    "file_id": str(row[0]),
                    "file_name": row[2],
                    "content_type": row[5],
                    "upload_date": row[7].isoformat() if row[7] else None,
                    "file_size": row[6],
                    "blob_url": row[4]  # This is already the aliased URL from DB
                }
                
                # Add user info for admin view
                if is_admin:
                    file_info["user_id"] = str(row[1])
                    file_info["user_name"] = row[9] if row[9] else row[8]  # Use common_name if available, otherwise user_name
                
                files.append(file_info)
            
            cursor.close()
            conn.close()
            
            return files, None
            
        except Exception as e:
            logger.error(f"Error retrieving files: {str(e)}")
            return None, str(e)
