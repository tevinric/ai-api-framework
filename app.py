from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import requests
from msal import ConfidentialClientApplication
import os
from datetime import datetime, timedelta
import logging
from functools import wraps
from flasgger import Swagger

from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.app_init import initialize_app


# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Enable CORS for all routes
CORS(app, origins=['http://localhost:3000'])

# Initialize application components
# This starts the job scheduler for async processing
initialize_app(app)

app.config['SWAGGER'] = {
    'title': 'Swagger'
}

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
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
        "version": "0.0.1"
    },
    "securityDefinitions": {
        "ApiKeyAuth": {
            "type": "apiKey",
            "name": "X-Token",
            "in": "header",
            "description": "API Key for authentication. Add your token with the X-Token header."
        }
    }
}


swagger = Swagger(app, config=swagger_config, template=swagger_template)


# INITIALIZE THE TOKEN SERVICE
token_service = TokenService()

# HTML PAGES

## HOME/LANDING
@app.route('/')
@app.route('/home')
def home():
    return render_template('index.html')

## GETTING STARTED
@app.route('/docs/getting_started')
def getting_started():
    return render_template('docs/getting_started.html')

## TOKEN SERVICES
@app.route('/docs/token_services')
def token_services():
    return render_template('docs/token_services.html')

## BALANCE MANAGEMENT
# @app.route('/docs/balance_management')
# def balance_management():
#     return render_template('docs/balance_management.html')

## FILE MANAGEMENT
@app.route('/docs/file_management')
def file_management():
    return render_template('docs/file_management.html')

from apis.utils.templateHelpers import get_llm_template_context
## LLMS
@app.route('/docs/llm')
# def llm():
#     return render_template('docs/llm.html')
def llm():
    try:
        # Get model data from database
        context = get_llm_template_context()
        
        return render_template('docs/llm.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading LLM page: {str(e)}")
        # Fallback to empty context
        return render_template('docs/llm.html', 
                             models_by_family={}, 
                             error="Failed to load model information")


## LLM CONVERSATION
@app.route('/docs/llm_conversation')
def llm_conversation():
    return render_template('docs/llm_conversation.html')

## IMAGE_GENERATION
@app.route('/docs/image_generation')
def image_generation():
    return render_template('docs/image_generation.html')

## SPEECH_SERVICE
@app.route('/docs/speech_services')
def speech_services():
    return render_template('docs/speech_services.html')

## OCR SERVICES
@app.route('/docs/ocr_services')
def ocr_services():
    return render_template('docs/ocr_services.html')

## DOCUMENT INTELLIGENCE
@app.route('/docs/document_intelligence')
def document_intelligence():
    return render_template('docs/document_intelligence.html')

## RAG
@app.route('/docs/rag')
def rag():
    return render_template('docs/rag.html')

## NLP
@app.route('/docs/nlp')
def nlp():
    return render_template('docs/nlp.html')

## file management
@app.route('/docs/file_portal')
def file_portal():
    return render_template('docs/file_portal.html')

##FAQ
@app.route('/docs/faq')
def faq():
    return render_template('docs/faq.html')

## TECHNICAL SUPPORT 
@app.route('/docs/technical_support')
def technical_support():    
    return render_template('docs/technical_support.html')

## CHANGELOG
@app.route('/docs/changelog')
def changelog():    
    return render_template('docs/changelog.html')

@app.route('/docs/coding_companion')
def coding_companion():    
    return render_template('docs/coding_companion.html')

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

# USER MANAGER 
## CREATE USER
from apis.admin.admin_create_user import register_create_user_routes
register_create_user_routes(app)
## UPDATE USER
from apis.admin.admin_update_user import register_admin_update_user_routes
register_admin_update_user_routes(app)
## GET USER DETAILS
from apis.admin.admin_get_user_details import register_get_user_details_routes
register_get_user_details_routes(app)
## GET ALL USERS
from apis.admin.admin_get_all_users import register_get_all_users_routes
register_get_all_users_routes(app)
## DELETE USER
from apis.admin.admin_delete_user import register_admin_delete_user_routes
register_admin_delete_user_routes(app)

# MODEL METADATA MANAGEMENT 
## CREATE model metadata record  
from apis.admin.admin_create_model_metadata import register_admin_create_model_metadata_routes
register_admin_create_model_metadata_routes(app)
## READ/GET model metadata record
from apis.admin.admin_read_model_metadata import register_admin_read_model_metadata_routes
register_admin_read_model_metadata_routes(app)
## UPDATE model metadata record
from apis.admin.admin_update_model_metadata import register_admin_update_model_metadata_routes
register_admin_update_model_metadata_routes(app)
## DELETE model metadata record
from apis.admin.admin_delete_model_metadata import register_admin_delete_model_metadata_routes
register_admin_delete_model_metadata_routes(app)

## RBAC ENDPOINT ACCESS CONTROL
from apis.admin.admin_endpoint_access import register_admin_endpoint_access_routes
register_admin_endpoint_access_routes(app)


# ENDPOINT MANAGEMENT
from apis.endpoint_management.admin_endpoint_management import register_admin_endpoint_routes
register_admin_endpoint_routes(app)

# BALANCE MANAGEMENT ENDPOINTS
from apis.balance_management.balance_endpoints import register_balance_routes
register_balance_routes(app)

# LLM ENDPOINTS
## DEEPSEEK
from apis.llm.deepseek_r1 import register_llm_deepseek_r1
register_llm_deepseek_r1(app)

from apis.llm.deepseekv3 import register_llm_deepseek_v3
register_llm_deepseek_v3(app)

## LLAMA
from apis.llm.llama import register_llm_llama
register_llm_llama(app)

from apis.llm.llama_32_vision_instruct import register_llm_llama_32_vision_instruct
register_llm_llama_32_vision_instruct(app)

from apis.llm.llama_4_maverick_17b_128E import register_llm_llama_4_maverick_17b_128E
register_llm_llama_4_maverick_17b_128E(app)

from apis.llm.llama_4_scout_17b_16E import register_llm_llama_4_scout_17b_16E
register_llm_llama_4_scout_17b_16E(app)

## MISTRAL
from apis.llm.mistral_medium_2505 import register_llm_mistral_medium_2505
register_llm_mistral_medium_2505(app)

from apis.llm.mistral_nemo import register_llm_mistral_nemo
register_llm_mistral_nemo(app)

## OPENAI
from apis.llm.gpt_4o_mini import register_llm_gpt_4o_mini
register_llm_gpt_4o_mini(app)

from apis.llm.gpt_4o import register_llm_gpt_4o
register_llm_gpt_4o(app)

from apis.llm.gpt_41_mini import register_llm_gpt_41_mini
register_llm_gpt_41_mini(app)

from apis.llm.gpt_41 import register_llm_gpt_41
register_llm_gpt_41(app)

from apis.llm.gpt_o1_mini import register_llm_o1_mini
register_llm_o1_mini(app)

from apis.llm.gpt_o3_mini import register_llm_o3_mini
register_llm_o3_mini(app)

from apis.llm.gpt_o4_mini import register_llm_gpt_o4_mini
register_llm_gpt_o4_mini(app)



# IMAGE GENERATION ENDPOINTS
from apis.image_generation.dalle3 import register_image_generation_routes
register_image_generation_routes(app)

from apis.image_generation.stable_diffusion_ultra import register_stable_diffusion_ultra_routes
register_stable_diffusion_ultra_routes(app)

# FILE MANAGEMENT ENDPOINTS
from apis.file_upload.upload_file import register_file_upload_routes
register_file_upload_routes(app)

# from apis.balance_management.usage_statistics import register_usage_stats_routes
# register_usage_stats_routes(app)

# JOB MANAGEMENT ENDPOINTS
from apis.jobs.job_routes import register_job_routes
register_job_routes(app)

# SPEECH SERVICES ENDPOINTS
from apis.speech_services.stt_async import register_async_speech_to_text_routes
register_async_speech_to_text_routes(app)

from apis.speech_services.tts import register_text_to_speech_routes
register_text_to_speech_routes(app)

# DOCUMENT INTELLIGENCE ENDPOINTS
from apis.document_intelligence.summarization import register_document_intelligence_routes
register_document_intelligence_routes(app)

from apis.document_intelligence.read import register_document_intelligence_read_routes
register_document_intelligence_read_routes(app)

from apis.document_intelligence.layout import register_document_intelligence_layout_routes
register_document_intelligence_layout_routes(app)

# OCR ENDPOINTS
from apis.ocr.sa_id import register_sa_id_ocr_routes
register_sa_id_ocr_routes(app)

from apis.ocr.vehicle_license_disc import register_vehicle_license_disc_routes
register_vehicle_license_disc_routes(app)

# RAG ENDPOINTS
from apis.rag.vectorstore import register_vectorstore_routes
register_vectorstore_routes(app)

from apis.rag.consume_vectorstore import register_consume_vectorstore_routes
register_consume_vectorstore_routes(app)

from apis.rag.vectorstore_advanced import register_advanced_vectorstore_routes
register_advanced_vectorstore_routes(app)

# CONVERSATIONAL AI ENDPOINTS
from apis.llm_conversation.conversation import register_llm_conversation_routes
register_llm_conversation_routes(app)

# NLP ENDPOINTS
from apis.nlp.sentiment_analysis import register_sentiment_routes
register_sentiment_routes(app)

from apis.nlp.classification import register_nlp_routes
register_nlp_routes(app)

# CONTEXT MANAGEMENT ENDPOINTS
from apis.context import register_context_routes
register_context_routes(app)

# USAGE TRACKING ENDPOINTS
from apis.usage_tracking.usage_analytics import register_usage_tracking_routes
from apis.usage_tracking.cost_management import register_cost_management_routes
register_usage_tracking_routes(app)
register_cost_management_routes(app)

# AGENT ENDPOINTS
from apis.agents.agent_routes import agents_bp
from apis.agents.tool_management_routes import tools_bp
app.register_blueprint(agents_bp)
app.register_blueprint(tools_bp)

if __name__ == '__main__':
    app.run(debug=True)
