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
    
    def get_subscription_costs(self, start_date: Optional[str] = None, 
                              end_date: Optional[str] = None) -> Dict:
        """
        Get hierarchical cost breakdown for a subscription
        
        Args:
            start_date: Start date in YYYY-MM-DD format (defaults to 30 days ago)
            end_date: End date in YYYY-MM-DD format (defaults to today)
        
        Returns:
            Hierarchical cost breakdown dictionary
        """
        subscription_id = self.subscription_id
        if not subscription_id:
            raise ValueError("AZURE_SUBSCRIPTION_ID not set in environment")
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
    
    def get_period_costs(self, period_type: str = 'mtd', 
                         start_period: Optional[str] = None, 
                         end_period: Optional[str] = None) -> Dict:
        """
        Get costs for specific periods (MTD, YTD, or custom YYYYMM range)
        
        Args:
            period_type: 'mtd' (month-to-date), 'ytd' (year-to-date), or 'custom'
            start_period: For custom periods, start in YYYYMM format
            end_period: For custom periods, end in YYYYMM format
        
        Returns:
            Detailed cost breakdown for the period
        """
        now = datetime.utcnow()
        
        if period_type == 'mtd':
            # Month to date
            start_date = now.replace(day=1).strftime('%Y-%m-%d')
            end_date = now.strftime('%Y-%m-%d')
        elif period_type == 'ytd':
            # Year to date
            start_date = now.replace(month=1, day=1).strftime('%Y-%m-%d')
            end_date = now.strftime('%Y-%m-%d')
        elif period_type == 'custom':
            if not start_period or not end_period:
                raise ValueError("start_period and end_period required for custom period type")
            
            # Parse YYYYMM format
            try:
                start_year = int(start_period[:4])
                start_month = int(start_period[4:6])
                end_year = int(end_period[:4])
                end_month = int(end_period[4:6])
                
                start_date = datetime(start_year, start_month, 1).strftime('%Y-%m-%d')
                
                # Get last day of end month
                if end_month == 12:
                    next_month = datetime(end_year + 1, 1, 1)
                else:
                    next_month = datetime(end_year, end_month + 1, 1)
                end_date = (next_month - timedelta(days=1)).strftime('%Y-%m-%d')
            except (ValueError, IndexError):
                raise ValueError("Invalid period format. Use YYYYMM (e.g., 202401)")
        else:
            raise ValueError(f"Invalid period_type: {period_type}. Use 'mtd', 'ytd', or 'custom'")
        
        return self.get_subscription_costs(start_date=start_date, end_date=end_date)
    
    def get_ai_service_costs(self, start_date: Optional[str] = None, 
                            end_date: Optional[str] = None) -> Dict:
        """
        Get detailed AI/ML/Cognitive Services costs with token-level breakdown
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        
        Returns:
            Detailed AI service costs with model and token attribution
        """
        subscription_id = self.subscription_id
        if not subscription_id:
            raise ValueError("AZURE_SUBSCRIPTION_ID not set in environment")
        
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        access_token = self._get_access_token()
        
        # Query URL for Cost Management API with detailed AI services
        url = f"{self.base_url}/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Specialized query for AI services with meter details
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
                    },
                    "usageQuantity": {
                        "name": "UsageQuantity",
                        "function": "Sum"
                    }
                },
                "grouping": [
                    {
                        "type": "Dimension",
                        "name": "ServiceName"
                    },
                    {
                        "type": "Dimension",
                        "name": "ResourceId"
                    },
                    {
                        "type": "Dimension",
                        "name": "MeterName"
                    },
                    {
                        "type": "Dimension",
                        "name": "MeterCategory"
                    },
                    {
                        "type": "Dimension",
                        "name": "MeterSubCategory"
                    },
                    {
                        "type": "Dimension",
                        "name": "UnitOfMeasure"
                    }
                ],
                "filter": {
                    "or": [
                        {
                            "dimensions": {
                                "name": "ServiceName",
                                "operator": "In",
                                "values": [
                                    "Cognitive Services",
                                    "Azure OpenAI",
                                    "Azure Machine Learning",
                                    "Azure Databricks",
                                    "Azure Cognitive Search"
                                ]
                            }
                        },
                        {
                            "dimensions": {
                                "name": "MeterCategory",
                                "operator": "In",
                                "values": [
                                    "Cognitive Services",
                                    "Azure OpenAI Service",
                                    "Machine Learning",
                                    "Azure Applied AI Services"
                                ]
                            }
                        }
                    ]
                }
            }
        }
        
        params = {
            'api-version': self.api_version
        }
        
        try:
            response = requests.post(url, headers=headers, json=query_body, params=params)
            response.raise_for_status()
            return self._format_ai_costs_response(response.json(), subscription_id, start_date, end_date)
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error getting AI service costs: {str(e)}")
            if response.status_code == 401:
                raise Exception("Authentication failed. Please check Azure credentials.")
            elif response.status_code == 403:
                raise Exception("Access denied. Please check permissions for Cost Management API.")
            else:
                raise Exception(f"Failed to get AI cost data: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting AI service costs: {str(e)}")
            raise
    
    def _format_ai_costs_response(self, raw_data: Dict, subscription_id: str, 
                                 start_date: str, end_date: str) -> Dict:
        """
        Format AI services cost response with detailed token attribution
        """
        result = {
            "subscription_id": subscription_id,
            "period": {
                "from": start_date,
                "to": end_date
            },
            "total_ai_cost": 0,
            "total_ai_cost_usd": 0,
            "services": {},
            "models": {},
            "metadata": {
                "queryTime": datetime.utcnow().isoformat(),
                "rowCount": 0
            }
        }
        
        if not raw_data or 'properties' not in raw_data:
            return result
        
        properties = raw_data['properties']
        columns = properties.get('columns', [])
        column_map = {col['name']: idx for idx, col in enumerate(columns)}
        
        rows = properties.get('rows', [])
        result['metadata']['rowCount'] = len(rows)
        
        for row in rows:
            try:
                cost = row[column_map.get('PreTaxCost', 0)] or 0
                cost_usd = row[column_map.get('PreTaxCostUSD', 0)] or 0
                usage_quantity = row[column_map.get('UsageQuantity', 2)] or 0
                service_name = row[column_map.get('ServiceName', 3)] or 'Unknown'
                resource_id = row[column_map.get('ResourceId', 4)] or 'Unknown'
                meter_name = row[column_map.get('MeterName', 5)] or 'Unknown'
                meter_category = row[column_map.get('MeterCategory', 6)] or 'Unknown'
                meter_subcategory = row[column_map.get('MeterSubCategory', 7)] or 'Unknown'
                unit_of_measure = row[column_map.get('UnitOfMeasure', 8)] or 'Unknown'
                
                # Update totals
                result['total_ai_cost'] += cost
                result['total_ai_cost_usd'] += cost_usd
                
                # Extract resource name
                resource_name = resource_id.split('/')[-1] if resource_id != 'Unknown' else 'Unknown'
                
                # Initialize service if not exists
                if service_name not in result['services']:
                    result['services'][service_name] = {
                        'name': service_name,
                        'total_cost': 0,
                        'total_cost_usd': 0,
                        'resources': {}
                    }
                
                # Update service totals
                result['services'][service_name]['total_cost'] += cost
                result['services'][service_name]['total_cost_usd'] += cost_usd
                
                # Initialize resource if not exists
                if resource_name not in result['services'][service_name]['resources']:
                    result['services'][service_name]['resources'][resource_name] = {
                        'name': resource_name,
                        'resource_id': resource_id,
                        'total_cost': 0,
                        'total_cost_usd': 0,
                        'meters': []
                    }
                
                # Add meter details
                meter_detail = {
                    'meter_name': meter_name,
                    'meter_category': meter_category,
                    'meter_subcategory': meter_subcategory,
                    'usage_quantity': usage_quantity,
                    'unit_of_measure': unit_of_measure,
                    'cost': cost,
                    'cost_usd': cost_usd
                }
                
                # Parse model information from meter name
                model_info = self._parse_ai_model_info(meter_name, meter_category, meter_subcategory)
                if model_info:
                    meter_detail.update(model_info)
                    
                    # Track by model
                    model_key = model_info.get('model', 'Unknown')
                    if model_key not in result['models']:
                        result['models'][model_key] = {
                            'model': model_key,
                            'total_cost': 0,
                            'total_cost_usd': 0,
                            'usage_breakdown': {}
                        }
                    
                    result['models'][model_key]['total_cost'] += cost
                    result['models'][model_key]['total_cost_usd'] += cost_usd
                    
                    # Track token usage if applicable
                    usage_type = model_info.get('usage_type', 'other')
                    if usage_type not in result['models'][model_key]['usage_breakdown']:
                        result['models'][model_key]['usage_breakdown'][usage_type] = {
                            'quantity': 0,
                            'cost': 0,
                            'cost_usd': 0,
                            'unit': unit_of_measure
                        }
                    
                    result['models'][model_key]['usage_breakdown'][usage_type]['quantity'] += usage_quantity
                    result['models'][model_key]['usage_breakdown'][usage_type]['cost'] += cost
                    result['models'][model_key]['usage_breakdown'][usage_type]['cost_usd'] += cost_usd
                
                result['services'][service_name]['resources'][resource_name]['meters'].append(meter_detail)
                result['services'][service_name]['resources'][resource_name]['total_cost'] += cost
                result['services'][service_name]['resources'][resource_name]['total_cost_usd'] += cost_usd
                
            except Exception as e:
                logger.warning(f"Error processing AI cost row: {str(e)}")
                continue
        
        # Sort services and models by cost
        result['services'] = dict(sorted(
            result['services'].items(),
            key=lambda x: x[1]['total_cost_usd'],
            reverse=True
        ))
        
        result['models'] = dict(sorted(
            result['models'].items(),
            key=lambda x: x[1]['total_cost_usd'],
            reverse=True
        ))
        
        return result
    
    def _parse_ai_model_info(self, meter_name: str, meter_category: str, meter_subcategory: str) -> Optional[Dict]:
        """
        Parse AI model information from meter details
        """
        model_info = {}
        meter_lower = meter_name.lower()
        
        # OpenAI models
        if 'gpt-4' in meter_lower:
            if 'turbo' in meter_lower:
                model_info['model'] = 'gpt-4-turbo'
            elif '32k' in meter_lower:
                model_info['model'] = 'gpt-4-32k'
            else:
                model_info['model'] = 'gpt-4'
        elif 'gpt-35' in meter_lower or 'gpt-3.5' in meter_lower:
            model_info['model'] = 'gpt-3.5-turbo'
        elif 'davinci' in meter_lower:
            model_info['model'] = 'text-davinci-003'
        elif 'ada' in meter_lower:
            if 'embedding' in meter_lower:
                model_info['model'] = 'text-embedding-ada-002'
            else:
                model_info['model'] = 'ada'
        elif 'dall-e' in meter_lower:
            model_info['model'] = 'dall-e'
        elif 'whisper' in meter_lower:
            model_info['model'] = 'whisper'
        
        # Determine usage type (input/output/cached tokens)
        if 'input' in meter_lower or 'prompt' in meter_lower:
            model_info['usage_type'] = 'input_tokens'
        elif 'output' in meter_lower or 'completion' in meter_lower:
            model_info['usage_type'] = 'output_tokens'
        elif 'cached' in meter_lower:
            model_info['usage_type'] = 'cached_tokens'
        elif 'embedding' in meter_lower:
            model_info['usage_type'] = 'embeddings'
        elif 'image' in meter_lower:
            model_info['usage_type'] = 'images'
        elif 'audio' in meter_lower or 'transcription' in meter_lower:
            model_info['usage_type'] = 'audio_minutes'
        else:
            model_info['usage_type'] = 'other'
        
        return model_info if model_info.get('model') else None


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
        logger.info(f"Azure costs request - User: {user_info.get('username', 'unknown')}")
        
        # Get cost data
        cost_service = AzureCostManagementService()
        cost_data = cost_service.get_subscription_costs(
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
        days = int(request.args.get('days', 30))
        
        # Calculate date range
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Get cost data
        cost_service = AzureCostManagementService()
        cost_data = cost_service.get_subscription_costs(
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
            "subscription_id": subscription_data.get('id', os.getenv('AZURE_SUBSCRIPTION_ID')),
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
        logger.info(f"Azure cost summary request - User: {user_info.get('username', 'unknown')}, Days: {days}")
        
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


def get_azure_period_costs_route():
    """
    Get Azure costs for specific periods (MTD, YTD, or custom)
    ---
    tags:
      - Azure Cost Management
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
      - name: period
        in: query
        type: string
        required: false
        description: Period type - 'mtd', 'ytd', or 'custom' (default 'mtd')
      - name: start_period
        in: query
        type: string
        required: false
        description: For custom period, start in YYYYMM format (e.g., 202401)
      - name: end_period
        in: query
        type: string
        required: false
        description: For custom period, end in YYYYMM format (e.g., 202412)
    produces:
      - application/json
    responses:
      200:
        description: Period cost data retrieved successfully
      400:
        description: Bad request - invalid parameters
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
        period_type = request.args.get('period', 'mtd').lower()
        start_period = request.args.get('start_period')
        end_period = request.args.get('end_period')
        
        # Validate custom period parameters
        if period_type == 'custom':
            if not start_period or not end_period:
                return create_api_response({
                    "error": "Bad Request",
                    "message": "start_period and end_period required for custom period"
                }, 400)
            
            # Validate format
            if len(start_period) != 6 or len(end_period) != 6:
                return create_api_response({
                    "error": "Bad Request",
                    "message": "Period format must be YYYYMM (e.g., 202401)"
                }, 400)
        
        # Log the API call
        logger.info(f"Azure period costs request - User: {user_info.get('username', 'unknown')}, Period: {period_type}")
        
        # Get cost data
        cost_service = AzureCostManagementService()
        cost_data = cost_service.get_period_costs(
            period_type=period_type,
            start_period=start_period,
            end_period=end_period
        )
        
        # Add period info to response
        cost_data['period_type'] = period_type
        if period_type == 'custom':
            cost_data['custom_period'] = {
                'start': start_period,
                'end': end_period
            }
        
        return create_api_response(cost_data, 200)
        
    except ValueError as e:
        logger.error(f"Configuration error in get_azure_period_costs_route: {str(e)}")
        return create_api_response({
            "error": "Configuration Error",
            "message": str(e)
        }, 400)
    except Exception as e:
        logger.error(f"Error in get_azure_period_costs_route: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": str(e)
        }, 500)


def get_azure_ai_costs_route():
    """
    Get detailed AI/ML/Cognitive Services costs with model breakdown
    ---
    tags:
      - Azure Cost Management
    parameters:
      - name: API-Key
        in: header
        type: string
        required: true
        description: API Key for authentication
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
        description: AI service costs retrieved successfully
        schema:
          type: object
          properties:
            subscription_id:
              type: string
            period:
              type: object
              properties:
                from:
                  type: string
                to:
                  type: string
            total_ai_cost:
              type: number
              description: Total AI services cost
            total_ai_cost_usd:
              type: number
              description: Total AI services cost in USD
            services:
              type: object
              description: Breakdown by AI service (OpenAI, Cognitive Services, etc.)
            models:
              type: object
              description: Breakdown by AI model with token usage details
              additionalProperties:
                type: object
                properties:
                  model:
                    type: string
                    description: Model name (e.g., gpt-4, gpt-3.5-turbo)
                  total_cost:
                    type: number
                  total_cost_usd:
                    type: number
                  usage_breakdown:
                    type: object
                    properties:
                      input_tokens:
                        type: object
                        properties:
                          quantity:
                            type: number
                          cost:
                            type: number
                          cost_usd:
                            type: number
                      output_tokens:
                        type: object
                        properties:
                          quantity:
                            type: number
                          cost:
                            type: number
                          cost_usd:
                            type: number
                      cached_tokens:
                        type: object
                        properties:
                          quantity:
                            type: number
                          cost:
                            type: number
                          cost_usd:
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
        
        # Log the API call
        logger.info(f"Azure AI costs request - User: {user_info.get('username', 'unknown')}")
        
        # Get AI cost data
        cost_service = AzureCostManagementService()
        ai_costs = cost_service.get_ai_service_costs(
            start_date=start_date,
            end_date=end_date
        )
        
        return create_api_response(ai_costs, 200)
        
    except ValueError as e:
        logger.error(f"Configuration error in get_azure_ai_costs_route: {str(e)}")
        return create_api_response({
            "error": "Configuration Error",
            "message": str(e)
        }, 400)
    except Exception as e:
        logger.error(f"Error in get_azure_ai_costs_route: {str(e)}")
        return create_api_response({
            "error": "Server Error",
            "message": str(e)
        }, 500)


def register_azure_cost_routes(app):
    """Register Azure cost management routes with the Flask app"""
    app.route('/azure/costs', methods=['GET'])(api_logger(get_azure_costs_route))
    app.route('/azure/costs/summary', methods=['GET'])(api_logger(get_azure_cost_summary_route))
    app.route('/azure/costs/period', methods=['GET'])(api_logger(get_azure_period_costs_route))
    app.route('/azure/costs/ai-services', methods=['GET'])(api_logger(get_azure_ai_costs_route))