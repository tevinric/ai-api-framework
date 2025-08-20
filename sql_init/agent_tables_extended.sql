-- Additional tables for agent system with OpenAI SDK integration

-- Table to store agent configurations from OpenAI SDK
CREATE TABLE IF NOT EXISTS agent_configurations (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    owner_id UNIQUEIDENTIFIER NOT NULL,
    agent_id NVARCHAR(255) NOT NULL, -- OpenAI Assistant ID
    name NVARCHAR(255) NOT NULL,
    instructions NVARCHAR(MAX) NOT NULL,
    model NVARCHAR(100) NOT NULL DEFAULT 'gpt-4o',
    tools NVARCHAR(MAX), -- JSON array of tools configuration
    metadata NVARCHAR(MAX), -- JSON metadata
    is_shared BIT DEFAULT 0,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    modified_at DATETIME2 DEFAULT GETUTCDATE(),
    
    -- Foreign key to users table
    CONSTRAINT FK_agent_configurations_owner FOREIGN KEY (owner_id) REFERENCES users(id),
    
    -- Index for quick lookup
    INDEX IDX_agent_configurations_owner (owner_id, created_at DESC),
    INDEX IDX_agent_configurations_agent_id (agent_id)
);

-- Table to store conversation threads
CREATE TABLE IF NOT EXISTS agent_threads (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    agent_id NVARCHAR(255) NOT NULL,
    thread_id NVARCHAR(255) NOT NULL, -- OpenAI Thread ID
    metadata NVARCHAR(MAX), -- JSON metadata
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    last_activity DATETIME2 DEFAULT GETUTCDATE(),
    
    -- Foreign key to users table
    CONSTRAINT FK_agent_threads_user FOREIGN KEY (user_id) REFERENCES users(id),
    
    -- Index for quick lookup
    INDEX IDX_agent_threads_user (user_id, last_activity DESC),
    INDEX IDX_agent_threads_thread_id (thread_id)
);

-- Table to store run information
CREATE TABLE IF NOT EXISTS agent_runs (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    agent_id NVARCHAR(255) NOT NULL,
    thread_id NVARCHAR(255) NOT NULL,
    run_id NVARCHAR(255) NOT NULL, -- OpenAI Run ID
    status NVARCHAR(50) NOT NULL DEFAULT 'queued',
    metadata NVARCHAR(MAX), -- JSON metadata
    result_data NVARCHAR(MAX), -- JSON result data
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),
    
    -- Foreign key to users table
    CONSTRAINT FK_agent_runs_user FOREIGN KEY (user_id) REFERENCES users(id),
    
    -- Index for quick lookup
    INDEX IDX_agent_runs_user (user_id, created_at DESC),
    INDEX IDX_agent_runs_run_id (run_id)
);

-- Table for custom agents created by users
CREATE TABLE IF NOT EXISTS custom_agents (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    agent_id NVARCHAR(255) NOT NULL, -- OpenAI Assistant ID
    name NVARCHAR(255) NOT NULL,
    description NVARCHAR(MAX),
    instructions NVARCHAR(MAX) NOT NULL,
    tools NVARCHAR(MAX), -- JSON array of tool names
    model NVARCHAR(100) NOT NULL DEFAULT 'gpt-4o',
    temperature FLOAT DEFAULT 0.7,
    base_template NVARCHAR(100), -- Template used as base
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    modified_at DATETIME2 DEFAULT GETUTCDATE(),
    
    -- Foreign key to users table
    CONSTRAINT FK_custom_agents_user FOREIGN KEY (user_id) REFERENCES users(id),
    
    -- Index for quick lookup
    INDEX IDX_custom_agents_user (user_id, created_at DESC)
);

-- Table for agent workflows (multi-agent)
CREATE TABLE IF NOT EXISTS agent_workflows (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    name NVARCHAR(255) NOT NULL,
    description NVARCHAR(MAX),
    flow_type NVARCHAR(50) NOT NULL DEFAULT 'sequential', -- sequential, parallel, conditional
    agents_config NVARCHAR(MAX) NOT NULL, -- JSON configuration of agents
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    modified_at DATETIME2 DEFAULT GETUTCDATE(),
    
    -- Foreign key to users table
    CONSTRAINT FK_agent_workflows_user FOREIGN KEY (user_id) REFERENCES users(id),
    
    -- Index for quick lookup
    INDEX IDX_agent_workflows_user (user_id, created_at DESC)
);

-- Table for custom tools created by users
CREATE TABLE IF NOT EXISTS custom_tools (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    tool_name NVARCHAR(100) NOT NULL UNIQUE,
    description NVARCHAR(500),
    category NVARCHAR(100) DEFAULT 'general',
    parameters_schema NVARCHAR(MAX), -- JSON schema for parameters
    tool_type NVARCHAR(50) DEFAULT 'function', -- function, mcp_server, api_endpoint
    config NVARCHAR(MAX), -- JSON configuration (e.g., MCP server details)
    is_enabled BIT DEFAULT 1,
    requires_auth BIT DEFAULT 0,
    max_execution_time_ms INT DEFAULT 30000,
    created_by UNIQUEIDENTIFIER,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    modified_at DATETIME2 DEFAULT GETUTCDATE(),
    
    -- Foreign key to users table
    CONSTRAINT FK_custom_tools_created_by FOREIGN KEY (created_by) REFERENCES users(id),
    
    -- Index for quick lookup
    INDEX IDX_custom_tools_category (category, is_enabled)
);

-- Table for MCP server registrations
CREATE TABLE IF NOT EXISTS mcp_servers (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    name NVARCHAR(255) NOT NULL UNIQUE,
    url NVARCHAR(500) NOT NULL,
    api_key NVARCHAR(500), -- Encrypted API key
    capabilities NVARCHAR(MAX), -- JSON array of capabilities
    is_enabled BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    modified_at DATETIME2 DEFAULT GETUTCDATE(),
    
    -- Index for quick lookup
    INDEX IDX_mcp_servers_enabled (is_enabled, name)
);

-- Insert default endpoint entries for agent features
INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/create', 'Create Agent', 1.0, 'Create a new AI agent', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/create');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/execute', 'Execute Agent', 5.0, 'Execute an agent task', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/execute');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/status', 'Agent Status', 0.0, 'Check agent job status', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/status');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/list', 'List Agents', 0.0, 'List available agents', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/list');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/custom/create', 'Create Custom Agent', 2.0, 'Create a custom agent', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/custom/create');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/templates', 'Agent Templates', 0.0, 'Get agent templates', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/templates');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/workflow/create', 'Create Workflow', 3.0, 'Create multi-agent workflow', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/workflow/create');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/tools', 'List Tools', 0.0, 'List available tools', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/tools');

-- Tool Management Endpoints
INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/tools/create', 'Create Custom Tool', 2.0, 'Create a custom tool', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/tools/create');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/tools/list', 'List Custom Tools', 0.0, 'List custom tools', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/tools/list');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/tools/get', 'Get Tool Details', 0.0, 'Get tool details', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/tools/get');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/tools/update', 'Update Custom Tool', 1.0, 'Update a custom tool', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/tools/update');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/tools/delete', 'Delete Custom Tool', 0.0, 'Delete a custom tool', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/tools/delete');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/tools/test', 'Test Custom Tool', 0.5, 'Test a custom tool', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/tools/test');

INSERT INTO endpoints (id, endpoint_path, endpoint_name, cost, description, active) 
SELECT NEWID(), '/agents/tools/share', 'Share Custom Tool', 0.0, 'Share tool with users', 1
WHERE NOT EXISTS (SELECT 1 FROM endpoints WHERE endpoint_path = '/agents/tools/share');

-- Create view for agent usage analytics
CREATE OR ALTER VIEW agent_usage_analytics AS
SELECT 
    u.user_name,
    u.user_email,
    COUNT(DISTINCT ac.agent_id) as total_agents_created,
    COUNT(DISTINCT at.thread_id) as total_threads,
    COUNT(ar.run_id) as total_runs,
    AVG(CASE 
        WHEN ar.status = 'completed' THEN DATEDIFF(second, ar.created_at, ar.updated_at)
        ELSE NULL 
    END) as avg_completion_time_seconds,
    SUM(CASE WHEN ar.status = 'completed' THEN 1 ELSE 0 END) as successful_runs,
    SUM(CASE WHEN ar.status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
    MAX(ar.created_at) as last_activity
FROM users u
LEFT JOIN agent_configurations ac ON u.id = ac.owner_id
LEFT JOIN agent_threads at ON u.id = at.user_id
LEFT JOIN agent_runs ar ON u.id = ar.user_id
GROUP BY u.id, u.user_name, u.user_email;

-- Create stored procedure for agent analytics
CREATE OR ALTER PROCEDURE GetAgentAnalytics
    @UserId UNIQUEIDENTIFIER = NULL,
    @StartDate DATETIME2 = NULL,
    @EndDate DATETIME2 = NULL
AS
BEGIN
    -- Set default date range if not provided
    IF @StartDate IS NULL
        SET @StartDate = DATEADD(day, -30, GETUTCDATE());
    IF @EndDate IS NULL
        SET @EndDate = GETUTCDATE();
    
    -- Agent usage summary
    SELECT 
        COUNT(DISTINCT ac.agent_id) as total_agents,
        COUNT(DISTINCT at.thread_id) as total_threads,
        COUNT(ar.run_id) as total_runs,
        AVG(CASE 
            WHEN ar.status = 'completed' THEN DATEDIFF(second, ar.created_at, ar.updated_at)
            ELSE NULL 
        END) as avg_run_time_seconds,
        SUM(CASE WHEN ar.status = 'completed' THEN 1 ELSE 0 END) * 100.0 / 
            NULLIF(COUNT(ar.run_id), 0) as success_rate
    FROM agent_configurations ac
    LEFT JOIN agent_threads at ON ac.agent_id = at.agent_id
    LEFT JOIN agent_runs ar ON at.thread_id = ar.thread_id
    WHERE (@UserId IS NULL OR ac.owner_id = @UserId)
    AND ar.created_at BETWEEN @StartDate AND @EndDate;
    
    -- Most used agents
    SELECT TOP 10
        ac.name as agent_name,
        ac.model,
        COUNT(ar.run_id) as usage_count,
        AVG(CASE 
            WHEN ar.status = 'completed' THEN DATEDIFF(second, ar.created_at, ar.updated_at)
            ELSE NULL 
        END) as avg_execution_time
    FROM agent_configurations ac
    JOIN agent_runs ar ON ac.agent_id = ar.agent_id
    WHERE (@UserId IS NULL OR ac.owner_id = @UserId)
    AND ar.created_at BETWEEN @StartDate AND @EndDate
    GROUP BY ac.name, ac.model
    ORDER BY usage_count DESC;
END;