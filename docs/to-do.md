# Features To-Do

## Repo Features

* Have unit-tests for web-client:
    - modify existing github actions to run web-client's unit-tests as well
    - have the PR (to dev) blocked if 80% coverage is not met for web-client

* Have integration pipeline (as a github action) that:
    - builds the web-client
    - copy the built web-client into the backend api (as static directory)
    - build the backend 

* Have unit-tests run if and only if necessary (if no change in python, no python unit-test run; similarly for web-client)

* Brainstorm and have an integration tests for the whole system (python backend + web-client). Put it in the github action as well and block the PR to dev. 

## Gameplay Features

* Instead of simple RAG retrieval before the director node (how would the director try to get more information mid-directing?), I would like the RAG retrieval to be a proper tool the director node call. At the same time, I want langgraph's `recursion_limit` parameter to be set in the `invoke` call as well as proper `query` and `top_k` as well as other necessary parameters. 

* The player should have the freedom to choose which LLM endpoint to be used in each node (currently, we would need one for embedding, one for director, one for query_npc_intent and one for narrator). Likewise, the player should have final say on `recursion_limit` and `max_iterations` for each call. Meanwhile, the cartridge developer should have defaults defined if the player does not specify any of them. 

* The player should have some kind of SSO with open router (instead of copy/pasting the API key). Implement PKCE authentication with open router in the web app. 

* There should be a factory-like pattern (or a suitable pattern if there is any) for the LLM creations. This is the first step to enable non-openrouter endpoints (for example, Google's gemini). By the way, tell me if there is any provider that does PKCE authentication other than open router. 

## Cartridge Developer Features

* I want another web-ui (integrated in the current one) and the backend APIs, where the necessary ingredients of a cartridges are built as the (new) agentic cartridge builder agent that chats with the user (cartridge creator). Brainstorm architecture for the whole sub-system. 