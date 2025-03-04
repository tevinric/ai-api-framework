-- API LOGS TABLE TO LOG EACH API TRANSACTION

USE AIAPISDEV;

CREATE TABLE api_logs (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    endpoint_id UNIQUEIDENTIFIER NOT NULL,
    user_id UNIQUEIDENTIFIER,
    timestamp DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    request_method NVARCHAR(10) NOT NULL,
    request_headers NVARCHAR(MAX),
    request_body NVARCHAR(MAX),
    response_body NVARCHAR(MAX),
    response_status INT,
    response_time_ms INT,
    user_agent NVARCHAR(500),
    ip_address NVARCHAR(50),
    token_id UNIQUEIDENTIFIER,
    error_message NVARCHAR(MAX),
    CONSTRAINT FK_api_logs_endpoints FOREIGN KEY (endpoint_id) REFERENCES endpoints(id),
    CONSTRAINT FK_api_logs_users FOREIGN KEY (user_id) REFERENCES users(id)
);
