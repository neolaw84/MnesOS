/**
 * TypeScript types aligned with the MnesOS API contracts
 * (docs/design/0005-interfaces-and-contracts.md §1).
 */

// ---------------------------------------------------------------------------
// §1.1 Process Turn
// ---------------------------------------------------------------------------

import type { MinigameInteractionPayload } from "./minigames";

export interface TurnRequestBase {
  parent_turn_id?: string | null;
  player_settings?: Record<string, unknown>;
  request_overrides?: Record<string, unknown>;
}

export type TurnRequest =
  | ({
      user_input: string;
      interaction?: never;
    } & TurnRequestBase)
  | ({
      user_input?: never;
      interaction: MinigameInteractionPayload;
    } & TurnRequestBase);

export interface TurnResponse {
  turn_id: string;
  narrator_response: string;
  yare_delta: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// §1.2 Inject State
// ---------------------------------------------------------------------------

export interface InjectRequest {
  parent_turn_id?: string | null;
  yare_delta: Record<string, unknown>;
}

export interface InjectResponse {
  turn_id: string;
}

// ---------------------------------------------------------------------------
// §1.3 Game Saves & Instances
// ---------------------------------------------------------------------------

export interface CreateInstanceRequest {
  version_id: string;
  persona_id: string;
}

export interface CreateInstanceResponse {
  instance_id: string;
  turn_id?: string;
}

export interface GameInstanceResponse {
  id: string;
  user_id: string;
  persona_id: string;
  version_id: string;
  status: string;
  created_at: string;
  last_played_at?: string;
}

export interface PlayInstancePayload {
  instance_id: string;
  turn_id: string | null;
}

export interface CreateSaveRequest {
  turn_log_id: string;
  label: string;
}

export interface CreateSaveResponse {
  save_id: string;
  created_at: string;
}

export interface GameSave {
  id: string;
  instance_id: string;
  turn_log_id: string;
  label: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// §1.4 Load Game State
// ---------------------------------------------------------------------------

export interface HydratedStateResponse {
  bot_memory: Record<string, unknown>;
  client_messages: ChatMessage[];
  current_turn_id?: string | null;
  last_user_input?: string | null;
  last_parent_turn_id?: string | null;
}

// ---------------------------------------------------------------------------
// Chat UI types
// ---------------------------------------------------------------------------

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/** A message displayed in the chat pane, augmented with turn metadata. */
export interface DisplayMessage extends ChatMessage {
  turnId?: string;
}

// ---------------------------------------------------------------------------
// Cartridge Library types
// ---------------------------------------------------------------------------

export interface Cartridge {
  id: string;
  creator_id: string;
  title: string;
  description: string;
  genre: string;
  visibility: "PUBLIC" | "PRIVATE";
}

export interface UpdateCartridgeRequest {
  title?: string;
  description?: string;
  genre?: string;
  visibility?: "PUBLIC" | "PRIVATE";
}

export interface CartridgeVersion {
  id: string;
  cartridge_id: string;
  version_tag: string;
  yare_spec: Record<string, unknown>;
  prompt_directives: Record<string, unknown>;
  bot_lore: string;
  first_message: string;
  checksum: string;
  yare_js_src?: string | null;
  published_at: string | null;
}

export interface CreateCartridgeRequest {
  title: string;
  description: string;
  genre: string;
  visibility: "PUBLIC" | "PRIVATE";
}

// ---------------------------------------------------------------------------
// Persona types
// ---------------------------------------------------------------------------

export interface Persona {
  id: string;
  user_id: string;
  name: string;
  pronoun_sub: string;
  pronoun_obj: string;
  pronoun_poss: string;
  pronoun_poss_obj: string;
  appearance: string;
  background: string;
  personality: string;
  created_at?: string;
}

export interface CreatePersonaRequest {
  name: string;
  pronoun_sub: string;
  pronoun_obj: string;
  pronoun_poss: string;
  pronoun_poss_obj: string;
  appearance: string;
  background: string;
  personality: string;
}

export interface UpdatePersonaRequest {
  name?: string;
  pronoun_sub?: string;
  pronoun_obj?: string;
  pronoun_poss?: string;
  pronoun_poss_obj?: string;
  appearance?: string;
  background?: string;
  personality?: string;
}

export * from "./minigames";
