from flask import jsonify, request, g, make_response
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
import logging
import uuid
import pytz
from datetime import datetime

# CONFIGURE LOGGING
logger = logging.getLogger(__name__)

def create_api_response(data, status_code=200):
    """Helper function to create consistent API responses"""
    response = make_response(jsonify(data))
    response.status_code = status_code
    return response

def admin_add_endpoint_route():
    """
    Add a new endpoint to the endpoints table (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: "Admin API Key for authentication"
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - token
            - endpoint_path
            - endpoint_name
          properties:
            token:
              type: string
              description: "A valid token for verification"
            endpoint_path:
              type: string
              description: "The API endpoint path (e.g., /llm/custom)"
            endpoint_name:
              type: string
              description: "A user-friendly name for the endpoint"
            description:
              type: string
              description: "Optional description of the endpoint"
            active:
              type: boolean
              description: "Whether the endpoint is active (default: true)"
            cost:
              type: integer
              description: "Cost in balance units for each call to this endpoint (default: 1)"
    produces:
      - application/json
    responses:
      201:
        description: "Endpoint created successfully"
      400:
        description: "Bad request"
      401:
        description: "Authentication error"
      403:
        description: "Forbidden - not an admin"
      409:
        description: "Conflict - endpoint already exists"
      500:
        description: "Server error"
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to manage endpoints"
        }, 403)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate token
    token = data.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Valid token is required"
        }, 400)
        
    # Verify token is valid and not expired
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
    # Check token expiration
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Validate required fields
    required_fields = ['endpoint_path', 'endpoint_name']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return create_api_response({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }, 400)
    
    # Extract endpoint data
    endpoint_path = data.get('endpoint_path')
    endpoint_name = data.get('endpoint_name')
    description = data.get('description', '')
    active = data.get('active', True)
    cost = data.get('cost', 1)  # Default cost is 1
    
    # Validate cost is a positive integer
    try:
        cost = int(cost)
        if cost <= 0:
            return create_api_response({
                "error": "Bad Request",
                "message": "Cost must be a positive integer"
            }, 400)
    except (ValueError, TypeError):
        return create_api_response({
            "error": "Bad Request",
            "message": "Cost must be a valid integer"
        }, 400)
    
    # Ensure endpoint_path starts with /
    if not endpoint_path.startswith('/'):
        endpoint_path = '/' + endpoint_path
    
    try:
        # Check if endpoint already exists
        existing_endpoint = get_endpoint_by_path(endpoint_path)
        if existing_endpoint:
            return create_api_response({
                "error": "Conflict",
                "message": f"Endpoint with path '{endpoint_path}' already exists",
                "endpoint_id": existing_endpoint["id"]
            }, 409)
        
        # Add endpoint to database
        endpoint_id = add_endpoint_to_database(endpoint_path, endpoint_name, description, active, cost)
        
        if not endpoint_id:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to add endpoint to database"
            }, 500)
        
        logger.info(f"Endpoint '{endpoint_path}' added successfully by admin {admin_info['id']}")
        
        return create_api_response({
            "message": "Endpoint added successfully",
            "endpoint_id": endpoint_id,
            "endpoint_path": endpoint_path,
            "endpoint_name": endpoint_name,
            "active": active,
            "cost": cost
        }, 201)
        
    except Exception as e:
        logger.error(f"Error adding endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error adding endpoint: {str(e)}"
        }, 500)

def admin_get_endpoints_route():
    """
    Get all endpoints from the endpoints table (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: "Admin API Key for authentication"
      - name: active
        in: query
        type: boolean
        required: false
        description: "Filter by active status (optional)"
    produces:
      - application/json
    responses:
      200:
        description: "Endpoints retrieved successfully"
      401:
        description: "Authentication error"
      403:
        description: "Forbidden - not an admin"
      500:
        description: "Server error"
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to view endpoints"
        }, 403)
    
    # Get optional active filter
    active_filter = request.args.get('active')
    if active_filter:
        active_filter = active_filter.lower() == 'true'
    
    try:
        # Get endpoints from database
        endpoints = get_all_endpoints(active_filter)
        
        return create_api_response({
            "endpoints": endpoints,
            "count": len(endpoints)
        }, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving endpoints: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error retrieving endpoints: {str(e)}"
        }, 500)

def admin_update_endpoint_route():
    """
    Update an existing endpoint in the endpoints table (Admin only endpoint)
    ---
    tags:
      - Admin Functions
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: "Admin API Key for authentication"
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - token
            - endpoint_id
          properties:
            token:
              type: string
              description: "A valid token for verification"
            endpoint_id:
              type: string
              description: "ID of the endpoint to update"
            endpoint_path:
              type: string
              description: "New API endpoint path (optional)"
            endpoint_name:
              type: string
              description: "New user-friendly name (optional)"
            description:
              type: string
              description: "New description (optional)"
            active:
              type: boolean
              description: "New active status (optional)"
            cost:
              type: integer
              description: "New cost in balance units for each call (optional)"
    produces:
      - application/json
    responses:
      200:
        description: "Endpoint updated successfully"
      400:
        description: "Bad request"
      401:
        description: "Authentication error"
      403:
        description: "Forbidden - not an admin"
      404:
        description: "Endpoint not found"
      409:
        description: "Conflict - endpoint path already exists"
      500:
        description: "Server error"
    """
    # Get API key from request header
    api_key = request.headers.get('API-Key')
    if not api_key:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Missing API Key header (API-Key)"
        }, 401)
    
    # Validate API key and check admin privileges
    admin_info = DatabaseService.validate_api_key(api_key)
    if not admin_info:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid API Key"
        }, 401)
        
    g.user_id = admin_info["id"]
    
    # Check if user has admin privileges (scope=0)
    if admin_info["scope"] != 0:
        return create_api_response({
            "error": "Forbidden",
            "message": "Admin privileges required to update endpoints"
        }, 403)
    
    # Get request data
    data = request.get_json()
    if not data:
        return create_api_response({
            "error": "Bad Request",
            "message": "Request body is required"
        }, 400)
    
    # Validate token
    token = data.get('token')
    if not token:
        return create_api_response({
            "error": "Bad Request",
            "message": "Valid token is required"
        }, 400)
        
    # Verify token is valid and not expired
    token_details = DatabaseService.get_token_details_by_value(token)
    if not token_details:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Invalid token provided"
        }, 401)
        
    g.token_id = token_details["id"]
    
    # Check token expiration
    now = datetime.now(pytz.UTC)
    expiration_time = token_details["token_expiration_time"]
    if expiration_time.tzinfo is None:
        johannesburg_tz = pytz.timezone('Africa/Johannesburg')
        expiration_time = johannesburg_tz.localize(expiration_time)
        
    if now > expiration_time:
        return create_api_response({
            "error": "Authentication Error",
            "message": "Token has expired"
        }, 401)
    
    # Validate endpoint_id
    endpoint_id = data.get('endpoint_id')
    if not endpoint_id:
        return create_api_response({
            "error": "Bad Request",
            "message": "endpoint_id is required"
        }, 400)
    
    try:
        # Check if endpoint exists
        endpoint = get_endpoint_by_id(endpoint_id)
        if not endpoint:
            return create_api_response({
                "error": "Not Found",
                "message": f"Endpoint with ID '{endpoint_id}' not found"
            }, 404)
        
        # Extract update fields
        update_data = {}
        if 'endpoint_path' in data:
            new_path = data['endpoint_path']
            # Ensure endpoint_path starts with /
            if not new_path.startswith('/'):
                new_path = '/' + new_path
                
            # Check if new path already exists for a different endpoint
            if new_path != endpoint['endpoint_path']:
                existing = get_endpoint_by_path(new_path)
                if existing and existing['id'] != endpoint_id:
                    return create_api_response({
                        "error": "Conflict",
                        "message": f"Endpoint with path '{new_path}' already exists"
                    }, 409)
            update_data['endpoint_path'] = new_path
            
        if 'endpoint_name' in data:
            update_data['endpoint_name'] = data['endpoint_name']
            
        if 'description' in data:
            update_data['description'] = data['description']
            
        if 'active' in data:
            update_data['active'] = 1 if data['active'] else 0
        
        if 'cost' in data:
            # Validate cost is a positive integer
            try:
                cost = int(data['cost'])
                if cost <= 0:
                    return create_api_response({
                        "error": "Bad Request",
                        "message": "Cost must be a positive integer"
                    }, 400)
                update_data['cost'] = cost
            except (ValueError, TypeError):
                return create_api_response({
                    "error": "Bad Request",
                    "message": "Cost must be a valid integer"
                }, 400)
        
        # Only proceed if there are fields to update
        if not update_data:
            return create_api_response({
                "message": "No changes to update",
                "endpoint": endpoint
            }, 200)
        
        # Update endpoint in database
        success = update_endpoint(endpoint_id, update_data)
        
        if not success:
            return create_api_response({
                "error": "Server Error",
                "message": "Failed to update endpoint"
            }, 500)
        
        # Get updated endpoint
        updated_endpoint = get_endpoint_by_id(endpoint_id)
        
        logger.info(f"Endpoint '{endpoint_id}' updated successfully by admin {admin_info['id']}")
        
        return create_api_response({
            "message": "Endpoint updated successfully",
            "endpoint": updated_endpoint
        }, 200)
        
    except Exception as e:
        logger.error(f"Error updating endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error updating endpoint: {str(e)}"
        }, 500)

# Database utility functions
def get_endpoint_by_path(endpoint_path):
    """Get endpoint details by path"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT id, endpoint_name, endpoint_path, description, active, cost
        FROM endpoints
        WHERE endpoint_path = ?
        """
        
        cursor.execute(query, [endpoint_path])
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            return None
            
        return {
            "id": str(result[0]),
            "endpoint_name": result[1],
            "endpoint_path": result[2],
            "description": result[3],
            "active": bool(result[4]),
            "cost": result[5]
        }
        
    except Exception as e:
        logger.error(f"Error getting endpoint by path: {str(e)}")
        return None

def get_endpoint_by_id(endpoint_id):
    """Get endpoint details by ID"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT id, endpoint_name, endpoint_path, description, active, cost,
               created_at, modified_at
        FROM endpoints
        WHERE id = ?
        """
        
        cursor.execute(query, [endpoint_id])
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            return None
            
        return {
            "id": str(result[0]),
            "endpoint_name": result[1],
            "endpoint_path": result[2],
            "description": result[3],
            "active": bool(result[4]),
            "cost": result[5],
            "created_at": result[6].isoformat() if result[6] else None,
            "modified_at": result[7].isoformat() if result[7] else None
        }
        
    except Exception as e:
        logger.error(f"Error getting endpoint by ID: {str(e)}")
        return None

def get_all_endpoints(active_filter=None):
    """Get all endpoints, optionally filtered by active status"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT id, endpoint_name, endpoint_path, description, active, cost,
               created_at, modified_at
        FROM endpoints
        """
        
        params = []
        if active_filter is not None:
            query += " WHERE active = ?"
            params.append(1 if active_filter else 0)
        
        query += " ORDER BY endpoint_path"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        endpoints = []
        for row in results:
            endpoints.append({
                "id": str(row[0]),
                "endpoint_name": row[1],
                "endpoint_path": row[2],
                "description": row[3],
                "active": bool(row[4]),
                "cost": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "modified_at": row[7].isoformat() if row[7] else None
            })
            
        return endpoints
        
    except Exception as e:
        logger.error(f"Error getting all endpoints: {str(e)}")
        return []

def add_endpoint_to_database(endpoint_path, endpoint_name, description, active, cost=1):
    """Add a new endpoint to the database"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        endpoint_id = str(uuid.uuid4())
        
        query = """
        INSERT INTO endpoints (
            id, endpoint_name, endpoint_path, description, active, cost,
            created_at, modified_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?,
            DATEADD(HOUR, 2, GETUTCDATE()), DATEADD(HOUR, 2, GETUTCDATE())
        )
        """
        
        cursor.execute(query, [
            endpoint_id,
            endpoint_name,
            endpoint_path,
            description,
            1 if active else 0,
            cost
        ])
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return endpoint_id
        
    except Exception as e:
        logger.error(f"Error adding endpoint: {str(e)}")
        return None

def update_endpoint(endpoint_id, update_data):
    """Update an existing endpoint in the database"""
    try:
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        
        # Build dynamic update query
        set_clauses = []
        params = []
        
        for field, value in update_data.items():
            set_clauses.append(f"{field} = ?")
            params.append(value)
        
        # Add modified_at timestamp
        set_clauses.append("modified_at = DATEADD(HOUR, 2, GETUTCDATE())")
        
        query = f"""
        UPDATE endpoints
        SET {', '.join(set_clauses)}
        WHERE id = ?
        """
        
        # Add endpoint_id to params
        params.append(endpoint_id)
        
        cursor.execute(query, params)
        
        rows_affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        return rows_affected > 0
        
    except Exception as e:
        logger.error(f"Error updating endpoint: {str(e)}")
        return False

def register_admin_endpoint_routes(app):
    """Register admin endpoint management routes with the Flask app"""
    app.route('/admin/endpoints', methods=['GET'])(api_logger(admin_get_endpoints_route))
    app.route('/admin/add-endpoint', methods=['POST'])(api_logger(admin_add_endpoint_route))
    app.route('/admin/update-endpoint', methods=['PUT'])(api_logger(admin_update_endpoint_route))