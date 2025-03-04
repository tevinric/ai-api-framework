import pyodbc
import uuid
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_connection():
    """
    Create a connection to the SQL Server database
    
    Returns:
    pyodbc.Connection: Database connection
    """
    DB_CONFIG={
        "DRIVER" : os.environ['DB_DRIVER'],
        "SERVER" : os.environ['DB_SERVER'],
        "DATABASE" : os.environ['DB_NAME'],
        "UID" : os.environ['DB_USER'],
        "PASSWORD" : os.environ['DB_PASSWORD']
    }

    connection_string = (
        f"DRIVER={DB_CONFIG['DRIVER']};"
        f"SERVER={DB_CONFIG['SERVER']};"
        f"DATABASE={DB_CONFIG['DATABASE']};"
        f"UID={DB_CONFIG['UID']};"
        f"PWD={DB_CONFIG['PASSWORD']};"
    )
    
    try:
        conn = pyodbc.connect(connection_string)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise

def create_user(user_name, user_email, common_name=None, scope=1, active=1, comment=None):
    """
    Create a new user in the database
    
    Parameters:
    user_name (str): Username
    user_email (str): User email (must be unique)
    common_name (str, optional): Common name
    scope (int, optional): Scope, either 0,1,2,3,4,5, defaults to '1' - 0 is for admin, 1 is for dev, 2 is for special user, 5 is for prod
    active (bool, optional): Active status, defaults to 1
    comment (str, optional): Comment
    
    Returns:
    dict: User information including the generated API key
    """
    if scope not in (1,2,3,4,5):
        raise ValueError("Scope must be either 1,2,3,4,5")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Generate a UUID for API key
        api_key = str(uuid.uuid4())
        
        # SQL query to insert a new user
        query = """
        INSERT INTO users (
            user_name, 
            user_email, 
            common_name, 
            api_key, 
            scope, 
            active,
            comment
        ) 
        OUTPUT INSERTED.id, INSERTED.api_key
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        # Execute the query
        cursor.execute(query, [
            user_name,
            user_email,
            common_name,
            api_key,
            scope,
            active,
            comment
        ])
        
        # Get the inserted ID and API key
        row = cursor.fetchone()
        inserted_id = str(row[0])
        inserted_api_key = str(row[1])
        
        # Commit the transaction
        conn.commit()
        cursor.close()
        conn.close()
        
        # Return user information
        user_info = {
            "id": inserted_id,
            "user_name": user_name,
            "user_email": user_email,
            "common_name": common_name,
            "api_key": inserted_api_key,
            "scope": scope,
            "active": active,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "comment": comment
        }
        
        logger.info(f"User created successfully: {user_name}, {user_email}")
        return user_info
            
    except pyodbc.IntegrityError as e:
        if "user_email" in str(e):
            logger.error(f"Email already exists: {user_email}")
            raise ValueError(f"Email already exists: {user_email}")
        logger.error(f"Database integrity error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise

def get_user_by_email(email):
    """
    Retrieve user by email
    
    Parameters:
    email (str): User email
    
    Returns:
    dict: User information or None if not found
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT id, user_name, user_email, common_name, api_key, scope, active, created_at, modified_at, comment
        FROM users
        WHERE user_email = ?
        """
        
        cursor.execute(query, [email])
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            return {
                "id": str(user[0]),
                "user_name": user[1],
                "user_email": user[2],
                "common_name": user[3],
                "api_key": str(user[4]),
                "scope": user[5],
                "active": user[6],
                "created_at": user[7].strftime("%Y-%m-%d %H:%M:%S") if user[7] else None,
                "modified_at": user[8].strftime("%Y-%m-%d %H:%M:%S") if user[8] else None,
                "comment": user[9]
            }
        return None
            
    except Exception as e:
        logger.error(f"Error retrieving user: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        # Example usage: create a new user
        new_user = create_user(
            user_name="Tevin Richard",
            user_email="tevinri@tihsa.co,za",
            common_name="Tevin Richard",
            scope=1,
            active=1,
            comment="Test user"
        )
        
        print("\n--- New User Created ---")
        for key, value in new_user.items():
            print(f"{key}: {value}")
        
        # Verify the user was created by retrieving it
        retrieved_user = get_user_by_email("tevinri@tihsa.co.za")
        if retrieved_user:
            print("\n--- User Retrieved Successfully ---")
        
    except ValueError as e:
        print(f"Validation error: {str(e)}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")