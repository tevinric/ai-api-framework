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
@app.route('/docs/balance_management')
def balance_management():
    return render_template('docs/balance_management.html')

## FILE MANAGEMENT
@app.route('/docs/file_management')
def file_management():
    return render_template('docs/file_management.html')

## LLMS
@app.route('/docs/llm')
def llm():
    return render_template('docs/llm.html')

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

from apis.balance_management.balance_endpoints import register_balance_routes
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

from apis.llm.deepseekv3 import register_llm_deepseek_v3
register_llm_deepseek_v3(app)

from apis.llm.gpt_o3_mini import register_llm_o3_mini
register_llm_o3_mini(app)

from apis.image_generation.dalle3 import register_image_generation_routes
register_image_generation_routes(app)

from apis.image_generation.stable_diffusion_ultra import register_stable_diffusion_ultra_routes
register_stable_diffusion_ultra_routes(app)

from apis.file_upload.upload_file import register_file_upload_routes
register_file_upload_routes(app)

from apis.balance_management.usage_statistics import register_usage_stats_routes
register_usage_stats_routes(app)

from apis.speech_services.stt import register_speech_to_text_routes
register_speech_to_text_routes(app)

from apis.speech_services.stt_diarize import register_speech_to_text_diarize_routes
register_speech_to_text_diarize_routes(app)

from apis.document_intelligence.summarization import register_document_intelligence_routes
register_document_intelligence_routes(app)

from apis.document_intelligence.read import register_document_intelligence_read_routes
register_document_intelligence_read_routes(app)

from apis.document_intelligence.layout import register_document_intelligence_layout_routes
register_document_intelligence_layout_routes(app)

from apis.ocr.sa_id import register_sa_id_ocr_routes
register_sa_id_ocr_routes(app)

from apis.ocr.vehicle_license_disc import register_vehicle_license_disc_routes
register_vehicle_license_disc_routes(app)

from apis.rag.vectorstore import register_vectorstore_routes
register_vectorstore_routes(app)

from apis.rag.consume_vectorstore import register_consume_vectorstore_routes
register_consume_vectorstore_routes(app)

from apis.rag.vectorstore_advanced import register_advanced_vectorstore_routes
register_advanced_vectorstore_routes(app)

from apis.llm_conversation.conversation import register_llm_conversation_routes
register_llm_conversation_routes(app)

from apis.nlp.sentiment_analysis import register_sentiment_routes
register_sentiment_routes(app)

from apis.nlp.classification import register_nlp_routes
register_nlp_routes(app)

from apis.llm_conversation.insurance_conversation import register_insurance_bot_routes
register_insurance_bot_routes(app)

if __name__ == '__main__':
    app.run(debug=True)
    


