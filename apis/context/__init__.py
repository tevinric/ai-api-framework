from apis.context.context_create import register_context_create_routes
from apis.context.context_get import register_context_get_routes
from apis.context.context_update import register_context_update_routes
from apis.context.context_delete import register_context_delete_routes

def register_context_routes(app):
    """Register all context routes with the Flask app"""
    register_context_create_routes(app)
    register_context_get_routes(app)
    register_context_update_routes(app)
    register_context_delete_routes(app)
