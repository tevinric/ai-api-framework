-- Create users table
USE AIAPISDEV;

CREATE TABLE users (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_name NVARCHAR(100) NOT NULL,
    user_email NVARCHAR(255) NOT NULL UNIQUE,
    common_name NVARCHAR(100),
    company NVARCHAR(255),            -- Company name
    department NVARCHAR(255),         -- Department name
    api_key UNIQUEIDENTIFIER NOT NULL UNIQUE DEFAULT NEWID(),
    scope INT CHECK (scope IN (0,1,2,3,4,5)) DEFAULT 1,
    active BIT NOT NULL DEFAULT 1,
    created_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    modified_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    comment NVARCHAR(MAX)
);