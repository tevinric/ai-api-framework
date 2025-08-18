from flask import request, g
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.config import create_api_response
from flasgger import swag_from
import logging
from datetime import datetime, timedelta
import json
import pytz
import os
from azure.identity import ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryDefinition, 
    QueryTimePeriod, 
    QueryDataset,
    QueryAggregation,
    QueryGrouping,
    TimeframeType,
    QueryColumnType,
    GranularityType,
    ExportType
)
from decimal import Decimal
import requests

# Configure logging
logger = logging.getLogger(__name__)

# Initialize token service
token_service = TokenService()

# Azure Cost Management Configuration
SUBSCRIPTION_ID = os.environ.get("AZURE_SUBSCRIPTION_ID")
TENANT_ID = os.environ.get("ENTRA_APP_TENANT_ID")
CLIENT_ID = os.environ.get("ENTRA_COST_CLIENT_ID", os.environ.get("ENTRA_APP_CLIENT_ID"))
CLIENT_SECRET = os.environ.get("ENTRA_COST_CLIENT_SECRET", os.environ.get("ENTRA_APP_CLIENT_SECRET"))

def get_cost_management_client():
    """
    Initialize and return Azure Cost Management client
    """
    try:
        credential = ClientSecretCredential(
            tenant_id=TENANT_ID,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET
        )
        
        client = CostManagementClient(
            credential=credential,
            subscription_id=SUBSCRIPTION_ID
        )
        
        return client
    except Exception as e:
        logger.error(f"Error initializing Cost Management client: {str(e)}")
        raise

def token_required_cost(f):
    """
    Decorator for cost management endpoints that require token authentication
    """
    from functools import wraps
    
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            # Get token from header
            token = request.headers.get('X-Token')
            if not token:
                return create_api_response({
                    "error": "Authentication Error",
                    "message": "Missing X-Token header"
                }, 401)
            
            # Validate token using DatabaseService
            token_details = DatabaseService.get_token_details_by_value(token)
            if not token_details:
                return create_api_response({
                    "error": "Authentication Error",
                    "message": "Invalid token"
                }, 401)
                
            # Check if token is expired
            now = datetime.now(pytz.UTC)
            expiration_time = token_details["token_expiration_time"]
            
            # Ensure expiration_time is timezone-aware
            if expiration_time.tzinfo is None:
                johannesburg_tz = pytz.timezone('Africa/Johannesburg')
                expiration_time = johannesburg_tz.localize(expiration_time)
                
            if now > expiration_time:
                return create_api_response({
                    "error": "Authentication Error",
                    "message": "Token has expired"
                }, 401)
            
            # Store user info in g for use in the endpoint
            g.user_id = token_details["user_id"]
            g.token_id = token_details["id"]
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return create_api_response({
                "error": "Authentication Error",
                "message": "Token validation failed"
            }, 401)
    
    return decorated

def get_resource_group_costs(start_date, end_date, resource_group=None):
    """
    Get costs for resource groups using Azure Cost Management API
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        resource_group (str): Optional specific resource group name
        
    Returns:
        dict: Cost data for resource groups
    """
    try:
        client = get_cost_management_client()
        
        # Define the scope
        scope = f"/subscriptions/{SUBSCRIPTION_ID}"
        if resource_group:
            scope = f"{scope}/resourceGroups/{resource_group}"
        
        # Create query definition
        query_definition = QueryDefinition(
            type=ExportType.ACTUAL_COST,
            timeframe=TimeframeType.CUSTOM,
            time_period=QueryTimePeriod(
                from_property=datetime.strptime(start_date, '%Y-%m-%d'),
                to=datetime.strptime(end_date, '%Y-%m-%d')
            ),
            dataset=QueryDataset(
                granularity=GranularityType.DAILY,
                aggregation={
                    "totalCost": QueryAggregation(
                        name="Cost",
                        function="Sum"
                    ),
                    "totalCostUSD": QueryAggregation(
                        name="CostUSD", 
                        function="Sum"
                    )
                },
                grouping=[
                    QueryGrouping(
                        type=QueryColumnType.DIMENSION,
                        name="ResourceGroup"
                    ),
                    QueryGrouping(
                        type=QueryColumnType.DIMENSION,
                        name="ServiceName"
                    )
                ] if not resource_group else [
                    QueryGrouping(
                        type=QueryColumnType.DIMENSION,
                        name="ServiceName"
                    )
                ]
            )
        )
        
        # Execute query
        result = client.query.usage(
            scope=scope,
            parameters=query_definition
        )
        
        # Process results
        costs_by_group = {}
        total_cost = Decimal('0')
        total_cost_usd = Decimal('0')
        
        if result.rows:
            for row in result.rows:
                if not resource_group:
                    # Multiple resource groups
                    rg_name = row[0] if row[0] else "No Resource Group"
                    service_name = row[1] if row[1] else "Unknown Service"
                    cost = Decimal(str(row[2])) if row[2] else Decimal('0')
                    cost_usd = Decimal(str(row[3])) if len(row) > 3 and row[3] else cost
                    
                    if rg_name not in costs_by_group:
                        costs_by_group[rg_name] = {
                            "total_cost": Decimal('0'),
                            "total_cost_usd": Decimal('0'),
                            "services": {}
                        }
                    
                    costs_by_group[rg_name]["total_cost"] += cost
                    costs_by_group[rg_name]["total_cost_usd"] += cost_usd
                    
                    if service_name not in costs_by_group[rg_name]["services"]:
                        costs_by_group[rg_name]["services"][service_name] = {
                            "cost": Decimal('0'),
                            "cost_usd": Decimal('0')
                        }
                    
                    costs_by_group[rg_name]["services"][service_name]["cost"] += cost
                    costs_by_group[rg_name]["services"][service_name]["cost_usd"] += cost_usd
                else:
                    # Single resource group
                    service_name = row[0] if row[0] else "Unknown Service"
                    cost = Decimal(str(row[1])) if row[1] else Decimal('0')
                    cost_usd = Decimal(str(row[2])) if len(row) > 2 and row[2] else cost
                    
                    if resource_group not in costs_by_group:
                        costs_by_group[resource_group] = {
                            "total_cost": Decimal('0'),
                            "total_cost_usd": Decimal('0'),
                            "services": {}
                        }
                    
                    costs_by_group[resource_group]["total_cost"] += cost
                    costs_by_group[resource_group]["total_cost_usd"] += cost_usd
                    
                    if service_name not in costs_by_group[resource_group]["services"]:
                        costs_by_group[resource_group]["services"][service_name] = {
                            "cost": Decimal('0'),
                            "cost_usd": Decimal('0')
                        }
                    
                    costs_by_group[resource_group]["services"][service_name]["cost"] += cost
                    costs_by_group[resource_group]["services"][service_name]["cost_usd"] += cost_usd
                
                total_cost += cost
                total_cost_usd += cost_usd
        
        # Convert Decimal to float for JSON serialization
        for rg_name in costs_by_group:
            costs_by_group[rg_name]["total_cost"] = float(costs_by_group[rg_name]["total_cost"])
            costs_by_group[rg_name]["total_cost_usd"] = float(costs_by_group[rg_name]["total_cost_usd"])
            for service_name in costs_by_group[rg_name]["services"]:
                costs_by_group[rg_name]["services"][service_name]["cost"] = float(
                    costs_by_group[rg_name]["services"][service_name]["cost"]
                )
                costs_by_group[rg_name]["services"][service_name]["cost_usd"] = float(
                    costs_by_group[rg_name]["services"][service_name]["cost_usd"]
                )
        
        return {
            "success": True,
            "costs_by_resource_group": costs_by_group,
            "total_cost": float(total_cost),
            "total_cost_usd": float(total_cost_usd),
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            },
            "currency": result.properties.currency if hasattr(result, 'properties') and hasattr(result.properties, 'currency') else "USD"
        }
        
    except Exception as e:
        logger.error(f"Error getting resource group costs: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def get_detailed_line_item_costs(start_date, end_date, resource_group=None):
    """
    Get detailed line item costs for resources
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        resource_group (str): Optional specific resource group name
        
    Returns:
        dict: Detailed cost data for resources
    """
    try:
        client = get_cost_management_client()
        
        # Define the scope
        scope = f"/subscriptions/{SUBSCRIPTION_ID}"
        if resource_group:
            scope = f"{scope}/resourceGroups/{resource_group}"
        
        # Create query definition for detailed line items
        query_definition = QueryDefinition(
            type=ExportType.ACTUAL_COST,
            timeframe=TimeframeType.CUSTOM,
            time_period=QueryTimePeriod(
                from_property=datetime.strptime(start_date, '%Y-%m-%d'),
                to=datetime.strptime(end_date, '%Y-%m-%d')
            ),
            dataset=QueryDataset(
                granularity=GranularityType.DAILY,
                aggregation={
                    "totalCost": QueryAggregation(
                        name="Cost",
                        function="Sum"
                    ),
                    "totalQuantity": QueryAggregation(
                        name="Quantity",
                        function="Sum"
                    )
                },
                grouping=[
                    QueryGrouping(
                        type=QueryColumnType.DIMENSION,
                        name="ResourceId"
                    ),
                    QueryGrouping(
                        type=QueryColumnType.DIMENSION,
                        name="ResourceType"
                    ),
                    QueryGrouping(
                        type=QueryColumnType.DIMENSION,
                        name="MeterCategory"
                    ),
                    QueryGrouping(
                        type=QueryColumnType.DIMENSION,
                        name="MeterSubCategory"
                    ),
                    QueryGrouping(
                        type=QueryColumnType.DIMENSION,
                        name="MeterName"
                    )
                ]
            )
        )
        
        # Execute query
        result = client.query.usage(
            scope=scope,
            parameters=query_definition
        )
        
        # Process results
        line_items = []
        total_cost = Decimal('0')
        
        if result.rows:
            for row in result.rows:
                resource_id = row[0] if row[0] else "Unknown Resource"
                resource_type = row[1] if row[1] else "Unknown Type"
                meter_category = row[2] if row[2] else "Unknown Category"
                meter_subcategory = row[3] if row[3] else "Unknown Subcategory"
                meter_name = row[4] if row[4] else "Unknown Meter"
                cost = Decimal(str(row[5])) if row[5] else Decimal('0')
                quantity = Decimal(str(row[6])) if len(row) > 6 and row[6] else Decimal('0')
                
                # Extract resource name from resource ID
                resource_name = resource_id.split('/')[-1] if '/' in resource_id else resource_id
                
                line_item = {
                    "resource_id": resource_id,
                    "resource_name": resource_name,
                    "resource_type": resource_type,
                    "meter_category": meter_category,
                    "meter_subcategory": meter_subcategory,
                    "meter_name": meter_name,
                    "cost": float(cost),
                    "quantity": float(quantity)
                }
                
                line_items.append(line_item)
                total_cost += cost
        
        # Sort by cost descending
        line_items.sort(key=lambda x: x["cost"], reverse=True)
        
        return {
            "success": True,
            "line_items": line_items,
            "total_cost": float(total_cost),
            "item_count": len(line_items),
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            },
            "currency": result.properties.currency if hasattr(result, 'properties') and hasattr(result.properties, 'currency') else "USD"
        }
        
    except Exception as e:
        logger.error(f"Error getting detailed line item costs: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def apportion_costs_by_usage(costs_data, usage_data):
    """
    Apportion subscription costs based on user usage
    
    Args:
        costs_data (dict): Cost data from Azure Cost Management
        usage_data (dict): User usage data from usage_analytics
        
    Returns:
        dict: Apportioned costs for the user
    """
    try:
        # Map service names to usage models
        service_model_mapping = {
            "Cognitive Services": {
                "gpt-4": ["gpt-4", "gpt-4-32k", "gpt-4-turbo"],
                "gpt-4o": ["gpt-4o", "gpt-4o-mini"],
                "gpt-3.5": ["gpt-3.5-turbo"],
                "dalle": ["dall-e-3"],
                "whisper": ["whisper"],
                "tts": ["tts-1", "tts-1-hd"]
            },
            "Storage": {
                "blob": ["file_uploads", "image_generation"]
            }
        }
        
        # Calculate user's proportion of usage for each service
        user_cost_breakdown = {}
        
        for resource_group, rg_data in costs_data.get("costs_by_resource_group", {}).items():
            user_cost_breakdown[resource_group] = {
                "services": {},
                "total_cost": 0,
                "total_cost_usd": 0
            }
            
            for service_name, service_cost in rg_data.get("services", {}).items():
                # Find matching models for this service
                matched_models = []
                for service_key, models in service_model_mapping.get(service_name, {}).items():
                    for model in models:
                        if model in usage_data.get("usage_by_model", {}):
                            matched_models.append(model)
                
                if matched_models:
                    # Calculate user's proportion based on token usage
                    user_tokens = sum(
                        usage_data["usage_by_model"][model].get("total_tokens", 0)
                        for model in matched_models
                    )
                    
                    # Get total tokens for these models from database (simplified for now)
                    # In production, you'd query total usage for all users
                    total_tokens = user_tokens * 10  # Placeholder multiplier
                    
                    if total_tokens > 0:
                        proportion = user_tokens / total_tokens
                        user_service_cost = service_cost["cost"] * proportion
                        user_service_cost_usd = service_cost["cost_usd"] * proportion
                    else:
                        user_service_cost = 0
                        user_service_cost_usd = 0
                    
                    user_cost_breakdown[resource_group]["services"][service_name] = {
                        "cost": user_service_cost,
                        "cost_usd": user_service_cost_usd,
                        "usage_proportion": proportion if total_tokens > 0 else 0,
                        "matched_models": matched_models
                    }
                    
                    user_cost_breakdown[resource_group]["total_cost"] += user_service_cost
                    user_cost_breakdown[resource_group]["total_cost_usd"] += user_service_cost_usd
        
        return {
            "success": True,
            "user_cost_breakdown": user_cost_breakdown,
            "usage_summary": {
                "total_tokens": usage_data.get("totals", {}).get("total_tokens", 0),
                "total_requests": usage_data.get("totals", {}).get("total_requests", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Error apportioning costs: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@token_required_cost
def cost_by_resource_group():
    """
    Get cost for each resource group in the subscription
    ---
    tags:
      - Cost Management
    security:
      - ApiKeyAuth: []
    parameters:
      - in: header
        name: X-Token
        type: string
        required: true
        description: User authentication token
      - in: body
        name: date_range
        required: true
        schema:
          type: object
          properties:
            start_date:
              type: string
              example: "2024-01-01"
              description: Start date in YYYY-MM-DD format
            end_date:
              type: string
              example: "2024-01-31"
              description: End date in YYYY-MM-DD format
            resource_group:
              type: string
              example: "my-resource-group"
              description: Optional specific resource group name
          required:
            - start_date
            - end_date
    responses:
      200:
        description: Resource group costs retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Resource group costs retrieved successfully"
            costs_by_resource_group:
              type: object
              description: Costs breakdown by resource group
            total_cost:
              type: number
              example: 1234.56
            total_cost_usd:
              type: number
              example: 1234.56
            date_range:
              type: object
            currency:
              type: string
              example: "USD"
      400:
        description: Bad request
      401:
        description: Authentication error
    """
    try:
        data = request.get_json()
        if not data:
            return create_api_response({
                "error": "Bad Request",
                "message": "Request body is required"
            }, 400)
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        resource_group = data.get('resource_group')
        
        if not start_date or not end_date:
            return create_api_response({
                "error": "Bad Request",
                "message": "start_date and end_date are required (YYYY-MM-DD format)"
            }, 400)
        
        # Validate date format
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return create_api_response({
                "error": "Bad Request",
                "message": "Invalid date format. Use YYYY-MM-DD"
            }, 400)
        
        # Get resource group costs
        result = get_resource_group_costs(start_date, end_date, resource_group)
        
        if not result["success"]:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error retrieving cost data: {result['error']}"
            }, 500)
        
        return create_api_response({
            "message": "Resource group costs retrieved successfully",
            "costs_by_resource_group": result["costs_by_resource_group"],
            "total_cost": result["total_cost"],
            "total_cost_usd": result["total_cost_usd"],
            "date_range": result["date_range"],
            "currency": result["currency"]
        }, 200)
        
    except Exception as e:
        logger.error(f"Error in cost_by_resource_group endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

@token_required_cost
def cost_all_resource_groups():
    """
    Get total cost for all resource groups in the subscription
    ---
    tags:
      - Cost Management
    security:
      - ApiKeyAuth: []
    parameters:
      - in: header
        name: X-Token
        type: string
        required: true
        description: User authentication token
      - in: body
        name: date_range
        required: true
        schema:
          type: object
          properties:
            start_date:
              type: string
              example: "2024-01-01"
              description: Start date in YYYY-MM-DD format
            end_date:
              type: string
              example: "2024-01-31"
              description: End date in YYYY-MM-DD format
          required:
            - start_date
            - end_date
    responses:
      200:
        description: Total costs retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Total costs retrieved successfully"
            costs_by_resource_group:
              type: object
              description: Costs breakdown by all resource groups
            total_cost:
              type: number
              example: 5678.90
            total_cost_usd:
              type: number
              example: 5678.90
            resource_group_count:
              type: integer
              example: 5
            date_range:
              type: object
            currency:
              type: string
              example: "USD"
      400:
        description: Bad request
      401:
        description: Authentication error
    """
    try:
        data = request.get_json()
        if not data:
            return create_api_response({
                "error": "Bad Request",
                "message": "Request body is required"
            }, 400)
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if not start_date or not end_date:
            return create_api_response({
                "error": "Bad Request",
                "message": "start_date and end_date are required (YYYY-MM-DD format)"
            }, 400)
        
        # Get costs for all resource groups
        result = get_resource_group_costs(start_date, end_date)
        
        if not result["success"]:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error retrieving cost data: {result['error']}"
            }, 500)
        
        return create_api_response({
            "message": "Total costs retrieved successfully",
            "costs_by_resource_group": result["costs_by_resource_group"],
            "total_cost": result["total_cost"],
            "total_cost_usd": result["total_cost_usd"],
            "resource_group_count": len(result["costs_by_resource_group"]),
            "date_range": result["date_range"],
            "currency": result["currency"]
        }, 200)
        
    except Exception as e:
        logger.error(f"Error in cost_all_resource_groups endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

@token_required_cost
def cost_line_items():
    """
    Get detailed line item costs for resources
    ---
    tags:
      - Cost Management
    security:
      - ApiKeyAuth: []
    parameters:
      - in: header
        name: X-Token
        type: string
        required: true
        description: User authentication token
      - in: body
        name: date_range
        required: true
        schema:
          type: object
          properties:
            start_date:
              type: string
              example: "2024-01-01"
              description: Start date in YYYY-MM-DD format
            end_date:
              type: string
              example: "2024-01-31"
              description: End date in YYYY-MM-DD format
            resource_group:
              type: string
              example: "my-resource-group"
              description: Optional specific resource group name
          required:
            - start_date
            - end_date
    responses:
      200:
        description: Line item costs retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Line item costs retrieved successfully"
            line_items:
              type: array
              items:
                type: object
                properties:
                  resource_id:
                    type: string
                  resource_name:
                    type: string
                  resource_type:
                    type: string
                  meter_category:
                    type: string
                  meter_subcategory:
                    type: string
                  meter_name:
                    type: string
                  cost:
                    type: number
                  quantity:
                    type: number
            total_cost:
              type: number
              example: 1234.56
            item_count:
              type: integer
              example: 50
            date_range:
              type: object
            currency:
              type: string
              example: "USD"
      400:
        description: Bad request
      401:
        description: Authentication error
    """
    try:
        data = request.get_json()
        if not data:
            return create_api_response({
                "error": "Bad Request",
                "message": "Request body is required"
            }, 400)
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        resource_group = data.get('resource_group')
        
        if not start_date or not end_date:
            return create_api_response({
                "error": "Bad Request",
                "message": "start_date and end_date are required (YYYY-MM-DD format)"
            }, 400)
        
        # Get detailed line item costs
        result = get_detailed_line_item_costs(start_date, end_date, resource_group)
        
        if not result["success"]:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error retrieving line item data: {result['error']}"
            }, 500)
        
        return create_api_response({
            "message": "Line item costs retrieved successfully",
            "line_items": result["line_items"],
            "total_cost": result["total_cost"],
            "item_count": result["item_count"],
            "date_range": result["date_range"],
            "currency": result["currency"]
        }, 200)
        
    except Exception as e:
        logger.error(f"Error in cost_line_items endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

@token_required_cost
def user_apportioned_costs():
    """
    Get user's apportioned costs based on their usage
    ---
    tags:
      - Cost Management
    security:
      - ApiKeyAuth: []
    parameters:
      - in: header
        name: X-Token
        type: string
        required: true
        description: User authentication token
      - in: body
        name: date_range
        required: true
        schema:
          type: object
          properties:
            start_date:
              type: string
              example: "2024-01-01"
              description: Start date in YYYY-MM-DD format
            end_date:
              type: string
              example: "2024-01-31"
              description: End date in YYYY-MM-DD format
          required:
            - start_date
            - end_date
    responses:
      200:
        description: User apportioned costs retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "User apportioned costs retrieved successfully"
            user_cost_breakdown:
              type: object
              description: User's apportioned costs by resource group and service
            usage_summary:
              type: object
              description: User's usage summary
            total_apportioned_cost:
              type: number
              example: 123.45
            date_range:
              type: object
      400:
        description: Bad request
      401:
        description: Authentication error
    """
    try:
        data = request.get_json()
        if not data:
            return create_api_response({
                "error": "Bad Request",
                "message": "Request body is required"
            }, 400)
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if not start_date or not end_date:
            return create_api_response({
                "error": "Bad Request",
                "message": "start_date and end_date are required (YYYY-MM-DD format)"
            }, 400)
        
        # Import the usage analytics function
        from apis.usage_tracking.usage_analytics import get_usage_analytics
        
        # Get user's usage data
        usage_result = get_usage_analytics(start_date, end_date, g.user_id)
        
        if not usage_result["success"]:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error retrieving usage data: {usage_result['error']}"
            }, 500)
        
        # Get subscription costs
        costs_result = get_resource_group_costs(start_date, end_date)
        
        if not costs_result["success"]:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error retrieving cost data: {costs_result['error']}"
            }, 500)
        
        # Apportion costs based on usage
        apportioned_result = apportion_costs_by_usage(costs_result, usage_result)
        
        if not apportioned_result["success"]:
            return create_api_response({
                "error": "Server Error",
                "message": f"Error apportioning costs: {apportioned_result['error']}"
            }, 500)
        
        # Calculate total apportioned cost
        total_apportioned_cost = sum(
            rg_data["total_cost"]
            for rg_data in apportioned_result["user_cost_breakdown"].values()
        )
        
        return create_api_response({
            "message": "User apportioned costs retrieved successfully",
            "user_id": g.user_id,
            "user_cost_breakdown": apportioned_result["user_cost_breakdown"],
            "usage_summary": apportioned_result["usage_summary"],
            "total_apportioned_cost": total_apportioned_cost,
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            }
        }, 200)
        
    except Exception as e:
        logger.error(f"Error in user_apportioned_costs endpoint: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": f"Error processing request: {str(e)}"
        }, 500)

def register_cost_management_routes(app):
    """Register cost management routes"""
    
    app.add_url_rule('/cost_management/resource_group',
                     'cost_by_resource_group',
                     cost_by_resource_group,
                     methods=['POST'])
                     
    app.add_url_rule('/cost_management/all_resource_groups',
                     'cost_all_resource_groups',
                     cost_all_resource_groups,
                     methods=['POST'])
                     
    app.add_url_rule('/cost_management/line_items',
                     'cost_line_items',
                     cost_line_items,
                     methods=['POST'])
                     
    app.add_url_rule('/cost_management/user_apportioned',
                     'user_apportioned_costs',
                     user_apportioned_costs,
                     methods=['POST'])