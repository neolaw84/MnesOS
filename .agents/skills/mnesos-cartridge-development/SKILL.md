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

## Best Practices 

*   **Logic goes in YARE**: Do not ask the LLM to calculate health drops or item prices. Make events in `yare.yaml` (e.g. `buy_item`, `take_damage`, `cast_spell`).
*   **Keep Directives Lean**: Directives should focus on psychological behavior ("NPCs run away when health is critically low", or "The Director should spawn encounters in the wilderness").
*   **Use the Macros**: Common mathematical calculations (e.g. combat rolls) should be offloaded to YARE macros for clean event structures.
*   **Dice Notation**: When using `roll(...)` in YARE expressions, do **not** add quotes around the dice notation. Write `@ roll(1d20)` instead of `@ roll('1d20')`. The engine pre-processes this automatically.
*   **Design for `MAX_ITERATIONS = 3`**: The engine allows at most 3 tool calls (YARE events or NPC queries) per turn. Each event should be self-contained — use `call` steps to chain sub-events internally rather than relying on the LLM to issue multiple tool calls. Keep complex flows inside a single event's `steps`.

## Available Resources

*   **Templates**: Found in `assets/`. You can copy these to begin a new generic RPG game.
    *   [assets/bot_lore.md](assets/bot_lore.md)
    *   [assets/prompt_directives.yaml](assets/prompt_directives.yaml)
    *   [assets/yare.yaml](assets/yare.yaml)
*   **Documentation**:
    *   [references/cartridge-guide.md](references/cartridge-guide.md)
    *   [references/yare-specification.md](references/yare-specification.md)
    *   [references/architecture_analysis.md](references/architecture_analysis.md)
    *   [references/combat_mechanics.md](references/combat_mechanics.md)
*   **Scripts**:
    *   [scripts/setup_cartridge.py](scripts/setup_cartridge.py): Use this python script to automatically scaffold a new cartridge using the assets in this skill. Usage: `python scripts/setup_cartridge.py <cartridge-name>`
