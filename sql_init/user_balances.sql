-- Create user_balances table
CREATE TABLE user_balances (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    balance_month DATE NOT NULL,  -- First day of the month
    current_balance DECIMAL(10, 2) NOT NULL,
    last_updated DATETIME2 NOT NULL DEFAULT DATEADD(HOUR, 2, GETUTCDATE()),
    CONSTRAINT FK_user_balances_users FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT UQ_user_month UNIQUE (user_id, balance_month)
);

