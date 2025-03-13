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

from flask import Flask, request, jsonify
from flasgger import Swagger

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
    """Extract bracode and/or content from vehicle license disc using Azure Document Intelligence"""
   
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
            results = [x for x in raw_barcode.split('%')]
            # print(results)

            vehicle_json = {
                "veh_no": results[5], 
                "veh_reg_no": results[6],
                "veh_register_no": results[7],
                "veh_description": results[8],
                "veh_make": results[9],
                "veh_model": results[10],
                "veh_color": results[11],
                "veh_vin_no": results[12],
                "veh_engine_no": results[13],
                "veh_expiry": results[14]
            }      

        return json.dumps(vehicle_json, indent=0)
   
   except Exception as ex:
        print(f"An error occurred: {ex}")
        return None
       
def create_json_gpt(text: str):
    """Extract bracode and/or content from vehicle license disc using Azure Document Intelligence"""
    
    try:
        system_prompt = """
            You are an OCR extraction assistant. 
            You are provided with the text from an OCR extraction from a South African vehicle license disc. You must extract the requested key pieces of information. 
            The extracted information contains both English and Afrikaans labels for each of the values to be extracted.
            Engine no./Enjinnr. is an alphanumeric value that is manufacturer specifc.
            VIN Number/Vinaginemr is an alphanumeric value that is unique to each vehicle.
        """

        assistant_prompt = """
            You are an OCR extraction assistant, which needs to extract data from a South African vehicle license disc, and return the data in a specified JSON format.
        """

        user_prompt = f"""    
            Please ensure that the resulting JSON contains only plain characters and no special characters from this text: '''{text}'''
            Respond in the following JSON format, without additional code blocks or any new lines. 
            {
                "RSA NO.": "answer",
                "License no./Lisensienr.": "answer",
                "Veh. register no./Vrt.registerer.": "answer",
                "VIN": "answer",
                "Fees/Gelde": "answer",
                "Engine no./Enjinnr.": "answer",
                "GVM/PVM": "answer",
                "Tare/Tarra": "answer",
                "Make": "answer",
                "Description/Beskrywing": "answer",
                "Persons/Personne": "answer",
                "Seated/Sittende": "answer",
                "Date of expiry/Vervaldatum": "answer"
            }                
        """

        client = create_openai_client()
        
        response = client.chat.completions.create(
            model = "gpt4o", 
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "assistant", "content": assistant_prompt}, 
                {"role": "user", "content": user_prompt}
            ],
            temperature = 0.3,
            response_format = {"type": "json_object"}
        )

        results = json.loads(response.choices[0].message.content)
        
        vehicle_json = {
            "veh_no": results["RSA NO."], 
            "veh_reg_no": results["License no./Lisensienr."],
            "veh_register_no": results["Veh. register no./Vrt.registerer."],
            "veh_description": results["Description/Beskrywing"],
            "veh_make": results["Make"],
            "veh_model": "",
            "veh_color": "",
            "veh_vin_no": results["VIN"],
            "veh_engine_no": results["Engine no./Enjinnr."],
            "veh_expiry": results["Date of expiry/Vervaldatum"]
        }  
            
        return json.dumps(vehicle_json, indent=0)
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
                                print("not a PDF417 barcode! so need to ignore")        
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
def veh_license_disc():   

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


# API SWAGGER DOCUMENTATION -> IMPORTED INTO THE MAIN FUNCTION
vehicle_license_disc_swagger_doc = {
    'tags': ['OCR'],
    'summary': 'Extract information from South African Vehicle License Disc',
    'description': '''Extract key fields from a South African Vehicle License Disc using Azure Document Intelligence and GPT-4. The system processes both English and Afrikaans text on the license disc.

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
  'https://api.example.com/vehicle_license_disc' \\
  -H 'Accept: application/json' \\
  -H 'Authorization: Bearer <your_access_token>' \\
  -H 'X-API-Key: <your_api_key>' \\
  -H 'Content-Type: multipart/form-data' \\
  -F 'file=@/path/to/license_disc.jpg'
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
            'description': 'Vehicle license disc image (Supported formats: PDF, PNG, JPG, JPEG, TIFF)'
        }
    ],
    'responses': {
        200: {
            'description': 'Successful extraction',
            'schema': {
                'type': 'object',
                'properties': {
                    'RSA NO.': {
                        'type': 'string',
                        'description': 'RSA identification number'
                    },
                    'License no./Lisensienr.': {
                        'type': 'string',
                        'description': 'Vehicle license number'
                    },
                    'Veh. register no./Vrt.registerer.': {
                        'type': 'string',
                        'description': 'Vehicle registration number'
                    },
                    'VIN': {
                        'type': 'string',
                        'description': 'Vehicle Identification Number'
                    },
                    'Fees/Gelde': {
                        'type': 'string',
                        'description': 'License fees paid'
                    },
                    'Engine no./Enjinnr.': {
                        'type': 'string',
                        'description': 'Unique engine number'
                    },
                    'GVM/PVM': {
                        'type': 'string',
                        'description': 'Gross Vehicle Mass in kg'
                    },
                    'Tare/Tarra': {
                        'type': 'string',
                        'description': 'Vehicle weight without load'
                    },
                    'Make': {
                        'type': 'string',
                        'description': 'Vehicle manufacturer'
                    },
                    'Description/Beskrywing': {
                        'type': 'string',
                        'description': 'Vehicle model and details'
                    },
                    'Persons/Personne': {
                        'type': 'string',
                        'description': 'Maximum number of persons'
                    },
                    'Seated/Sittende': {
                        'type': 'string',
                        'description': 'Number of seated persons'
                    },
                    'Date of expiry/Vervaldatum': {
                        'type': 'string',
                        'description': 'License expiry date'
                    }
                },
                'example': {
                    'RSA NO.': 'RSA123456',
                    'License no./Lisensienr.': 'ABC123GP',
                    'Veh. register no./Vrt.registerer.': 'REG123456',
                    'VIN': 'VINX123456789',
                    'Fees/Gelde': '1.1',
                    'Engine no./Enjinnr.': 'ENG123456',
                    'GVM/PVM': '2100',
                    'Tare/Tarra': '1450',
                    'Make': 'VEHICLE MAKE',
                    'Description/Beskrywing': 'VEHICLE MODEL DESCRIPTION',
                    'Persons/Personne': '5',
                    'Seated/Sittende': '5',
                    'Date of expiry/Vervaldatum': 'YYYY-MM-DD'
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