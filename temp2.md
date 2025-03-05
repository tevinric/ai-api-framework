-- Update endpoints table to use DECIMAL type for cost
ALTER TABLE endpoints
ALTER COLUMN cost DECIMAL(10, 2) NOT NULL DEFAULT 1.0;

-- Update balance_transactions table to use DECIMAL type for deducted_amount and balance_after
ALTER TABLE balance_transactions
ALTER COLUMN deducted_amount DECIMAL(10, 2) NOT NULL;

ALTER TABLE balance_transactions
ALTER COLUMN balance_after DECIMAL(10, 2) NOT NULL;

-- Update scope_balance_config table to use DECIMAL type for monthly_balance
ALTER TABLE scope_balance_config
ALTER COLUMN monthly_balance DECIMAL(10, 2) NOT NULL;

-- Update user_balances table to use DECIMAL type for current_balance
ALTER TABLE user_balances
ALTER COLUMN current_balance DECIMAL(10, 2) NOT NULL;