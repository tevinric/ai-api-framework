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
        
        # Query body for detailed hierarchical cost data with meter-level granularity
        query_body = {
            "type": "ActualCost",  # Use ActualCost for more detailed meter information
            "timeframe": "Custom",
            "timePeriod": {
                "from": start_date,
                "to": end_date
            },
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "totalCost": {
                        "name": "Cost",
                        "function": "Sum"
                    },
                    "totalCostUSD": {
                        "name": "CostUSD",
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
                        "name": "ResourceGroupName"
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
                # Extract values from row with enhanced column mapping
                cost = (row[column_map.get('Cost')] if 'Cost' in column_map else 
                       row[column_map.get('PreTaxCost')] if 'PreTaxCost' in column_map else 0) or 0
                cost_usd = (row[column_map.get('CostUSD')] if 'CostUSD' in column_map else 
                           row[column_map.get('PreTaxCostUSD')] if 'PreTaxCostUSD' in column_map else cost) or cost
                
                resource_group = (row[column_map.get('ResourceGroupName')] if 'ResourceGroupName' in column_map else
                                row[column_map.get('ResourceGroup')] if 'ResourceGroup' in column_map else 'unassigned') or 'unassigned'
                resource_id = row[column_map.get('ResourceId')] if 'ResourceId' in column_map else 'unknown'
                service_name = row[column_map.get('ServiceName')] if 'ServiceName' in column_map else 'unknown'
                resource_type = row[column_map.get('ResourceType')] if 'ResourceType' in column_map else 'unknown'
                
                # Additional meter details
                meter_name = row[column_map.get('MeterName')] if 'MeterName' in column_map else 'unknown'
                meter_category = row[column_map.get('MeterCategory')] if 'MeterCategory' in column_map else 'unknown'
                meter_subcategory = row[column_map.get('MeterSubCategory')] if 'MeterSubCategory' in column_map else 'unknown'
                unit_of_measure = row[column_map.get('UnitOfMeasure')] if 'UnitOfMeasure' in column_map else 'unknown'
                usage_quantity = (row[column_map.get('UsageQuantity')] if 'UsageQuantity' in column_map else 0) or 0
                
                currency = row[column_map.get('Currency')] if 'Currency' in column_map else 'USD'
                
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
                        "resources": {}
                    }
                
                # Update resource group total
                rg = hierarchy['subscription']['resourceGroups'][resource_group]
                rg['totalCost'] += cost
                rg['totalCostUSD'] += cost_usd
                
                # Extract resource name from resource ID
                resource_name = resource_id.split('/')[-1] if resource_id else 'unknown'
                
                # Initialize resource if doesn't exist
                if resource_name not in rg['resources']:
                    rg['resources'][resource_name] = {
                        "resourceId": resource_id,
                        "resourceName": resource_name,
                        "resourceType": resource_type,
                        "serviceName": service_name,
                        "totalCost": 0,
                        "totalCostUSD": 0,
                        "currency": currency,
                        "meters": []
                    }
                
                # Update resource totals
                resource_ref = rg['resources'][resource_name]
                resource_ref['totalCost'] += cost
                resource_ref['totalCostUSD'] += cost_usd
                
                # Add detailed meter entry
                meter_entry = {
                    "meterName": meter_name,
                    "meterCategory": meter_category,
                    "meterSubCategory": meter_subcategory,
                    "usageQuantity": usage_quantity,
                    "unitOfMeasure": unit_of_measure,
                    "cost": round(cost, 2),
                    "costUSD": round(cost_usd, 2)
                }
                
                resource_ref['meters'].append(meter_entry)
                    
            except Exception as e:
                logger.warning(f"Error processing row: {str(e)}")
                continue
        
        # Sort meters within each resource and convert resources dict to sorted list
        for rg_name, rg_data in hierarchy['subscription']['resourceGroups'].items():
            # Sort resources within resource group by cost
            rg_data['resources'] = dict(sorted(
                rg_data['resources'].items(),
                key=lambda x: x[1]['totalCostUSD'],
                reverse=True
            ))
            
            # Sort meters within each resource by cost
            for resource_name, resource_data in rg_data['resources'].items():
                resource_data['meters'] = sorted(
                    resource_data['meters'],
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
                            end_date: Optional[str] = None, use_fallback: bool = False) -> Dict:
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
        
        if use_fallback:
            # Fallback: Get all costs and filter client-side
            logger.info("Using fallback method - getting all costs and filtering client-side")
            all_costs = self.get_subscription_costs(start_date=start_date, end_date=end_date)
            return self._filter_ai_costs_from_all(all_costs, subscription_id, start_date, end_date)
        
        # Query for individual meter entries with minimal grouping to get granular details
        query_body = {
            "type": "ActualCost",  # ActualCost provides individual cost records
            "timeframe": "Custom",
            "timePeriod": {
                "from": start_date,
                "to": end_date
            },
            "dataset": {
                "granularity": "Daily",  # Use Daily granularity for detailed records
                "aggregation": {
                    "totalCost": {
                        "name": "Cost",
                        "function": "Sum"
                    },
                    "totalCostUSD": {
                        "name": "CostUSD", 
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
                        "name": "ResourceGroupName"
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
                        "name": "ResourceType"
                    },
                    {
                        "type": "Dimension",
                        "name": "UnitOfMeasure"
                    },
                    {
                        "type": "Dimension",
                        "name": "UsageDate"
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
                                    "Azure Cognitive Search",
                                    "Microsoft Defender for Cloud"
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
            if response.status_code == 400 and not use_fallback:
                logger.info("Trying fallback method without filters...")
                return self.get_ai_service_costs(start_date, end_date, use_fallback=True)
            elif response.status_code == 401:
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
        Format AI services cost response with detailed meter-level data matching Azure portal
        Structure: Resource Groups -> Resources -> Services -> Individual Meter Records (portal match)
        """
        result = {
            "subscription_id": subscription_id,
            "period": {
                "from": start_date,
                "to": end_date
            },
            "total_ai_cost": 0,
            "total_ai_cost_usd": 0,
            "resource_groups": {},
            "meter_summary": {},
            "model_summary": {},
            "individual_meter_records": [],  # New: Individual records like portal
            "metadata": {
                "queryTime": datetime.utcnow().isoformat(),
                "rowCount": 0,
                "detail_level": "granular_meter_records"
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
                # Extract fields from ActualCost query with enhanced column mapping
                cost = (row[column_map.get('Cost')] if 'Cost' in column_map else 
                       row[column_map.get('PreTaxCost')] if 'PreTaxCost' in column_map else 0) or 0
                cost_usd = (row[column_map.get('CostUSD')] if 'CostUSD' in column_map else 
                           row[column_map.get('PreTaxCostUSD')] if 'PreTaxCostUSD' in column_map else cost) or cost
                
                # Handle different resource group column names
                resource_group = (row[column_map.get('ResourceGroupName')] if 'ResourceGroupName' in column_map else
                                row[column_map.get('ResourceGroup')] if 'ResourceGroup' in column_map else 'Unknown') or 'Unknown'
                
                resource_id = row[column_map.get('ResourceId')] if 'ResourceId' in column_map else 'Unknown'
                service_name = row[column_map.get('ServiceName')] if 'ServiceName' in column_map else 'Unknown'
                meter_name = row[column_map.get('MeterName')] if 'MeterName' in column_map else 'Unknown'
                meter_category = row[column_map.get('MeterCategory')] if 'MeterCategory' in column_map else 'Unknown'
                meter_subcategory = row[column_map.get('MeterSubCategory')] if 'MeterSubCategory' in column_map else 'Unknown'
                resource_type = row[column_map.get('ResourceType')] if 'ResourceType' in column_map else 'Unknown'
                unit_of_measure = row[column_map.get('UnitOfMeasure')] if 'UnitOfMeasure' in column_map else 'Unknown'
                usage_date = row[column_map.get('UsageDate')] if 'UsageDate' in column_map else 'Unknown'
                usage_quantity = (row[column_map.get('UsageQuantity')] if 'UsageQuantity' in column_map else
                                row[column_map.get('Quantity')] if 'Quantity' in column_map else 0) or 0
                
                # Skip if cost is zero or negligible
                if cost_usd < 0.001:
                    continue
                
                # Update totals
                result['total_ai_cost'] += cost
                result['total_ai_cost_usd'] += cost_usd
                
                # Extract resource name from resource ID
                resource_name = resource_id.split('/')[-1] if resource_id != 'Unknown' else 'Unknown'
                
                # Build the hierarchy: Resource Group -> Resource -> Service -> Meters
                # Initialize Resource Group
                if resource_group not in result['resource_groups']:
                    result['resource_groups'][resource_group] = {
                        'name': resource_group,
                        'total_cost': 0,
                        'total_cost_usd': 0,
                        'resources': {}
                    }
                
                # Initialize Resource within Resource Group
                if resource_name not in result['resource_groups'][resource_group]['resources']:
                    result['resource_groups'][resource_group]['resources'][resource_name] = {
                        'name': resource_name,
                        'resource_id': resource_id,
                        'resource_type': resource_type,
                        'total_cost': 0,
                        'total_cost_usd': 0,
                        'services': {}
                    }
                
                # Initialize Service within Resource
                resource_ref = result['resource_groups'][resource_group]['resources'][resource_name]
                if service_name not in resource_ref['services']:
                    resource_ref['services'][service_name] = {
                        'name': service_name,
                        'category': meter_category,
                        'total_cost': 0,
                        'total_cost_usd': 0,
                        'meters': []
                    }
                
                # Create detailed meter entry (individual cost record like portal)
                meter_detail = {
                    'meter_name': meter_name,
                    'meter_category': meter_category,
                    'meter_subcategory': meter_subcategory,
                    'usage_quantity': usage_quantity,
                    'unit_of_measure': unit_of_measure,
                    'cost': round(cost, 2),
                    'cost_usd': round(cost_usd, 2),
                    'usage_date': usage_date,
                    'resource_name': resource_name,
                    'resource_group': resource_group,
                    'service_name': service_name
                }
                
                # Parse model and token information from meter name
                model_info = self._parse_ai_model_info(meter_name, meter_category, meter_subcategory)
                if model_info:
                    meter_detail.update(model_info)
                
                # Add individual meter record (like portal detail view)
                individual_record = meter_detail.copy()
                individual_record['resource_id'] = resource_id
                individual_record['resource_type'] = resource_type
                result['individual_meter_records'].append(individual_record)
                
                # Add meter to service
                resource_ref['services'][service_name]['meters'].append(meter_detail)
                
                # Update all level totals
                resource_ref['services'][service_name]['total_cost'] += cost
                resource_ref['services'][service_name]['total_cost_usd'] += cost_usd
                resource_ref['total_cost'] += cost
                resource_ref['total_cost_usd'] += cost_usd
                result['resource_groups'][resource_group]['total_cost'] += cost
                result['resource_groups'][resource_group]['total_cost_usd'] += cost_usd
                
                # Track meters for summary (like portal's meter view)
                meter_key = f"{meter_name}_{meter_category}"
                if meter_key not in result['meter_summary']:
                    result['meter_summary'][meter_key] = {
                        'meter_name': meter_name,
                        'meter_category': meter_category,
                        'total_cost': 0,
                        'total_cost_usd': 0,
                        'usage_count': 0
                    }
                result['meter_summary'][meter_key]['total_cost'] += cost
                result['meter_summary'][meter_key]['total_cost_usd'] += cost_usd
                result['meter_summary'][meter_key]['usage_count'] += 1
                
                # Track models for summary
                if model_info and 'model' in model_info:
                    model_key = model_info['model']
                    if model_key not in result['model_summary']:
                        result['model_summary'][model_key] = {
                            'model': model_key,
                            'total_cost': 0,
                            'total_cost_usd': 0,
                            'usage_breakdown': {}
                        }
                    
                    result['model_summary'][model_key]['total_cost'] += cost
                    result['model_summary'][model_key]['total_cost_usd'] += cost_usd
                    
                    # Track token usage breakdown
                    usage_type = model_info.get('usage_type', 'other')
                    if usage_type not in result['model_summary'][model_key]['usage_breakdown']:
                        result['model_summary'][model_key]['usage_breakdown'][usage_type] = {
                            'quantity': 0,
                            'cost': 0,
                            'cost_usd': 0,
                            'unit': unit_of_measure
                        }
                    
                    result['model_summary'][model_key]['usage_breakdown'][usage_type]['quantity'] += usage_quantity
                    result['model_summary'][model_key]['usage_breakdown'][usage_type]['cost'] += cost
                    result['model_summary'][model_key]['usage_breakdown'][usage_type]['cost_usd'] += cost_usd
                
            except Exception as e:
                logger.warning(f"Error processing AI cost row: {str(e)}")
                continue
        
        # Sort all hierarchies by cost (highest first) - matching Azure portal
        # Sort resource groups by total cost
        result['resource_groups'] = dict(sorted(
            result['resource_groups'].items(),
            key=lambda x: x[1]['total_cost_usd'],
            reverse=True
        ))
        
        # Sort resources within each resource group
        for rg_name, rg_data in result['resource_groups'].items():
            rg_data['resources'] = dict(sorted(
                rg_data['resources'].items(),
                key=lambda x: x[1]['total_cost_usd'],
                reverse=True
            ))
            
            # Sort services within each resource and meters within services
            for resource_name, resource_data in rg_data['resources'].items():
                resource_data['services'] = dict(sorted(
                    resource_data['services'].items(),
                    key=lambda x: x[1]['total_cost_usd'],
                    reverse=True
                ))
                
                # Sort meters within each service by cost
                for service_name, service_data in resource_data['services'].items():
                    service_data['meters'] = sorted(
                        service_data['meters'],
                        key=lambda x: x['cost_usd'],
                        reverse=True
                    )
        
        # Sort summaries by cost
        result['meter_summary'] = dict(sorted(
            result['meter_summary'].items(),
            key=lambda x: x[1]['total_cost_usd'],
            reverse=True
        ))
        
        result['model_summary'] = dict(sorted(
            result['model_summary'].items(),
            key=lambda x: x[1]['total_cost_usd'],
            reverse=True
        ))
        
        # Sort individual meter records by cost (matching portal order)
        result['individual_meter_records'] = sorted(
            result['individual_meter_records'],
            key=lambda x: x['cost_usd'],
            reverse=True
        )
        
        return result
    
    def _filter_ai_costs_from_all(self, all_costs: Dict, subscription_id: str, 
                                 start_date: str, end_date: str) -> Dict:
        """
        Filter AI/ML services from standard cost response when direct API filtering fails
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
                "rowCount": 0,
                "fallback_method": True
            }
        }
        
        # AI service keywords to look for
        ai_keywords = [
            'cognitive', 'openai', 'machine learning', 'databricks', 
            'search', 'ai', 'ml', 'gpt', 'whisper', 'dall-e',
            'embedding', 'vision', 'speech', 'text analytics'
        ]
        
        # Filter resources that appear to be AI-related
        if 'subscription' in all_costs and 'resourceGroups' in all_costs['subscription']:
            for rg_name, rg_data in all_costs['subscription']['resourceGroups'].items():
                if 'resources' in rg_data:
                    for resource in rg_data['resources']:
                        resource_name = resource.get('resourceName', '').lower()
                        service_name = resource.get('serviceName', '').lower()
                        resource_type = resource.get('resourceType', '').lower()
                        
                        # Check if this looks like an AI service
                        is_ai_service = any(keyword in resource_name or 
                                          keyword in service_name or 
                                          keyword in resource_type 
                                          for keyword in ai_keywords)
                        
                        if is_ai_service:
                            result['metadata']['rowCount'] += 1
                            cost = resource.get('cost', 0)
                            cost_usd = resource.get('costUSD', 0)
                            
                            result['total_ai_cost'] += cost
                            result['total_ai_cost_usd'] += cost_usd
                            
                            # Determine service name
                            if 'openai' in resource_name or 'gpt' in resource_name:
                                service_name = 'Azure OpenAI'
                            elif 'cognitive' in resource_name or 'cognitive' in service_name:
                                service_name = 'Cognitive Services'
                            elif 'machine learning' in service_name or 'ml' in resource_name:
                                service_name = 'Azure Machine Learning'
                            elif 'search' in resource_name:
                                service_name = 'Azure Cognitive Search'
                            else:
                                service_name = resource.get('serviceName', 'AI Services')
                            
                            # Initialize service if not exists
                            if service_name not in result['services']:
                                result['services'][service_name] = {
                                    'name': service_name,
                                    'total_cost': 0,
                                    'total_cost_usd': 0,
                                    'resources': {}
                                }
                            
                            result['services'][service_name]['total_cost'] += cost
                            result['services'][service_name]['total_cost_usd'] += cost_usd
                            
                            # Add resource
                            resource_key = resource.get('resourceName', 'Unknown')
                            result['services'][service_name]['resources'][resource_key] = {
                                'name': resource_key,
                                'resource_id': resource.get('resourceId', ''),
                                'total_cost': cost,
                                'total_cost_usd': cost_usd,
                                'meters': [{
                                    'meter_name': 'Aggregated Usage',
                                    'meter_category': service_name,
                                    'cost': cost,
                                    'cost_usd': cost_usd
                                }]
                            }
                            
                            # Try to parse model info from resource name
                            model_info = self._parse_ai_model_info(resource_name, service_name, '')
                            if model_info:
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
        
        # Sort by cost
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
        Parse AI model information from meter details - enhanced to match portal examples
        Examples from portal: 'gpt-4o 1120 Outp glbl Tokens', 'gpt-4o 1120 Inp glbl Tokens'
        """
        model_info = {}
        meter_lower = meter_name.lower()
        
        # Enhanced OpenAI model detection based on portal examples
        if 'gpt-4o' in meter_lower:
            if '1120' in meter_lower:
                model_info['model'] = 'gpt-4o-1120'
            else:
                model_info['model'] = 'gpt-4o'
        elif 'gpt-4' in meter_lower:
            if 'mini' in meter_lower:
                if '0718' in meter_lower:
                    model_info['model'] = 'gpt-4o-mini-0718'
                else:
                    model_info['model'] = 'gpt-4o-mini'
            elif 'turbo' in meter_lower:
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
        elif 'text-embedding' in meter_lower:
            if 'large' in meter_lower:
                model_info['model'] = 'text-embedding-3-large'
            elif '3' in meter_lower:
                model_info['model'] = 'text-embedding-3-small'
            else:
                model_info['model'] = 'text-embedding-ada-002'
        elif 'dall-e' in meter_lower or 'dalle' in meter_lower:
            model_info['model'] = 'dall-e'
        elif 'whisper' in meter_lower:
            model_info['model'] = 'whisper'
        elif 'kontext' in meter_lower:
            model_info['model'] = 'kontext-pro'
        elif 'flux' in meter_lower:
            model_info['model'] = 'flux-1.1-pro'
        elif 'llama' in meter_lower:
            if 'maverick' in meter_lower:
                model_info['model'] = 'llama-4-maverick-17b'
            else:
                model_info['model'] = 'llama'
        
        # Enhanced usage type detection based on portal examples
        if 'inp' in meter_lower or 'input' in meter_lower or 'prompt' in meter_lower:
            model_info['usage_type'] = 'input_tokens'
        elif 'outp' in meter_lower or 'output' in meter_lower or 'completion' in meter_lower:
            model_info['usage_type'] = 'output_tokens'
        elif 'cached' in meter_lower:
            model_info['usage_type'] = 'cached_tokens'
        elif 'embedding' in meter_lower:
            model_info['usage_type'] = 'embeddings'
        elif 'image' in meter_lower or 'images' in meter_lower:
            model_info['usage_type'] = 'images'
        elif 'audio' in meter_lower or 'transcription' in meter_lower:
            model_info['usage_type'] = 'audio_minutes'
        elif 'text records' in meter_lower:
            model_info['usage_type'] = 'text_records'
        elif 'tokens' in meter_lower:
            model_info['usage_type'] = 'tokens'
        else:
            model_info['usage_type'] = 'other'
        
        # Parse additional details from meter name
        if 'glbl' in meter_lower:
            model_info['region'] = 'global'
        
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
            for resource_data in rg_data['resources'].values():
                all_resources.append(resource_data)
        
        all_resources.sort(key=lambda x: x['totalCostUSD'], reverse=True)
        top_resources = []
        for resource in all_resources[:10]:
            top_resources.append({
                "name": resource['resourceName'],
                "type": resource['resourceType'],
                "service": resource['serviceName'],
                "cost": round(resource['totalCostUSD'], 2),
                "percentage": round((resource['totalCostUSD'] / total_cost * 100) if total_cost > 0 else 0, 2)
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
            resource_groups:
              type: object
              description: Hierarchical breakdown by resource group containing all resources and services
            services:
              type: object
              description: Breakdown by AI service (OpenAI, Cognitive Services, etc.)
            models:
              type: object
              description: Breakdown by AI model with token usage details
            individual_meter_records:
              type: array
              description: Individual meter usage records matching Azure portal detail view
              items:
                type: object
                properties:
                  meter_name:
                    type: string
                    description: Specific meter name (e.g., 'gpt-4o 1120 Outp glbl Tokens')
                  meter_category:
                    type: string
                    description: Meter category (e.g., 'Cognitive Services')
                  meter_subcategory:
                    type: string
                    description: Meter subcategory
                  service_name:
                    type: string
                    description: Service name (e.g., 'Cognitive Services')
                  resource_name:
                    type: string
                    description: Resource name
                  resource_group:
                    type: string
                    description: Resource group name
                  usage_quantity:
                    type: number
                    description: Quantity of usage
                  unit_of_measure:
                    type: string
                    description: Unit of measurement (e.g., 'Tokens', 'Images')
                  cost:
                    type: number
                    description: Cost in original currency
                  cost_usd:
                    type: number
                    description: Cost in USD
                  usage_date:
                    type: string
                    description: Date of usage
                  model:
                    type: string
                    description: Parsed AI model name (if applicable)
                  usage_type:
                    type: string
                    description: Token type (input_tokens, output_tokens, etc.)
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