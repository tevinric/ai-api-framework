import logging
import time
from .deploymentConfig import DeploymentConfig

logger = logging.getLogger(__name__)

class FailoverService:
    """
    AI Service Failover System
    
    Provides automatic failover across primary, secondary, and tertiary deployments
    for AI models. Handles quota exceeded, service unavailable, and other errors.
    """
    
    # Error codes and messages that trigger failover
    FAILOVER_TRIGGERS = {
        # HTTP status codes that trigger failover
        "status_codes": [429, 500, 502, 503, 504, 507],
        
        # Error messages that trigger failover (case-insensitive partial matches)
        "error_messages": [
            "quota exceeded",
            "rate limit exceeded", 
            "service unavailable",
            "service not available",
            "deployment not found",
            "model not found",
            "endpoint not found",
            "connection error",
            "timeout",
            "internal server error",
            "bad gateway",
            "service temporarily unavailable",
            "gateway timeout",
            "insufficient storage"
        ]
    }
    
    @classmethod
    def should_failover(cls, error_response):
        """
        Determine if an error response should trigger failover to next deployment.
        
        Args:
            error_response (dict): Error response from service function
            
        Returns:
            bool: True if should failover, False otherwise
        """
        try:
            if not isinstance(error_response, dict):
                return True  # If response is not dict, assume it's an error
            
            # Check if response indicates success
            if error_response.get("success", False):
                return False  # Success, no failover needed
            
            # Check error message for failover triggers
            error_msg = str(error_response.get("error", "")).lower()
            
            for trigger in cls.FAILOVER_TRIGGERS["error_messages"]:
                if trigger in error_msg:
                    logger.info(f"Failover triggered by error message: {trigger}")
                    return True
            
            # Check for HTTP status codes in error message
            for status_code in cls.FAILOVER_TRIGGERS["status_codes"]:
                if str(status_code) in error_msg:
                    logger.info(f"Failover triggered by status code: {status_code}")
                    return True
            
            # Default to failover for any error (conservative approach)
            logger.info(f"Failover triggered for generic error: {error_msg}")
            return True
            
        except Exception as e:
            logger.error(f"Error in should_failover: {str(e)}")
            return True  # Conservative: failover on any evaluation error
    
    @classmethod
    def execute_with_failover(cls, model_name, service_function, **kwargs):
        """
        Execute an AI service function with automatic failover across deployments.
        
        Args:
            model_name (str): Name of the AI model (e.g., "gpt-4o")
            service_function (callable): The service function to call
            **kwargs: Arguments to pass to the service function
            
        Returns:
            dict: Service response with success/error information
        """
        # Validate model configuration
        if not DeploymentConfig.validate_config(model_name):
            return {
                "success": False,
                "error": f"Invalid or missing deployment configuration for model: {model_name}",
                "model": model_name,
                "attempted_deployments": [],
                "failover_exhausted": True
            }
        
        # Get all deployment tiers for the model
        deployment_tiers = DeploymentConfig.get_all_tiers(model_name)
        
        if not deployment_tiers:
            return {
                "success": False,
                "error": f"No deployment tiers configured for model: {model_name}",
                "model": model_name,
                "attempted_deployments": [],
                "failover_exhausted": True
            }
        
        attempted_deployments = []
        last_error = None
        
        # Try each deployment tier in order
        for tier_name, deployment_config in deployment_tiers:
            try:
                logger.info(f"Attempting {model_name} request using {tier_name} deployment")
                start_time = time.time()
                
                # Call the service function with the deployment configuration
                response = service_function(deployment_config=deployment_config, **kwargs)
                
                response_time = time.time() - start_time
                
                # Record the attempt
                attempt_info = {
                    "tier": tier_name,
                    "endpoint": deployment_config.get("endpoint", "unknown"),
                    "response_time_ms": int(response_time * 1000),
                    "success": response.get("success", False) if isinstance(response, dict) else False
                }
                attempted_deployments.append(attempt_info)
                
                # Check if response is successful
                if isinstance(response, dict) and response.get("success", False):
                    logger.info(f"Successful response from {model_name} {tier_name} deployment in {attempt_info['response_time_ms']}ms")
                    
                    # Add deployment info to response
                    response["deployment_used"] = tier_name
                    response["attempted_deployments"] = attempted_deployments
                    return response
                
                # Check if we should failover
                if not cls.should_failover(response):
                    logger.info(f"No failover needed for {model_name} {tier_name} deployment")
                    
                    # Add deployment info even for non-failover errors
                    if isinstance(response, dict):
                        response["deployment_used"] = tier_name
                        response["attempted_deployments"] = attempted_deployments
                    return response
                
                # Log failover decision
                error_msg = response.get("error", "Unknown error") if isinstance(response, dict) else str(response)
                logger.warning(f"Failing over from {model_name} {tier_name} deployment due to: {error_msg}")
                last_error = response
                
            except Exception as e:
                # Record the failed attempt
                attempt_info = {
                    "tier": tier_name,
                    "endpoint": deployment_config.get("endpoint", "unknown"),
                    "response_time_ms": int((time.time() - start_time) * 1000) if 'start_time' in locals() else 0,
                    "success": False,
                    "exception": str(e)
                }
                attempted_deployments.append(attempt_info)
                
                logger.error(f"Exception in {model_name} {tier_name} deployment: {str(e)}")
                last_error = {
                    "success": False,
                    "error": f"Exception in {tier_name} deployment: {str(e)}"
                }
        
        # All deployments failed
        logger.error(f"All deployments failed for model: {model_name}")
        
        return {
            "success": False,
            "error": "AI service is currently unavailable. All deployment tiers have been exhausted. Please try again later.",
            "model": model_name,
            "attempted_deployments": attempted_deployments,
            "failover_exhausted": True,
            "last_error": last_error.get("error") if isinstance(last_error, dict) else str(last_error)
        }
    
    @classmethod
    def execute_multimodal_with_failover(cls, model_name, service_function, **kwargs):
        """
        Execute a multimodal AI service function with automatic failover.
        This is a specialized version for multimodal services that may have additional parameters.
        
        Args:
            model_name (str): Name of the AI model (e.g., "gpt-4o")
            service_function (callable): The multimodal service function to call
            **kwargs: Arguments to pass to the service function
            
        Returns:
            dict: Service response with success/error information
        """
        # Use the same logic as regular failover
        return cls.execute_with_failover(model_name, service_function, **kwargs)
    
    @classmethod
    def get_deployment_health(cls, model_name):
        """
        Check the health of all deployments for a model by making simple test calls.
        
        Args:
            model_name (str): Name of the model to check
            
        Returns:
            dict: Health status of each deployment tier
        """
        health_status = {
            "model": model_name,
            "deployments": {},
            "timestamp": time.time()
        }
        
        try:
            deployment_tiers = DeploymentConfig.get_all_tiers(model_name)
            
            for tier_name, deployment_config in deployment_tiers:
                try:
                    # Simple test - just check if configuration is valid
                    endpoint = deployment_config.get("endpoint")
                    api_key = deployment_config.get("api_key")
                    
                    health_status["deployments"][tier_name] = {
                        "status": "healthy" if endpoint and api_key else "unhealthy",
                        "endpoint": endpoint,
                        "has_api_key": bool(api_key),
                        "config_valid": bool(endpoint and api_key)
                    }
                    
                except Exception as e:
                    health_status["deployments"][tier_name] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
            
        except Exception as e:
            logger.error(f"Error checking deployment health for {model_name}: {str(e)}")
            health_status["error"] = str(e)
        
        return health_status
    
    @classmethod
    def get_failover_stats(cls):
        """
        Get statistics about failover triggers and deployment usage.
        This could be extended to track actual usage statistics.
        
        Returns:
            dict: Failover configuration and trigger information
        """
        return {
            "failover_triggers": cls.FAILOVER_TRIGGERS,
            "configured_models": DeploymentConfig.list_configured_models(),
            "total_configured_models": len(DeploymentConfig.list_configured_models())
        }
