You are given my ai api code base. 

As an expert python flask api engineer, you are tasked with evaluating the implementation of this current middleware and perform the addition tasks that I ask. 

Your task: 

1. I want to create agentic apis - i.e apis that allow users to envoke agents using the OpenAI Agents SDK. 
2. All the llm models will be served through Azure OpenAI. 
3. You must design this to work within the current implementation of these apis
4. The agents should be designed to standalone, connect to tools and mcp servers
5. I want useful business agents that boost productivity for business users
6. Please allow for plug and play capability of tools and mcp servers
7. YOU MUST USE openai agents SDK to create and connects agents
8. I want the users to be able to also create custom agents 
9. Users should be able to link agents together if they wish 
10. Deisgn this solution for an agentic ecosystem
11. Bear in mind the KONG gateway timeout limitation of 1 minute - SO the APIS should work asynchronously.
12. You can use the other apis as folders as guides to see how I want my agent apis to work - DO NOT depend on any of them though - Make all the neccessary services functions you need - see apis/utils for how servicefunctions are set up
13. All apis and agent usage must use the track_usage middleware to log the token usage for agent interactions - This must be logged as per how other apis log and track usage. 

Please design a working system!

