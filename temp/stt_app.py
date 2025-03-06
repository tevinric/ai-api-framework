import requests
import json 
import streamlit as st
import Functions

def split_text(text, max_chunk_size=12000):
    """Split text into chunks of roughly equal size while preserving sentence boundaries"""
    sentences = text.replace('? ', '?|').replace('! ', '!|').replace('. ', '.|').split('|')
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        sentence_size = len(sentence)
        if current_size + sentence_size > max_chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_size = 0
        current_chunk.append(sentence)
        current_size += sentence_size
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def cleanup_long_transcription(client, deployment, transcript):
    """Handle long transcripts by processing them in chunks"""
    # Split transcript into manageable chunks
    chunks = split_text(transcript)
    cleaned_chunks = []
    
    # Process each chunk
    for i, chunk in enumerate(chunks):
        context = ""
        if i > 0:  # Add overlap context from previous chunk
            context = f"Previous context: {chunks[i-1][-200:]}\n\n"
        
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system",
                 "content": """You are tasked with refining a chunk of transcription from an audio conversation. 
                             Your goal is to enhance clarity and coherence while maintaining the original meaning.
                             Implement speaker diarization to distinguish between speakers as Speaker 1 and Speaker 2.
                             Remove filler words and correct grammatical errors. Do not remove any important context or information when cleaning the transcript.
                             If this is a continuation chunk, ensure smooth connection with the context provided."""},
                {"role": "user",
                 "content": f"{context}Please clean up this transcript chunk:\n\n{chunk}"}
            ],
            temperature=0.7
        )
        cleaned_chunks.append(response.choices[0].message.content)
    
    # Combine cleaned chunks
    return "\n".join(cleaned_chunks)

def process_prompt_with_transcript(client, deployment, cleaned_transcript, user_prompt):
    """Process user prompt against the entire transcript"""
    # Split transcript into chunks if needed
    chunks = split_text(cleaned_transcript)
    
    if len(chunks) == 1:
        # If transcript fits in one chunk, process directly
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system",
                 "content": "You are an AI assistant analyzing a transcript. Provide accurate responses based on the entire transcript content."},
                {"role": "user",
                 "content": f"Here is the transcript:\n\n{cleaned_transcript}\n\nBased on this transcript, please address the following:\n{user_prompt}"}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    else:
        # For long transcripts, process in chunks and combine insights
        all_insights = []
        
        # Process each chunk
        for chunk in chunks:
            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system",
                     "content": "You are an AI assistant analyzing a portion of a transcript. Extract relevant information related to the user's prompt."},
                    {"role": "user",
                     "content": f"Based on this portion of the transcript:\n\n{chunk}\n\nPlease extract relevant information addressing:\n{user_prompt}"}
                ],
                temperature=0.7
            )
            all_insights.append(response.choices[0].message.content)
        
        # Combine and summarize all insights
        combined_insights = "\n\n".join(all_insights)
        final_response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system",
                 "content": "You are an AI assistant combining and summarizing insights from multiple transcript analyses. Provide a coherent, complete response to the user's prompt."},
                {"role": "user",
                 "content": f"Based on these collected insights:\n\n{combined_insights}\n\nProvide a comprehensive response to:\n{user_prompt}"}
            ],
            temperature=0.7
        )
        return final_response.choices[0].message.content


def transcribe_audio(audio_file):
    headers = {
        #"Content-Type": "multipart/form-data",
        "Ocp-Apim-Subscription-Key": Functions.stt_api_key,
        "Accept": "application/json"
    }

    definition = json.dumps({
        "locales": ["en-US"],
        "profanityFilterMode": "Masked",
        "channels": []
    })

    files = {
        "audio": audio_file,
        "definition": (None, definition, "application/json")
    }

    try:
        response = requests.post(Functions.stt_endpoint, headers=headers, files=files)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Try to parse JSON, but have a fallback for non-JSON responses
        try:
            return response.json()
        except json.JSONDecodeError:
            return {
                "error": "Response was not in JSON format",
                "response_text": response.text,
                "status_code": response.status_code
            }
    
    except requests.RequestException as e:
        return {
            "error": f"Request failed: {str(e)}",
            "response_text": getattr(e.response, 'text', None),
            "status_code": getattr(e.response, 'status_code', None)
        }

def cleanup_transcription(client, deployment, transcript):  

    response = client.chat.completions.create(  
        model=deployment,  
        messages=[  
            {"role": "system",
             "content": f"""You are tasked with refining a rough transcription from an audio conversation between two speakers. Your goal is to enhance clarity and coherence while maintaining the original meaning. Additionally, you will implement speaker diarization to clearly distinguish between the two speakers.

                            Instructions:

                            Text Cleaning:
                            Remove any irrelevant filler words, false starts, and repetitions.
                            Eliminate any irregularities caused by background noise (e.g., "uh," "um," "you know," etc.).
                            Correct spelling and grammatical errors for improved readability.
                            Speaker Diarization:
                            Identify and label each speaker as "Speaker 1" and "Speaker 2."
                            Clearly indicate when each speaker is talking, using appropriate formatting (e.g., "Speaker 1: [text]" and "Speaker 2: [text]").
                            Context Preservation:
                            Ensure that the cleaned-up version retains the essence of the conversation.
                            Maintain any important context or specific terminology relevant to the discussion.
                            Formatting:
                            Present the final cleaned transcript in a structured format, ensuring it's easy to follow.
                            Use line breaks to separate different exchanges between speakers.

                            Example Input:
                            "Um, I was thinking that maybe we should, like, go to the park? I mean, uh, what do you think? You know, it could be fun."

                            Expected Output:
                            Speaker 1: I was thinking that maybe we should go to the park. What do you think? It could be fun.
                            
                            Final Note:
                            Your output should result in a polished transcript that is easy to read and understand, reflecting the natural flow of conversation while eliminating distractions."""                      
            },
            {"role": "user",
             "content": f"Here is the transcript: \n\n{transcript}"
            }  
        ],
        temperature=0.7
    )  
    return response.choices[0].message.content


def speech_to_text(client):
    
        st.title("AI Audio Transcription Service")
        
        with st.expander("How to use"):
            st.write('''
                Use AI to perform speech to text conversion for converting your audio files into text format. Follow these steps:
                
                1. Upload an audio file in supported format.
                2. Once uploaded you can play the uploaded audio (if required).
                3. When ready click "Transcribe" to start the transcription process.
                4. Once complete, you'll see:
                - Raw transcript on the left
                - Cleaned transcript on the right
                - Option to analyze the transcript with custom prompts
                5. You can download the transcripts as a text (.txt) file.
                
                For long audio files, the processing may take a few moments as the system handles the content in chunks.
            ''')
            
        # Initialize session state for transcripts if they don't exist
        if 'raw_transcript' not in st.session_state:
            st.session_state.raw_transcript = None
        if 'cleaned_transcript' not in st.session_state:
            st.session_state.cleaned_transcript = None
            
        uploaded_file = st.file_uploader("Choose an audio file", type=["wav", "mp3", "ogg", "wma", "m4a"])

        if uploaded_file is not None:
            st.audio(uploaded_file, format="audio/wav")
            
            if st.button("Transcribe"):
                with st.spinner("Transcribing..."):
                    result = transcribe_audio(uploaded_file)
                    raw_transcript = result["combinedPhrases"][0]["text"]

                    # Clean up the transcription
                    cleaned_transcript = cleanup_long_transcription(client, "gpt4omini", raw_transcript)
                    
                    cleaned_transcript = cleaned_transcript.replace("\nSpeaker", "\n\nSpeaker")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### <span style='color:orange'>Raw Transcription</span>", unsafe_allow_html=True)
                        st.write(raw_transcript)
                    
                    with col2:
                        st.markdown("### <span style='color:orange'>Cleaned Transcription</span>", unsafe_allow_html=True)
                        st.write(cleaned_transcript)

                    # Store transcripts in session state for later use
                    st.session_state.raw_transcript = raw_transcript
                    st.session_state.cleaned_transcript = cleaned_transcript

                    # Provide download button
                    combined_transcript = (
                        "### Raw Transcription ###\n\n"
                        + raw_transcript
                        + "\n\n### Cleaned Transcription ###\n\n"
                        + cleaned_transcript
                    )

                    st.download_button(
                        label="Download Transcript Results",
                        data=combined_transcript,
                        file_name="transcript.txt",
                        mime="text/plain"
                    )

        # Add prompt analysis section if transcript exists
        if st.session_state.cleaned_transcript is not None:
            st.markdown("### <span style='color:orange'>Analyze Transcript</span>", unsafe_allow_html=True)
            st.write("Enter a prompt to analyze the transcript (e.g., 'Summarize the main points', 'List all action items', etc.)")
            
            user_prompt = st.text_area(
                label="Enter your prompt:",
                placeholder="""Example prompt structure:
    1. Summarize the key points discussed
    2. List any action items or next steps
    3. Identify the main speakers and their roles
    4. Extract any mentioned dates or deadlines""",
                height=150,  # Initial height
                key="transcript_analysis_prompt"
            )
            
            if user_prompt and st.button("Analyze"):
                with st.spinner("Analyzing transcript..."):
                    analysis_result = process_prompt_with_transcript(
                        client, 
                        "gpt4o", # Use a a larger model for answering questions about the transcript
                        st.session_state.cleaned_transcript,
                        user_prompt
                    )
                    
                    st.markdown("### <span style='color:orange'>Analysis Result</span>", unsafe_allow_html=True)
                    st.write(analysis_result)
                    
                    # Add download button for analysis
                    st.download_button(
                        label="Download Analysis",
                        data=f"Prompt: {user_prompt}\n\nAnalysis:\n{analysis_result}",
                        file_name="transcript_analysis.txt",
                        mime="text/plain"
                    )
