#!/usr/bin/env python3

import argparse
import base64
import json
import os
from openai import AzureOpenAI
import sys
from datetime import datetime

# Configuration - replace with your values
AZURE_OPENAI_ENDPOINT = os.environ.get("OPENAI_API_ENDPOINT")
AZURE_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = "2024-02-01"
DEPLOYMENT = "gpt-4o"

# Reference images - update these paths to your actual reference images
REFERENCE_IMAGES = {
    "front-view": "static/resources/romeo/references/front-view.jpg",
    "rear-view": "static/resources/romeo/references/rear-view.jpg",
    "left-view": "static/resources/romeo/references/left-view.jpg",
    "right-view": "static/resources/romeo/references/right-view.jpg",
    "top-view": "static/resources/romeo/references/top-view.jpg",
    "front-left": "static/resources/romeo/references/front-left.jpg",
    "front-right": "static/resources/romeo/references/front-right.jpg",
    "rear-left": "static/resources/romeo/references/rear-left.jpg",
    "rear-right": "static/resources/romeo/references/rear-right.jpg"
}

def encode_image(image_path):
    """Encode an image file as base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_mime_type(file_path):
    """Get MIME type based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp'
    }
    return mime_types.get(ext, 'application/octet-stream')

def analyze_vehicle_image(vehicle_image_path):
    """Analyze the vehicle image against individual reference images."""
    try:
        # Initialize the OpenAI client
        client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION
        )
        
        # Ensure the vehicle image exists
        if not os.path.exists(vehicle_image_path):
            print(f"Error: Vehicle image not found at {vehicle_image_path}")
            return None
        
        # Check if reference images exist
        missing_refs = []
        for view, path in REFERENCE_IMAGES.items():
            if not os.path.exists(path):
                missing_refs.append(f"{view}: {path}")
        
        if missing_refs:
            print(f"Error: The following reference images are missing:")
            for missing in missing_refs:
                print(f"  - {missing}")
            return None
        
        # Encode vehicle image as base64
        vehicle_image_base64 = encode_image(vehicle_image_path)
        vehicle_mime_type = get_mime_type(vehicle_image_path)
        
        # Create image content list with each reference image
        reference_content = []
        for view, path in REFERENCE_IMAGES.items():
            ref_image_base64 = encode_image(path)
            ref_mime_type = get_mime_type(path)
            
            reference_content.append({
                "type": "text",
                "text": f"REFERENCE IMAGE FOR '{view}':"
            })
            reference_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{ref_mime_type};base64,{ref_image_base64}"
                }
            })
        
        # System prompt focusing on direct comparison
        system_prompt = """
        You are an expert vehicle damage assessor. Your task is to compare an uploaded vehicle image against several reference images showing standard vehicle views.
        
        You will be shown:
        1. A vehicle image to classify
        2. Reference images for these views: front-view, rear-view, left-view, right-view, top-view, front-left, front-right, rear-left, rear-right
        
        Compare the vehicle image against EACH reference image and determine which reference view it most closely matches. Pay close attention to the specific angle, visible sides, and orientation.
        
        Return a JSON object with:
        1. "vehicle_view" - EXACTLY ONE of: front-view, rear-view, left-view, right-view, top-view, front-left, front-right, rear-left, rear-right
        2. "confidence" - Your confidence level (0-100%)
        3. "damage_assessment" - Brief description of any visible damage
        """
        
        # Structure the message
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {
                    "type": "text",
                    "text": "Here is the VEHICLE IMAGE to classify:"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{vehicle_mime_type};base64,{vehicle_image_base64}"
                    }
                },
                *reference_content,
                {
                    "type": "text",
                    "text": "Compare the vehicle image against each reference image. Which reference view does it most closely match? Provide your analysis and classification."
                }
            ]}
        ]
        
        print(f"Analyzing vehicle image: {vehicle_image_path}")
        start_time = datetime.now()
        
        # Make the API call to GPT-4o
        response = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4000
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Extract response data
        result = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        
        # Parse the JSON result
        result_dict = json.loads(result)
        
        # Print analysis information
        print("\n----- Analysis Results -----")
        print(f"Vehicle View: {result_dict.get('vehicle_view', 'Unknown')}")
        print(f"Confidence: {result_dict.get('confidence', 'N/A')}")
        print(f"Damage Assessment: {result_dict.get('damage_assessment', 'No assessment provided')}")
        print("\n----- Token Usage -----")
        print(f"Prompt Tokens: {input_tokens}")
        print(f"Completion Tokens: {completion_tokens}")
        print(f"Total Tokens: {total_tokens}")
        print(f"Processing Time: {duration:.2f} seconds")
        
        return result_dict
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

if __name__ == "__main__":
    
    result = analyze_vehicle_image(r"C:\Users\E100545\Git\submissions\Vehicle_Damage_Detector\images\vehicle_4.jpeg")
    
    if result:
        # Output JSON format for easier integration with other tools
        print("\n----- JSON Output -----")
        print(json.dumps(result, indent=2))
