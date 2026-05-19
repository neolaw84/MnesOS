# Frontend Standardized Minigame Architecture (Revised)

This document outlines the architectural design for the MnesOS minigame suite, ensuring strict adherence to SOLID principles, decoupling the frontend from the backend, and allowing cartridges to dictate the rules securely.

## 1. The Minigame Registry (Single Source of Truth)

**Where to put it:** 
The React Frontend repository. 

**Why:** Minigames are strictly client-side UI/UX components. The backend orchestrator (FastAPI/LangGraph) should remain completely blind to how a game is played, rendered, or structured.

**Design:**
- Each minigame inside the React client (e.g., `/src/components/minigames/LightsOut`) will export a standard interface or `manifest.json`.
- This manifest defines exactly what the minigame expects:
  - `difficulty_schema`: e.g., `{ grid_size: int, time_limit: int }`
  - `assets_schema`: e.g., `{ icon_on: string, icon_off: string }`
  - `events_schema`: e.g., `["on_combo", "on_near_miss"]`
  - `output_schema`: e.g., `{ moves_left: int }`

## 2. The Discovery Mechanism & DX

To automate discovery and ensure a smooth Developer Experience (DX):

1. **Build-Time Aggregation:** During the frontend build process, a script scans all minigame manifests and aggregates them into a single `minigames.schema.json`.
2. **Distribution:** 
   - This schema is published to the `docs/` folder automatically.
   - It is hosted on the frontend as a static asset (`/schemas/minigames.json`).
3. **Cartridge Developer DX:** 
   - Tooling like the YARE VSCode extension will pull this schema.
   - **Action Item:** The `mnesos-cartridge-development` AI skill (`SKILL.md` and related references) will be explicitly updated to ingest this schema, enabling the AI to correctly scaffold `_pending_interaction` payloads for different games with full knowledge of their unique manifests.

## 3. Requesting a Minigame via YARE (Vocabulary & Grammar)

We introduce a standardized, domain-agnostic `_pending_interaction` state object. A cartridge developer "requests" a minigame by having a YARE event write to this state.

### The Universal Grammar
The YARE event will construct an interaction object using standard nested dictionaries:

```json
{
  "interaction_type": "minigame",
  "minigame_id": "lights_out",
  "resolver_event": "hack_terminal_resolve", // Stored in backend state for security
  "config": {
    "difficulty": {
      "grid_size": 4,
      "speed_multiplier": 1.2
    },
    "assets": {
      "icon_on": "fire_emoji",
      "icon_off": "ice_emoji"
    },
    "narrative_hooks": {
      "on_combo": "You are hacking the mainframe!",
      "on_near_miss": "Sparks fly, but you recover."
    }
  }
}
```

### Security & Prompt Injection Prevention
The `resolver_event` is stored purely in the **backend's GameState**. The client only reads this to know a minigame is pending, but the client **cannot** specify which event to call upon completion. This strictly prevents malicious API callers from injecting unauthorized YARE events (e.g., resolving a lockpick game with `give_player_max_gold`).

## 4. The Universal Return Value

When the player finishes the minigame, the React frontend posts an `InteractivePayload` back to the backend's `Input Router`.

To ensure the backend never needs to be updated, the payload follows a strict, universal interface wrapper:

```typescript
interface InteractivePayload {
  interaction_type: "minigame";
  minigame_id: string;
  status: "completed" | "failed" | "aborted"; // Strict Enum
  metrics: Record<string, string | number | boolean>; // Flexible flat metrics mapping
  minigame_specific_data: Record<string, any>; // Deeply nested game-specific data
}
```

**Example JSON Payload:**
```json
{
  "interaction_type": "minigame",
  "minigame_id": "lights_out",
  "status": "completed", 
  "metrics": {
    "time_taken_ms": 14500,
    "score": 8500,
    "perfect_run": false,
    "rank": "A"
  },
  "minigame_specific_data": {
    "moves_made": 12,
    "grid_remaining": 0
  }
}
```

### The Input Router & Resolver Event
1. The frontend sends the above payload (without `resolver_event`).
2. The backend `Input Router` intercepts the POST request.
3. It looks at the **trusted server-side GameState** and verifies that `_pending_interaction` exists and the `minigame_id` matches.
4. It extracts the `resolver_event` securely from the state.
5. It clears the `_pending_interaction` from the state.
6. It dynamically invokes the extracted YARE event (e.g., `hack_terminal_resolve`), passing the frontend's payload as `inputs`.

The cartridge developer writes the resolver event in `yare.yaml`:

```yaml
events:
  hack_terminal_resolve:
    inputs:
      status: string
      metrics: dict
      minigame_specific_data: dict
    steps:
      - branch:
        - if: "@ inputs.status == 'completed'"
          steps:
            - action: set
              var: state.door_unlocked
              value: true
            - action: note
              message: "Player hacked the terminal with rank {inputs.metrics.rank}."
        - else: true
          steps:
            - action: note
              message: "The terminal locked out. Hack failed."
```

## User Review Required
The plan has been revised to incorporate your feedback:
1. Explicitly added the `mnesos-cartridge-development` skill update to the DX plan.
2. Secured `resolver_event` by moving it to trusted state resolution (preventing API spoofing).
3. Made `status` a strict enum.
4. Broadened `metrics` to natively support booleans and strings alongside numbers.

Does this revised approach address all your concerns?
