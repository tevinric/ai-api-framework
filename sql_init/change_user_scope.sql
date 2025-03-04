-- This script is used to change scope of a user in the user tables:

UPDATE users
SET scope = 0, -- pass in the desired scope for the user
modified_at = DATEADD(HOUR,2, GETUTCDATE())
WHERE ID = '' -- pass in the user ID here
AND scope = 1; -- pass in the users's existing scope