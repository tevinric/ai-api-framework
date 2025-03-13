from flask import Flask, request, jsonify
from flasgger import Swagger

import os
import io
import re
import json

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import DocumentAnalysisFeature
from azure.ai.documentintelligence.models import DocumentBarcodeKind
from azure.core.exceptions import HttpResponseError

from openai import AzureOpenAI

app = Flask(__name__)
swagger = Swagger(app)

## SECRETS
from config import OPENAI_API_KEY, OPENAI_API_ENDPOINT, DOCINT_KEY, DOCINT_ENDPOINT

# Define allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'tiff'}

def clean_text(text):
    """Clean extracted text by removing extra whitespace and special characters"""
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    # Remove any standalone newline characters
    text = text.replace('\n', ' ')
    # Remove special characters
    text = re.sub(r'[^A-Za-z0-9 ]+', '', text)
    return text

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS    

def create_openai_client():
    """Create Azure OpenAI Client"""

    try:
        client = AzureOpenAI(
            azure_endpoint = OPENAI_API_ENDPOINT,
            api_key = OPENAI_API_KEY,
            api_version = "2024-02-15-preview"
        )
        return client
    except Exception as ex:
        print(f"An error occurred: {ex}")
        return None

def create_docint_client():
    """Create Azure Document Intelligence Client"""

    try:
        client = DocumentIntelligenceClient(
            endpoint = DOCINT_ENDPOINT, 
            credential = AzureKeyCredential(DOCINT_KEY)
        )
         
        return client
    except Exception as ex:
        print(f"An error occurred: {ex}")
        return None
    
def create_docint_poller(file_stream: io.BytesIO):
    """Process content using Azure Document Intelligence"""

    try:
        document_intelligence_client = create_docint_client()

        poller = document_intelligence_client.begin_analyze_document(
            "prebuilt-layout",
            analyze_request = file_stream,
            features = [DocumentAnalysisFeature.BARCODES],
            content_type = "application/octet-stream"
        )
         
        return poller
    except Exception as ex:
        print(f"An error occurred: {ex}")
        return None

def extract_document_content(file_stream: io.BytesIO):
    """Extract bracode and/or content from South African Identity Documents using Azure Document Intelligence"""
   
    try:
        poller = create_docint_poller(file_stream)

        result = poller.result()
        return result
      
    except HttpResponseError as error:
        raise ValueError(f"Document processing error: {str(error)}") 

def create_json_barcode(raw_barcode: str):
   """Process content using Azure Document Intelligence"""

   try:
        if len(raw_barcode) > 0:
            results = [x for x in raw_barcode.split('|')]
            # print(results)

            id_json = {
                "surname": results[0], 
                "names": results[1],
                "sex": results[2],
                "nationality": results[3],
                "identity_number": results[4],
                "date_of_birth": results[5],
                "country_of_birth": results[6],
            }      

        return json.dumps(id_json, indent=0)
   
   except Exception as ex:
        print(f"An error occurred: {ex}")
        return None

def create_json_gpt(text: str):
    """Extract bracode and/or content from South African Identity Documents using Azure Document Intelligence"""
    
    try:
        system_prompt = """
            You are an OCR extraction assistant. 
            You are provided with the text from an OCR extraction and you must extract the requested key pieces of information 
            from a South African Identity Document, which is either a Smart ID Card (front or back) or a Green ID Book.
            Please ensure that the resulting JSON contains only plain characters and no special characters.
        """

        assistant_prompt = """
            You are an OCR extraction assistant, which needs to extract data from a South African Identity Documents.
            Please return the data in a specified JSON format.
        """
        
        user_prompt = f"""    
            Please ensure that the resulting JSON contains only plain characters and no special characters from this text: '''{text}'''
            Respond in the following JSON format: 
            "Surname": "answer",
            "Names": "answer",
            "Sex": "answer",
            "Nationality": "answer",
            "RSA Identity Number": "answer",
            "Date of Birth": "answer",
            "Country of Birth": "answer"
        """

        client = create_openai_client()
        
        response = client.chat.completions.create(
            model = "gpt4o", 
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "assistant", "content": assistant_prompt}, 
                {"role": "user", "content": user_prompt}
            ],
            temperature = 0.25
            # response_format = {"type": "json_object"}
        )

        # print(response.choices[0].message.content)
        results = json.loads(response.choices[0].message.content)
        
        id_json = {
            "surname": results["Surname"], 
            "names": results["Names"],
            "sex": results["Sex"],
            "nationality": results["Nationality"],
            "identity_number": results["RSA Identity Number"],
            "date_of_birth": results["Date of Birth"],
            "country_of_birth": results["Country of Birth"],
        }  
            
        return json.dumps(id_json, indent=0)
    except Exception as ex:
        print(f"An error occurred: {ex}")
        return None
    
def process_data(result):
    """Extract bracode and/or content from vehicle license disc using Azure Document Intelligence"""

    try:
        if result != None:
            for page in result.pages:
                    if page.barcodes != None:
                        for barcode_idx, barcode in enumerate(page.barcodes):
                            if barcode.kind == DocumentBarcodeKind.PDF417:
                                json_data = create_json_barcode(barcode.value)                                                
                    else:
                        extracted_text = []
                        if page.lines:                            
                            for line in page.lines:
                                if line.content:
                                    extracted_text.append(line.content)
                        
                        cleaned_text = clean_text(" ".join(extracted_text))
                        json_data = create_json_gpt(cleaned_text)          
                    
            return json_data
        else:
            print("results are empty")
    except Exception as ex:
        print(f"An error occurred: {ex}")
        return None                

# MAIN FUNCTION WITH SWAGGER API DOCUMENTATION 
def id_smart_card():   

    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    try:
        # Read and process the file
        file_stream = io.BytesIO(file.read())
        
        # Extract and clean document content
        extracted_content = extract_document_content(file_stream)
        
        # Process data and return the JSON response directly
        response = process_data(extracted_content)
        
        return response, 200, {'Content-Type': 'application/json'}

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


id_smart_card_swagger_doc = {
    'tags': ['OCR'],
    'summary': 'Extract information from South African Identity Smart Card',
    'description': '''Upload a picture of a South African Identity Smart Card and extract key fields using OCR. Only fields that are visibly recognizable will be extracted.

Required Headers:
```
Accept: application/json
Authorization: Bearer <your_access_token>
X-API-Key: <your_api_key>
Content-Type: multipart/form-data
```

Sample CURL request:
```bash
curl -X POST \\
  'https://api.example.com/id_smart_card' \\
  -H 'Accept: application/json' \\
  -H 'Authorization: Bearer <your_access_token>' \\
  -H 'X-API-Key: <your_api_key>' \\
  -H 'Content-Type: multipart/form-data' \\
  -F 'file=@/path/to/id_card.jpg'
```''',
    'security': [
        {'ApiKeyAuth': [], 'BearerAuth': []}
    ],
    'parameters': [
        {
            'name': 'file',
            'in': 'formData',
            'type': 'file',
            'required': True,
            'description': 'ID Smart Card image (Supported formats: PDF, PNG, JPG, JPEG, TIFF)'
        }
    ],
    'responses': {
        200: {
            'description': 'Successful extraction',
            'schema': {
                'type': 'object',
                'properties': {
                    'Surname': {
                        'type': 'string',
                        'description': 'Last name of the ID holder'
                    },
                    'Names': {
                        'type': 'string',
                        'description': 'Given names of the ID holder'
                    },
                    'Sex': {
                        'type': 'string',
                        'description': 'Gender of the ID holder'
                    },
                    'Nationality': {
                        'type': 'string',
                        'description': 'Nationality of the ID holder'
                    },
                    'RSA Identity Number': {
                        'type': 'string',
                        'description': '13-digit South African ID number'
                    },
                    'Date of Birth': {
                        'type': 'string',
                        'description': 'Birth date in DD/MM/YYYY format'
                    },
                    'Country of Birth': {
                        'type': 'string',
                        'description': 'Country where ID holder was born'
                    }
                },
                'example': {
                    'Surname': 'DOE',
                    'Names': 'JOHN',
                    'Sex': 'M',
                    'Nationality': 'RSA',
                    'RSA Identity Number': '1234567891011',
                    'Date of Birth': 'DD MMM YYYY',
                    'Country of Birth': 'SOUTH AFRICA'
                }
            }
        },
        400: {
            'description': 'Bad request',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {
                        'type': 'string',
                        'enum': [
                            'No file provided',
                            'No selected file',
                            'Invalid file type. Allowed types: PNG, JPG, JPEG, PDF, TIFF'
                        ]
                    }
                }
            }
        },
        401: {
            'description': 'Authentication error',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {
                        'type': 'string',
                        'enum': [
                            'Missing access token',
                            'Missing API key',
                            'Invalid access token',
                            'Invalid API key'
                        ]
                    }
                }
            }
        },
        500: {
            'description': 'Server error',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {
                        'type': 'string',
                        'description': 'Error message details'
                    }
                }
            }
        }
    },
    'consumes': ['multipart/form-data'],
    'produces': ['application/json']
}