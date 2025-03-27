# Install the following dependencies: azure.identity and azure-ai-inference
import os
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.identity import DefaultAzureCredential

endpoint = os.getenv("AZURE_INFERENCE_SDK_ENDPOINT", "https://ai-coe-services-dev.services.ai.azure.com/models")
model_name = os.getenv("DEPLOYMENT_NAME", "DeepSeek-V3")
# Set the AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, and AZURE_TENANT_ID environment variables
client = ChatCompletionsClient(endpoint=endpoint, credential=DefaultAzureCredential())

response = client.complete(
  messages=[
    SystemMessage(content="You are a helpful assistant."),
    UserMessage(content="What are 3 things to visit in Seattle?")
  ],
  model = model_name,
  max_tokens=1000
)

print(response)
