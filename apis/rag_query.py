from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.balanceMiddleware import check_balance
from apis.utils.config import get_openai_client
import logging
import pytz
import os
import uuid
from datetime import datetime
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.messages import AIMessage, HumanMessage
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI

# CONFIGURE LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# LLM Client for token counting
client = get_openai_client()

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def preprocess_query(query):
    """Preprocess the query similar to the Streamlit app's preprocessing"""
    # This is a simple implementation. Add more sophisticated preprocessing if needed
    return query.strip()

def format_source_documents(source_docs):
    """Format source documents similar to the Streamlit app's formatting"""
    if not source_docs:
        return ""
    
    formatted_sources = "\n\n**Sources:**\n"
    for i, doc in enumerate(source_docs):
        if hasattr(doc, 'metadata') and 'source' in doc.metadata:
            source = doc.metadata['source']
            formatted_sources += f"- {source}\n"
    
    return formatted_sources

def rag_query_route():
    """
    Query the GIT Policies RAG system with a user query
    ---
    tags:
      - RAG
    parameters:
      - name: X-Token
        in: header
        type: string
        required: true
        description: Authentication token
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - query
          properties:
            query:
              type: string
              description: The user query to process about GIT Policies
            include_sources:
              type: boolean
              default: true
              description: Whether to include source documents in the response
    produces:
      - application/json
    responses:
      200:
        description: Successful RAG response
      400:
        description: Bad request
      401:
        description: Authentication error
      500:
        description: Server error
    """
    # Get token from X-Token header
    token = request.headers.get('X-Token')
    if not token:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing X-Token header"
        }, 401)
    
    # Validate token from database
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token - not found in database"
        }, 401)
    
    # Store token ID and user ID in g for logging and balance check
    g.token_id = token_details["id"]
    g.user_id = token_details["user_id"]
    
    # Check if token is expired
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    
    # Ensure expiration_time is timezone-aware
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Validate token with Microsoft Graph
    is_valid = TokenService.validate_token(token)
    if not is_valid:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token is no longer valid with provider"
        }, 401)
    
    # Get user details
    user_id = token_details["user_id"]
    user_details = DatabaseService.get_user_by_id(user_id)
    if not user_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "User associated with token not found"
        }, 401)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate required fields
    if 'query' not in data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Missing required field: query"
        }, 400)
    
    # Extract parameters with defaults
    user_query = data.get('query', '')
    include_sources = data.get('include_sources', True)
    
    # Set bot_type to GIT Policies only
    bot_type = 'GIT Policies'
    
    try:
        # Set up paths and configurations for GIT Policies
        base_directory = os.getcwd()
        assets_folder = "assets"
        folder_name = "faiss_index"
        vectorstore_path = os.path.join(base_directory,assets_folder,folder_name)
        
        # Get the path to the GIT Policies vectorstore
        load_path = os.path.join(vectorstore_path,"git_policies")
        
        # Check if vectorstore exists
        if not os.path.exists(load_path):
            return create_api_response({
                "error": "Server Error",
                "message": f"No vectorstore found at {load_path}. Please ensure the FAISS index has been created and saved."
            }, 500)
        
        # Initialize embeddings
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "coe-chatbot-embedding3large"),
            api_key=os.environ.get("OPENAI_API_KEY"),
            azure_endpoint=os.environ.get("OPENAI_API_ENDPOINT")
        )
        
        # Load the FAISS index
        vectorstore = FAISS.load_local(
            load_path,
            embeddings,
            allow_dangerous_deserialization=True
        )
        
        # Set the GIT Policies system prompt
        system_prompt = """
                You are an AI assistant specifically trained on the Group Infrutructure & Technology Policies (GIT) for XYZ Investment Holdings (ABC). 
                Your primary function is to provide accurate and helpful information using the provided context knowledge base of the GIT policies and procedures. Adhere to the following guidelines strictly:
                
                    1. Scope of Knowledge:
                        - Only provide information related to XYZ Investment Holding's (ABC) Group Infrustructure & Technology Policies.
                        - Do not answer questions that are not IT related or provided in the supplied context.
                        - Do not attempt to answer using information that is not included in the provided context - Avoid answering from General knowledge.

                    2. Response Format:
                        - Always respond in English.
                        - DO NOT summarise the context when answering questions unless it is specifically requested by the user. You must aim to present factual response at all times using the provided context.
                        - Your response must be properly formated for display are markdown text. Ordered lists must be indented correctly and bullet points must be used where necessary.
                        - If a question is unclear, ask for clarification before attempting to answer.

                    3. Information Accuracy:
                        - Only use information from the provided context which is about XYZ Investment Holdings (ABC) GIT policies.
                        - If the supplied context does not contain information to answer the user's question then you must respond with: "I am sorry, but was not able to find a suitable match for your query. Can you please rephrase your question?  It may also be possible that the information related to your query was not included in my training base. Could you please provide more details or ask about a specific GIT policy and procedures?"

                    4. Ethical Guidelines:
                        - Never provide any information that could be considered financial advice or recommendations.
                        - Do not discuss or compare ABC's policies with that of other companies.
                        - Avoid any language that could be interpreted as making promises or guarantees about insurance coverage or claims.

                    5. Personal Information:
                        - Do not ask for or handle any personal or sensitive information
                        - If a user attempts to share personal information, advise them to contact ABC's customer service directly.

                    6. Limitations:
                        - You cannot process or issue insurance policies, file claims, or make changes to existing policies.
                        - For such actions, direct users to the T-Junction GIT policies and procedures page. 

                    7. Tone and Manner:
                        - Maintain a professional, helpful, and friendly tone at all times.
                        - Be patient with users who may not be familiar with insurance terminology.
                        - Do not be suggestive in your responses.
                        - Do not try to assume or generalise when responding to the user's query.
            """
        
        # Set LLM hyperparameters for GIT Policies
        temperature = 0.1
        frequency_penalty = 0.0
        presence_penalty = 0.0
        
        # Create the prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            ("human", "Here's some context that might be helpful: {context}")
        ])
        
        # Initialize the LLM
        llm = AzureChatOpenAI(
            openai_api_version="2023-07-01-preview",
            azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "coe-chatbot-gpt4o"),
            azure_endpoint=os.environ.get("OPENAI_API_ENDPOINT"),
            api_key=os.environ.get("OPENAI_API_KEY"),
            temperature=temperature
        )
        
        # Create document chain
        document_chain = create_stuff_documents_chain(llm, prompt_template)
        
        # Set up the retriever
        retriever = vectorstore.as_retriever(
            search_kwargs={"k": 4, "fetch_k": 8}
        )
        
        # Set up the retrieval chain
        retrieval_chain = create_retrieval_chain(retriever, document_chain)
        
        # Preprocess the query
        processed_query = preprocess_query(user_query)
        
        # Generate response
        result = retrieval_chain.invoke({
            "input": processed_query,
            "chat_history": []  # Empty for API calls
        })
        
        # Get the response
        full_response = result["answer"]
        
        # Format source documents if requested
        source_docs = result.get("context", [])
        if include_sources and source_docs:
            formatted_sources = format_source_documents(source_docs)
            full_response += formatted_sources
        
        # Log conversation to database 
        conversation_id = str(uuid.uuid4())
        endpoint_id = DatabaseService.get_endpoint_id_by_path(request.path)
        
        # Estimate token usage (simple estimation for demonstration)
        input_tokens = len(processed_query.split())
        completion_tokens = len(full_response.split())
        output_tokens = input_tokens + completion_tokens
        
        # Prepare successful response
        response_data = {
            "response": "200",
            "answer": full_response,
            "user_id": user_details["id"],
            "user_name": user_details["user_name"],
            "user_email": user_details["user_email"],
            "bot_type": bot_type,
            "input_tokens": input_tokens,
            "completion_tokens": completion_tokens,
            "output_tokens": output_tokens,
            "conversation_id": conversation_id
        }
        
        # Log API call is handled by the api_logger middleware
        
        return create_api_response(response_data, 200)
        
    except Exception as e:
        logger.error(f"RAG API error: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing RAG query: {str(e)}"
        }, 500)

def register_rag_query_routes(app):
    """Register routes with the Flask app"""
    app.route('/rag/query', methods=['POST'])(api_logger(check_balance(rag_query_route)))