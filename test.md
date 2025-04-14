The error indicates that the API requires a "model" parameter in the request body. Let's update the code to include this parameter:

```python
import urllib.request
import json
import base64

def perform_ocr_on_pdf(pdf_file_path):
    # Read the PDF file as binary data
    with open(pdf_file_path, 'rb') as file:
        pdf_content = file.read()
    
    # Base64 encode the PDF content
    base64_encoded_pdf = base64.b64encode(pdf_content).decode('utf-8')
    
    # Prepare the request data - add the 'model' parameter
    data = {
        "file": base64_encoded_pdf,
        "file_type": "pdf",
        "model": "mistral-ocr"  # Add the model parameter
    }
    
    # Convert data to JSON
    body = str.encode(json.dumps(data))
    
    # API endpoint
    url = 'https://mistral-ocr-2503-deployment.eastus.models.ai.azure.com/v1/ocr'
    
    # API key
    api_key = 'XX'
    
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
    pdf_path = "path/to/your/document.pdf"  # Replace with your PDF file path
    ocr_result = perform_ocr_on_pdf(pdf_path)
    
    # Print or process the OCR result
    print(json.dumps(ocr_result, indent=2))
```

The key change is adding the "model" parameter with the value "mistral-ocr" to the request data. If this specific model name doesn't work, you might need to get the exact model name from the Azure documentation or your deployment details.
