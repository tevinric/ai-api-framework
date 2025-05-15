import logging
from apis.utils.job_scheduler import start_job_scheduler

# Configure logging
logger = logging.getLogger(__name__)

def initialize_app(app):
    """Initialize application components and services"""
    logger.info("Initializing application components...")
    
    # Start the job scheduler for async processing
    start_job_scheduler()
    logger.info("Job scheduler initialized")
    
    # Here you can add other initialization tasks as needed
    
    logger.info("Application initialization complete")
