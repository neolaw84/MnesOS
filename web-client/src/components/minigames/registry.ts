import type { ComponentType } from "react";
import LightsOut from "./LightsOut";
import ArticulationScramble from "./ArticulationScramble";
import ReflexDial from "./ReflexDial";

export type MinigameComponentProps = {
  config: {
    difficulty: Record<string, unknown>;
    assets: Record<string, unknown>;
    narrative_hooks: Record<string, unknown>;
  };
  onComplete: (payload: {
    status: "completed" | "failed" | "aborted";
    metrics: Record<string, string | number | boolean | string[]>;
    minigame_specific_data: Record<string, unknown>;
    triggered_hooks?: string[];
  }) => void;
};

export const minigameRegistry: Record<string, ComponentType<MinigameComponentProps>> = {
  lights_out: LightsOut,
  articulation_scramble: ArticulationScramble,
  reflex_dial: ReflexDial,
};

