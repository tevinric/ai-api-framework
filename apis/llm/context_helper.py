from flask import g
import logging

logger = logging.getLogger(__name__)

def apply_context_if_provided(system_prompt, context_id):
    """
    Helper function to apply context integration if context_id is provided
    
    Args:
        system_prompt (str): Original system prompt
        context_id (str or None): Context ID to apply, if any
        
    Returns:
        tuple: (enhanced_system_prompt, context_used)
            enhanced_system_prompt: System prompt with context applied (if any)
            context_used: The context_id that was used, or None
    """
    if context_id:
        try:
            from apis.llm.context_integration import apply_context_to_system_prompt
            enhanced_system_prompt, error = apply_context_to_system_prompt(
                system_prompt, context_id, g.user_id
            )
            if error:
                logger.warning(f"Error applying context {context_id}: {error}")
                # Continue with original system prompt but log the issue
                return system_prompt, None
            else:
                logger.info(f"Successfully applied context {context_id}")
                return enhanced_system_prompt, context_id
        except Exception as e:
            logger.error(f"Exception applying context {context_id}: {str(e)}")
            return system_prompt, None
    else:
        return system_prompt, None

def add_context_to_response(response_data, context_used):
    """
    Helper function to add context usage info to response
    
    Args:
        response_data (dict): The response data dictionary
        context_used (str or None): The context_id that was used, or None
        
    Returns:
        dict: Updated response data with context info
    """
    if context_used:
        response_data["context_used"] = context_used
    return response_data
