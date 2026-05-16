import type { ComponentType } from "react";

export type MinigameComponentProps = {
  config: {
    difficulty: Record<string, unknown>;
    assets: Record<string, unknown>;
    narrative_hooks: Record<string, unknown>;
  };
  onComplete: (payload: {
    status: "completed" | "failed" | "aborted";
    metrics: Record<string, string | number | boolean>;
    minigame_specific_data: Record<string, unknown>;
  }) => void;
};

export const minigameRegistry: Record<string, ComponentType<MinigameComponentProps>> = {};

