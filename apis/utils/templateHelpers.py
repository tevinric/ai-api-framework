## Used to render model costs on the LLM page - Creates a connection to DB to pull in and render model metadata from database

from .modelMetadataService import ModelMetadataService

def get_llm_template_context():
    """
    Get context data for the LLM template with all model information from database
    """
    # Get all models from database
    models_result = ModelMetadataService.get_all_models()
    
    if not models_result['success']:
        # Fallback to empty structure if database fails
        return {
            'models_by_family': {},
            'error': models_result.get('error', 'Failed to load model data')
        }
    
    models_by_family = models_result['data']
    
    # Process each model for template rendering
    processed_models = {}
    
    for family, models in models_by_family.items():
        processed_models[family] = []
        
        for model in models:
            # Add processed data for template rendering
            model['cost_stars'] = ModelMetadataService.get_cost_stars(model['modelCostIndicator'])
            model['model_tags'] = ModelMetadataService.get_model_tags(model)
            model['formatted_regions'] = ModelMetadataService.format_region_flags(model['deploymentRegions'])
            model['prompt_cost_display'] = ModelMetadataService.format_cost_display(model['promptTokens'])
            model['completion_cost_display'] = ModelMetadataService.format_cost_display(model['completionTokens'])
            model['cached_cost_display'] = ModelMetadataService.format_cost_display(model['cachedTokens'])
            
            # Format input types for display
            model['formatted_inputs'] = [input_type.strip() for input_type in model['modelInputs']]
            
            processed_models[family].append(model)
    
    return {
        'models_by_family': processed_models,
        'error': None
    }