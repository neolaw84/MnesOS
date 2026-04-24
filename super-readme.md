# MnesOS — Super README for an offline LLM assisting {{user}}

This file is intended to be a single, self-contained reference an LLM without web access can rely on when helping a novice user use MnesOS locally, author cartridges, debug issues, and run play-tests. It embeds installation steps, UI walkthroughs, cartridge/YARE guidance, example YARE snippets and prompt directives, troubleshooting checks, and suggested conversation templates.

Table of contents
- Purpose & usage for the assistant
- Quick setup (Linux/macOS & Windows)
- Starting the backend & web UI
- UI walkthrough (controls + workflow)
- Cartridge layout and authoring rules
- YARE primer with examples (attack, take_damage, use_potion)
- Prompt directives & `bot_lore.md` guidance
- Turn model, `MAX_ITERATIONS`, and best patterns
- Troubleshooting checklist and commands
- Testing, docs, and developer commands
- Dialogue templates, Q&A examples, and assistant policy

Purpose & usage for the assistant
- Goal: answer novice questions concisely, provide copyable commands, and avoid assuming web access.
- When a user asks a setup or runtime question, always ask for: OS, full command they ran, exact terminal output (copy/paste), and the repository path (`pwd`).
- When giving fixes, provide one change at a time and request the user re-run the command and paste results.

Quick setup — prerequisites
- Python: 3.12 or newer is required.
- Node.js: used for the web client. Recommend installing via `nvm` (or `nvm-windows`). Use latest LTS.

Quick setup — commands (Linux/macOS)

```bash
# from project root
python3.12 -m venv venv
source venv/bin/activate
pip install -e ".[dev,api]"
mnesos-ingest-cartridges
```

Windows (PowerShell)

```powershell
# from project root
python -m venv venv
.\venv\Scripts\activate
pip install -e ".[dev,api]"
mnesos-ingest-cartridges
```

Starting the backend & web UI (two terminals)
- Terminal 1 — Backend API server (Python/Uvicorn):

```bash
source venv/bin/activate   # or Windows activation
uvicorn MnesOS.api.app:app --reload
```

Expected useful backend log lines to check:
- "INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)"
- "Application startup complete."

- Terminal 2 — Web UI (Vite):

```bash
cd web-client
npm install    # first-run only
npm run dev
```

Open `http://localhost:5173` in a browser.

UI walkthrough — main controls & workflow
- Header buttons (left-to-right):
  - 🕹 Play — main chat/play pane where you talk with the narrator.
  - 📚 Library — browse cartridges, upload new versions, view metadata.
  - 🎭 Personas — create/manage player characters (persona cards).
  - 📂 Active Games — resume or delete saved game instances.
  - 🚀 Start New Game — select cartridge, version, persona and launch.
  - ⚙️ Settings — configure `OpenRouter API Key` (BYOK), `User ID`, and optional `Game Instance ID`.

Settings notes:
- `User ID`: required by the web UI for Personas and Library actions. Any string (e.g., `tester01`).
- `OpenRouter API Key`: stored only in browser localStorage and used directly by the client to call LLM APIs. It is not proxied through the MnesOS backend.

Library — upload modes
- ZIP upload: upload a single `.zip` containing `yare.yaml`, `bot_lore.md`, and optionally `prompt_directives.yaml`.
- Individual files upload: upload `yare.yaml`, `bot_lore.md`, and `prompt_directives.yaml` separately.

Persona fields (recommended)
- Name (required)
- Pronouns (subject, object, possessive) (required)
- Appearance, Background, Personality (optional) — used by Narrator to render consistent prose.

Play view components
- Chat pane — story history and narrator responses.
- Save Bar — `Retry` (re-run last narrator response), save label input, `Save`, and `Loads (N)` list.
- Input box — type actions like "I search the room" or "I attack with my sword".
- State Debugger (right-hand panel) — live JSON of `GameState` (HP, Gold, Items, Location, etc.). Useful when play-testing cartridges.

Cartridge layout and authoring rules
- Cartridge directory: `cartridges/<name>/` with three principal files:
  - `yare.yaml`: deterministic rules, event definitions, state schema.
  - `bot_lore.md`: narrative lore used for vector retrieval and context assembly.
  - `prompt_directives.yaml`: directives for `director`, `narrator`, and `npc` roles — tone and behavior only.
- Authoring rules:
  - Put all deterministic mechanics in `yare.yaml` (damage calculation, inventory mutations, XP growth, price math).
  - Do not rely on the LLM for arithmetic or authoritative state transitions.
  - Keep `prompt_directives.yaml` concentrated on play style, persona behavior, and narration constraints.

YARE primer — structure and examples
Overview
- YARE defines `state` schema and `events` that mutate `GameState`. The engine executes events atomically and deterministically.
- Common YARE constructs: `params`, `steps`, `set`, `call`, `condition`, and macros.
- Dice notation: use `roll(1d20)` without quotes, invoked in expressions like `@ roll(1d20)`.

Example: simple attack flow (YAML snippet)

```yaml
events:
  player_attack:
    params: [attacker, target]
    steps:
      - set: "attack_roll = @ roll(1d20) + attacker.attack_bonus"
      - condition: "attack_roll >= target.armor_class"
        then:
          - call: "apply_damage"
        else:
          - call: "miss_reaction"

  apply_damage:
    params: [attacker, target]
    steps:
      - set: "damage = @ roll(1d8) + attacker.damage_bonus"
      - set: "target.hp = target.hp - damage"
      - condition: "target.hp <= 0"
        then:
          - call: "handle_death"

  handle_death:
    params: [entity]
    steps:
      - set: "entity.alive = false"
```

Example: consumable potion that heals 10 HP

```yaml
events:
  use_potion_healing:
    params: [actor, item_id]
    steps:
      - set: "actor.hp = min(actor.max_hp, actor.hp + 10)"
      - call: "consume_item"

  consume_item:
    params: [actor, item_id]
    steps:
      - set: "actor.inventory = actor.inventory.filter(i => i.id != item_id)"
```

Notes on writing YARE
- Use `call` to compose behaviors into reusable events.
- Keep events self-contained to respect `MAX_ITERATIONS` (see below).
- Use macros for repeated calculations (e.g., `roll_damage(dice, bonus)`).

Prompt directives — examples and guidance
- `prompt_directives.yaml` should contain role-specific instructions only. Example structure:

```yaml
director: |
  You are the Director. Translate player intents into YARE events. Do NOT perform arithmetic—use YARE events.

narrator: |
  You are the Narrator. Render the resolved game state and show outcome in vivid prose. Keep responses concise and actionable.

npc: |
  You are an NPC. Reply only to Director's `query_npc_intent` prompts. Keep persona and objectives consistent with `bot_lore.md`.
```

`bot_lore.md` — what to include
- Use clear headings and short sections describing locations, factions, named NPCs, important items, and notable rules. This is the retrieval corpus; prefer factual bulleted lists and short paragraphs.
- Example fragment:

```
# The Ruined Keep

Once a castle of the High Queen. The inner courtyard is collapsed; the western tower holds a locked armory.

## NPCs
- Aldren, former captain of the guard. Scar on left cheek. Disciplined, pragmatic.

## Items
- Ashwood Potion: common healing potion. Restores 10 HP when consumed.
```

Turn model, `MAX_ITERATIONS`, and best patterns
- The engine is stateless between invocations: the client passes a `GameState` and receives an updated `GameState` back.
- `MAX_ITERATIONS = 3`: the engine allows at most three tool calls (YARE events or LLM tool queries) per turn. Design events to do complex work internally using `call` steps rather than requiring multiple external Director calls.

Troubleshooting checklist (step-by-step)
- Backend not starting or crashing:
  1. Ensure venv activated: `source venv/bin/activate` (Linux/macOS) or `.\venv\Scripts\activate` (Windows PowerShell).
  2. Reinstall dependencies: `pip install -e ".[dev,api]"` and watch for errors.
  3. In Terminal 1 run: `uvicorn MnesOS.api.app:app --reload` and paste any traceback.
  4. Check for these lines on success: `INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)` and `Application startup complete.`

- Web UI errors / No Cartridges Available:
  1. Confirm `mnesos-ingest-cartridges` was run after dependencies were installed.
  2. Confirm `User ID` is set in ⚙️ Settings.
  3. In web-client dev console, copy any JS error messages.

- Narrator slow or missing responses:
  1. In browser Settings, verify `OpenRouter API Key` is set.
  2. Check network and OpenRouter quota.
  3. Check backend logs for errors/timeouts.

- When asking the user for help, request:
  - Exact commands they ran.
  - Full terminal output (no screenshots — paste text).
  - The `pwd` value and `git status --porcelain` if repository changes matter.

Developer & testing commands
- Run tests: `python -m pytest`
- Build docs locally: `mkdocs build` (requires docs dependencies)
- Ingest cartridges after edits: `mnesos-ingest-cartridges`

Dialogue templates and example Q&A
- Setup troubleshooting prompt:
  - "Which OS are you using? Paste `python3 --version` and the exact command you ran."
- Cartridge authoring prompt:
  - "Do you want a minimal `yare.yaml` event for combat or a full template cartridge folder? Which cartridge should I modify?"

Example exchanges (4 condensed pairs)
1) Setup & first play-test (Linux)
- User: "How do I run MnesOS locally?"
- Assistant: (asks OS and Python version). Then provides the Quick setup commands block (venv, pip install, mnesos-ingest-cartridges), instructs to run `uvicorn` and `npm run dev`, and asks to paste any errors.

2) No Cartridges Available in UI
- User: "UI shows 'No Cartridges Available'."
- Assistant: "Did you run `mnesos-ingest-cartridges` in an activated venv? Also set `User ID` in Settings. Run these and paste the `mnesos-ingest-cartridges` output."

3) Cartridge authoring — healing potion
- User: "How do I create a potion that heals 10 HP?"
- Assistant: Provides the `use_potion_healing` YARE event snippet and explains to add item text in `bot_lore.md` and, optionally, a `prompt_directives.yaml` note so the Narrator mentions it.

4) Narrator slow / missing
- User: "Narrator response never arrives."
- Assistant: Instructs to check `OpenRouter API Key` in Settings, check backend logs for timeouts, and paste the backend traceback and the approximate timestamp of the failed request.

Assistant policy & helpful constraints
- Do not invent file contents or claim side-effects happened without evidence. Ask for logs or outputs to validate success.
- Keep suggestions limited to one actionable change when guiding novices.
- Prefer deterministic YARE fixes for gameplay logic rather than creative LLM arithmetic.

Appendix — useful examples & snippets
- Minimal `prompt_directives.yaml` example (complete):

```yaml
director: |
  You are the Director. Map player intent to a set of YARE events. Do not perform arithmetic; instruct events to run deterministic logic. Keep instructions short.

narrator: |
  You are the Narrator. Describe the results after YARE events resolve. Be concise, avoid altering deterministic state, and never contradict `bot_lore.md`.

npc: |
  You are an NPC. Reply only to Director's `query_npc_intent` calls. Keep dialogue in-character and consistent with `bot_lore.md`.
```

- Minimal `bot_lore.md` example fragment:

```
# The Ruined Keep

The Ruined Keep was once the seat of the High Queen. The courtyard has collapsed; the western tower contains a locked armory.

## NPCs
- Aldren: former captain of the guard. Scar on left cheek. Practical and wary of strangers.

## Items
- Ashwood Potion: a common healing potion that restores 10 HP when consumed.
```

Published docs (web links)

- [MnesOS — Home](https://neolaw84.github.io/MnesOS)
- [Play-Testing (Linux/macOS)](https://neolaw84.github.io/MnesOS/play-test/)
- [Play-Testing (Windows)](https://neolaw84.github.io/MnesOS/play-test-win/)
- [Cartridge Guide](https://neolaw84.github.io/MnesOS/cartridge-guide/)
- [YARE Specification](https://neolaw84.github.io/MnesOS/yare-specification/)


