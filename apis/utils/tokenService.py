from apis.utils.config import Config
from apis.utils.databaseService import DatabaseService
from msal import ConfidentialClientApplication
from datetime import datetime, timedelta
import logging
import requests
import pytz

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
            
            # Use a standard format without timezone abbreviation to avoid parsing issues
            formatted_expiry = expires_gmt_plus_2.strftime('%Y-%m-%d %H:%M:%S %z')
            
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