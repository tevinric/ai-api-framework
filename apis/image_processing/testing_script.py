#!/usr/bin/env python3

import argparse
import base64
import json
import os
from openai import AzureOpenAI
import sys
from datetime import datetime

# Configuration - replace with your values
AZURE_OPENAI_ENDPOINT = os.environ.get("OPENAI_API_ENDPOINT")  # e.g. "https://your-resource.openai.azure.com/"
AZURE_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = "2024-02-01"
DEPLOYMENT = "gpt-4o"

# Path to reference image
REFERENCE_IMAGE_PATH = "static/resources/romeo/vehicle_all_views.jpg"

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
        
        # Enhanced system prompt
        system_prompt = """
        You are an expert vehicle damage assessor analyzing vehicle images. Follow these precise classification guidelines:

        IMPORTANT VEHICLE VIEW DEFINITIONS:
        - "front-view": Direct front view showing hood, grille, and both headlights equally
        - "rear-view": Direct rear view showing trunk/hatch and both taillights equally
        - "left-view": Complete driver's side view (left side when sitting in driver's seat)
        - "right-view": Complete passenger's side view (right side when sitting in driver's seat)
        - "top-view": Bird's eye view showing roof and hood from above
        - "front-left": Angled view showing front and driver's side (left side)
        - "front-right": Angled view showing front and passenger's side (right side)
        - "rear-left": Angled view showing rear and driver's side (left side)
        - "rear-right": Angled view showing rear and passenger's side (right side)

        CRITICAL LEFT VS RIGHT INDICATORS:
        - Driver position: In most vehicles, driver is on left side
        - For front-right view: You see front plus passenger's side
        - For front-left view: You see front plus driver's side
        - Side mirrors: Note their position and shape
        - Wheels: Observe which way they're turning
        - License plate visibility and angle

        Carefully examine the uploaded vehicle image against the reference image and select the SINGLE most appropriate view.

        Your output must include ONLY ONE of these exact view names: "top-view", "left-view", "right-view", "front-view", "rear-view", "front-left", "front-right", "rear-left", "rear-right".

        Also provide a brief assessment of any visible damage.

        Return a JSON object with:
        1. "vehicle_view" - EXACTLY ONE of the defined view names
        2. "damage_assessment" - Brief description of visible damage
        """
        
        # Create the message structure
        messages = [
            {"role": "system", "content": "You are a vehicle assessment expert. You will be shown two images: a vehicle to classify and a reference image. Your task is to determine which standard view the vehicle image represents."},
            {"role": "user", "content": [
                {"type": "text", "text": "First, look at ONLY this vehicle image. Which view does it show? Please analyze the directional orientation (front/rear/left/right):"},
                {"type": "image_url", "image_url": {"url": f"data:{vehicle_mime_type};base64,{vehicle_image_base64}"}}
            ]},
            {"role": "assistant", "content": "I'll analyze this vehicle image on its own first. [Analysis of vehicle orientation]"},
            {"role": "user", "content": [
                {"type": "text", "text": "Now refer to this standard reference image showing different vehicle views:"},
                {"type": "image_url", "image_url": {"url": f"data:{reference_mime_type};base64,{reference_image_base64}"}},
                {"type": "text", "text": "Match the vehicle image to ONE of these views: top-view, left-view, right-view, front-view, rear-view, front-left, front-right, rear-left, rear-right. IMPORTANT NOTE: 'front-right' means front + passenger side, 'front-left' means front + driver side."},
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
    
    result = analyze_vehicle_image(r"C:\Users\E100545\Git\submissions\Vehicle_Damage_Detector\images\vehicle_4.jpeg")
    
    if result:
        # Output JSON format for easier integration with other tools
        print("\n----- JSON Output -----")
        print(json.dumps(result, indent=2))
