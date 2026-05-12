---
name: mnesos-cartridge-development
description: Develop, template, and design new RPG cartridges for the MnesOS engine. Includes boilerplate templates, guidelines, and validation tools.
license: MIT
metadata:
  version: "1.0"
  author: mnesos-team
---

# MnesOS Cartridge Development Skill

This skill is designed to help you build standard Role-Playing Game cartridges for the MnesOS engine.

## Overview of Cartridge Structure

A MnesOS cartridge divides game responsibilities across explicitly named files:

1.  **`bot_lore.md`**: Contains the world setting, factions, locations, character backgrounds, and items.
2.  **`prompt_directives.yaml`**: Contains instructions for the Director, NPC, and Narrator roles, steering their behavior and tone.
3.  **`yare.yaml`**: The deterministic logic layer handling character stats (HP, Mana, Gold, Status Effects) and state mutations through defined events (e.g., combat strikes, trading, exploring).
4.  **`first-message.md`** (Optional): Contains the initial starting prompt or scenario preamble to kickstart the story narrative.

## Best Practices 

*   **Logic goes in YARE**: Do not ask the LLM to calculate health drops or item prices. Make events in `yare.yaml` (e.g. `buy_item`, `take_damage`, `cast_spell`).
*   **Keep Directives Lean**: Directives should focus on psychological behavior ("NPCs run away when health is critically low", or "The Director should spawn encounters in the wilderness"). **Important:** When referring to the game state inside `prompt_directives.yaml`, you MUST use the term `bot_memory` (e.g., `If bot_memory['player']['hp'] < 10`), as this is the variable name injected into the LLM context. Do not use the `state.` prefix here; that is only for `yare.yaml`.
*   **Use the Macros**: Common mathematical calculations (e.g. combat rolls) should be offloaded to YARE macros for clean event structures.
*   **Dice Notation**: When using `roll(...)` in YARE expressions, do **not** add quotes around the dice notation. Write `@ roll(1d20)` instead of `@ roll('1d20')`. The engine pre-processes this automatically.
*   **Advanced YARE Expressions**: The engine's `YAREEvaluator` has been modernized. You can now use:
    *   **Dict literals** for clean generation: `@ {'hp': 100, 'name': 'Goblin'}`
    *   **Bracket indexing** for array/dict access: `@ state.active_npcs[inputs.npc_index].hp`
    *   **String concatenation** with numbers: `@ 'npc_' + 1` evaluates to `'npc_1'`
    *   **Dynamic Mutation Paths**: Use string concatenation for dynamic `mutate` variables (e.g., `var: "@ 'state.active_npcs.' + inputs.npc_id + '.hp'"`)
*   **Design for `MAX_ITERATIONS = 3`**: The engine allows at most 3 tool calls (YARE events or NPC queries) per turn. Each event should be self-contained — use `call` steps to chain sub-events internally rather than relying on the LLM to issue multiple tool calls. Keep complex flows inside a single event's `steps`.

## Available Resources

*   **Templates**: Found in `assets/`. You can copy these to begin a new generic RPG game.
    *   [assets/bot_lore.md](assets/bot_lore.md)
    *   [assets/prompt_directives.yaml](assets/prompt_directives.yaml)
    *   [assets/yare.yaml](assets/yare.yaml)
*   **Documentation**:
    Use your file reading tools to view the local index router:
    *   **Bundled AI Index Router**: Read `references/ai-index.md` relative to this `SKILL.md` file directory. Follow its path mappings by prepending `references/` to locate the target file (e.g., `references/guides/cartridge-developer-guide.md` or `references/yare-specification.md`).
*   **Scripts**:
    *   [scripts/setup_cartridge.py](scripts/setup_cartridge.py): Use this python script to automatically scaffold a new cartridge using the assets in this skill. Usage: `python scripts/setup_cartridge.py <cartridge-name>`
