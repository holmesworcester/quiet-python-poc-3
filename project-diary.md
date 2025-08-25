todo: 
- incoming_handler.json has bad smell
- the way we're using sqlite is weird. i think handle should be using transactions e.g.

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
- need to find a good place to remind it about basic things like venv and runner
- it would be good if the demo came with the framework. we could have a cli demo and a gui demo and think about some tricks to get it to autogenerate. the gui demo would be identities and slash commands maybe. or we could make columns customizable for api queries and command entry context, so you get something like a message experience. 
- like lots of boxes and tiles. or you could get a bunch of checkboxes about what queries from the api you want to show and what values you want to put in them based on stuff you have! 
- i have to remind the llm about projecting after a command quite a bit.
- it seems that when we get to blocking/unblocking, there could be a protocol-generic way of doing it: every event has an event-id (hash of signed plaintext event) and there's a blocked-by table that lists the event-id that's blocked and the event-id that's blocking, and whenever we newly project an event we re-handle all the events in blocked. that way there's a first class "mark blocked" function, a first class "get id" function, and everything gets unblocking for free. we have to think about cycles but i don't think there are any because once an event gets projected it's in, and that won't happen again. and we make all this atomic. 
- keeping protocol-specific stuff like identity out of test runner is a real battle with the llm. one instruction could be, we are only working on framework and not protocol, or vice versa.  
- yaml seems more readable than json and it has variables which are good for tests. and you can mess with the format more and add comments and linebreaks etc. probably that's best
- i don't know how to make a closed loop that lets the llm use the demo the way i would 
- 
