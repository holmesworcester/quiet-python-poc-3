Notes:

- I settled on the overall project structure in a previous iteration
- Intentionally creating handlers and test runners as a bottleneck is helpful for LLM wrangling and for following its work
- Having multiple protocols in the same project is nice, to avoid context-shifting between different projects and to make it lower-cost to try new variations
- building a text demo was a good idea in *some* ways: we don't have to mess with ports and a server running, or a browser, and sometimes the llm was able to test a screen just by looking at it.
- nudging the llm to create textui "screenshots" was helpful, but in the end it was best to avoid modals entirely and use /commands
- a good mode for demos is either CLI or, if persistent state is required, "/" commands. 
- we could also add cheap persistence and just use a CLI instead of a GUI at all... perhaps this is an advantage to starting the real sql phase of the project sooner instead of being in-memory only.   
- basic mismatches between the commands and the api spec were costly. in implementing something in the UI i could have it look at the api code and the commands underneath.
- i'm also interested in using types to clamp the api spec to the command signatures
- having `api_results:` in tests as a separate thing will help. 
- it's cool that a lot of the custom testing can be centralized into core and not /protocol and shared across protocols, and that a dummy protocol can be used to test the tests. 
- it might be helpful to declare core off limits when doing a protocol implementation. llm sometimes wants to edit tick. (or change the working directory to protocol) 
- i'm seeing a lot of type issues. 
- dummy crypto makes things easier in some ways and harder in others: bugs can persist for longer. real crypto is kind of good for checking correctness.
- invite and join are a nexus of difficulty