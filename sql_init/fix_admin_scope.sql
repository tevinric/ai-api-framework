-- Fix Admin User Scope
-- This script updates the admin user's scope to 0 (Admin level)

USE AIAPISDEV;

-- First, check current user scopes
SELECT user_name, user_email, scope 
FROM users 
WHERE user_email = 'gaiatester@test.com' -- Replace with your admin email
   OR scope = 0;

-- Update the admin user to have scope 0 (Admin)
UPDATE users
SET scope = 0,
    modified_at = DATEADD(HOUR, 2, GETUTCDATE())
WHERE user_email = 'gaiatester@test.com' -- Replace with your admin email from .env
  AND scope != 0; -- Only update if not already admin

-- Verify the update
SELECT user_name, user_email, scope, modified_at
FROM users 
WHERE user_email = 'gaiatester@test.com' -- Replace with your admin email
   OR scope = 0;