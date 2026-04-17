# Architecture: NPC Interaction Model

This document describes how NPCs maintain autonomy and identity within the MnesOS 2-node graph.

## 1. Overview

MnesOS uses a **Tool-Based Intent Model** to handle NPCs. Rather than giving NPCs their own graph nodes (which increases latency and costs), NPCs are treated as "consultants" queried by the Director via a specialized tool: `query_npc_intent`.

## 2. Motivation

Separating NPC logic from the high-level Director logic prevents **Character Bleed**—the tendency of LLMs to mix personalities when one agent plays multiple roles. By using a specialized query for NPCs, we ensure:
1. **Persona Purity**: NPCs are grounded in their specific profiles, tags, and internal monologues.
2. **Reduced Hallucinatons**: NPCs propose *intent*, but the Director (the GM) resolves *outcomes* using deterministic YARE rules.
3. **Contextual Isolation**: NPCs only see a subset of the global state (filtered by `npc_visibility` flags), preventing them from acting on meta-knowledge they shouldn't have.

## 3. Implementation: query_npc_intent

When the Director identifies that NPCs are present, it invokes the NPC Brain via a structured tool call.

### Flow of Intent
1. **Director** identifies qualifying NPCs from `bot_memory`.
2. **Director** calls `query_npc_intent(present_npcs=[...], scene_context="...")`.
3. **NPC Brain** (a separate LLM instance) generates a JSON response containing `dialogue`, `action_intent`, and `internal_monologue` for each requested NPC.
4. **Director** receives the intents, resolves any triggered mechanics via YARE, and summarizes the results for the Narrator.

### State Subsetting
To prevent NPCs from being overwhelmed by global state, the engine uses the `get_npc_visible_state` function. Only variables in `yare.yaml` marked with `npc_visibility: true` are passed to the NPC Brain tool.

## 4. NPC Configuration

### Templates and Tags
NPCs utilize a mix of **Name Mode** (unique individuals) and **Tag Mode** (archetypes).

- **Name Mode**: Linked to a unique `npc_templates` entry in `yare.yaml`.
- **Tag Mode**: Inherits qualities from one or more "tag" templates.

### Example Profile (in bot_memory)
```json
{
  "id": "npc_goblin_guard",
  "name": "Zrek",
  "template": "goblin_chieftain",
  "tags": ["goblin", "aggressive"],
  "hp": 20
}
```

## 5. Directives

NPC behavior can be steered at the cartridge level via the `npc` key in `prompt_directives.yaml`.

```yaml
# prompt_directives.yaml
npc: >
  Goblins are cowardly and prioritize swarming. 
  They always speak in high-pitched, gravelly voices.
```

The Director automatically injects these directives into the `query_npc_intent` call.
