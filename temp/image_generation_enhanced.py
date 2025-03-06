import streamlit as st
import os
import requests



# Predefined style guides with detailed descriptions
STYLE_GUIDES = {
    "Photorealistic": "Create a photorealistic image with natural lighting, detailed textures, and real-world accuracy. Focus on subtle details, natural shadows, and true-to-life colors",
    "Digital Art": "Create a digital art piece with vibrant colors, clean lines, and modern styling. Emphasize bold choices, sharp details, and contemporary aesthetic",
    "Oil Painting": "Create an oil painting style image with visible brushstrokes, rich colors, and classical composition. Include texture, depth, and traditional artistic techniques",
    "Anime": "Create an anime-style illustration with characteristic styling, clean lines, and expressive features. Focus on bold colors, dynamic poses, and distinctive anime aesthetics",
    "Watercolor": "Create a watercolor style image with soft edges, transparent colors, and gentle blending. Include paper texture, color bleeds, and delicate gradients",
    "3D Render": "Create a 3D rendered image with perfect lighting, smooth surfaces, and realistic materials. Focus on depth, reflections, and precise geometric details",
    "Minimalist": "Create a minimalist design with simple shapes, limited color palette, and clean composition. Emphasize negative space, essential elements, and geometric harmony",
    "Fantasy": "Create a fantasy-style illustration with magical elements, dramatic lighting, and otherworldly atmosphere. Include ethereal effects, mystical elements, and imaginative details"
}

# Lighting presets
LIGHTING_PRESETS = {
    "Soft": "soft, diffused lighting with gentle shadows",
    "Dramatic": "high-contrast lighting with strong shadows",
    "Natural": "natural daylight with balanced shadows",
    "Studio": "professional studio lighting setup",
    "Moody": "atmospheric lighting with emphasis on mood",
}

def enhance_prompt(client, prompt, style_guide="", additional_instructions="", current_settings=None):
    """
    Enhanced prompt generation with style guidance, custom instructions, and live settings updates.
    """
    try:
        system_message = """You are an expert at crafting detailed image generation prompts. 
        Your task is to enhance user prompts to create high-quality, detailed images using DALL-E 3.
        
        Consider these aspects in your enhancement:
        - Composition: Rule of thirds, focal points, perspective
        - Lighting: Direction, intensity, atmosphere
        - Color palette: Complementary colors, mood
        - Texture and materials: Surface details, material properties
        - Depth and dimensionality: Foreground, middle ground, background
        - Atmosphere and mood: Overall feeling and emotional impact
        - Scale and proportions: Size relationships and spatial arrangement
        - Environmental context: Setting and surroundings
        
        IMPORTANT RULES:
        - NEVER include instructions for text, words, letters, numbers, or writing
        - Focus purely on visual elements and artistic style
        - Maintain the original intent while adding detail
        - Be specific about visual attributes
        - Include lighting and atmosphere details
        - Avoid any copyright-protected content or famous characters
        """

        # Incorporate current settings into the prompt enhancement
        settings_guide = ""
        if current_settings:
            style = STYLE_GUIDES.get(current_settings.get('style', ''), '')
            mood = current_settings.get('mood', 'Neutral')
            detail_level = current_settings.get('detail_level', 'Balanced')
            lighting = LIGHTING_PRESETS.get(current_settings.get('lighting', ''), '')
            composition = current_settings.get('composition', 'Centered')
            
            settings_guide = f"""
            Style: {style}
            Overall mood: {mood}
            Detail level: {detail_level}
            Lighting: {lighting}
            Composition: Use {composition} composition
            """

        # Combine all guidance
        full_prompt = f"{prompt}"
        if style_guide:
            full_prompt = f"{full_prompt}. {style_guide}"
        if settings_guide:
            full_prompt = f"{full_prompt}. {settings_guide}"
        if additional_instructions:
            full_prompt = f"{full_prompt}. {additional_instructions}"

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Enhance this prompt for image generation: {full_prompt}"}
        ]

        response = client.chat.completions.create(
            model="gpt4o",
            messages=messages,
            temperature=0.7,
        )

        return response.choices[0].message.content

    except Exception as e:
        st.error("An error occurred while enhancing the prompt. Please try again.")
        raise e
    
def improve_prompt_based_on_feedback(client, original_prompt, satisfaction, aspects, feedback_text, current_settings):
    """
    Use GPT-4 to improve the prompt based on user feedback and current settings.
    """
    try:
        # Get current style details
        style_guide = STYLE_GUIDES.get(current_settings.get('style', ''), '')
        lighting_guide = LIGHTING_PRESETS.get(current_settings.get('lighting', ''), '')
        
        # Construct detailed feedback context with current settings
        settings_details = f"""
        Current Settings:
        - Style: {current_settings.get('style', 'Not specified')} ({style_guide})
        - Mood: {current_settings.get('mood', 'Not specified')}
        - Detail Level: {current_settings.get('detail_level', 'Not specified')}
        - Lighting: {current_settings.get('lighting', 'Not specified')} ({lighting_guide})
        - Composition: {current_settings.get('composition', 'Not specified')}
        """

        feedback_context = f"""
        Original prompt: {original_prompt}
        User satisfaction level: {satisfaction}
        Areas needing improvement: {', '.join(aspects)}
        Specific feedback: {feedback_text}
        {settings_details}
        """

        system_message = """You are an expert at improving image generation prompts based on user feedback.
        Analyze the original prompt, user feedback, and current settings to create an enhanced version.
        
        Follow these guidelines:
        - If satisfaction is low, make substantial changes to the prompt
        - Address each aspect mentioned as needing improvement
        - Maintain the core concept while enhancing specific details
        - Add precise instructions for areas mentioned in feedback
        - Actively incorporate the current style settings
        - Ensure the prompt reflects the selected mood and lighting
        - Adjust composition based on the specified preference
        - Scale detail level according to the current setting
        
        IMPORTANT:
        - Never add text or writing instructions
        - Keep the focus on visual elements
        - Maintain clarity and specificity
        - Preserve the original artistic intent while incorporating new settings
        
        Return only the improved prompt without explanations."""

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Improve this image generation prompt based on feedback and settings: {feedback_context}"}
        ]

        response = client.chat.completions.create(
            model="gpt4o",
            messages=messages,
            temperature=0.7,
        )

        return response.choices[0].message.content

    except Exception as e:
        st.error("An error occurred while improving the prompt. Please try again.")
        raise e
    
def generate_image(client, prompt):
    """
    Generate image with error handling and quality settings.
    """
    try:
        response = client.images.generate(
            model="Dalle3",
            prompt=prompt,
            size="1024x1024",
            quality="hd",  # Using HD quality for better results
            n=1,
            style="vivid"  # Using vivid style for more striking images
        )
        
        return response.data[0].url
    
    except Exception as e:
        error_message = str(e).lower()
        if any(keyword in error_message for keyword in ['content_policy', 'safety', 'policy', 'violated']):
            st.error("Whoops! That image cannot be generated as it triggers content filters. Please rephrase your prompt and avoid any famous character or copyright references.")
        else:
            st.error("An unexpected error occurred while generating the image. Please try again.")
        raise e

def download_image(image_url):
    """
    Download the image from the URL and return it as bytes.
    """
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        st.error("Failed to download the generated image. Please try again.")
        raise e

def get_text_height(text):
    """
    Calculate dynamic height for text area based on content.
    """
    num_lines = len(text.split('\n')) + text.count('\n')
    num_chars = len(text)
    chars_per_line = 80  # approximate characters per line
    estimated_lines = max(num_lines, (num_chars // chars_per_line) + 1)
    return max(100, min(400, estimated_lines * 25))  # min 100px, max 400px


def image_generation(client): 
        st.title("AI Image Generator")
        
        # Initialize session state
        if 'generation_history' not in st.session_state:
            st.session_state.generation_history = []
        if 'current_prompt' not in st.session_state:
            st.session_state.current_prompt = ""
        if 'image_url' not in st.session_state:
            st.session_state.image_url = None
        if 'is_iterating' not in st.session_state:
            st.session_state.is_iterating = False
        if 'current_settings' not in st.session_state:
            st.session_state.current_settings = {}

        # Sidebar for style selection and additional controls
        with st.sidebar:
            st.header("Image Style Controls")
            
            # Style selection
            selected_style = st.selectbox(
                "Choose Art Style",
                list(STYLE_GUIDES.keys()),
                help="Select a base style for your image"
            )

            # Advanced controls
            st.subheader("Fine-tune Your Image")
            mood = st.select_slider(
                "Mood",
                options=["Dark", "Neutral", "Bright"],
                value="Neutral"
            )
            
            detail_level = st.select_slider(
                "Detail Level",
                options=["Simple", "Balanced", "Complex"],
                value="Balanced"
            )

            # Lighting selection
            lighting = st.selectbox(
                "Lighting Style",
                list(LIGHTING_PRESETS.keys()),
                help="Choose the lighting style for your image"
            )

            # Composition guidance
            composition = st.selectbox(
                "Composition",
                ["Centered", "Rule of Thirds", "Dynamic", "Symmetrical"],
                help="Select the overall composition style"
            )

        # Main content area
        if not st.session_state.is_iterating:
            st.subheader("Create Your Image")
            
            # Input area with guidance
            prompt_placeholder = "Describe what you want to see in the image..."
            prompt_help = "Tip: Be specific about colors, lighting, and important details"
            
            prompt = st.text_area(
                "Enter your prompt:",
                placeholder=prompt_placeholder,
                help=prompt_help,
                height=100
            )

            # Additional instructions
            with st.expander("Additional Instructions (Optional)"):
                additional_instructions = st.text_area(
                    "Add specific details about:",
                    placeholder="Lighting, colors, textures, perspective, etc.",
                    height=100
                )

            # Generate button
            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("Generate Image", type="primary"):
                    try:
                        with st.spinner("Creating your image..."):
                            # Store current settings
                            st.session_state.current_settings = {
                                'style': selected_style,
                                'mood': mood,
                                'detail_level': detail_level,
                                'lighting': lighting,
                                'composition': composition
                            }
                            
                            # Construct style instruction and include current settings
                            style_instruction = f"{STYLE_GUIDES[selected_style]}. {mood} mood with {LIGHTING_PRESETS[lighting]}. {composition} composition. {detail_level} detail level."
                            
                            # Generate image with current settings
                            enhanced_prompt = enhance_prompt(
                                client, 
                                prompt, 
                                style_instruction, 
                                additional_instructions, 
                                current_settings=st.session_state.current_settings
                            )
                            image_url = generate_image(client, enhanced_prompt)
                            
                            # Update session state
                            st.session_state.current_prompt = enhanced_prompt
                            st.session_state.image_url = image_url
                            st.session_state.is_iterating = True
                            
                            # Add to history with current settings
                            st.session_state.generation_history.append({
                                'prompt': prompt,
                                'enhanced_prompt': enhanced_prompt,
                                'style': selected_style,
                                'settings': st.session_state.current_settings.copy(),  # Store a copy of settings
                                'image_url': image_url
                            })

                    except Exception:
                        return
    
        # Display current image and iterative feedback
        if st.session_state.image_url:
            st.image(st.session_state.image_url)
            
            # Feedback section with immediate iteration
            st.subheader("Image Feedback & Iteration")
            
            col1, col2 = st.columns(2)
            
            with col1:
                satisfaction = st.select_slider(
                    "How satisfied are you with this image?",
                    options=["Very Unsatisfied", "Unsatisfied", "Neutral", "Satisfied", "Very Satisfied"],
                    value="Neutral"
                )
            
            with col2:
                aspects = st.multiselect(
                    "What aspects need improvement?",
                    ["Composition", "Colors", "Style", "Details", "Lighting", "Overall Quality"]
                )
            
            feedback_text = st.text_area("Specific feedback to improve the image", height=100)

            col3, col4 = st.columns(2)
            
            with col3:
                if st.button("Regenerate with Improvements", type="primary"):
                    if satisfaction != "Very Satisfied" and (aspects or feedback_text):
                        try:
                            with st.spinner("Improving and regenerating..."):
                                # Update current settings before regenerating
                                st.session_state.current_settings = {
                                    'style': selected_style,
                                    'mood': mood,
                                    'detail_level': detail_level,
                                    'lighting': lighting,
                                    'composition': composition
                                }
                                
                                # Improve prompt based on feedback and current settings
                                improved_prompt = improve_prompt_based_on_feedback(
                                    client,
                                    st.session_state.current_prompt,
                                    satisfaction,
                                    aspects,
                                    feedback_text,
                                    st.session_state.current_settings
                                )
                                
                                # Generate new image
                                new_image_url = generate_image(client, improved_prompt)
                                
                                # Update session state
                                st.session_state.current_prompt = improved_prompt
                                st.session_state.image_url = new_image_url
                                
                                # Add to history with current settings
                                st.session_state.generation_history.append({
                                    'prompt': improved_prompt,
                                    'enhanced_prompt': improved_prompt,
                                    'style': st.session_state.current_settings['style'],
                                    'settings': st.session_state.current_settings.copy(),  # Store a copy of settings
                                    'image_url': new_image_url
                                })
                                
                                st.rerun()
                        except Exception:
                            return
                    else:
                        st.info("Please provide specific aspects to improve or detailed feedback.")
        
            with col4:
                if st.button("Start New Image"):
                    st.session_state.is_iterating = False
                    st.rerun()

            # Download section - only show if user is satisfied
            if satisfaction in ["Satisfied", "Very Satisfied"]:
                st.subheader("Download Image")
                col5, col6 = st.columns([3, 1])
                
                with col5:
                    file_format = st.selectbox("Select format:", ["PNG", "JPG"])
                
                with col6:
                    if st.download_button(
                        label=f"Download Image",
                        data=requests.get(st.session_state.image_url).content,
                        file_name=f"generated_image.{file_format.lower()}",
                        mime=f"image/{file_format.lower()}"
                    ):
                        st.success(f"Image downloaded as {file_format}!")
                        st.session_state.is_iterating = False
                        st.rerun()

            # History viewer
            if st.session_state.generation_history:
                with st.expander("View Generation History"):
                    for i, entry in enumerate(reversed(st.session_state.generation_history)):
                        st.write(f"Generation {len(st.session_state.generation_history) - i}")
                        st.write(f"Style: {entry['style']}")
                        st.write(f"Settings: {entry['settings']}")
                        st.write("Original Prompt:", entry['prompt'])
                        st.write("Enhanced Prompt:", entry['enhanced_prompt'])
                        st.image(entry['image_url'], width=300)
                        
                        
                                # Add usage tips in an expander
            with st.expander("Tips for Better Results"):
                st.markdown("""
                ### Tips for Better Image Generation:
                1. **Be Specific**: Include details about colors, lighting, and composition
                2. **Avoid Copyrighted Content**: Don't reference famous characters or branded content
                3. **Use Style Controls**: Experiment with different styles and moods
                4. **Provide Clear Feedback**: Be specific about what aspects need improvement
                5. **Iterate Gradually**: Make incremental improvements rather than dramatic changes
                
                ### Effective Feedback Examples:
                - "Make the lighting more dramatic with stronger shadows"
                - "Adjust the color palette to be warmer"
                - "Increase the detail level in the background"
                - "Shift the composition to better follow the rule of thirds"
                """)

            # System status and information
            with st.sidebar:
                st.markdown("---")
                st.markdown("### Current Session Info")
                st.write(f"Generations: {len(st.session_state.generation_history)}")
                if st.session_state.current_settings:
                    st.write("Active Style:", st.session_state.current_settings['style'])
                    st.write("Current Mood:", st.session_state.current_settings['mood'])
