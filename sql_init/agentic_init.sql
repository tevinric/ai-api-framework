-- Database schema additions for agentic LLM features

-- Table to store agent tasks and their execution details
CREATE TABLE agent_tasks (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    agent_id NVARCHAR(255) NOT NULL,
    user_id UNIQUEIDENTIFIER NOT NULL,
    task_input NVARCHAR(MAX) NOT NULL,
    context NVARCHAR(MAX), -- JSON blob for execution context
    status NVARCHAR(50) NOT NULL DEFAULT 'pending', -- idle, thinking, planning, executing, completed, error
    steps NVARCHAR(MAX), -- JSON array of execution steps
    result NVARCHAR(MAX), -- Final result/response
    error NVARCHAR(MAX), -- Error message if status = error
    
    -- Token usage tracking
    prompt_tokens INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    cached_tokens INT DEFAULT 0,
    llm_calls INT DEFAULT 0, -- Number of LLM calls made
    model_used NVARCHAR(100), -- Model used for this task
    
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    completed_at DATETIME2,
    modified_at DATETIME2 DEFAULT GETUTCDATE(),
    
    -- Foreign key to users table
    CONSTRAINT FK_agent_tasks_user FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Index for efficient querying by user and status
CREATE INDEX IDX_agent_tasks_user_status ON agent_tasks(user_id, status, created_at);
CREATE INDEX IDX_agent_tasks_agent_id ON agent_tasks(agent_id, created_at);

-- Table to store agent memory/conversation history
CREATE TABLE agent_memory (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    agent_id NVARCHAR(255) NOT NULL,
    role NVARCHAR(50) NOT NULL, -- user, assistant, system, tool
    content NVARCHAR(MAX) NOT NULL,
    timestamp DATETIME2 DEFAULT GETUTCDATE(),
    metadata NVARCHAR(MAX), -- JSON blob for additional message metadata
    
    -- Index for efficient retrieval of recent messages
    INDEX IDX_agent_memory_agent_time (agent_id, timestamp DESC)
);

-- Table to store tool execution logs
CREATE TABLE tool_executions (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    task_id UNIQUEIDENTIFIER NOT NULL,
    tool_name NVARCHAR(100) NOT NULL,
    parameters NVARCHAR(MAX), -- JSON blob of tool parameters
    result NVARCHAR(MAX), -- Tool execution result
    error NVARCHAR(MAX), -- Error message if tool failed
    execution_time_ms INT, -- Execution time in milliseconds
    started_at DATETIME2 DEFAULT GETUTCDATE(),
    completed_at DATETIME2,
    
    -- Foreign key to agent_tasks
    CONSTRAINT FK_tool_executions_task FOREIGN KEY (task_id) REFERENCES agent_tasks(id)
);

-- Index for tool usage analytics
CREATE INDEX IDX_tool_executions_tool_time ON tool_executions(tool_name, started_at);
CREATE INDEX IDX_tool_executions_task ON tool_executions(task_id, started_at);

-- Table to store agent configurations
CREATE TABLE agent_configurations (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    agent_name NVARCHAR(255) NOT NULL,
    model NVARCHAR(100) NOT NULL DEFAULT 'gpt-4o',
    max_iterations INT NOT NULL DEFAULT 10,
    enabled_tools NVARCHAR(MAX), -- JSON array of enabled tool names
    system_prompt NVARCHAR(MAX), -- Custom system prompt
    is_default BIT DEFAULT 0,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    modified_at DATETIME2 DEFAULT GETUTCDATE(),
    
    -- Foreign key to users table
    CONSTRAINT FK_agent_configurations_user FOREIGN KEY (user_id) REFERENCES users(id),
    
    -- Ensure only one default config per user
    CONSTRAINT UQ_agent_configurations_user_default UNIQUE (user_id, is_default, agent_name)
);

-- Table to store tool registry and metadata
CREATE TABLE agent_tools (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    tool_name NVARCHAR(100) NOT NULL UNIQUE,
    description NVARCHAR(500),
    category NVARCHAR(100) DEFAULT 'general',
    parameters_schema NVARCHAR(MAX), -- JSON schema for tool parameters
    is_enabled BIT DEFAULT 1,
    requires_auth BIT DEFAULT 0, -- Whether tool requires special authorization
    max_execution_time_ms INT DEFAULT 30000, -- Maximum allowed execution time
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    modified_at DATETIME2 DEFAULT GETUTCDATE()
);

-- Insert default tools
INSERT INTO agent_tools (tool_name, description, category, parameters_schema, max_execution_time_ms) VALUES
('web_search', 'Search the internet for current information', 'information', 
 '{"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer", "default": 5}}}', 
 30000),
('file_operations', 'Perform file operations like reading, writing, or analyzing files', 'file',
 '{"type": "object", "properties": {"operation": {"type": "string", "enum": ["read", "list", "analyze"]}, "file_id": {"type": "string"}}}',
 60000),
('calculator', 'Perform mathematical calculations and solve equations', 'math',
 '{"type": "object", "properties": {"expression": {"type": "string"}, "operation": {"type": "string", "default": "basic"}}}',
 10000),
('database_query', 'Query database for user-specific information', 'data',
 '{"type": "object", "properties": {"query_type": {"type": "string", "enum": ["usage_stats", "file_history", "balance"]}}}',
 15000),
('code_executor', 'Execute Python code in a sandboxed environment', 'development',
 '{"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string", "enum": ["python"]}}}',
 30000);

-- Table to control which users can access which tools
CREATE TABLE user_tool_access (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    tool_name NVARCHAR(100) NOT NULL,
    is_enabled BIT DEFAULT 1,
    granted_at DATETIME2 DEFAULT GETUTCDATE(),
    granted_by UNIQUEIDENTIFIER, -- Admin who granted access
    
    -- Foreign keys
    CONSTRAINT FK_user_tool_access_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT FK_user_tool_access_tool FOREIGN KEY (tool_name) REFERENCES agent_tools(tool_name),
    CONSTRAINT FK_user_tool_access_granted_by FOREIGN KEY (granted_by) REFERENCES users(id),
    
    -- Unique constraint to prevent duplicates
    CONSTRAINT UQ_user_tool_access UNIQUE (user_id, tool_name)
);

-- Grant default tool access to all existing users (run this after creating tables)
-- INSERT INTO user_tool_access (user_id, tool_name)
-- SELECT u.id, t.tool_name
-- FROM users u
-- CROSS JOIN agent_tools t
-- WHERE t.is_enabled = 1;

-- Add new endpoint entries for agentic features
INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) VALUES
(NEWID(), '/llm/agentic', 'Agentic LLM', 5.0, 'Agentic LLM endpoint with planning, tool use, and iteration', 1);

-- Update user_usage table to track agentic-specific metrics
ALTER TABLE user_usage ADD 
    tools_used NVARCHAR(MAX), -- JSON array of tools used in the request
    iterations_count INT DEFAULT 0, -- Number of agent iterations
    planning_time_ms INT DEFAULT 0; -- Time spent on planning

-- Create view for agent analytics
CREATE VIEW agent_analytics AS
SELECT 
    u.user_name,
    u.user_email,
    COUNT(at.id) as total_tasks,
    AVG(DATEDIFF(second, at.created_at, at.completed_at)) as avg_execution_time_seconds,
    SUM(CASE WHEN at.status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
    SUM(CASE WHEN at.status = 'error' THEN 1 ELSE 0 END) as failed_tasks,
    COUNT(DISTINCT te.tool_name) as unique_tools_used,
    AVG(JSON_VALUE(at.steps, '$.length()')) as avg_steps_per_task,
    
    -- Token usage analytics
    SUM(at.total_tokens) as total_tokens_consumed,
    AVG(at.total_tokens) as avg_tokens_per_task,
    SUM(at.llm_calls) as total_llm_calls,
    AVG(at.llm_calls) as avg_llm_calls_per_task,
    SUM(at.prompt_tokens) as total_prompt_tokens,
    SUM(at.completion_tokens) as total_completion_tokens
FROM users u
LEFT JOIN agent_tasks at ON u.id = at.user_id
LEFT JOIN tool_executions te ON at.id = te.task_id
WHERE at.created_at >= DATEADD(day, -30, GETDATE()) -- Last 30 days
GROUP BY u.id, u.user_name, u.user_email;

-- Create view for tool usage analytics
CREATE VIEW tool_usage_analytics AS
SELECT 
    at.tool_name,
    COUNT(*) as execution_count,
    AVG(at.execution_time_ms) as avg_execution_time_ms,
    SUM(CASE WHEN at.error IS NULL THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN at.error IS NOT NULL THEN 1 ELSE 0 END) as error_count,
    (SUM(CASE WHEN at.error IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as success_rate
FROM agent_tools tools
LEFT JOIN tool_executions at ON tools.tool_name = at.tool_name
WHERE at.started_at >= DATEADD(day, -30, GETDATE()) -- Last 30 days
GROUP BY at.tool_name;

-- Add indexes for performance
CREATE INDEX IDX_tool_executions_tool_time ON tool_executions(tool_name, started_at DESC);
CREATE INDEX IDX_agent_tasks_status_time ON agent_tasks(status, created_at DESC);
CREATE INDEX IDX_agent_memory_timestamp ON agent_memory(timestamp DESC);

-- Add triggers to update modified_at timestamps
CREATE TRIGGER TR_agent_tasks_update_modified
ON agent_tasks
AFTER UPDATE
AS
BEGIN
    UPDATE agent_tasks 
    SET modified_at = GETUTCDATE()
    WHERE id IN (SELECT id FROM inserted);
END;

CREATE TRIGGER TR_agent_configurations_update_modified
ON agent_configurations
AFTER UPDATE
AS
BEGIN
    UPDATE agent_configurations 
    SET modified_at = GETUTCDATE()
    WHERE id IN (SELECT id FROM inserted);
END;

-- Add stored procedure for cleaning up old agent memory
CREATE PROCEDURE CleanupAgentMemory
    @RetentionDays INT = 30
AS
BEGIN
    DELETE FROM agent_memory 
    WHERE timestamp < DATEADD(day, -@RetentionDays, GETUTCDATE());
    
    SELECT @@ROWCOUNT as rows_deleted;
END;

-- Add stored procedure for getting agent statistics
CREATE PROCEDURE GetAgentStatistics
    @UserId UNIQUEIDENTIFIER = NULL,
    @DaysBack INT = 30
AS
BEGIN
    DECLARE @StartDate DATETIME2 = DATEADD(day, -@DaysBack, GETUTCDATE());
    
    -- Overall statistics including token usage
    SELECT 
        COUNT(*) as total_tasks,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
        SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed_tasks,
        AVG(DATEDIFF(second, created_at, completed_at)) as avg_execution_time_seconds,
        
        -- Token usage statistics
        SUM(total_tokens) as total_tokens_consumed,
        AVG(total_tokens) as avg_tokens_per_task,
        SUM(llm_calls) as total_llm_calls,
        AVG(llm_calls) as avg_llm_calls_per_task,
        SUM(prompt_tokens) as total_prompt_tokens,
        SUM(completion_tokens) as total_completion_tokens
    FROM agent_tasks
    WHERE created_at >= @StartDate
    AND (@UserId IS NULL OR user_id = @UserId);
    
    -- Model usage breakdown
    SELECT 
        model_used,
        COUNT(*) as task_count,
        SUM(total_tokens) as tokens_consumed,
        AVG(total_tokens) as avg_tokens_per_task
    FROM agent_tasks
    WHERE created_at >= @StartDate
    AND (@UserId IS NULL OR user_id = @UserId)
    GROUP BY model_used
    ORDER BY task_count DESC;
    
    -- Tool usage statistics
    SELECT 
        te.tool_name,
        COUNT(*) as usage_count,
        AVG(te.execution_time_ms) as avg_execution_time_ms
    FROM tool_executions te
    JOIN agent_tasks at ON te.task_id = at.id
    WHERE at.created_at >= @StartDate
    AND (@UserId IS NULL OR at.user_id = @UserId)
    GROUP BY te.tool_name
    ORDER BY usage_count DESC;
END;
