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
    - Include a few to get me started
  
2. Select the year of the {selected vehicle make}
    - user must specify a year of the vehicle here
    - include validation to check that a valid year is provided

3. What is the models of the {selected year} {selected vehicle make}
   - Select from a list of vehicle models
   - Use validation and provide a list to get me started
   - the models must be based on the selected vehicle make
  
4. What is the type of {selected vehicle year} {selected vehicle make} {selected vehicle model}
    - Select from a list of vehicle model types
    - Use validation and provide a list to get me started
    - the types must be based on the selected vehicle model
  
5. What colour is your vehicle?
   - Provide a list of valid colors to get me stared
   - Use validation against this list
  
6. What's the car used for?
    - The following options must be provided to the user:
      1.  Private and/or travelling to work (The car is used for social, domestic or pleasure purposes including travel to and from work. The car is not used for business and professional purposes)
      2.   Private and occasional business
(The car is used for social, domestic or pleasure purposes including travel to and from work. The car is used for up to 10 business/professional trips a month. The car may not be used to do deliveries or to carry fare paying passengers. Only the regular driver and spouse will be covered for business use.)
3.  Private and full business
The car is used to visit clients or to attend work related commitments away from your regular workplace. The car may not be used to do deliveries or to carry fare paying passengers. Only the regular driver and spouse will be covered for business use. The car may also be used for social, domestic or pleasure purposes including travel to and from work.
 - You must only provide the user with te options.
 - if the user asks for the difference or to explain what each one is then the chatbot will answer with the provided descriptions so that the user can make an informed decision.

7. Is the car registered in South Africa?
    - yes or no 

8. Is the car financed?
    - Yes or no

9. Select your preffered cover type:
    1. Comprehensive: 
        Covers the loss of, or damage to your car due to accident – regardless of who’s at fault – theft, weather, malicious damage, fire and accidental damage your car causes to other people’s property.
   2. Trailsure:
      Comprehensive cover with some added benefits for your 4x4 or SUV cars.
    3. Third-party fire and theft 
    Cover for damages to your car as a direct result of fire, explosions, lightning or theft, including damages you may cause to someone else’s car, for which you are legally liable.
    4. Budget Lite 1 
    You are covered for damages caused by someone else or if stolen.
    5. Budget Lite 2 
    You are covered for hail damages, damages your car caused to other cars/property for which you are legally liable and if your car was written off.
    6. Budget Lite 3
   You are covered for limited accident damage, hail damages, damages your car caused to other cars/property for which you are legally liable and if your car was written off.

    - You must only provide the user with the options in the question, if the user asks for more information then you can provide what each one means

10. Select your preferred insured value:
    1. Market Value
        In the event of a claim, your car will be covered for the average amount your car would sell for today.
    2. Retail Value 
        We will pay you the price you would expect to pay for your car if you bought it from a motor dealer. This attracts a higher premium, but also means you will get a higher payout when you claim.
    3. Trade Value
        We will pay you the estimated amount the dealership would offer you for your car after inspecting it. This will provide you with the lowest possible premium, but also the lowest payout when you claim.
    4. BetterCar
         We will pay out for, or replace, your car with the same model that is one year newer than your insured car, in the event of a write off (this excludes theft related claims). If there’s no newer model of the car, we will pay out 15% more than your car’s retail value.
    
    - You must only provide the user with the options in the question, if the user asks for more information then you can provide what each one means
   
11. In which are or suburb is the car normally parked at night?
    - The user will provide a suburb that you will capture
    - This will later be passed to an API for validation and matching
    - Just accept the suburb for now
   
12. Where is the car normally parked at night?
    1. Basement
    2. Carport
    3. Driveway/yard
    4. Garage
    5. Open parking lot
    6. Pavement/street
   
13. What type of security do you have where the car is parked at night?
    - options:
          1. Security guarded access control
          2. Electronic access control
          3. Locked gate
          4. None
    - THis is a multiselect so you must tell the user that then can select one or more.
    - Make provisions if the user answers with one or more
   
14. In which are or suburb is the car parked during the day?
    - The user will provide a suburb that you will capture
    - This will later be passed to an API for validation and matching
    - Just accept the suburb for now
   
15. Where is the car normally parked during the day?
    1. Basement
    2. Carport
    3. Driveway/yard
    4. Garage
    5. Open parking lot
    6. Pavement/street 

16.  What type of security do you have where the car is parked during the day?
    - options:
          1. Security guarded access control
          2. Electronic access control
          3. Locked gate
          4. None
    - THis is a multiselect so you must tell the user that then can select one or more.
    - Make provisions if the user answers with one or more

17. Do you have a vehicle tracking and recovery device installed in the car?
    - yes or no

Now its time to get teh customer details:

18. What is your South African ID number?
    - This will be a 13-digit numeric number
    - Do validation on this
    - include the following disclaimer:
          By pressing proceed, you consent to insurance company processing your personal information for insurance and risk management purposes.

19. What is your gender?
    - Male or Female
   
20. What is your name and surname?
    - Validate and ensure both a name and surname is passed through
    - Check for use of testers or profane words

21. nice to meet you {User First name}. WHat is your cellphone number?

22. What is your email address
    - perform validation
   
23. What is your marital status?
    - Options:
          1. Cohabitating/partnered
          2. Separated
            3. Widowed
          4. Divorced
          5. Single
          6. Married

24. What's your employment status?
    -= Employed
    - Emplyed and owrking from home (3 or more days a week)
    - Unemployed
    - Student
    - Civil Servant

25. Will you be the regular driver of the vehicle?


API inputs:
- The initial message will return a conversation_id.
- The developer will take this conversation_id and pass it back to the api endpoint so that conversation can continue
- The conversation will continue until the user terminates the conversation or all questions are run through

API outputs:
1. You must retrun the total token consumption
2. If the question has options, you must return a list of options for for each question the api is asking so that a front end developer can present this list to the user for selection
3. You must keep a dictionary of the data as the conversation flows. As the conversation prgresses you must populate this list with the extrated information from the conversation. This will be later used for mapping


api function file requirements:
1.You must modularise this api function as much as possible where static references are in seperate files and read into the main api file. THis will make it easier to update the statif lists
2. Please do not make any ofthe files exceedingly long whihch will cause context window limitations later on. I need you be clever with the implementation

