export type JsonSchema = Record<string, unknown>;

export interface MinigameManifest {
  minigame_id: string;
  difficulty_schema: JsonSchema;
  assets_schema: JsonSchema;
  events_schema: string[];
  output_schema: JsonSchema;
}

export type MinigameStatus = "completed" | "failed" | "aborted";

/** Universal payload wrapper posted back to the backend turn endpoint. */
export interface MinigameInteractionPayload {
  interaction_type: "minigame";
  minigame_id: string;
  status: MinigameStatus;
  metrics: Record<string, string | number | boolean>;
  minigame_specific_data: Record<string, unknown>;
  triggered_hooks?: string[];
}

