$ python app.py
INFO:apis.app_init:Initializing application components...
INFO:apis.utils.job_scheduler:Job scheduler thread started
INFO:apis.utils.job_scheduler:Job scheduler started
INFO:apis.app_init:Job scheduler initialized
INFO:apis.app_init:Application initialization complete
INFO:apis.agents.tool_registry:Registered tool: web_search
INFO:apis.agents.tool_registry:Registered tool: database_query
INFO:apis.agents.tool_registry:Registered tool: calculator
INFO:apis.agents.tool_registry:Registered tool: send_email
INFO:apis.agents.tool_registry:Registered tool: data_analysis
INFO:apis.agents.tool_registry:Registered tool: document_generator
INFO:apis.agents.tool_registry:Registered tool: calendar_manager
INFO:apis.agents.tool_registry:Registered tool: task_manager
ERROR:apis.agents.tool_registry:Error loading custom tools: ('42S02', "[42S02] [Microsoft][ODBC Driver 17 for SQL Server][SQL Server]Invalid object name 'custom_tools'. (208) (SQLExecDirectW)")
Traceback (most recent call last):
  File "C:\Users\E100545\Git\ai-api-framework\app.py", line 361, in <module>
    from apis.agents.agent_routes import agents_bp
  File "C:\Users\E100545\Git\ai-api-framework\apis\agents\agent_routes.py", line 42, in <module>
    @check_balance(cost=1.0)
     ^^^^^^^^^^^^^^^^^^^^^^^
TypeError: check_balance() got an unexpected keyword argument 'cost'