from flask import jsonify, request, g
from apis.utils.tokenService import TokenService
from apis.utils.databaseService import DatabaseService
from apis.utils.logMiddleware import api_logger
from apis.utils.config import create_api_response
import logging
import requests
from datetime import datetime, timedelta
import os
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)

class AzureCostManagementService:
    """Service for extracting hierarchical cost data from Azure"""
    
    def __init__(self):
        self.tenant_id = os.environ.get('ENTRA_APP_TENANT_ID')
        self.client_id = os.environ.get('ENTRA_APP_CLIENT_ID')
        self.client_secret = os.environ.get('ENTRA_APP_CLIENT_SECRET')
        self.subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        self.base_url = "https://management.azure.com"
        self.api_version = "2023-11-01"  # Use stable API version
        self.access_token = None
        self.token_expiry = None
        
        # Validate required credentials
        self._validate_credentials()
    
    def _validate_credentials(self):
        """Validate that all required Azure credentials are present"""
        missing_vars = []
        if not self.tenant_id:
            missing_vars.append('ENTRA_APP_TENANT_ID')
        if not self.client_id:
            missing_vars.append('ENTRA_APP_CLIENT_ID')
        if not self.client_secret:
            missing_vars.append('ENTRA_APP_CLIENT_SECRET')
        if not self.subscription_id:
            missing_vars.append('AZURE_SUBSCRIPTION_ID')
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}. Please set these in your .env file.")
    
    def _get_access_token(self) -> str:
        """Get Azure access token using client credentials"""
        if self.access_token and self.token_expiry and datetime.utcnow() < self.token_expiry:
            return self.access_token
        
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://management.azure.com/.default'
        }
        
        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()
            
            self.access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)
            self.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 60)
            
            return self.access_token
        except Exception as e:
            logger.error(f"Failed to get Azure access token: {str(e)}")
            raise
    
    def get_subscription_costs(self, subscription_id: Optional[str] = None, 
                              start_date: Optional[str] = None, 
                              end_date: Optional[str] = None) -> Dict:
        """
        Get hierarchical cost breakdown for a subscription
        
        Args:
            subscription_id: Azure subscription ID (uses env var if not provided)
            start_date: Start date in YYYY-MM-DD format (defaults to 30 days ago)
            end_date: End date in YYYY-MM-DD format (defaults to today)
        
        Returns:
            Hierarchical cost breakdown dictionary
        """
        # Use subscription ID from environment if not provided
        if not subscription_id:
            subscription_id = self.subscription_id
        
        if not subscription_id:
            raise ValueError("No subscription ID provided and AZURE_SUBSCRIPTION_ID not set in environment")
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        access_token = self._get_access_token()
        
        # Query URL for Cost Management API
        url = f"{self.base_url}/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Query body for hierarchical cost data
        query_body = {
            "type": "Usage",
            "timeframe": "Custom",
            "timePeriod": {
                "from": start_date,
                "to": end_date
            },
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "totalCost": {
                        "name": "PreTaxCost",
                        "function": "Sum"
                    },
                    "totalCostUSD": {
                        "name": "PreTaxCostUSD",
                        "function": "Sum"
                    }
                },
                "grouping": [
                    {
                        "type": "Dimension",
                        "name": "ResourceGroup"
                    },
                    {
                        "type": "Dimension",
                        "name": "ResourceId"
                    },
                    {
                        "type": "Dimension",
                        "name": "ServiceName"
                    },
                    {
                        "type": "Dimension",
                        "name": "ResourceType"
                    }
                ]
            }
        }
        
        params = {
            'api-version': self.api_version
        }
        
        try:
            response = requests.post(url, headers=headers, json=query_body, params=params)
            response.raise_for_status()
            return self._format_hierarchical_response(response.json(), subscription_id)
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error getting subscription costs: {str(e)}")
            if response.status_code == 401:
                raise Exception("Authentication failed. Please check Azure credentials.")
            elif response.status_code == 403:
                raise Exception("Access denied. Please check permissions for Cost Management API.")
            else:
                raise Exception(f"Failed to get cost data: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting subscription costs: {str(e)}")
            raise
    
    def _format_hierarchical_response(self, raw_data: Dict, subscription_id: str) -> Dict:
        """
        Format the raw Azure Cost Management response into hierarchical structure
        
        Args:
            raw_data: Raw response from Azure Cost Management API
            subscription_id: Azure subscription ID
        
        Returns:
            Formatted hierarchical cost breakdown
        """
        hierarchy = {
            "subscription": {
                "id": subscription_id,
                "totalCost": 0,
                "totalCostUSD": 0,
                "currency": None,
                "resourceGroups": {}
            },
            "dateRange": {
                "from": None,
                "to": None
            },
            "metadata": {
                "queryTime": datetime.utcnow().isoformat(),
                "rowCount": 0
            }
        }
        
        if not raw_data or 'properties' not in raw_data:
            return hierarchy
        
        properties = raw_data['properties']
        
        # Extract column indices
        columns = properties.get('columns', [])
        column_map = {col['name']: idx for idx, col in enumerate(columns)}
        
        # Process rows
        rows = properties.get('rows', [])
        hierarchy['metadata']['rowCount'] = len(rows)
        
        for row in rows:
            try:
                # Extract values from row
                cost = row[column_map.get('PreTaxCost', 0)] or 0
                cost_usd = row[column_map.get('PreTaxCostUSD', 0)] or 0
                resource_group = row[column_map.get('ResourceGroup', 2)] or 'unassigned'
                resource_id = row[column_map.get('ResourceId', 3)] or 'unknown'
                service_name = row[column_map.get('ServiceName', 4)] or 'unknown'
                resource_type = row[column_map.get('ResourceType', 5)] or 'unknown'
                currency = row[column_map.get('Currency', 6)] if 'Currency' in column_map else 'USD'
                
                # Update subscription total
                hierarchy['subscription']['totalCost'] += cost
                hierarchy['subscription']['totalCostUSD'] += cost_usd
                hierarchy['subscription']['currency'] = currency
                
                # Create resource group if doesn't exist
                if resource_group not in hierarchy['subscription']['resourceGroups']:
                    hierarchy['subscription']['resourceGroups'][resource_group] = {
                        "name": resource_group,
                        "totalCost": 0,
                        "totalCostUSD": 0,
                        "resources": []
                    }
                
                # Update resource group total
                rg = hierarchy['subscription']['resourceGroups'][resource_group]
                rg['totalCost'] += cost
                rg['totalCostUSD'] += cost_usd
                
                # Extract resource name from resource ID
                resource_name = resource_id.split('/')[-1] if resource_id else 'unknown'
                
                # Add resource details
                resource_entry = {
                    "resourceId": resource_id,
                    "resourceName": resource_name,
                    "resourceType": resource_type,
                    "serviceName": service_name,
                    "cost": cost,
                    "costUSD": cost_usd,
                    "currency": currency
                }
                
                # Check if resource already exists and aggregate
                existing_resource = next(
                    (r for r in rg['resources'] if r['resourceId'] == resource_id), 
                    None
                )
                
                if existing_resource:
                    existing_resource['cost'] += cost
                    existing_resource['costUSD'] += cost_usd
                else:
                    rg['resources'].append(resource_entry)
                    
            except Exception as e:
                logger.warning(f"Error processing row: {str(e)}")
                continue
        
        # Sort resources by cost (descending)
        for rg_name, rg_data in hierarchy['subscription']['resourceGroups'].items():
            rg_data['resources'] = sorted(
                rg_data['resources'], 
                key=lambda x: x['costUSD'], 
                reverse=True
            )
        
        # Sort resource groups by total cost (descending)
        hierarchy['subscription']['resourceGroups'] = dict(
            sorted(
                hierarchy['subscription']['resourceGroups'].items(),
                key=lambda x: x[1]['totalCostUSD'],
                reverse=True
            )
        )
        
        return hierarchy


def get_azure_costs_route():
    """
    Get hierarchical Azure cost breakdown for a subscription
    ---
    tags:
      - Azure Cost Management
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
      - name: subscription_id
        in: query
        type: string
        required: false
        description: Azure subscription ID (uses AZURE_SUBSCRIPTION_ID env var if not provided)
      - name: start_date
        in: query
        type: string
        required: false
        description: Start date in YYYY-MM-DD format (defaults to 30 days ago)
      - name: end_date
        in: query
        type: string
        required: false
        description: End date in YYYY-MM-DD format (defaults to today)
    produces:
      - application/json
    responses:
      200:
        description: Hierarchical cost breakdown retrieved successfully
        schema:
          type: object
          properties:
            subscription:
              type: object
              properties:
                id:
                  type: string
                  description: Subscription ID
                totalCost:
                  type: number
                  description: Total cost in subscription currency
                totalCostUSD:
                  type: number
                  description: Total cost in USD
                currency:
                  type: string
                  description: Currency code
                resourceGroups:
                  type: object
                  description: Resource groups with their costs and resources
            dateRange:
              type: object
              properties:
                from:
                  type: string
                  description: Start date of the query
                to:
                  type: string
                  description: End date of the query
            metadata:
              type: object
              properties:
                queryTime:
                  type: string
                  description: Timestamp of the query
                rowCount:
                  type: integer
                  description: Number of cost records processed
      400:
        description: Bad request - missing or invalid parameters
      401:
        description: Authentication error
      403:
        description: Access denied - insufficient permissions
      500:
        description: Server error
    """
    try:
        # Validate API key
        api_key = request.headers.get('API-Key')
        if not api_key:
            return create_api_response({
                "error": "Authentication Error",
                "message": "Missing API Key header (API-Key)"
            }, 401)
        
        user_info = DatabaseService.validate_api_key(api_key)
        if not user_info:
            return create_api_response({
                "error": "Authentication Error",
                "message": "Invalid API Key"
            }, 401)
        
        # Get request parameters
        subscription_id = request.args.get('subscription_id')
        
        # Try to get subscription ID from environment if not provided
        if not subscription_id:
            subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        
        if not subscription_id:
            return create_api_response({
                "error": "Bad Request",
                "message": "Missing subscription_id parameter and AZURE_SUBSCRIPTION_ID not set in environment"
            }, 400)
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Validate date formats if provided
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                return create_api_response({
                    "error": "Bad Request",
                    "message": "Invalid start_date format. Use YYYY-MM-DD"
                }, 400)
        
        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                return create_api_response({
                    "error": "Bad Request",
                    "message": "Invalid end_date format. Use YYYY-MM-DD"
                }, 400)
        
        # Log the API call details
        logger.info(f"Azure costs request - User: {user_info.get('username', 'unknown')}, Subscription: {subscription_id[:8] if subscription_id else 'default'}...")
        
        # Get cost data
        cost_service = AzureCostManagementService()
        cost_data = cost_service.get_subscription_costs(
            subscription_id=subscription_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Add date range to response
        cost_data['dateRange'] = {
            'from': start_date or (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'to': end_date or datetime.utcnow().strftime('%Y-%m-%d')
        }
        
        return create_api_response(cost_data, 200)
        
    except ValueError as e:
        logger.error(f"Configuration error in get_azure_costs_route: {str(e)}")
        return create_api_response({
            "error": "Configuration Error",
            "message": str(e)
        }, 400)
    except Exception as e:
        logger.error(f"Error in get_azure_costs_route: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": str(e)
        }, 500)


def get_azure_cost_summary_route():
    """
    Get summarized Azure cost data for a subscription
    ---
    tags:
      - Azure Cost Management
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
      - name: subscription_id
        in: query
        type: string
        required: false
        description: Azure subscription ID (uses AZURE_SUBSCRIPTION_ID env var if not provided)
      - name: days
        in: query
        type: integer
        required: false
        description: Number of days to look back (default 30)
    produces:
      - application/json
    responses:
      200:
        description: Cost summary retrieved successfully
        schema:
          type: object
          properties:
            subscription_id:
              type: string
            total_cost:
              type: number
            total_cost_usd:
              type: number
            currency:
              type: string
            period_days:
              type: integer
            top_resource_groups:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  cost:
                    type: number
                  percentage:
                    type: number
            top_resources:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  type:
                    type: string
                  cost:
                    type: number
                  percentage:
                    type: number
      400:
        description: Bad request
      401:
        description: Authentication error
      500:
        description: Server error
    """
    try:
        # Validate API key
        api_key = request.headers.get('API-Key')
        if not api_key:
            return create_api_response({
                "error": "Authentication Error",
                "message": "Missing API Key header (API-Key)"
            }, 401)
        
        user_info = DatabaseService.validate_api_key(api_key)
        if not user_info:
            return create_api_response({
                "error": "Authentication Error",
                "message": "Invalid API Key"
            }, 401)
        
        # Get request parameters
        subscription_id = request.args.get('subscription_id')
        
        # Try to get subscription ID from environment if not provided
        if not subscription_id:
            subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        
        if not subscription_id:
            return create_api_response({
                "error": "Bad Request",
                "message": "Missing subscription_id parameter and AZURE_SUBSCRIPTION_ID not set in environment"
            }, 400)
        
        days = int(request.args.get('days', 30))
        
        # Calculate date range
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Get cost data
        cost_service = AzureCostManagementService()
        cost_data = cost_service.get_subscription_costs(
            subscription_id=subscription_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Create summary
        subscription_data = cost_data['subscription']
        total_cost = subscription_data['totalCostUSD']
        
        # Top 5 resource groups by cost
        top_resource_groups = []
        for rg_name, rg_data in list(subscription_data['resourceGroups'].items())[:5]:
            top_resource_groups.append({
                "name": rg_name,
                "cost": round(rg_data['totalCostUSD'], 2),
                "percentage": round((rg_data['totalCostUSD'] / total_cost * 100) if total_cost > 0 else 0, 2)
            })
        
        # Top 10 resources across all resource groups
        all_resources = []
        for rg_data in subscription_data['resourceGroups'].values():
            all_resources.extend(rg_data['resources'])
        
        all_resources.sort(key=lambda x: x['costUSD'], reverse=True)
        top_resources = []
        for resource in all_resources[:10]:
            top_resources.append({
                "name": resource['resourceName'],
                "type": resource['resourceType'],
                "service": resource['serviceName'],
                "cost": round(resource['costUSD'], 2),
                "percentage": round((resource['costUSD'] / total_cost * 100) if total_cost > 0 else 0, 2)
            })
        
        summary = {
            "subscription_id": subscription_id,
            "total_cost": round(subscription_data['totalCost'], 2),
            "total_cost_usd": round(subscription_data['totalCostUSD'], 2),
            "currency": subscription_data['currency'],
            "period_days": days,
            "date_range": {
                "from": start_date,
                "to": end_date
            },
            "top_resource_groups": top_resource_groups,
            "top_resources": top_resources,
            "resource_group_count": len(subscription_data['resourceGroups']),
            "total_resources": len(all_resources)
        }
        
        # Log the API call details
        logger.info(f"Azure cost summary request - User: {user_info.get('username', 'unknown')}, Subscription: {subscription_id[:8] if subscription_id else 'default'}..., Days: {days}")
        
        return create_api_response(summary, 200)
        
    except ValueError as e:
        logger.error(f"Configuration error in get_azure_cost_summary_route: {str(e)}")
        return create_api_response({
            "error": "Configuration Error",
            "message": str(e)
        }, 400)
    except Exception as e:
        logger.error(f"Error in get_azure_cost_summary_route: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": str(e)
        }, 500)


def register_azure_cost_routes(app):
    """Register Azure cost management routes with the Flask app"""
    app.route('/azure/costs', methods=['GET'])(api_logger(get_azure_costs_route))
    app.route('/azure/costs/summary', methods=['GET'])(api_logger(get_azure_cost_summary_route))