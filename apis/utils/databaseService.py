import os
import pyodbc
import logging
import uuid
import json 

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DATABASE SERVICE
class DatabaseService:
    DB_CONFIG={
    "DRIVER" : os.environ['DB_DRIVER'],
    "SERVER" : os.environ['DB_SERVER'],
    "DATABASE" : os.environ['DB_NAME'],
    "UID" : os.environ['DB_USER'],
    "PASSWORD" : os.environ['DB_PASSWORD']}
    
    CONNECTION_STRING = (
        f"DRIVER={DB_CONFIG['DRIVER']};"
        f"SERVER={DB_CONFIG['SERVER']};"
        f"DATABASE={DB_CONFIG['DATABASE']};"
        f"UID={DB_CONFIG['UID']};"
        f"PWD={DB_CONFIG['PASSWORD']};"
    )
    
    @staticmethod
    def execute_query(query, params=None):
        """
        Execute a SQL query and return results
        
        Args:
            query (str): SQL query to execute
            params (tuple): Query parameters (optional)
            
        Returns:
            dict: {'success': bool, 'data': list, 'error': str}
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # For SELECT queries, fetch results
            if query.strip().upper().startswith('SELECT'):
                results = cursor.fetchall()
                data = [list(row) for row in results]  # Convert to list of lists
            else:
                # For non-SELECT queries (INSERT, UPDATE, DELETE)
                conn.commit()
                data = cursor.rowcount  # Number of affected rows
            
            cursor.close()
            conn.close()
            
            return {
                'success': True,
                'data': data,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Database query error: {str(e)}")
            if 'conn' in locals():
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
            return {
                'success': False,
                'data': None,
                'error': str(e)
            }
    
    @staticmethod
    def get_connection():
        try:
            conn = pyodbc.connect(DatabaseService.CONNECTION_STRING)
            return conn
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise


    @staticmethod
    def validate_api_key(api_key):
        """Validate API key and return user details if valid"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT id, user_name, user_email, common_name, company, department, api_key, scope, active
            FROM users
            WHERE api_key = ?
            """
            
            cursor.execute(query, [api_key])
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user:
                return {
                    "id": str(user[0]),
                    "user_name": user[1],
                    "user_email": user[2],
                    "common_name": user[3],
                    "company": user[4],
                    "department": user[5],
                    "api_key": str(user[6]),
                    "scope": user[7],
                    "active": user[8]
                }
            return None
            
        except Exception as e:
            logger.error(f"API key validation error: {str(e)}")
            return None


    @staticmethod
    def get_token_details_by_value(token_value):
        """Get token details by token value"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT 
                tt.id,
                tt.token_value,
                tt.user_id,
                tt.token_scope,
                tt.expires_on as token_expiration_time
            FROM 
                token_transactions tt
            WHERE 
                tt.token_value = ?
            """
            
            cursor.execute(query, [token_value])
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not result:
                return None
                
            return {
                "id": result[0],
                "token_value": result[1],
                "user_id": result[2],
                "token_scope": result[3],
                "token_expiration_time": result[4]
            }
            
        except Exception as e:
            logger.error(f"Token details retrieval error: {str(e)}")
            return None
    
    @staticmethod
    def log_token_transaction(user_id, token_scope, expires_in, expires_on, token_value):
        """Log token generation transaction to database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            INSERT INTO token_transactions (id, user_id, token_scope, expires_in, expires_on, token_provider, token_value, created_at)
            VALUES (?, ?, ?, ?, ?, 'Microsoft Entra App', ?, DATEADD(HOUR, 2, GETUTCDATE()))
            """
            
            transaction_id = str(uuid.uuid4())
            
            cursor.execute(query, [
                transaction_id,
                user_id,
                token_scope,
                expires_in,
                expires_on,
                token_value
            ])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return transaction_id
            
        except Exception as e:
            logger.error(f"Token logging error: {str(e)}")
            return None
    
    
    @staticmethod
    def update_token(existing_token, new_token_value, expires_in, expires_on, token_scope, regenerated_by, regenerated_from=None):
        """Update existing token with new values and regeneration info"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            UPDATE token_transactions
            SET token_value = ?,
                expires_in = ?,
                expires_on = ?,
                token_scope = ?,
                modified_at = DATEADD(HOUR, 2, GETUTCDATE()),
                regenerated_at = DATEADD(HOUR, 2, GETUTCDATE()),
                regenerated_by = ?,
                regenerated_from = ?
            WHERE token_value = ?
            """
            
            cursor.execute(query, [
                new_token_value,
                expires_in,
                expires_on,
                token_scope,
                regenerated_by,
                regenerated_from,
                existing_token
            ])
            
            # Check if any rows were affected
            rows_affected = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Token update error: {str(e)}")
            return False

    @staticmethod
    def log_refreshed_token(user_id, token_scope, expires_in, expires_on, token_value, regenerated_from, regenerated_by):
        """Log refreshed token transaction to database with reference to original token"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            INSERT INTO token_transactions (
                id, 
                user_id, 
                token_scope, 
                expires_in, 
                expires_on, 
                token_provider, 
                token_value, 
                created_at,
                regenerated_at,
                regenerated_by,
                regenerated_from
            )
            VALUES (
                ?, ?, ?, ?, ?, 'Microsoft Entra App', ?, 
                DATEADD(HOUR, 2, GETUTCDATE()),
                DATEADD(HOUR, 2, GETUTCDATE()),
                ?,
                ?
            )
            """
            
            transaction_id = str(uuid.uuid4())
            
            cursor.execute(query, [
                transaction_id,
                user_id,
                token_scope,
                expires_in,
                expires_on,
                token_value,
                regenerated_by,
                regenerated_from
            ])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return transaction_id
            
        except Exception as e:
            logger.error(f"Refreshed token logging error: {str(e)}")
            return None
        
    @staticmethod
    def create_user(user_data):
        """Create a new user in the database with default aic_balance based on scope"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Generate UUID for user ID and API key
            user_id = str(uuid.uuid4())
            api_key = str(uuid.uuid4())
            
            # Set default values for optional fields
            common_name = user_data.get('common_name')
            company = user_data.get('company')
            department = user_data.get('department')
            phone_ext = user_data.get('phone_ext')
            division = user_data.get('division')
            sub_department = user_data.get('sub_department')
            cost_center = user_data.get('cost_center')
            manager_full_name = user_data.get('manager_full_name')
            manager_email = user_data.get('manager_email')
            scope = user_data.get('scope', 1)
            active = user_data.get('active', True)
            comment = user_data.get('comment')
            
            # Get default balance from scope_balance_config
            balance_query = """
            SELECT monthly_balance FROM scope_balance_config
            WHERE scope = ?
            """
            cursor.execute(balance_query, [scope])
            scope_balance_result = cursor.fetchone()
            aic_balance = scope_balance_result[0] if scope_balance_result else 100  # Default to 100 if not found
            
            # Prepare the SQL query
            query = """
            INSERT INTO users (
                id, 
                user_name, 
                user_email, 
                common_name,
                company,
                department,
                phone_ext,
                division,
                sub_department,
                cost_center,
                manager_full_name,
                manager_email,
                api_key, 
                scope, 
                active, 
                created_at, 
                modified_at, 
                comment,
                aic_balance
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                DATEADD(HOUR, 2, GETUTCDATE()),
                DATEADD(HOUR, 2, GETUTCDATE()),
                ?,
                ?
            )
            """
            
            # Execute the query
            cursor.execute(query, [
                user_id,
                user_data['user_name'],
                user_data['user_email'],
                common_name,
                company,
                department,
                phone_ext,
                division,
                sub_department,
                cost_center,
                manager_full_name,
                manager_email,
                api_key,
                scope,
                1 if active else 0,  # Convert boolean to bit
                comment,
                aic_balance
            ])
            
            # Commit the transaction
            conn.commit()
            cursor.close()
            conn.close()
            
            return (user_id, api_key)
            
        except pyodbc.IntegrityError as ie:
            # Handle unique constraint violations (e.g., duplicate email)
            if "Violation of UNIQUE constraint" in str(ie):
                logger.error(f"Duplicate email or API key: {str(ie)}")
            else:
                logger.error(f"Database integrity error: {str(ie)}")
            return (None, None)
            
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return (None, None)
     
        
    @staticmethod
    def get_user_by_id(user_id):
        """Get user details by ID
        
        Args:
            user_id (str): UUID of the user to retrieve
            
        Returns:
            dict: User details if found, None otherwise
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT id, user_name, user_email, common_name, company, department, api_key, scope, active, comment
            FROM users
            WHERE id = ?
            """
            
            cursor.execute(query, [user_id])
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user:
                return {
                    "id": str(user[0]),
                    "user_name": user[1],
                    "user_email": user[2],
                    "common_name": user[3],
                    "company": user[4],
                    "department": user[5],
                    "api_key": str(user[6]),
                    "scope": user[7],
                    "active": bool(user[8]),
                    "comment": user[9]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving user by ID: {str(e)}")
            return None


    @staticmethod
    def update_user(user_id, update_data):
        """Update user details
        
        Args:
            user_id (str): UUID of the user to update
            update_data (dict): Dictionary containing fields to update
                
        Returns:
            tuple: (success, updated_fields)
        """
        try:
            if not update_data:
                return True, []
                
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Build dynamic update query based on provided fields
            set_clauses = []
            params = []
            updated_fields = []
            
            for field, value in update_data.items():
                set_clauses.append(f"{field} = ?")
                
                # Convert boolean to bit for SQL if field is 'active'
                if field == 'active':
                    params.append(1 if value else 0)
                else:
                    params.append(value)
                    
                updated_fields.append(field)
            
            # Always update modified_at timestamp
            set_clauses.append("modified_at = DATEADD(HOUR, 2, GETUTCDATE())")
            
            # Build the final query
            query = f"""
            UPDATE users
            SET {', '.join(set_clauses)}
            WHERE id = ?
            """
            
            # Add user_id to params
            params.append(user_id)
            
            # Execute update
            cursor.execute(query, params)
            
            # Check if any rows were affected
            rows_affected = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return rows_affected > 0, updated_fields
            
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            return False, []
        
    @staticmethod
    def delete_user(user_id):
        """Delete a user from the database
        
        Args:
            user_id (str): UUID of the user to delete
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            Exception: If the user has active tokens or other database constraints
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Check if user has any active tokens first
            token_check_query = """
            SELECT COUNT(*) 
            FROM token_transactions 
            WHERE user_id = ?
            """
            
            cursor.execute(token_check_query, [user_id])
            token_count = cursor.fetchone()[0]
            
            if token_count > 0:
                # We could automatically delete tokens, but it's safer to make the admin
                # explicitly revoke tokens first to prevent accidental data loss
                cursor.close()
                conn.close()
                raise Exception("User has active tokens. Please revoke all tokens before deleting user.")
            
            # Delete the user
            delete_query = """
            DELETE FROM users
            WHERE id = ?
            """
            
            cursor.execute(delete_query, [user_id])
            
            # Check if any rows were affected
            rows_affected = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Error deleting user: {str(e)}")
            raise
        
    @staticmethod
    def get_endpoint_id_by_path(endpoint_path):
        """Get endpoint ID by path"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT id, cost FROM endpoints 
            WHERE endpoint_path = ?
            """
            
            cursor.execute(query, [endpoint_path])
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error getting endpoint ID: {str(e)}")
            return None
    
    @staticmethod
    def get_endpoint_cost_by_id(endpoint_id):
        """Get endpoint cost by ID"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT cost FROM endpoints 
            WHERE id = ?
            """
            
            cursor.execute(query, [endpoint_id])
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return result[0] if result else 1  # Default to 1 if not found
            
        except Exception as e:
            logger.error(f"Error getting endpoint cost: {str(e)}")
            return 1  # Default to 1 in case of error
    
    @staticmethod
    def log_api_call(endpoint_id, user_id=None, token_id=None, request_method=None, 
                    request_headers=None, request_body=None, response_status=None, 
                    response_time_ms=None, user_agent=None, ip_address=None, 
                    error_message=None, response_body=None, correlation_id=None):
        """Log API call to database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            log_id = str(uuid.uuid4())
            
            query = """
            INSERT INTO api_logs (
                id, endpoint_id, user_id, timestamp, request_method, 
                request_headers, request_body, response_status, response_time_ms,
                user_agent, ip_address, token_id, error_message, response_body, correlation_id
            )
            VALUES (
                ?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()), ?, 
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            """
            
            # Convert dictionary to JSON string if necessary
            if request_headers and isinstance(request_headers, dict):
                request_headers = json.dumps(request_headers)
                
            if request_body and isinstance(request_body, dict):
                request_body = json.dumps(request_body)
                
            if response_body and isinstance(response_body, dict):
                response_body = json.dumps(response_body)
            
            cursor.execute(query, [
                log_id, endpoint_id, user_id, request_method,
                request_headers, request_body, response_status, response_time_ms,
                user_agent, ip_address, token_id, error_message, response_body, correlation_id
            ])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return log_id
            
        except Exception as e:
            logger.error(f"Error logging API call: {str(e)}")
            return None

    @staticmethod
    def update_api_log_with_usage_id(api_log_id, usage_id):
        """Update an api_logs record with the corresponding user_usage_id
        
        Args:
            api_log_id (str): The ID of the API log entry
            usage_id (str): The ID of the user_usage entry
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            UPDATE api_logs
            SET user_usage_id = ?
            WHERE id = ?
            """
            
            cursor.execute(query, [usage_id, api_log_id])
            
            # Check if any rows were affected
            rows_affected = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            if rows_affected > 0:
                logger.info(f"Updated API log {api_log_id} with usage ID {usage_id}")
                return True
            else:
                logger.warning(f"No API log found with ID {api_log_id} to update")
                return False
                
        except Exception as e:
            logger.error(f"Error updating API log with usage ID: {str(e)}")
            return False

    # New methods for endpoint access management

    @staticmethod
    def get_endpoint_by_id(endpoint_id):
        """Get endpoint details by ID
        
        Args:
            endpoint_id (str): UUID of the endpoint to retrieve
            
        Returns:
            dict: Endpoint details if found, None otherwise
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT id, endpoint_path, endpoint_name, cost, description, active
            FROM endpoints
            WHERE id = ?
            """
            
            cursor.execute(query, [endpoint_id])
            endpoint = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if endpoint:
                return {
                    "id": str(endpoint[0]),
                    "endpoint_path": endpoint[1],
                    "endpoint_name": endpoint[2],
                    "cost": float(endpoint[3]),
                    "description": endpoint[4],
                    "active": bool(endpoint[5])
                }
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving endpoint by ID: {str(e)}")
            return None

    @staticmethod
    def get_user_endpoint_access(user_id, endpoint_id):
        """Get endpoint access details for a specific user and endpoint
        
        Args:
            user_id (str): UUID of the user
            endpoint_id (str): UUID of the endpoint
            
        Returns:
            dict: Access details if found, None otherwise
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT id, user_id, endpoint_id, created_at, created_by
            FROM user_endpoint_access
            WHERE user_id = ? AND endpoint_id = ?
            """
            
            cursor.execute(query, [user_id, endpoint_id])
            access = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if access:
                return {
                    "id": str(access[0]),
                    "user_id": str(access[1]),
                    "endpoint_id": str(access[2]),
                    "created_at": access[3].isoformat() if access[3] else None,
                    "created_by": str(access[4]) if access[4] else None
                }
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving endpoint access: {str(e)}")
            return None

    @staticmethod
    def get_all_user_endpoint_access(user_id):
        """Get all endpoint access for a specific user
        
        Args:
            user_id (str): UUID of the user
            
        Returns:
            list: List of endpoint access details
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT uea.id, uea.user_id, uea.endpoint_id, uea.created_at, uea.created_by,
                   e.endpoint_path, e.endpoint_name
            FROM user_endpoint_access uea
            JOIN endpoints e ON uea.endpoint_id = e.id
            WHERE uea.user_id = ?
            """
            
            cursor.execute(query, [user_id])
            access_list = []
            
            for row in cursor.fetchall():
                access_list.append({
                    "id": str(row[0]),
                    "user_id": str(row[1]),
                    "endpoint_id": str(row[2]),
                    "created_at": row[3].isoformat() if row[3] else None,
                    "created_by": str(row[4]) if row[4] else None,
                    "endpoint_path": row[5],
                    "endpoint_name": row[6]
                })
            
            cursor.close()
            conn.close()
            
            return access_list
            
        except Exception as e:
            logger.error(f"Error retrieving all endpoint access: {str(e)}")
            return []

    @staticmethod
    def add_user_endpoint_access(user_id, endpoint_id, admin_id):
        """Grant a user access to a specific endpoint
        
        Args:
            user_id (str): UUID of the user to grant access
            endpoint_id (str): UUID of the endpoint to grant access for
            admin_id (str): UUID of the admin who is granting access
            
        Returns:
            tuple: (success, access_id_or_message)
                - success (bool): True if operation succeeded, False otherwise
                - access_id_or_message: The ID of the created access record or an error message
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Check if user already has access
            check_query = """
            SELECT id FROM user_endpoint_access 
            WHERE user_id = ? AND endpoint_id = ?
            """
            cursor.execute(check_query, [user_id, endpoint_id])
            existing = cursor.fetchone()
            
            if existing:
                cursor.close()
                conn.close()
                return True, "User already has access to this endpoint"
            
            # Add access
            access_id = str(uuid.uuid4())
            
            # Insert the access record - using the correct column names from schema
            query = """
            INSERT INTO user_endpoint_access (
                id, user_id, endpoint_id, created_by
            )
            VALUES (
                ?, ?, ?, ?
            )
            """
            
            cursor.execute(query, [access_id, user_id, endpoint_id, admin_id])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Endpoint access granted: User {user_id} can now access endpoint {endpoint_id}")
            return True, access_id
            
        except Exception as e:
            logger.error(f"Error adding endpoint access: {str(e)}")
            if conn:
                conn.rollback()
            return False, str(e)

    @staticmethod
    def add_all_endpoints_access(user_id, admin_id):
        """Grant a user access to all active endpoints
        
        Args:
            user_id (str): UUID of the user to grant access
            admin_id (str): UUID of the admin who is granting access
            
        Returns:
            tuple: (success, count_or_message)
                - success (bool): True if operation succeeded, False otherwise
                - count_or_message: Number of endpoints access was granted for, or an error message
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # Get all active endpoints
            endpoint_query = "SELECT id FROM endpoints WHERE active = 1"
            cursor.execute(endpoint_query)
            endpoints = cursor.fetchall()
            
            added_count = 0
            for endpoint in endpoints:
                endpoint_id = endpoint[0]
                
                # Check if user already has access
                check_query = """
                SELECT id FROM user_endpoint_access 
                WHERE user_id = ? AND endpoint_id = ?
                """
                cursor.execute(check_query, [user_id, endpoint_id])
                existing = cursor.fetchone()
                
                if not existing:
                    # Add access
                    access_id = str(uuid.uuid4())
                    
                    # Insert the access record using the correct column names
                    add_query = """
                    INSERT INTO user_endpoint_access (
                        id, user_id, endpoint_id, created_by
                    )
                    VALUES (
                        ?, ?, ?, ?
                    )
                    """
                    
                    cursor.execute(add_query, [access_id, user_id, endpoint_id, admin_id])
                    added_count += 1
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"All endpoint access granted: User {user_id} can now access {added_count} endpoints")
            return True, added_count
            
        except Exception as e:
            logger.error(f"Error adding all endpoints access: {str(e)}")
            if conn:
                conn.rollback()
            return False, str(e)

    @staticmethod
    def remove_user_endpoint_access(user_id, endpoint_id):
        """Remove a user's access to a specific endpoint
        
        Args:
            user_id (str): UUID of the user to remove access
            endpoint_id (str): UUID of the endpoint to remove access for
            
        Returns:
            bool: True if access was removed, False otherwise
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            DELETE FROM user_endpoint_access 
            WHERE user_id = ? AND endpoint_id = ?
            """
            cursor.execute(query, [user_id, endpoint_id])
            rows_affected = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            if rows_affected > 0:
                logger.info(f"Endpoint access removed: User {user_id} no longer has access to endpoint {endpoint_id}")
            else:
                logger.info(f"No endpoint access record found to remove for user {user_id} and endpoint {endpoint_id}")
                
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Error removing endpoint access: {str(e)}")
            if conn:
                conn.rollback()
            return False

    @staticmethod
    def remove_all_user_endpoint_access(user_id):
        """Remove all endpoint access for a user
        
        Args:
            user_id (str): UUID of the user to remove all access for
            
        Returns:
            int: Number of endpoint access entries removed
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = "DELETE FROM user_endpoint_access WHERE user_id = ?"
            cursor.execute(query, [user_id])
            rows_affected = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"All endpoint access removed: User {user_id} had {rows_affected} endpoint access records removed")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Error removing all endpoints access: {str(e)}")
            if conn:
                conn.rollback()
            return 0

    @staticmethod
    def check_user_endpoint_access(user_id, endpoint_id):
        """Check if a user has access to a specific endpoint
        
        Args:
            user_id (str): UUID of the user to check
            endpoint_id (str): UUID of the endpoint to check
            
        Returns:
            bool: True if the user has access, False otherwise
        """
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            # First check user's scope - admins can access everything
            query = "SELECT scope FROM users WHERE id = ?"
            cursor.execute(query, [user_id])
            scope_result = cursor.fetchone()
            
            if scope_result and scope_result[0] == 0:
                cursor.close()
                conn.close()
                return True
            
            # Check specific endpoint access
            query = """
            SELECT 1 FROM user_endpoint_access 
            WHERE user_id = ? AND endpoint_id = ?
            """
            cursor.execute(query, [user_id, endpoint_id])
            access_result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return access_result is not None
            
        except Exception as e:
            logger.error(f"Error checking endpoint access: {str(e)}")
            return False
