# MnesOS Minigame Implementation Plan

## Overview
This document outlines the step-by-step implementation plan for the MnesOS minigame suite. It is designed to be highly specific so that a junior developer or an AI agent can execute these tasks independently.

The architecture decouples the frontend minigame logic from the backend YARE (YARE Agentic Rules Engine) execution. Minigame definitions and schemas are exclusively owned by the React frontend, while the backend routes states safely and deterministically.

---

## Phase 1: Frontend Registry & Schema Generation

**Goal:** Establish the minigame registry as the single source of truth and automate the discovery mechanism.

### 1.1 Define Minigame Interface
**Location:** Frontend React Repository (`/src/types/minigames.ts` or similar)
- Create a TypeScript interface for the minigame manifest.
- The manifest must include:
  - `minigame_id` (string)
  - `difficulty_schema` (JSON Schema object defining properties like `grid_size`, `time_limit`)
  - `assets_schema` (JSON Schema object defining required visual assets like `icon_on`)
  - `events_schema` (Array of strings defining narrative hooks, e.g., `["on_combo"]`)
  - `output_schema` (JSON Schema defining minigame-specific return values)

### 1.2 Create Build-Time Schema Aggregator
**Location:** Frontend React Repository (`/scripts/generate-minigame-schema.ts` or similar)
- Write a Node.js script that:
  1. Scans a dedicated directory (e.g., `/src/components/minigames/`) for all minigame manifests (e.g., `manifest.json` or exported TypeScript objects).
  2. Aggregates these manifests into a single `minigames.schema.json` file.
  3. Writes this aggregated file to the frontend's public folder (e.g., `/public/schemas/minigames.json`) so it can be hosted statically.
  4. Copies the aggregated file to the project's root `docs/` folder for repository documentation.
- Update `package.json` to ensure this script runs automatically before the `build` and `dev` scripts.

---

## Phase 2: Backend Input Routing & Security

**Goal:** Implement the logic in the backend `Input Router` to safely resolve minigame interactions without allowing prompt injection.

### 2.1 Standardize `_pending_interaction` Schema
**Location:** Backend (`yare` schema definitions / LangGraph state models)
- Update the GameState schema to formally support a `_pending_interaction` object with the following shape:
  ```json
  {
    "interaction_type": "minigame",
    "minigame_id": "string",
    "resolver_event": "string",
    "config": {
      "difficulty": "dict",
      "assets": "dict",
      "narrative_hooks": "dict"
    }
  }
  ```

### 2.2 Update the Input Router Node
**Location:** Backend LangGraph definition (`Input Router` node)
- Update the router to intercept incoming interactions of type `minigame`.
- **Validation:** 
  - Check that the `GameState` currently contains a `_pending_interaction`.
  - Verify that the incoming `minigame_id` matches the `minigame_id` in the backend state.
- **Security & Extraction:**
  - **Crucial:** Extract the `resolver_event` from the trusted **server-side** `_pending_interaction`, NOT from the incoming API payload.
- **State Cleanup:**
  - Remove `_pending_interaction` from the `GameState` to prevent replay attacks.
- **Execution:**
  - Route the incoming payload as `inputs` to the dynamically extracted YARE `resolver_event`.

---

## Phase 3: Frontend Minigame Framework & Payload Dispatch

**Goal:** Implement the universal return value structure and the React wrapper for minigames.

### 3.1 Define the Universal Payload Interface
**Location:** Frontend (`/src/types/minigames.ts`)
- Define the `InteractivePayload` interface that will be sent back to the API:
  ```typescript
  export interface InteractivePayload {
    interaction_type: "minigame";
    minigame_id: string;
    status: "completed" | "failed" | "aborted";
    metrics: Record<string, string | number | boolean>;
    minigame_specific_data: Record<string, any>;
  }
  ```

### 3.2 Implement the Minigame Wrapper Component
**Location:** Frontend (`/src/components/minigames/MinigameWrapper.tsx`)
- Create a higher-order React component or wrapper that:
  1. Reads `_pending_interaction` from the current GameState.
  2. Dynamically loads the corresponding minigame component based on `minigame_id`.
  3. Passes the `config` (difficulty, assets, narrative hooks) down as props.
  4. Provides a callback function (e.g., `onComplete(payload)`) that the child minigame calls upon finishing.
  5. The wrapper handles formatting the final `InteractivePayload` and posting it to the backend's `/api/instances/{id}/turn` endpoint.

---

## Phase 4: DX & AI Skill Updating

**Goal:** Ensure the AI tooling and Cartridge Developers can effortlessly utilize the new minigame suite.

### 4.1 Update the Cartridge Development Skill
**Location:** `.agents/skills/mnesos-cartridge-development/SKILL.md`
- Update the skill document to instruct AI agents on how to construct a `_pending_interaction` state mutation using YARE.
- Explain the separation of the initial request event and the `resolver_event`.
- Explicitly instruct the AI to reference the newly generated `minigames.schema.json` when determining what properties belong in `config.difficulty`, `config.assets`, and `config.narrative_hooks` for a specific minigame.
- Provide a clear template in the skill file showing a request event and a resolver event.
