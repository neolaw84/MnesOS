# MnesOS Web Client Architecture

The MnesOS Web Client is a single-page application built with React, Vite, and TypeScript. It serves as the official frontend for the MnesOS Agentic RPG Engine. It provides a rich user interface for playing text-based RPG cartridges, managing game saves, interacting with dynamic minigames, and administering cartridge libraries and player personas.

## Technology Stack
- **Framework:** React 19 + TypeScript
- **Bundler:** Vite
- **Testing:** 
  - Vitest & React Testing Library (Unit Tests)
  - Playwright (E2E Tests)
- **Styling:** Vanilla CSS (`App.css`, `index.css`)
- **Linting/Formatting:** ESLint

## High-Level Architecture

The web client operates as a thin UI layer over the core MnesOS backend. It manages local session state and streams chat interactions, leaning heavily on the stateless graph backend to maintain the actual game progression.

### 1. View Orchestration (`App.tsx`)
The main application acts as a view router relying on React state rather than a dedicated routing library. It orchestrates three primary views:
- **Play View:** The active gameplay session containing the chat pane, input area, save manager, and debugging sidebar.
- **Library View:** The cartridge administration interface (`CartridgeLibrary`) for uploading, managing, and browsing playable game modules.
- **Personas View:** The profile manager (`PersonaManager`) to set up player characters before launching a game.

Transitions into the "Play View" are typically triggered by a custom global event (`mnesos-play-instance`), which signals the app to hydrate a specific game instance ID.

### 2. State Management (`useGameSession.ts`)
The `useGameSession` hook is the heart of the gameplay loop. It abstracts all complex state required during a live game, including:
- **Message History (`messages`)**: Optimistically updates and stores user and assistant messages for display.
- **Turn Tracking (`currentTurnId`)**: Keeps track of the node graph turn progression.
- **Bot Memory (`botMemory`)**: A live reflection of the backend's internal state tracker, constantly refreshed via hydrated state polling.
- **Minigame Interactions (`pendingInteraction`)**: Automatically detects if the bot memory contains a `_pending_interaction` flag and surfaces it to the UI layer to intercept the flow.
- **Checkpointing**: Facilitates saving (`saveCheckpoint`) and loading (`loadCheckpoint`) by interacting with the instance APIs.

### 3. API Client (`api/client.ts`)
A dedicated module handling all REST communication with the FastAPI backend. It is responsible for:
- Injecting required authentication headers (`X-OpenRouter-Key`) and provider definitions.
- Normalizing user sessions (`X-User-Id`).
- Providing strongly-typed interfaces for core endpoints: Instances, Turns, States, Cartridges, and Personas.

### 4. Component Hierarchy
- **`ChatPane` & `ChatInput`**: Renders the ongoing RPG narrative. `ChatPane` parses standard narrative text and system messages.
- **`SaveManager`**: A sidebar/overlay allowing users to visually manage time-travel checkpoints (saves).
- **`StateDebugger`**: A developer panel toggled on during gameplay that exposes raw `botMemory` and variables for testing cartridges.
- **`MinigameWrapper`**: A conditional overlay that takes control of the UI when an interactive YARE minigame is requested by the backend. It dynamically resolves the requested minigame UI and submits the interaction result back to the server to resume standard text generation.
- **`PlayHub`**: The dashboard for starting new instances or resuming previous game sessions.

## Core Workflows

### Authentication Workflow
MnesOS utilizes an embedded PKCE OAuth flow to exchange an authorization code for a Bring-Your-Own-Key (BYOK) OpenRouter API key.
1. The app detects a `?code=` query parameter on load.
2. `App.tsx` calls `exchangeCodeForKey` (`utils/pkce.ts`).
3. Upon success, the returned key is stored in `localStorage` and seamlessly injected into all subsequent `api/client.ts` requests.

### Gameplay Turn Loop
1. The user inputs text via `ChatInput`.
2. `useGameSession` optimistically adds the user's message to the local chat history.
3. `api/client.ts -> processTurn` fires, appending the new message to the backend session tree.
4. The backend evaluates state, invokes LLMs, and returns a narrator response.
5. The frontend appends the assistant's message and immediately queries `getGameState` to hydrate and synchronize the `botMemory` sidebar.
6. If the new `botMemory` contains a `_pending_interaction`, the frontend pauses standard chat input and mounts the `MinigameWrapper`.

### Cartridge Administration
Users can manage "Cartridges" (the portable zip bundles or raw files that define an RPG world) using the Library view. The API supports multi-part form uploads allowing direct submission of `.zip` files, or individual `yare`, `lore`, and `directives` files, abstracting the complexity of local file management.

## Scripts & Development
- `npm run dev`: Starts the Vite development server. Automatically runs `predev` hooks to generate required minigame JSON schemas (`scripts/generate-minigame-schema.js`).
- `npm run build`: Type-checks and bundles the application for production deployment.
- `npm run test`: Executes the Vitest unit testing suite.
- `npm run test:e2e`: Runs Playwright E2E browser automation tests to validate core workflows.
