import os
import logging

logger = logging.getLogger(__name__)

class DeploymentConfig:
    """
    Centralized deployment configuration for all AI models.
    Each model has primary, secondary, and tertiary deployments for failover.
    """
    
    # Configuration structure for all models
    # Each model should have primary, secondary, tertiary deployments
    DEPLOYMENTS = {
        "gpt-4o": {
            "primary": {
                "type": "azure_openai",
                "endpoint": os.environ.get("OPENAI_API_ENDPOINT", "https://ai-coe-services-dev.openai.azure.com/"),
                "api_key": os.environ.get("OPENAI_API_KEY"),
                "deployment": "gpt-4o",
                "api_version": "2024-02-01"
            },
            "secondary": {
                "type": "azure_openai", 
                "endpoint": os.environ.get("OPENAI_API_ENDPOINT_SECONDARY", "https://ai-coe-services-backup.openai.azure.com/"),
                "api_key": os.environ.get("OPENAI_API_KEY_SECONDARY", os.environ.get("OPENAI_API_KEY")),
                "deployment": "gpt-4o-backup",
                "api_version": "2024-02-01"
            },
            "tertiary": {
                "type": "azure_openai",
                "endpoint": os.environ.get("OPENAI_API_ENDPOINT_TERTIARY", "https://ai-coe-services-tertiary.openai.azure.com/"),
                "api_key": os.environ.get("OPENAI_API_KEY_TERTIARY", os.environ.get("OPENAI_API_KEY")),
                "deployment": "gpt-4o-tertiary", 
                "api_version": "2024-02-01"
            }
        },
        
        "gpt-4o-mini": {
            "primary": {
                "type": "azure_openai",
                "endpoint": os.environ.get("OPENAI_API_ENDPOINT", "https://ai-coe-services-dev.openai.azure.com/"),
                "api_key": os.environ.get("OPENAI_API_KEY"),
                "deployment": "gpt-4o-mini",
                "api_version": "2024-02-01"
            },
            "secondary": {
                "type": "azure_openai",
                "endpoint": os.environ.get("OPENAI_API_ENDPOINT_SECONDARY", "https://ai-coe-services-backup.openai.azure.com/"),
                "api_key": os.environ.get("OPENAI_API_KEY_SECONDARY", os.environ.get("OPENAI_API_KEY")),
                "deployment": "gpt-4o-mini-backup",
                "api_version": "2024-02-01"
            },
            "tertiary": {
                "type": "azure_openai",
                "endpoint": os.environ.get("OPENAI_API_ENDPOINT_TERTIARY", "https://ai-coe-services-tertiary.openai.azure.com/"),
                "api_key": os.environ.get("OPENAI_API_KEY_TERTIARY", os.environ.get("OPENAI_API_KEY")),
                "deployment": "gpt-4o-mini-tertiary",
                "api_version": "2024-02-01"
            }
        },
        
        "o1-mini": {
            "primary": {
                "type": "azure_openai",
                "endpoint": os.environ.get("OPENAI_API_ENDPOINT", "https://ai-coe-services-dev.openai.azure.com/"),
                "api_key": os.environ.get("OPENAI_API_KEY"),
                "deployment": "o1-mini",
                "api_version": "2024-02-01"
            },
            "secondary": {
                "type": "azure_openai",
                "endpoint": os.environ.get("OPENAI_API_ENDPOINT_SECONDARY", "https://ai-coe-services-backup.openai.azure.com/"),
                "api_key": os.environ.get("OPENAI_API_KEY_SECONDARY", os.environ.get("OPENAI_API_KEY")),
                "deployment": "o1-mini-backup", 
                "api_version": "2024-02-01"
            },
            "tertiary": {
                "type": "azure_openai",
                "endpoint": os.environ.get("OPENAI_API_ENDPOINT_TERTIARY", "https://ai-coe-services-tertiary.openai.azure.com/"),
                "api_key": os.environ.get("OPENAI_API_KEY_TERTIARY", os.environ.get("OPENAI_API_KEY")),
                "deployment": "o1-mini-tertiary",
                "api_version": "2024-02-01"
            }
        },
        
        "o3-mini": {
            "primary": {
                "type": "azure_openai",
                "endpoint": os.environ.get("O3_MINI_ENDPOINT", "https://ai-coe-services-dev.openai.azure.com/"),
                "api_key": os.environ.get("O3_MINI_API_KEY", os.environ.get("OPENAI_API_KEY")),
                "deployment": "o3-mini",
                "api_version": "2024-12-01-preview"
            },
            "secondary": {
                "type": "azure_openai",
                "endpoint": os.environ.get("O3_MINI_ENDPOINT_SECONDARY", "https://ai-coe-services-backup.openai.azure.com/"),
                "api_key": os.environ.get("O3_MINI_API_KEY_SECONDARY", os.environ.get("OPENAI_API_KEY")),
                "deployment": "o3-mini-backup",
                "api_version": "2024-12-01-preview"
            },
            "tertiary": {
                "type": "azure_openai",
                "endpoint": os.environ.get("O3_MINI_ENDPOINT_TERTIARY", "https://ai-coe-services-tertiary.openai.azure.com/"),
                "api_key": os.environ.get("O3_MINI_API_KEY_TERTIARY", os.environ.get("OPENAI_API_KEY")),
                "deployment": "o3-mini-tertiary",
                "api_version": "2024-12-01-preview"
            }
        },
        
        "deepseek-r1": {
            "primary": {
                "type": "azure_inference",
                "endpoint": os.environ.get("DEEPSEEK_R1_ENDPOINT", "https://deepseek-r1-aiapi.eastus.models.ai.azure.com"),
                "api_key": os.environ.get("DEEPSEEK_API_KEY"),
                "deployment": None  # Not needed for Azure AI Inference
            },
            "secondary": {
                "type": "azure_inference",
                "endpoint": os.environ.get("DEEPSEEK_R1_ENDPOINT_SECONDARY", "https://deepseek-r1-aiapi-backup.eastus.models.ai.azure.com"),
                "api_key": os.environ.get("DEEPSEEK_API_KEY_SECONDARY", os.environ.get("DEEPSEEK_API_KEY")),
                "deployment": None
            },
            "tertiary": {
                "type": "azure_inference",
                "endpoint": os.environ.get("DEEPSEEK_R1_ENDPOINT_TERTIARY", "https://deepseek-r1-aiapi-tertiary.eastus.models.ai.azure.com"),
                "api_key": os.environ.get("DEEPSEEK_API_KEY_TERTIARY", os.environ.get("DEEPSEEK_API_KEY")),
                "deployment": None
            }
        },
        
        "deepseek-v3": {
            "primary": {
                "type": "azure_inference",
                "endpoint": os.environ.get("DEEPSEEK_V3_ENDPOINT", "https://ai-coe-services-dev.services.ai.azure.com/models"),
                "api_key": os.environ.get("DEEPSEEK_V3_API_KEY", os.environ.get("OPENAI_API_KEY")),
                "model_name": "DeepSeek-V3"
            },
            "secondary": {
                "type": "azure_inference",
                "endpoint": os.environ.get("DEEPSEEK_V3_ENDPOINT_SECONDARY", "https://ai-coe-services-backup.services.ai.azure.com/models"),
                "api_key": os.environ.get("DEEPSEEK_V3_API_KEY_SECONDARY", os.environ.get("OPENAI_API_KEY")),
                "model_name": "DeepSeek-V3"
            },
            "tertiary": {
                "type": "azure_inference",
                "endpoint": os.environ.get("DEEPSEEK_V3_ENDPOINT_TERTIARY", "https://ai-coe-services-tertiary.services.ai.azure.com/models"),
                "api_key": os.environ.get("DEEPSEEK_V3_API_KEY_TERTIARY", os.environ.get("OPENAI_API_KEY")),
                "model_name": "DeepSeek-V3"
            }
        },
        
        "llama-3-1-405b": {
            "primary": {
                "type": "azure_inference",
                "endpoint": os.environ.get("LLAMA_ENDPOINT", "https://Meta-Llama-3-1-405B-aiapis.eastus.models.ai.azure.com"),
                "api_key": os.environ.get("LLAMA_API_KEY"),
                "deployment": None
            },
            "secondary": {
                "type": "azure_inference", 
                "endpoint": os.environ.get("LLAMA_ENDPOINT_SECONDARY", "https://Meta-Llama-3-1-405B-aiapis-backup.eastus.models.ai.azure.com"),
                "api_key": os.environ.get("LLAMA_API_KEY_SECONDARY", os.environ.get("LLAMA_API_KEY")),
                "deployment": None
            },
            "tertiary": {
                "type": "azure_inference",
                "endpoint": os.environ.get("LLAMA_ENDPOINT_TERTIARY", "https://Meta-Llama-3-1-405B-aiapis-tertiary.eastus.models.ai.azure.com"),
                "api_key": os.environ.get("LLAMA_API_KEY_TERTIARY", os.environ.get("LLAMA_API_KEY")),
                "deployment": None
            }
        }
    }
    
    @classmethod
    def get_deployment_config(cls, model_name, tier="primary"):
        """
        Get deployment configuration for a specific model and tier.
        
        Args:
            model_name (str): Name of the model (e.g., "gpt-4o")
            tier (str): Deployment tier ("primary", "secondary", "tertiary")
            
        Returns:
            dict: Deployment configuration or None if not found
        """
        try:
            return cls.DEPLOYMENTS.get(model_name, {}).get(tier)
        except Exception as e:
            logger.error(f"Error getting deployment config for {model_name} {tier}: {str(e)}")
            return None
    
    @classmethod
    def get_all_tiers(cls, model_name):
        """
        Get all deployment tiers for a model in order (primary, secondary, tertiary).
        
        Args:
            model_name (str): Name of the model
            
        Returns:
            list: List of (tier_name, config) tuples
        """
        try:
            model_config = cls.DEPLOYMENTS.get(model_name, {})
            tiers = []
            
            for tier in ["primary", "secondary", "tertiary"]:
                config = model_config.get(tier)
                if config:
                    tiers.append((tier, config))
            
            return tiers
        except Exception as e:
            logger.error(f"Error getting all tiers for {model_name}: {str(e)}")
            return []
    
    @classmethod
    def add_model_deployment(cls, model_name, deployments):
        """
        Add or update deployment configuration for a new model.
        
        Args:
            model_name (str): Name of the model
            deployments (dict): Dictionary with primary, secondary, tertiary configs
            
        Example:
            DeploymentConfig.add_model_deployment("new-model", {
                "primary": {
                    "type": "azure_openai",
                    "endpoint": "...",
                    "api_key": "...",
                    "deployment": "..."
                },
                "secondary": {...},
                "tertiary": {...}
            })
        """
        try:
            cls.DEPLOYMENTS[model_name] = deployments
            logger.info(f"Added deployment configuration for model: {model_name}")
        except Exception as e:
            logger.error(f"Error adding model deployment for {model_name}: {str(e)}")
    
    @classmethod
    def validate_config(cls, model_name):
        """
        Validate that a model has at least a primary deployment configured.
        
        Args:
            model_name (str): Name of the model to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            model_config = cls.DEPLOYMENTS.get(model_name)
            if not model_config:
                logger.error(f"No deployment configuration found for model: {model_name}")
                return False
            
            primary_config = model_config.get("primary")
            if not primary_config:
                logger.error(f"No primary deployment configuration found for model: {model_name}")
                return False
            
            # Check required fields
            required_fields = ["type", "endpoint", "api_key"]
            for field in required_fields:
                if not primary_config.get(field):
                    logger.error(f"Missing required field '{field}' in primary deployment for model: {model_name}")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Error validating config for {model_name}: {str(e)}")
            return False
    
    @classmethod
    def list_configured_models(cls):
        """
        Get list of all configured model names.
        
        Returns:
            list: List of model names
        """
        return list(cls.DEPLOYMENTS.keys())
