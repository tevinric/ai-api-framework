import streamlit as st
import base64
import mimetypes
from PIL import Image
import io

def get_image_mime_type(file):
    """Determine the MIME type of an image file."""
    return mimetypes.guess_type(file.name)[0] or "application/octet-stream"

def encode_image(image_file):
    """Encode image file to base64."""
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

def extract_text_from_content(content):
    """Extract plain text from content structure."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text_parts.append(item.get('text', ''))
        return ' '.join(text_parts)
    return ''

def clear_chat_history():
    """Clear chat history and uploaded files from session state."""
    st.session_state.chat_messages = []
    st.session_state.uploaded_files_content = []

def chatgpt(client):
    # Display the Chat Header
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1: 
        st.write(" ")
    with col2:
        st.write(" ")
    with col3:
        st.image("Telesure-logo.png", width=200)
    with col4:
        st.write(" ")
    with col5:
        st.write(" ")
    
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    if "uploaded_files_content" not in st.session_state:
        st.session_state.uploaded_files_content = []

    # Sidebar configurations
    with st.sidebar:
        st.header("Configuration")
        
        # New Chat button at the top of sidebar
        if st.button("🔄 Start New Chat", help="Clear current chat history and start fresh"):
            clear_chat_history()
            st.rerun()  # Rerun the app to refresh the UI
        
        st.divider()  # Add a visual separator after the button
        
        # Model selection
        deployment_option = st.selectbox("Select a GPT model", ("GPT-4o-mini", "GPT-4o"))
        deployment_dict = {
            "GPT-4o-mini": "gpt4omini", 
            "GPT-4o": "gpt4o"
        }
        deployment = deployment_dict[deployment_option]
        st.session_state["chatbot_deployment"] = deployment

        # Assistant type selection
        ai_behaviour = st.selectbox("Select the type of AI assistant", 
                                  ("General AI", "Coding Assistant", "Creative Assistant", 
                                   "Summarisation Assistant", "Document Analysis Assistant"))
        st.session_state["chatbot_behaviour"] = ai_behaviour

        # File upload section - only show if GPT-4o is selected
        if deployment_option == "GPT-4o":
            st.header("File Upload")
            uploaded_files = st.file_uploader("Upload files for analysis", 
                                            accept_multiple_files=True,
                                            type=['txt', 'pdf', 'doc', 'docx', 'csv', 'jpg', 'jpeg', 'png'])
            
            if uploaded_files:
                st.session_state.uploaded_files_content = []
                for file in uploaded_files:
                    file_type = file.type
                    if file_type.startswith('image/'):
                        try:
                            image_base64 = encode_image(file)
                            st.session_state.uploaded_files_content.append({
                                "filename": file.name,
                                "type": "image",
                                "content": image_base64,
                                "mime_type": get_image_mime_type(file)
                            })
                        except Exception as e:
                            st.error(f"Error processing image {file.name}: {str(e)}")
                    else:
                        try:
                            file_content = file.read()
                            if isinstance(file_content, bytes):
                                file_content = file_content.decode('utf-8', errors='ignore')
                            st.session_state.uploaded_files_content.append({
                                "filename": file.name,
                                "type": "text",
                                "content": file_content
                            })
                        except Exception as e:
                            st.error(f"Error processing file {file.name}: {str(e)}")
                
                st.success(f"Successfully loaded {len(uploaded_files)} files")
        else:
            if st.session_state.uploaded_files_content:
                st.session_state.uploaded_files_content = []

        # Temperature control
        if ai_behaviour != 'General AI':
            temperature = 0.7
        else:
            temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 
                                  help="Lower temperature for more concise responses, higher for more creative ones")
        
        st.session_state["chatbot_temperature"] = temperature

    # Define assistant behaviors
    behaviours = {
        "General AI": "I am your helpful AI assistant, how may I assist you today?",
        "Coding Assistant": "You are a coding AI assistant that must focus on providing response tailored towards coding questions.",
        "Creative Assistant": "You are a creative AI assistant providing creative answers in response to the users questions",
        "Summarisation Assistant": "You are a summarisation AI assistant. Your role is to concisely summarise the content provided by the user",
        "Document Analysis Assistant": "You are a document analysis assistant. You will analyze documents and images provided by the user and answer questions about their content."
    }

    # Create system message
    system_message = behaviours[st.session_state["chatbot_behaviour"]]

    # Help section
    with st.expander("How to use"):
        st.write('''
            1. Choose the OpenAI model that you would like to interact with. 
            2. Select the type of AI assistant that you would like to use:
                * General AI                 - Good for general tasks
                * Coding assistant           - Great for asking coding related questions
                * Creative assistance        - Great for creating content
                * Summarisation assistant    - Great for summarising pieces of text provided
                * Document Analysis assistant - Great for analyzing uploaded documents and images
            3. If using GPT-4o, you can upload files for analysis:
                * Supports text files (txt, pdf, doc, docx, csv)
                * Supports images (jpg, jpeg, png)
            4. Set the temperature of the model:
                * Low temperatures (close to 0) make the model more deterministic
                * Higher temperatures (closer to 1) make the model more creative
            5. Ask questions about the uploaded files or any other topics
            6. To start fresh, click the "Start New Chat" button in the sidebar
        ''')

    # Display conversation history
    for message in st.session_state.chat_messages:
        if message["role"] != "system":
            with st.chat_message(message["role"], avatar="user.png" if message["role"] == "user" else "DNA Navigators.png"):
                display_text = extract_text_from_content(message["content"])
                st.markdown(display_text)

    # Chat input and response
    if prompt := st.chat_input("How can I assist you today?"):
        # Create user message
        user_message_content = prompt
        
        # Create message payload that includes uploaded files
        api_message_content = []
        
        # Add any images from uploaded files
        for file in st.session_state.uploaded_files_content:
            if file["type"] == "image":
                api_message_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{file['mime_type']};base64,{file['content']}"
                    }
                })
        
        # Add the user's text prompt
        api_message_content.append({
            "type": "text",
            "text": prompt
        })
        
        # Add text file contents to the prompt
        for file in st.session_state.uploaded_files_content:
            if file["type"] == "text":
                api_message_content.append({
                    "type": "text",
                    "text": f"\nContent of {file['filename']}:\n{file['content']}"
                })

        # Store and display user message
        st.session_state.chat_messages.append({"role": "user", "content": user_message_content})
        with st.chat_message("user", avatar="user.png"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="DNA Navigators.png"):
            # Prepare messages for API call
            messages = [
                {"role": "system", "content": system_message}
            ]
            
            # Add the conversation history
            for message in st.session_state.chat_messages[1:]:  # Skip the original system message
                if message["role"] == "user":
                    if isinstance(message["content"], list):
                        # If content is a list (structured content with images)
                        messages.append({
                            "role": "user",
                            "content": message["content"]
                        })
                    else:
                        # If content is just text
                        messages.append({
                            "role": "user",
                            "content": [{"type": "text", "text": message["content"]}]
                        })
                else:
                    messages.append({
                        "role": "assistant",
                        "content": message["content"]
                    })
            
            # Add the current message
            messages.append({
                "role": "user",
                "content": api_message_content
            })

            # Make API call
            stream = client.chat.completions.create(
                model=deployment,
                messages=messages,
                stream=True,
                temperature=st.session_state["chatbot_temperature"]
            )
            response = st.write_stream(stream)
        st.session_state.chat_messages.append({"role": "assistant", "content": response})