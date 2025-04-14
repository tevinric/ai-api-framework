#!/usr/bin/env python3

import argparse
import base64
import json
import os
from openai import AzureOpenAI
import sys
from datetime import datetime

# Configuration - replace with your values
AZURE_OPENAI_ENDPOINT = "your_azure_endpoint"  # e.g. "https://your-resource.openai.azure.com/"
AZURE_OPENAI_API_KEY = "your_api_key"
AZURE_OPENAI_API_VERSION = "2024-02-01"
DEPLOYMENT = "gpt-4o"

# Path to reference image
REFERENCE_IMAGE_PATH = "static/resources/romeo/vehicle-reference-views.jpg"

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
    """Analyze the vehicle image against the reference image."""
    try:
        # Initialize the OpenAI client
        client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION
        )
        
        # Ensure the reference image exists
        if not os.path.exists(REFERENCE_IMAGE_PATH):
            print(f"Error: Reference image not found at {REFERENCE_IMAGE_PATH}")
            return None
        
        # Ensure the vehicle image exists
        if not os.path.exists(vehicle_image_path):
            print(f"Error: Vehicle image not found at {vehicle_image_path}")
            return None
        
        # Encode images as base64
        vehicle_image_base64 = encode_image(vehicle_image_path)
        reference_image_base64 = encode_image(REFERENCE_IMAGE_PATH)
        
        # Get MIME types
        vehicle_mime_type = get_mime_type(vehicle_image_path)
        reference_mime_type = get_mime_type(REFERENCE_IMAGE_PATH)
        
        # Create system prompt
        system_prompt = """
        You are an expert vehicle damage assessor. Your task is to analyze the uploaded vehicle image and compare it to the reference image containing standard vehicle views.
        
        The reference image shows different views of a vehicle: front, left-side, right-side, rear, and top-view.
        
        Based on the uploaded image, determine which of these standard views the uploaded image most closely matches, ignoring any damage present.
        
        Your output must include ONLY ONE of these exact view names: "front", "left-side", "right-side", "rear", or "top-view".
        
        Additionally, provide a brief assessment of any damage visible in the uploaded image.
        
        Format your response as a JSON object with two fields:
        1. "vehicle_view" - MUST be exactly one of: "front", "left-side", "right-side", "rear", or "top-view"
        2. "damage_assessment" - A brief description of visible damage, if any
        """
        
        # Create the message structure
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {
                    "type": "text",
                    "text": "I need to identify which standard vehicle view this image represents, using the reference image provided."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{vehicle_mime_type};base64,{vehicle_image_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": "Here is the reference image showing the standard vehicle views:"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{reference_mime_type};base64,{reference_image_base64}"
                    }
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
            temperature=0.3,
            max_tokens=1000
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
    parser = argparse.ArgumentParser(description="Analyze vehicle images using GPT-4o")
    parser.add_argument("image_path", help="Path to the vehicle image to analyze")
    args = parser.parse_args()
    
    result = analyze_vehicle_image(args.image_path)
    
    if result:
        # Output JSON format for easier integration with other tools
        print("\n----- JSON Output -----")
        print(json.dumps(result, indent=2))
