import streamlit as st
from openai import AzureOpenAI
import fitz  # PyMuPDF
import docx
import io
import json
from typing import List, Dict
import os

#from config import api_key, endpoint

api_key = os.environ.get("AZURE_OPENAI_KEY")
endpoint  = os.environ.get("AZURE_OPENAI_ENDPOINT")

# Initialize Azure OpenAI client
def init_azure_openai_client():
    client = AzureOpenAI(
        azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
        api_key=os.getenv('AZURE_OPENAI_KEY'),
        api_version="2024-02-15-preview"
    )
    return client

def extract_text_from_pdf(file_bytes):
    with fitz.open(stream=file_bytes.read(), filetype="pdf") as doc:
        text = ""
        for page in doc:
            text += page.get_text()
    return text

def extract_text_from_docx(file_bytes):
    doc = docx.Document(io.BytesIO(file_bytes.read()))
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

def generate_extraction_prompt(text: str, fields: List[str]) -> str:
    fields_str = "\n".join([f"- {field}" for field in fields])
    prompt = f"""Extract the following fields from the document text. 
Provide the output in JSON format with the field names as keys.
If a field is not found, return null for that field.

Fields to extract:
{fields_str}

Document text:
{text}

Provide only the JSON output, nothing else."""
    return prompt

def extract_data(client, text: str, fields: List[str]) -> Dict:
    prompt = generate_extraction_prompt(text, fields)
    
    response = client.chat.completions.create(
        model="gpt4omini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts specific fields from documents and returns them in JSON format."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )
    
    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON response"}

def data_extraction(client):
    
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
    
    
    # App header
    st.markdown("<h1 style='text-align: center;'>Document Data Field Extractor</h1>", unsafe_allow_html=True)
    st.write("Upload a document and specify the fields you want to extract.")

    # Initialize session state
    if 'fields' not in st.session_state:
        st.session_state.fields = [""]

    # File uploader
    uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'docx'])

    # Add field button
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("Add Field") and len(st.session_state.fields) < 30:
            st.session_state.fields.append("")

    # Remove field button
    with col1:
        if st.button("Remove Last Field") and len(st.session_state.fields) > 1:
            st.session_state.fields.pop()

    # Field input
    fields_to_extract = []
    for i in range(len(st.session_state.fields)):
        # Get the current value from session state, defaulting to empty string if index doesn't exist
        current_value = st.session_state.fields[i] if i < len(st.session_state.fields) else ""
        
        field = st.text_input(
            f"Field {i+1}", 
            key=f"field_{i}",
            value=current_value
        )
        if field:
            fields_to_extract.append(field)
            # Update session state
            st.session_state.fields[i] = field

    # Display current number of fields
    st.write(f"Current number of fields: {len(st.session_state.fields)}/30")

    if uploaded_file and fields_to_extract:
        try:
            # Extract text based on file type
            if uploaded_file.name.endswith('.pdf'):
                text = extract_text_from_pdf(uploaded_file)
            elif uploaded_file.name.endswith('.docx'):
                text = extract_text_from_docx(uploaded_file)
            else:
                st.error("Unsupported file type")
                return

            # Initialize Azure OpenAI client
            client = init_azure_openai_client()

            # Display processing message
            with st.spinner("Extracting data..."):
                extracted_data = extract_data(client, text, fields_to_extract)

            # Display results
            st.subheader("Extracted Data")
            st.json(extracted_data)

            # Download button for JSON
            if extracted_data:
                json_str = json.dumps(extracted_data, indent=2)
                st.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name="extracted_data.json",
                    mime="application/json"
                )

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

