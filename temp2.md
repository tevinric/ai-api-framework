You are required to create the following conversational AI API endpoint.

You are provided with the following supporting API services that you must use: 
1. LLMServices.py - you must use GPT-4o as the model
2. You must create and use tools to handle functionality withing the API

Desired behaviour of the chatbot api:
1. The user may greet the chatbt and the chatbot must respond with a friendly message stating that it will help the client get a quotation for car insurance.
2. The chatbot must always be friendly
3. It must ask for more information or for the client to elaborate further if there is something that the chatbot is not sure of
4. It must not answer questions or respond to messages that are not related to getting a car insurance quote - It must respond in a friendly manner and route the client back to the conversation, picking up on where the conversation diverted.


The chatbot must ask the user the following question in the following order:

Please ensure that validation is performed against to esnure that the user selects valid options only. If the user enters something that is not part of the validation list then teh chatbot must inform the user and offer possible options that are close to what the user has typed. 

underqriting questions:
1. Select the make of the car:
    - Provide a list of cars that the user can select from.
    - Specify this list in a separete file taht can be easiy edited
    - This list will later on be replaced with an API (you dont have to coed this, im telling you for context)
    
