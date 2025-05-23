-- Create users table
USE AIAPISDEV;

CREATE TABLE users (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_name NVARCHAR(100) NOT NULL,
    user_email NVARCHAR(255) NOT NULL UNIQUE,
    common_name NVARCHAR(100),
    company NVARCHAR(255),            -- Company name
    department NVARCHAR(255),         -- Department name
    phone_ext NVARCHAR(50),           -- Phone extension
    division NVARCHAR(255),           -- Division name
    sub_department NVARCHAR(255),       -- Sub-division name
    cost_center NVARCHAR(100),        -- Cost center
    manager_full_name NVARCHAR(255),  -- Manager's full name
    manager_email NVARCHAR(255),      -- Manager's email address
    api_key UNIQUEIDENTIFIER NOT NULL UNIQUE DEFAULT NEWID(),
    scope INT CHECK (scope IN (0,1,2,3,4,5)) DEFAULT 1,
    active BIT NOT NULL DEFAULT 1,
    created_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    modified_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    comment NVARCHAR(MAX),
    aic_balance DECIMAL(10, 2)
);


--

-- Add new fields to existing users table
USE AIAPISDEV;

ALTER TABLE users 
ADD phone_ext NVARCHAR(50),
    division NVARCHAR(255),
    sub_division NVARCHAR(255),
    cost_center NVARCHAR(100),
    manager_full_name NVARCHAR(255),
    manager_email NVARCHAR(255);
