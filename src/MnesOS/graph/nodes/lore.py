from ..state import GameState
from ...context import VectorLoreStore

def context_retrieval_node(state: GameState) -> dict:
    """
    1. Lore Node: Executes FIRST. Grabs the Vector RAG context
    based on the user's input, current location, active NPCs, and items.
    """
    lore_content = state.get("lore_content", "")
    store = VectorLoreStore(lore_content) if lore_content else VectorLoreStore.from_file(state["lore_path"])
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
