/**
 * TypeScript types aligned with the MnesOS API contracts
 * (docs/design/0005-interfaces-and-contracts.md §1).
 */

// ---------------------------------------------------------------------------
// §1.1 Process Turn
// ---------------------------------------------------------------------------

export interface TurnRequest {
  parent_turn_id?: string | null;
  user_input: string;
}

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
// §1.3 Game Saves
// ---------------------------------------------------------------------------

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
