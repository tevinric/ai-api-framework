## This model is said to handel text and image input
## Check If the model can handle structure JSON output 


# Install the following dependencies: azure.identity and azure-ai-inference
import os
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

endpoint = os.getenv("AZURE_INFERENCE_SDK_ENDPOINT", "https://gaia-foundry-za.services.ai.azure.com/models")
model_name = os.getenv("DEPLOYMENT_NAME", "mistral-medium-2505")
key = os.getenv("AZURE_INFERENCE_SDK_KEY", "YOUR_KEY_HERE")
client = ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(key))

response = client.complete(
  messages=[
    SystemMessage(content="You are a helpful assistant."),
    UserMessage(content="What are 3 things to visit in Seattle?")
  ],
  model = model_name,
  max_tokens=1000
)

print(response)