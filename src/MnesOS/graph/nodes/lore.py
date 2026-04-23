from langchain_core.runnables import RunnableConfig
from ..state import GameState
from ...context import VectorLoreStore


def _build_lore_store(config: RunnableConfig) -> VectorLoreStore:
    configurable = (config or {}).get("configurable", {})
    lore_content = configurable.get("lore_content")
    if lore_content is not None:
        return VectorLoreStore(lore_content)
    return VectorLoreStore.from_file(configurable.get("lore_path", ""))


def context_retrieval_node(state: GameState, config: RunnableConfig) -> dict:
    """
    1. Lore Node: Executes FIRST. Grabs the Vector RAG context
    based on the user's input, current location, active NPCs, and items.

    Lore source (``lore_content`` / ``lore_path``) is read from
    ``config["configurable"]`` rather than from graph state.
    """
    store = _build_lore_store(config)
    content = state['client_messages'][-1].get('content', '')

    query_parts = [content]
    memory = state.get("bot_memory", {})

    if "current_location" in memory:
        query_parts.append(str(memory["current_location"]))

    npc_data = memory.get("npc", {})
    if isinstance(npc_data, dict):
        if "name" in npc_data:
            query_parts.append(str(npc_data["name"]))

        # Check for Name Mode template
        if "template" in npc_data:
            query_parts.append(str(npc_data["template"]))

        # Check for Tag Mode array (can be multiple tags!)
        if "tags" in npc_data and isinstance(npc_data["tags"], list):
            query_parts.extend([str(tag) for tag in npc_data["tags"]])

    inventory = memory.get("inventory", [])
    if isinstance(inventory, list):
        query_parts.extend([str(item) for item in inventory])

    query_text = " ".join(query_parts)
    lore = store.query(query_text, top_k=3)
    return {"retrieved_lore": lore}
