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
import decimal
import requests

def safe_decimal(value, default=0):
    """
    Safely convert a value to Decimal, handling None and invalid values
    
    Args:
        value: The value to convert
        default: Default value if conversion fails
        
    Returns:
        Decimal: The converted value or default
    """
    try:
        if value is None or value == '':
            return Decimal(str(default))
        return Decimal(str(value))
    except (ValueError, TypeError, decimal.InvalidOperation, decimal.ConversionSyntax):
        return Decimal(str(default))

def safe_string(value, default="Unknown"):
    """
    Safely convert a value to string, handling None and other types
    
    Args:
        value: The value to convert
        default: Default value if conversion fails
        
    Returns:
        str: The converted value or default
    """
    try:
        if value is None:
            return default
        return str(value)
    except (ValueError, TypeError):
        return default

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

def get_simplified_costs(start_date, end_date, resource_group=None):
    """
    Get simplified cost data using only valid fields
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        resource_group (str): Optional specific resource group name
        
    Returns:
        dict: Simplified cost data
    """
    try:
        client = get_cost_management_client()
        
        # Define the scope
        scope = f"/subscriptions/{SUBSCRIPTION_ID}"
        if resource_group:
            scope = f"{scope}/resourceGroups/{resource_group}"
        
        # Create simplified query definition with only valid fields
        query_definition = QueryDefinition(
            type=ExportType.ACTUAL_COST,
            timeframe=TimeframeType.CUSTOM,
            time_period=QueryTimePeriod(
                from_property=datetime.strptime(start_date, '%Y-%m-%d'),
                to=datetime.strptime(end_date, '%Y-%m-%d')
            ),
            dataset=QueryDataset(
                granularity=GranularityType.MONTHLY,  # Changed to MONTHLY for aggregation
                aggregation={
                    "totalCost": QueryAggregation(
                        name="PreTaxCost",
                        function="Sum"
                    )
                },
                grouping=[
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
        costs_by_service = {}
        total_cost = Decimal('0')
        
        if result.rows:
            for row in result.rows:
                service_name = safe_string(row[0] if len(row) > 0 else None, "Unknown Service")
                cost = safe_decimal(row[1] if len(row) > 1 else None)
                
                if service_name not in costs_by_service:
                    costs_by_service[service_name] = Decimal('0')
                
                costs_by_service[service_name] += cost
                total_cost += cost
        
        # Convert Decimal to float for JSON serialization
        for service in costs_by_service:
            costs_by_service[service] = float(costs_by_service[service])
        
        return {
            "success": True,
            "costs_by_service": costs_by_service,
            "total_cost": float(total_cost),
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            },
            "scope": "resource_group" if resource_group else "subscription",
            "resource_group": resource_group if resource_group else None
        }
        
    except Exception as e:
        logger.error(f"Error getting simplified costs: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def get_resource_group_summary(start_date, end_date):
    """
    Get cost summary by resource groups
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        
    Returns:
        dict: Cost summary by resource groups
    """
    try:
        client = get_cost_management_client()
        
        # Define the scope
        scope = f"/subscriptions/{SUBSCRIPTION_ID}"
        
        # Create query for resource group summary
        query_definition = QueryDefinition(
            type=ExportType.ACTUAL_COST,
            timeframe=TimeframeType.CUSTOM,
            time_period=QueryTimePeriod(
                from_property=datetime.strptime(start_date, '%Y-%m-%d'),
                to=datetime.strptime(end_date, '%Y-%m-%d')
            ),
            dataset=QueryDataset(
                granularity=GranularityType.MONTHLY,
                aggregation={
                    "totalCost": QueryAggregation(
                        name="PreTaxCost",
                        function="Sum"
                    )
                },
                grouping=[
                    QueryGrouping(
                        type=QueryColumnType.DIMENSION,
                        name="ResourceGroupName"
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
        resource_groups = {}
        total_cost = Decimal('0')
        
        if result.rows:
            for row in result.rows:
                rg_name = safe_string(row[0] if len(row) > 0 else None, "No Resource Group")
                cost = safe_decimal(row[1] if len(row) > 1 else None)
                
                resource_groups[rg_name] = float(cost)
                total_cost += cost
        
        return {
            "success": True,
            "resource_groups": resource_groups,
            "total_cost": float(total_cost),
            "resource_group_count": len(resource_groups),
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting resource group summary: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def get_detailed_costs_by_resource(start_date, end_date, resource_group=None):
    """
    Get detailed costs grouped by resource
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        resource_group (str): Optional specific resource group name
        
    Returns:
        dict: Detailed cost data by resources
    """
    try:
        client = get_cost_management_client()
        
        # Define the scope
        scope = f"/subscriptions/{SUBSCRIPTION_ID}"
        if resource_group:
            scope = f"{scope}/resourceGroups/{resource_group}"
        
        # Create query for resource-level costs
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
                        name="PreTaxCost",
                        function="Sum"
                    ),
                    "totalUsage": QueryAggregation(
                        name="UsageQuantity",
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
        resources = []
        total_cost = Decimal('0')
        
        if result.rows:
            logger.info(f"Processing {len(result.rows)} rows from Azure Cost Management")
            for i, row in enumerate(result.rows):
                try:
                    logger.debug(f"Row {i}: {row} (types: {[type(x).__name__ for x in row]})")
                    resource_id = safe_string(row[0] if len(row) > 0 else None, "Unknown Resource")
                    resource_type = safe_string(row[1] if len(row) > 1 else None, "Unknown Type")
                    service_name = safe_string(row[2] if len(row) > 2 else None, "Unknown Service")
                    cost = safe_decimal(row[3] if len(row) > 3 else None)
                    usage = safe_decimal(row[4] if len(row) > 4 else None)
                
                    # Extract resource name from resource ID (now safe since resource_id is always a string)
                    resource_name = resource_id.split('/')[-1] if '/' in resource_id else resource_id
                    
                    resources.append({
                        "resource_id": resource_id,
                        "resource_name": resource_name,
                        "resource_type": resource_type,
                        "service_name": service_name,
                        "cost": float(cost),
                        "usage_quantity": float(usage)
                    })
                    
                    total_cost += cost
                except Exception as row_error:
                    logger.error(f"Error processing row {i}: {row_error}")
                    continue
        
        # Sort by cost descending
        resources.sort(key=lambda x: x["cost"], reverse=True)
        
        return {
            "success": True,
            "resources": resources,
            "total_cost": float(total_cost),
            "resource_count": len(resources),
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting detailed resource costs: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }