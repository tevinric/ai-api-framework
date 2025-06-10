-- Create scope_balance_config table
USE AIAPISDEV;

CREATE TABLE scope_balance_config (
    scope INT PRIMARY KEY CHECK (scope IN (0,1,2,3,4,5)),
    monthly_balance DECIMAL(10, 2) NOT NULL,
    description NVARCHAR(100),
    created_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    modified_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE())
);

-- Insert default scope balances
INSERT INTO scope_balance_config (scope, monthly_balance, description) VALUES
(0, 999999.0, 'Admin - Unlimited'),
(1, 999.0, 'Developer'),
(2, 5000.0, 'Production Tier 3 - Basic'),
(3, 10000.0, 'Production Tier 2 - Professional'),
(4, 25000.0, 'Production Tier 1 - Enterprise'),
(5, 100.0, 'Test/Trial');

