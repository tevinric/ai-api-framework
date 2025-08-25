
import logging
from openai import AzureOpenAI
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from apis.utils.config import (
    get_openai_client, 
    DEEPSEEK_API_KEY, 
    DEEPSEEK_V3_API_KEY, 
    LLAMA_API_KEY,
    O3_MINI_API_KEY,
    DEPLOYMENTS
    
)

client = AzureOpenAI(
azure_endpoint=DEPLOYMENTS["openai"]["primary"]["api_endpoint"],
api_key=DEPLOYMENTS["openai"]["primary"]["api_key"],
max_retries=0,
api_version="2024-10-21",)
    
    
response = client.chat.completions.create(
    model="gpt-4o",
    messages = [
            {"role": "system", "content": "You are a helpful AI assustanmt"},
            {"role": "user", "content": "Why is the sky blue?"}
        ],
    # temperature=0.4.
    # response_format={"type": "json_object"} if json_output else {"type": "text"}
    )

print("\n=== FULL TOKEN USAGE ===")
print("Response 1:")
print(f"  Prompt tokens: {response.usage.prompt_tokens}")
print(f"  Completion tokens: {response.usage.completion_tokens}")
print(f"  Total tokens: {response.usage.total_tokens}")
print(f"  Cached tokens: {response.usage.prompt_tokens_details.cached_tokens}")
print(f"  Audio promopt tokens: {response.usage.prompt_tokens_details.audio_tokens}")

import pprint
pprint.pprint(response)
