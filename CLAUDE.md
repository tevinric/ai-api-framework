you are given the following AI API base. 

These apis are deployed to the base url http:gaia.com

For all database table schemas and designs refer to the sql_init folder

Your task is as follows:

1. Create a react front end to manage the admin functions of my application. 
2. Application process flow:

    - The app will load the email_address from the .env file
    - The email address will be used in the apis/admin/admin_get_user_details endpoint
    - This will lookup the user details in the DB (users table) based on the email address
    - If the user scope of the user for the passed email address is 0 then return get the user details and display the username, department and user_id on the top of the sidebar (user details sections)
    - if the scope is > 0 then return and error message that the user is not allowed to access this portal. 
    - from the user details, you must get the api_key
    - Use the api_key to generate a token using the apis/token_services/get_token endpoint 
    - the token will be saved to the session state for the user to authenticate api calls


For Now just create this react front end in the frontend folder. Please read in the backend API base url from the .env file (only once and dynamically referenced)

Please ensure that there is good print statements to the terminal for debugging issues


