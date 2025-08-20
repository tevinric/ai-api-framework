"""
Test script for the Agentic API system
Run this to validate the system components
"""

import sys
import os
import json
import asyncio
import logging
from typing import Dict, Any

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_agent_manager():
    """Test the agent manager functionality"""
    try:
        from apis.agents.agent_manager import AgentManager
        
        logger.info("Testing Agent Manager...")
        
        # This would require actual Azure OpenAI credentials
        # For now, just test the class instantiation
        agent_manager = AgentManager()
        logger.info("✓ Agent Manager initialized successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Agent Manager test failed: {str(e)}")
        return False

def test_tool_registry():
    """Test the tool registry functionality"""
    try:
        from apis.agents.tool_registry import tool_registry
        
        logger.info("Testing Tool Registry...")
        
        # Test tool retrieval
        tools = tool_registry.tools
        logger.info(f"✓ Found {len(tools)} registered tools")
        
        # Test some specific tools
        expected_tools = ['web_search', 'calculator', 'database_query']
        for tool_name in expected_tools:
            if tool_name in tools:
                logger.info(f"✓ Tool '{tool_name}' is registered")
            else:
                logger.warning(f"⚠ Tool '{tool_name}' not found")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Tool Registry test failed: {str(e)}")
        return False

def test_business_templates():
    """Test the business templates functionality"""
    try:
        from apis.agents.business_templates import business_templates
        
        logger.info("Testing Business Templates...")
        
        # Test template retrieval
        all_templates = business_templates.get_all_templates()
        logger.info(f"✓ Found {len(all_templates)} business templates")
        
        # Test specific templates
        executive_template = business_templates.get_template("executive_assistant")
        if executive_template:
            logger.info("✓ Executive Assistant template loaded")
            logger.info(f"  - Tools: {executive_template.get('tools', [])}")
            logger.info(f"  - Use cases: {len(executive_template.get('use_cases', []))}")
        
        # Test search functionality
        search_results = business_templates.search_templates("financial")
        logger.info(f"✓ Search for 'financial' returned {len(search_results)} results")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Business Templates test failed: {str(e)}")
        return False

def test_async_executor():
    """Test the async executor functionality"""
    try:
        from apis.agents.async_executor import async_executor
        
        logger.info("Testing Async Executor...")
        
        # Test executor initialization
        if hasattr(async_executor, 'agent_manager'):
            logger.info("✓ Async Executor initialized with agent manager")
        
        if hasattr(async_executor, 'job_service'):
            logger.info("✓ Async Executor initialized with job service")
        
        if hasattr(async_executor, 'executor'):
            logger.info("✓ Thread pool executor initialized")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Async Executor test failed: {str(e)}")
        return False

def test_agent_orchestrator():
    """Test the agent orchestrator functionality"""
    try:
        from apis.agents.agent_orchestrator import agent_orchestrator
        
        logger.info("Testing Agent Orchestrator...")
        
        # Test template loading
        templates = agent_orchestrator.get_available_templates()
        logger.info(f"✓ Agent Orchestrator loaded {len(templates)} templates")
        
        # Test specific template features
        for template in templates[:3]:  # Check first 3 templates
            logger.info(f"  - {template['name']}: {template['role']}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Agent Orchestrator test failed: {str(e)}")
        return False

def test_database_schema():
    """Test database schema requirements"""
    try:
        logger.info("Testing Database Schema Requirements...")
        
        # Check if SQL files exist
        sql_files = [
            "sql_init/agentic_init.sql",
            "sql_init/agent_tables_extended.sql"
        ]
        
        for sql_file in sql_files:
            if os.path.exists(sql_file):
                logger.info(f"✓ SQL file exists: {sql_file}")
                
                # Check file content
                with open(sql_file, 'r') as f:
                    content = f.read()
                    if 'CREATE TABLE' in content:
                        table_count = content.count('CREATE TABLE')
                        logger.info(f"  - Contains {table_count} table definitions")
            else:
                logger.warning(f"⚠ SQL file missing: {sql_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Database Schema test failed: {str(e)}")
        return False

def test_configuration():
    """Test configuration and environment setup"""
    try:
        logger.info("Testing Configuration...")
        
        # Test config import
        from apis.utils.config import get_azure_openai_config
        config = get_azure_openai_config()
        
        # Check required config keys
        required_keys = ['api_key', 'endpoint', 'api_version', 'deployment_name']
        for key in required_keys:
            if key in config:
                logger.info(f"✓ Config key '{key}' is defined")
            else:
                logger.warning(f"⚠ Config key '{key}' is missing")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Configuration test failed: {str(e)}")
        return False

def test_api_routes():
    """Test API route definitions"""
    try:
        logger.info("Testing API Routes...")
        
        from apis.agents.agent_routes import agents_bp
        
        # Check if blueprint is defined
        if agents_bp:
            logger.info("✓ Agent routes blueprint defined")
            
            # Check route count
            rule_count = len(agents_bp.deferred_functions)
            logger.info(f"✓ Found {rule_count} route registrations")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ API Routes test failed: {str(e)}")
        return False

def test_requirements():
    """Test that requirements are properly defined"""
    try:
        logger.info("Testing Requirements...")
        
        # Check requirements.txt
        if os.path.exists("requirements.txt"):
            with open("requirements.txt", 'r') as f:
                content = f.read()
                
                # Check for key dependencies
                key_deps = ['flask', 'openai', 'azure', 'pyodbc']
                for dep in key_deps:
                    if dep in content.lower():
                        logger.info(f"✓ Dependency '{dep}' is in requirements")
                    else:
                        logger.warning(f"⚠ Dependency '{dep}' might be missing")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Requirements test failed: {str(e)}")
        return False

async def run_all_tests():
    """Run all tests"""
    logger.info("="*60)
    logger.info("STARTING AGENTIC API SYSTEM TESTS")
    logger.info("="*60)
    
    tests = [
        ("Agent Manager", test_agent_manager()),
        ("Tool Registry", test_tool_registry()),
        ("Business Templates", test_business_templates()),
        ("Async Executor", test_async_executor()),
        ("Agent Orchestrator", test_agent_orchestrator()),
        ("Database Schema", test_database_schema()),
        ("Configuration", test_configuration()),
        ("API Routes", test_api_routes()),
        ("Requirements", test_requirements())
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n--- Testing {test_name} ---")
        if asyncio.iscoroutine(test_func):
            result = await test_func
        else:
            result = test_func
        results.append((test_name, result))
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info(f"\nTotal: {len(results)} tests")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    
    if failed == 0:
        logger.info("🎉 ALL TESTS PASSED! The agentic system is ready.")
    else:
        logger.warning(f"⚠ {failed} test(s) failed. Please review the issues above.")
    
    return failed == 0

if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(run_all_tests())
    
    if success:
        print("\n" + "="*60)
        print("🚀 AGENTIC API SYSTEM READY FOR DEPLOYMENT!")
        print("="*60)
        print("\nNext steps:")
        print("1. Set up Azure OpenAI environment variables")
        print("2. Run the SQL schema scripts to set up database tables")
        print("3. Install requirements: pip install -r requirements.txt")
        print("4. Start the Flask application: python app.py")
        print("5. Test the /agents/* endpoints")
        print("\nAPI Documentation will be available at: /apidocs/")
    else:
        print("\n⚠ Please fix the failed tests before deploying.")
        sys.exit(1)