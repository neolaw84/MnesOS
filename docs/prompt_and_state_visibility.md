I have analyzed the codebase and your requirements. Here are my suggestions and the changes I've made to the code.

### 1. Balancing Prompt Injection and Developer Freedom

To allow cartridge developers to inject prompts without opening up the system to prompt-injection attacks, I've implemented a system where developers can add `directives` to the system prompts. These directives are added to the end of the base system prompts, ensuring that the core instructions to the LLM remain intact.

I've modified the `director_node`, `npc_brain_node`, and `narrator_node` in `src/graph.py` to look for a `prompt_directives` section in the `yare.yaml` file.

Here's how a cartridge developer can use this feature in their `yare.yaml`:

```yaml
prompt_directives:
  director: "The player is in a dream-like state. Actions should be interpreted with a surreal and unpredictable lens."
  narrator: "The narration should be poetic and metaphorical, reflecting the player's dream state."
  npc_brain: "The NPCs in this dream are manifestations of the player's fears. They should act accordingly."
```

This approach provides a safe way for developers to customize the behavior of the LLMs without compromising the integrity of the system prompts.

### 2. Differentiating Public and Private State Variables

To allow cartridge developers to specify which variables are visible to the player, I've introduced a `visibility` property in the `state_schema` of the `yare.yaml` file. By default, all variables are considered `private`.

Here's an example of how a developer can define public and private variables:

```yaml
state_schema:
  player:
    hp: { type: int, default: 100, min: 0, visibility: "public" }
    mana: { type: int, default: 50, min: 0, visibility: "public" }
    is_poisoned_with_asymptomatic_poison: { type: bool, default: false, visibility: "private" } # This will be hidden
```

I've made the following changes to enforce this:

1.  **`src/interpreter.py`**: The `_eval_node` method now checks the `visibility` of a state variable before allowing access. If a script tries to access a private variable, it will raise a `ValueError`. This prevents cartridge logic from accidentally (or maliciously) using private data in calculations that might be exposed to the player.

2.  **`src/graph.py`**: I've added a `get_public_state` function that filters the `bot_memory` to only include variables marked as `public`. The `narrator_node` now uses this function to create a "public" version of the state that is used to generate the narrative, ensuring that private variables are not accidentally leaked to the player.

These changes provide a robust and secure way to manage state visibility, giving cartridge developers the flexibility they need while maintaining the integrity of the game's reality.
