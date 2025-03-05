from flask import Flask, jsonify, request, render_template
import requests
from msal import ConfidentialClientApplication
import os
from datetime import datetime, timedelta
import logging
from functools import wraps
from flasgger import Swagger

from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService


# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.config['SWAGGER'] = {
    'title': 'Swagger'
}

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "API Documentation",
        "description": "API endpoints with authentication",
        "version": "1.0.0"
    }     
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)


# INITIALIZE THE TOKEN SERVICE
token_service = TokenService()

# Serve the index.html file
# @app.route('/')
# def index():
#     return render_template('index.html')

# TOKEN SERVICE ENDPOINTS
## GET TOKEN
from apis.token_services.get_token import register_routes as get_token_endpoint 
get_token_endpoint(app)
## GET TOKEN DETAILS
from apis.token_services.get_token_details import register_token_details_routes as get_token_details_endpoint
get_token_details_endpoint(app)
## REFRESH TOKEN 
from apis.token_services.refresh_token import register_refresh_token_routes
register_refresh_token_routes(app)

# ADMIN ENDPOINTS
## CREATE USER
from apis.admin.admin_create_user import register_create_user_routes
register_create_user_routes(app)
## UPDATE USER
from apis.admin.admin_update_user import register_admin_update_user_routes
register_admin_update_user_routes(app)
## DELETE USER
# from apis.admin.admin_delete_user import register_admin_delete_user_routes
# register_admin_delete_user_routes(app)

# ENDPOINT MANAGEMENT
from apis.endpoint_management.admin_endpoint_management import register_admin_endpoint_routes
register_admin_endpoint_routes(app)

from apis.balance_endpoints import register_balance_routes
register_balance_routes(app)


from apis.llm.deepseek_r1 import register_llm_deepseek_r1
register_llm_deepseek_r1(app)

from apis.llm.llama import register_llm_llama
register_llm_llama(app)

from apis.llm.gpt_4o_mini import register_llm_gpt_4o_mini
register_llm_gpt_4o_mini(app)

from apis.llm.gpt_4o import register_llm_gpt_4o
register_llm_gpt_4o(app)

from apis.llm.gpt_o1_mini import register_llm_o1_mini
register_llm_o1_mini(app)

from apis.rag_query import register_rag_query_routes
register_rag_query_routes(app)

from apis.image_generation.dalle3 import register_image_generation_routes
register_image_generation_routes(app)


from apis.file_upload.upload_file import register_file_upload_routes
register_file_upload_routes(app)

if __name__ == '__main__':
    app.run()