from typing import List, Any
from langchain_core.messages import AIMessage, HumanMessage

def _client_messages_to_langchain_messages(client_messages: List[dict]) -> List[Any]:
    """Convert persisted client story messages into LangChain message objects."""
    converted: List[Any] = []
    for msg in client_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "assistant":
            converted.append(AIMessage(content=content))
        else:
            converted.append(HumanMessage(content=content))
    return converted
