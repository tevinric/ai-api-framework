-- Create balance_transactions table for audit trail
CREATE TABLE balance_transactions (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    endpoint_id UNIQUEIDENTIFIER NOT NULL,
    transaction_date DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    deducted_amount INT NOT NULL,
    balance_after INT NOT NULL,
    CONSTRAINT FK_balance_transactions_users FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT FK_balance_transactions_endpoints FOREIGN KEY (endpoint_id) REFERENCES endpoints(id)
);