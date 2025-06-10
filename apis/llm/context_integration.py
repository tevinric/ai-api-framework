from apis.context.context_service import ContextService
import logging

# Configure logging
logger = logging.getLogger(__name__)

def apply_context_to_system_prompt(system_prompt, context_id, user_id):
    """
    Apply a context file to a system prompt
    
    Args:
        system_prompt (str): Original system prompt
        context_id (str): ID of the context to apply
        user_id (str): ID of the user requesting context
        
    Returns:
        tuple: (enhanced_prompt, error)
            enhanced_prompt is the system prompt with context
            error is None on success, otherwise contains error message
    """
    try:
        # If no context_id provided, return original prompt
        if not context_id:
            return system_prompt, None
        
        # Get context file
        context_data, error = ContextService.get_context(
            context_id=context_id,
            user_id=user_id,
            metadata_only=False
        )
        
        if error:
            return system_prompt, f"Error loading context: {error}"
        
        # Get context content
        context_content = context_data.get("content", "")
        
        # Create enhanced prompt with context
        separator = "\n\n====================\n"
        enhanced_prompt = f"""
{system_prompt}

{separator}
CONTEXT INFORMATION:
{context_content}
{separator}

Use the above context information to help inform your responses. If the context doesn't contain relevant information, rely on your general knowledge.
"""
        
        return enhanced_prompt, None
        
    except Exception as e:
        logger.error(f"Error applying context to system prompt: {str(e)}")
        return system_prompt, f"Error applying context: {str(e)}"
