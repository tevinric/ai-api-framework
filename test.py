import urllib.request
import json
import base64
import os

def perform_ocr_on_pdf(pdf_file_path):
    # Read the PDF file as binary data
    with open(pdf_file_path, 'rb') as file:
        pdf_content = file.read()
    
    # Base64 encode the PDF content
    base64_encoded_pdf = base64.b64encode(pdf_content).decode('utf-8')
    
    # Prepare the request data
    data = {
        "file": base64_encoded_pdf,
        "file_type": "png"
    }
    
    # Convert data to JSON
    body = str.encode(json.dumps(data))
    
    # API endpoint
    url = 'https://mistral-ocr-2503-jqirl.eastus.models.ai.azure.com/v1/ocr'
    
    # API key
    api_key = 'XX'
    if not api_key:
        raise Exception("A key should be provided to invoke the endpoint")
    # Headers
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + api_key
    }
    
    # Create the request
    req = urllib.request.Request(url, body, headers)
    
    try:
        # Send the request and get the response
        response = urllib.request.urlopen(req)
        result = response.read().decode('utf-8')
        
        # Parse the JSON response
        ocr_result = json.loads(result)
        return ocr_result
    
    except urllib.error.HTTPError as error:
        print("The request failed with status code: " + str(error.code))
        print(error.info())
        error_response = error.read().decode("utf8", 'ignore')
        print(error_response)
        return {"error": error_response}

# Example usage
if __name__ == "__main__":
    pdf_path = r"C:\Users\E100545\Downloads\artificial-intelligence.png"
    ocr_result = perform_ocr_on_pdf(pdf_path)
    
    # Print or process the OCR result
    print(json.dumps(ocr_result, indent=2))
