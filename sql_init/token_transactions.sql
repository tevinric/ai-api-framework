-- Create token_transactions table
USE AIAPISDEV;

CREATE TABLE token_transactions (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    token_scope INT NOT NULL,
    expires_in INT NOT NULL,
    expires_on DATETIME2 NOT NULL,
    token_provider NVARCHAR(50) NOT NULL DEFAULT 'Microsoft Entra App',
    token_value NVARCHAR(MAX) NOT NULL,
    created_at DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    modified_at DATETIME2, -- Date and time when the token was last modified (regnerated counts)
    regenerated_at DATETIME2, -- Date and time when the token was regenerated (if applicable)
    regenerated_by UNIQUEIDENTIFIER,  -- User ID of the user who regenerated the token
    regenerated_from UNIQUEIDENTIFIER, -- ID of the original token that requested a refresh
    CONSTRAINT FK_token_transactions_users FOREIGN KEY (user_id) REFERENCES users(id)
);
