You are given my codebase.

Please accomplish the following objectives on the frontend folder:

The front end is created in React. 

1. The front end will have a login in page. Under normal circumstances the front end will use Azure Active Directory Entra App Authentication. 
2. For prod when the user logins in -> Entra will get their email address -> Email addres will get passed to an apis/admin endpoit to check the the scope of the user in the  users table (see sql_init table for schema). If the scope is 0 then redirect the user to the add. if scope is NOT 0 then give then user an error that they are not authorised to access the application
3. For development -> bypass the login process and use a default email that is "gaiatester@test.com". Use an environment vairable to check the environment. if PROD then use login page and if DEV then bypass. Do not overcomplicate this use one variable only

Next you must create Admin APIS in the apis/admin folder for: 

1. GET user details -> takes an email and and looks up the users table (see sql_init folder for schema). only is scope =0 then return the user details including the api_key of the user. If scope not 0 then return a suitable response that forces the app to give the user an error message that they are not authorised to use the application.

2. When a valid admin user autheticates themselve the application will then use the user's api_key to generate a token which gets cached to session_state. Please include checking validity of the token -> if token is expired then generated a new one and replace in cached variables (use the apis/token_services endpoints for this) 

3. Please create any other useful admin apis that will support the admin portal and management of users. Please allow for CRUD operations where neccessary. 

Please check how my apis are structured and take this into account for the front end.

Please ensure that all admin portal interations are api driven and that all required apis are available. 

DO NOT change anything regarding functionality of other apis. 

Create a file in the frontend folder called changes_made.md which documents all the changes you make. 

Please note that the base url is https:gaia.com - please reference this once from the .env file only! 