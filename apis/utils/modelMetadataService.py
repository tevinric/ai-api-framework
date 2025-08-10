import logging
from .databaseService import DatabaseService

logger = logging.getLogger(__name__)

class ModelMetadataService:
    """Service for managing model metadata from the database"""
    
    @staticmethod
    def get_all_models():
        """
        Retrieve all active models from the database
        Returns a dictionary organized by model family for easy template rendering
        """
        try:
            db_service = DatabaseService()
            query = """
            SELECT 
                id, modelName, modelFamily, modelDescription, modelCostIndicator,
                promptTokens, completionTokens, cachedTokens, estimateCost,
                modelInputs, deploymentRegions, supportsMultimodal, 
                supportsJsonOutput, supportsContextFiles, maxContextTokens,
                apiEndpoint, isActive, created_at, modified_at,
                supportsReasoning, supportsTools
            FROM model_metadata 
            WHERE isActive = 1
            ORDER BY modelFamily, modelName
            """
            
            result = db_service.execute_query(query)
            
            if not result['success']:
                logger.error(f"Failed to fetch model metadata: {result.get('error', 'Unknown error')}")
                return {"success": False, "error": result.get('error', 'Database query failed')}
            
            # Organize models by family for template rendering
            models_by_family = {}
            
            for row in result['data']:
                model_data = {
                    'id': row[0],
                    'modelName': row[1],
                    'modelFamily': row[2],
                    'modelDescription': row[3],
                    'modelCostIndicator': row[4],
                    'promptTokens': float(row[5]) if row[5] is not None else None,
                    'completionTokens': float(row[6]) if row[6] is not None else None,
                    'cachedTokens': float(row[7]) if row[7] is not None else None,
                    'estimateCost': float(row[8]) if row[8] is not None else None,
                    'modelInputs': row[9].split(',') if row[9] else [],
                    'deploymentRegions': row[10].split(',') if row[10] else [],
                    'supportsMultimodal': bool(row[11]),
                    'supportsJsonOutput': bool(row[12]),
                    'supportsContextFiles': bool(row[13]),
                    'maxContextTokens': row[14],
                    'apiEndpoint': row[15],
                    'isActive': bool(row[16]),
                    'created_at': row[17],
                    'modified_at': row[18],
                    'reasoningSupport': bool(row[19]),
                    'toolsSupport': bool(row[20])
                }
                
                family = model_data['modelFamily']
                if family not in models_by_family:
                    models_by_family[family] = []
                
                models_by_family[family].append(model_data)
            
            logger.info(f"Successfully retrieved {len(result['data'])} active models")
            return {"success": True, "data": models_by_family}
            
        except Exception as e:
            logger.error(f"Error retrieving model metadata: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_model_by_name(model_name):
        """
        Retrieve a specific model by name
        """
        try:
            db_service = DatabaseService()
            query = """
            SELECT 
                id, modelName, modelFamily, modelDescription, modelCostIndicator,
                promptTokens, completionTokens, cachedTokens, estimateCost,
                modelInputs, deploymentRegions, supportsMultimodal, 
                supportsJsonOutput, supportsContextFiles, maxContextTokens,
                apiEndpoint, isActive, created_at, modified_at,
                supportsReasoning, supportsTools
            FROM model_metadata 
            WHERE modelName = ? AND isActive = 1
            """
            
            result = db_service.execute_query(query, (model_name,))
            
            if not result['success']:
                logger.error(f"Failed to fetch model metadata for {model_name}: {result.get('error', 'Unknown error')}")
                return {"success": False, "error": result.get('error', 'Database query failed')}
            
            if not result['data']:
                return {"success": False, "error": f"Model {model_name} not found or inactive"}
            
            row = result['data'][0]
            model_data = {
                'id': row[0],
                'modelName': row[1],
                'modelFamily': row[2],
                'modelDescription': row[3],
                'modelCostIndicator': row[4],
                'promptTokens': float(row[5]) if row[5] is not None else None,
                'completionTokens': float(row[6]) if row[6] is not None else None,
                'cachedTokens': float(row[7]) if row[7] is not None else None,
                'estimateCost': float(row[8]) if row[8] is not None else None,
                'modelInputs': row[9].split(',') if row[9] else [],
                'deploymentRegions': row[10].split(',') if row[10] else [],
                'supportsMultimodal': bool(row[11]),
                'supportsJsonOutput': bool(row[12]),
                'supportsContextFiles': bool(row[13]),
                'maxContextTokens': row[14],
                'apiEndpoint': row[15],
                'isActive': bool(row[16]),
                'created_at': row[17],
                'modified_at': row[18],
                'reasoningSupport': bool(row[19]),
                'toolsSupport': bool(row[20])
            }
            
            return {"success": True, "data": model_data}
            
        except Exception as e:
            logger.error(f"Error retrieving model metadata for {model_name}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_models_by_family(family):
        """
        Retrieve all models from a specific family (e.g., 'OpenAI', 'Meta', 'Mistral')
        """
        try:
            db_service = DatabaseService()
            query = """
            SELECT 
                id, modelName, modelFamily, modelDescription, modelCostIndicator,
                promptTokens, completionTokens, cachedTokens, estimateCost,
                modelInputs, deploymentRegions, supportsMultimodal, 
                supportsJsonOutput, supportsContextFiles, maxContextTokens,
                apiEndpoint, isActive, created_at, modified_at,
                supportsReasoning, supportsTools
            FROM model_metadata 
            WHERE modelFamily = ? AND isActive = 1
            ORDER BY modelName
            """
            
            result = db_service.execute_query(query, (family,))
            
            if not result['success']:
                logger.error(f"Failed to fetch models for family {family}: {result.get('error', 'Unknown error')}")
                return {"success": False, "error": result.get('error', 'Database query failed')}
            
            models = []
            for row in result['data']:
                model_data = {
                    'id': row[0],
                    'modelName': row[1],
                    'modelFamily': row[2],
                    'modelDescription': row[3],
                    'modelCostIndicator': row[4],
                    'promptTokens': float(row[5]) if row[5] is not None else None,
                    'completionTokens': float(row[6]) if row[6] is not None else None,
                    'cachedTokens': float(row[7]) if row[7] is not None else None,
                    'estimateCost': float(row[8]) if row[8] is not None else None,
                    'modelInputs': row[9].split(',') if row[9] else [],
                    'deploymentRegions': row[10].split(',') if row[10] else [],
                    'supportsMultimodal': bool(row[11]),
                    'supportsJsonOutput': bool(row[12]),
                    'supportsContextFiles': bool(row[13]),
                    'maxContextTokens': row[14],
                    'apiEndpoint': row[15],
                    'isActive': bool(row[16]),
                    'created_at': row[17],
                    'modified_at': row[18],
                    'reasoningSupport': bool(row[19]),
                    'toolsSupport': bool(row[20])
                }
                models.append(model_data)
            
            return {"success": True, "data": models}
            
        except Exception as e:
            logger.error(f"Error retrieving models for family {family}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def format_cost_display(cost_value):
        """
        Format cost values for display in templates
        """
        if cost_value is None:
            return "Pricing TBA"
        return f"${cost_value:.2f}/1M tokens"
    
    @staticmethod
    def format_region_flags(regions_list):
        """
        Convert region codes to flag display format
        """
        region_flags = {
            'ZA': {'name': 'South Africa', 'flag_class': 'flag-za'},
            'EU': {'name': 'Europe', 'flag_class': 'flag-eu'},
            'US': {'name': 'United States', 'flag_class': 'flag-us'}
        }
        
        formatted_regions = []
        for region in regions_list:
            region = region.strip().upper()
            if region in region_flags:
                formatted_regions.append(region_flags[region])
            else:
                # Default format for unknown regions
                formatted_regions.append({'name': region, 'flag_class': f'flag-{region.lower()}'})
        
        return formatted_regions
    
    @staticmethod
    def get_model_tags(model_data):
        """
        Generate model tags based on capabilities for display
        """
        tags = []
        
        if model_data.get('supportsMultimodal'):
            tags.append({'type': 'multimodal', 'label': 'Multimodal', 'icon': 'fas fa-image'})
        
        if model_data.get('supportsJsonOutput'):
            tags.append({'type': 'tooling', 'label': 'JSON Output', 'icon': 'fas fa-code'})
        
        if model_data.get('supportsContextFiles'):
            tags.append({'type': 'text', 'label': 'Context Files', 'icon': 'fas fa-file-text'})
        
        # Always add text tag as all models support text
        if not any(tag['type'] == 'text' for tag in tags):
            tags.insert(0, {'type': 'text', 'label': 'Text', 'icon': 'fas fa-comment'})
        
        return tags
    
    @staticmethod
    def get_cost_stars(cost_indicator):
        """
        Generate cost star display (1-5 scale)
        """
        if cost_indicator is None:
            return []
        
        stars = []
        for i in range(1, 6):
            stars.append({
                'active': i <= cost_indicator,
                'number': i
            })
        return stars