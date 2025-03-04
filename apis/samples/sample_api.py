from flask import Flask, jsonify, request
import requests
from msal import ConfidentialClientApplication
import os
from datetime import datetime, timedelta
import logging
from functools import wraps
import json
import pytz
import pyodbc
import uuid

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


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
            SELECT id, user_name, user_email, common_name, api_key, scope, active
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
                    "api_key": str(user[4]),
                    "scope": user[5],
                    "active": user[6]
                }
            return None
            
        except Exception as e:
            logger.error(f"API key validation error: {str(e)}")
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
        
class TokenService:
    def __init__(self):
        Config.validate()
        self.msal_app = ConfidentialClientApplication(
            client_id=Config.CLIENT_ID,
            client_credential=Config.CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{Config.TENANT_ID}"
        )
        
    def get_token(self, user_info=None) -> dict:
        try:
            import requests
            
            # DEFINE THE TOKEN ENDPOINT
            token_endpoint = f"https://login.microsoftonline.com/{Config.TENANT_ID}/oauth2/token/"
            
            # PREPARE THE REQUEST BODY
            data = {
                "client_id": Config.CLIENT_ID,
                "client_secret": Config.CLIENT_SECRET,
                "resource": 'https://graph.microsoft.com',
                "grant_type": "client_credentials"
            }
            
            # MAKE THE POST REQUEST
            response = requests.post(token_endpoint, data=data)
            
            # CHECK IF THE REQUEST WAS SUCCESSFUL
            response.raise_for_status()
            
            # PARSE THE RESPONSE
            result = response.json()
            
            expires_on = int(result.get("expires_on"))
            utc_time = datetime.fromtimestamp(expires_on, pytz.UTC)
            gmt_plus_2 = pytz.timezone('Africa/Johannesburg')
            expires_gmt_plus_2 = utc_time.astimezone(gmt_plus_2)
            formatted_expiry = expires_gmt_plus_2.strftime('%Y-%m-%d %H:%M:%S %Z%z')
            
            if "access_token" not in result:
                logger.error(f"Token acquisition failed: {result.get('error_description', 'Unknown error')}")
                return {
                    "error": "Failed to acquire token",
                    "details": result.get("error_description", "Unknown error")
                }, 500
                
            # Log token transaction if user_info is provided
            if user_info:
                transaction_id = DatabaseService.log_token_transaction(
                    user_id=user_info["id"],
                    token_scope=user_info["scope"],
                    expires_in=result.get("expires_in"),
                    expires_on=expires_gmt_plus_2,
                    token_value=result.get("access_token")
                )
                
                if not transaction_id:
                    logger.warning("Failed to log token transaction")
                
            output = {
                "access_token": result.get("access_token"),
                "token_type": result.get("token_type"),
                "expires_in": result.get("expires_in"),
                "expires_on": formatted_expiry
            }
            return output, 200
            
        except Exception as e:
            logger.error(f"Token acquisition failed: {str(e)}")
            return {
                "error": "Failed to acquire token",
                "details": str(e)
            }, 500
 
    # CREATE THE TOKEN VALIDATION FUNCTION
    def validate_token(token):
        """ Validate token by making a simple call to MS Graph API"""
        
        try: 
            graph_endpoint = "https://graph.microsoft.com/v1.0/$metadata"
            headers = {
                "Authorization": f"Bearer {token}",      
                'Accept': 'application/xml' 
            }
            response = requests.get(graph_endpoint, headers=headers)
            
            # IF THE STATUS CODE IS 200, TOKEN IS VALID
            logger.info(f"Token validation status code: {response.status_code}")
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            return False
 
# INITIALIZE THE TOKEN SERVICE
token_service = TokenService()

# CREATE THE ENDPOINTS

### GET TOKEN ENDPOINT (Now requires API key validation)
@app.route('/get-token', methods=['GET'])
def get_token():
    """Endpoint to generate a token, protected by API key authentication"""
    
    # Get API key from request header
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return jsonify({
            "error": "Authentication Error",
            "message": "Missing API Key header (X-API-Key)"
        }), 401
    
    # Validate API key
    user_info = DatabaseService.validate_api_key(api_key)
    if not user_info:
        return jsonify({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }), 401
    
    # Get token with user info for logging
    response, status_code = token_service.get_token(user_info)
    return jsonify(response), status_code


### CREATE A SIMPLE ENDPOINT THAT WILL USE TOKEN VALIDATION
@app.route('/api/multiply', methods=['POST'])
def multiply():
    """Endpoint to multiply two numbers"""

    # GET TOKEN FROM AUTHORIZATION HEADER
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({
            "error": "Authentication Error",
            "message": "Missing or invalid Authorization Header"
            }), 401

    token = auth_header.split(' ')[1]
    
    # NEXT VALIDATE THE TOKEN
    if not token_service.validate_token(token):
        return jsonify({
            "error": "Authentication Error",
            "message": "Invalid or Expired Token"
            }), 401

    # TOKEN IS VALID, PROCESS WITH API FUNCTION
    try:
        data = request.get_json()
        if not data or 'num1' not in data or 'num2' not in data:
            return jsonify({
                "error": "Invalid Request",
                "message": "Missing required data"
                }), 400
            
        # Convert to numbers
        num1 = float(data['num1'])
        num2 = float(data['num2'])
        
        # Perform the multiplication
        result = num1 * num2
        
        return jsonify({
            "result": result
        }), 200
    
    except ValueError:
        return jsonify({
            "error": "Invalid Input ",
            "message": "Input values must be numbers"
            }), 400
        
    except Exception as e:
        logger.error(f"multiplication error: {str(e)}")
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e)
            }), 500
        
        
if __name__ == '__main__':
    app.run(debug=True)