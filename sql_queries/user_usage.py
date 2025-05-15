-- Create user_usage table for tracking API usage metrics
USE AIAPISDEV;

CREATE TABLE user_usage (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    api_log_id UNIQUEIDENTIFIER NULL,
    user_id UNIQUEIDENTIFIER NOT NULL,
    endpoint_id UNIQUEIDENTIFIER NOT NULL,
    timestamp DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    images_generated INT DEFAULT 0,
    audio_seconds_processed DECIMAL(10, 2) DEFAULT 0,
    pages_processed INT DEFAULT 0,
    documents_processed INT DEFAULT 0,
    model_used NVARCHAR(100),
    prompt_tokens INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    cached_tokens INT DEFAULT 0,
    files_uploaded INT DEFAULT 0,
    CONSTRAINT FK_user_usage_users FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT FK_user_usage_endpoints FOREIGN KEY (endpoint_id) REFERENCES endpoints(id),
    CONSTRAINT FK_user_usage_api_logs FOREIGN KEY (api_log_id) REFERENCES api_logs(id)
);

-- Create indexes for better query performance
CREATE INDEX IX_user_usage_user_id ON user_usage(user_id);
CREATE INDEX IX_user_usage_endpoint_id ON user_usage(endpoint_id);
CREATE INDEX IX_user_usage_timestamp ON user_usage(timestamp);
CREATE INDEX IX_user_usage_api_log_id ON user_usage(api_log_id);
