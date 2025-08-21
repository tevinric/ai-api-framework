{
    "message": "Failed to create agent: Error code: 424 - {'error': {'message': 'Invalid URL (POST /v1/assistants)', 'type': 'invalid_request_error', 'param': None, 'code': None}}",
    "response": "500"
}



from openai import AsyncAzureOpenAI
from agents import set_default_openai_client, function_tool
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(override=True)

# Create OpenAI client using Azure OpenAI
openai_client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment="gpt-4o-mini"
)

# Set the default OpenAI client for the Agents SDK
set_default_openai_client(openai_client)

@function_tool()
async def get_datetime() -> str:
    """Get the current date and time."""
    from datetime import datetime
    return datetime.now().isoformat()

from agents import Agent, OpenAIChatCompletionsModel
from openai.types.chat import ChatCompletionMessageParam

# Create a banking assistant agent
banking_assistant = Agent(
    name="Banking Assistant",
    instructions="You are a helpful banking assistant. Be concise and professional.",
    model=OpenAIChatCompletionsModel(
            model="gpt-4o-mini", # This will use the deployment specified in your Azure OpenAI/APIM client
            openai_client=openai_client,
        ),
    tools=[get_datetime]  # A function tool defined elsewhere
)

from agents import Runner
import asyncio

# Run the banking assistant
result = await Runner.run(
    banking_assistant, 
    input="What is the current time?"
)

print(result.final_output)