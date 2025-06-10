-- Create user_endpoint_access table for role-based access control
USE AIAPISDEV;

CREATE TABLE user_endpoint_access (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    endpoint_id UNIQUEIDENTIFIER NOT NULL,
    created_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    created_by UNIQUEIDENTIFIER NOT NULL,
    CONSTRAINT FK_user_endpoint_access_users FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT FK_user_endpoint_access_endpoints FOREIGN KEY (endpoint_id) REFERENCES endpoints(id),
    CONSTRAINT FK_user_endpoint_access_created_by FOREIGN KEY (created_by) REFERENCES users(id),
    CONSTRAINT UQ_user_endpoint UNIQUE (user_id, endpoint_id)
);

-- Create indexes for better query performance
CREATE INDEX IX_user_endpoint_access_user_id ON user_endpoint_access(user_id);
CREATE INDEX IX_user_endpoint_access_endpoint_id ON user_endpoint_access(endpoint_id);
