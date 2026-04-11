# MnesOS Feature Roadmap

This document tracks planned and in-development features for the MnesOS (YARE) engine.

## In Development

### Separate NPC Brain Architecture

**Status:** Design Phase / Not Yet Implemented  
**Configuration Flag:** `separate_npc_brain` (default: `false`)  
**Estimated Complexity:** High

#### Overview

In traditional tabletop RPGs, the Dungeon Master (DM) controls all NPCs, playing their dialogue, actions, and thoughts while simultaneously managing plot progression, world state, and combat mechanics. In MnesOS, we currently replicate this monolithic architecture with a single Director node that handles both narrative direction and NPC roleplay.

This feature introduces an **optional** architectural separation that allows cartridge developers to decouple the Director (plot/world management) from individual NPC "brain" nodes (character-specific roleplay).

#### Motivation

**Pros of Separation:**
1. **Elimination of Character Bleed:** Independent NPC nodes maintain purity of persona, avoiding personality/accent mixing when a single LLM manages multiple characters
2. **Reduced Cognitive Load:** Director focuses purely on scenario logic (world state, pacing, consequences); NPCs focus on deep in-character simulation
3. **Emergent Narrative:** NPCs act based on localized knowledge rather than omniscient Director knowledge, enabling genuine surprises and organic interactions
4. **Modularity & Scalability:** Mix-and-match models (expensive reasoning models for Director, cheaper/faster models for minor NPCs); plug-in specialized character cartridges

**Cons of Separation:**
1. **Increased Latency & Cost:** Multiple sequential LLM calls per scene instead of one monolithic call
2. **Context Redundancy:** Same conversation history sent to multiple agents repeatedly
3. **Orchestration Complexity:** Need to prevent independent NPCs from derailing plot while preserving agency
4. **Hallucination Risk:** NPCs may claim to perform actions/possess items beyond what the world state allows

#### Current Workarounds

We have already reduced cognitive load for rigid game mechanics by offloading them to **tool calls**:
- Combat rules → `combat_strike` event/tool
- Spell casting → `cast_spell` event/tool  
- Skill checks → `generic_check` event/tool

This leaves the Director free to focus on plot and NPC characterization without managing dice rolls and state mutations manually.

#### Technical Design (When Implemented)

When `separate_npc_brain: true` in `yare.yaml`:

**Communication Protocol:**
```
1. Broadcast (Director → NPCs):
   - Scene state: who is present, current location, plot goals
   - Player action: what the player just said/did
   
2. Intention (NPC → Director):
   - NPC proposes an action (not directly rendered)
   - Example: "I (bartender) am angry. I intend to throw a mug and yell."
   
3. Resolution (Director → NPC/Narrator):
   - Director validates: does this break physics? derail plot?
   - If valid → approve and send to Narrator for rendering
   - If invalid → send correction back to NPC to revise
```

**Graph Modifications:**
- Add `NPC_Coordination` node between Director and NPC_Brain
- Implement intention/validation loop before Narrator rendering
- Add NPC roster tracking to GameState
- Support per-NPC prompt directives in `prompt_directives.yaml`

#### Configuration

In `yare.yaml`:
```yaml
version: "1.0"
bot_name: "example-cartridge"

# Optional: defaults to false
separate_npc_brain: false

# When separate_npc_brain is true:
npcs:
  bartender:
    personality_file: "npcs/bartender.md"
    model: "gpt-3.5-turbo"  # optional: cheaper model for minor NPCs
  
  king:
    personality_file: "npcs/king.md"
    model: "gpt-4"  # expensive model for complex characters
```

In `prompt_directives.yaml`:
```yaml
director: "Manage plot pacing and world state."

# When separate_npc_brain is false:
npc_brain: "Goblins act in packs and prioritize swarming."

# When separate_npc_brain is true:
npc_personalities:
  bartender: "Gruff but fair. Protective of regulars."
  king: "Wise and melancholic. Haunted by past failures."
```

#### Implementation Status

- [x] Documentation written
- [x] Configuration flag added to schema validator
- [x] Default behavior (`separate_npc_brain: false`) enforced
- [ ] Communication protocol design finalized
- [ ] NPC roster tracking in GameState
- [ ] Intention/validation loop implementation
- [ ] Per-NPC prompt directive support
- [ ] Performance benchmarking (latency/cost analysis)
- [ ] Example cartridge demonstrating the feature

#### Testing Strategy

1. **Unit tests verify:**
   - `separate_npc_brain` flag is recognized and validated
   - Default is `false`
   - When `true`, raises `NotImplementedError` with clear message
   
2. **Integration tests (future):**
   - Multi-NPC scenes with independent personalities
   - NPC actions correctly validated by Director
   - NPCs cannot hallucinate invalid world state
   - Latency benchmarks vs. monolithic architecture

#### Migration Path for Existing Cartridges

Fully backward compatible. Existing cartridges continue to work without modification:
- If `separate_npc_brain` key is omitted → defaults to `false`
- Monolithic Director continues to handle all NPCs as before
- No changes to existing `prompt_directives.yaml` required

#### Future Enhancements

- **Hybrid mode:** Some NPCs managed by Director, others independent
- **NPC memory:** Persistent per-NPC memory separate from global `bot_memory`
- **Inter-NPC dialogue:** NPCs negotiate with each other, not just react to player
- **Voice cloning integration:** Different TTS voices per independent NPC brain

---

## Completed Features

(To be populated as features are completed)

## Backlog / Proposed

(Future features can be documented here)
