/**
 * MinigameWrapper — intercepts a pending `_pending_interaction` from
 * `botMemory` and renders the matching minigame component from the registry.
 *
 * When the game completes (or is aborted), the wrapper calls `onInteractionComplete`
 * with the full `MinigameInteractionPayload` so the parent can post it to the API.
 */

import type { MinigameInteractionPayload, PendingInteraction } from "../../types/minigames";
import { minigameRegistry } from "./registry";

interface MinigameWrapperProps {
  pendingInteraction: PendingInteraction;
  onInteractionComplete: (payload: MinigameInteractionPayload) => void;
}

export default function MinigameWrapper({
  pendingInteraction,
  onInteractionComplete,
}: MinigameWrapperProps) {
  const { minigame_id, config } = pendingInteraction;

  const MinigameComponent = minigameRegistry[minigame_id];

  if (!MinigameComponent) {
    return (
      <div className="minigame-wrapper minigame-unknown">
        <p>
          Unknown minigame: <strong>{minigame_id}</strong>. Please update your
          client.
        </p>
        <button
          className="btn btn-secondary btn-small"
          onClick={() =>
            onInteractionComplete({
              interaction_type: "minigame",
              minigame_id,
              status: "aborted",
              metrics: {},
              minigame_specific_data: {},
            })
          }
        >
          Dismiss (abort)
        </button>
      </div>
    );
  }

  const mergedConfig = {
    difficulty: (config?.difficulty ?? {}) as Record<string, unknown>,
    assets: (config?.assets ?? {}) as Record<string, unknown>,
    narrative_hooks: (config?.narrative_hooks ?? {}) as Record<string, unknown>,
  };

  return (
    <div className="minigame-wrapper">
      <MinigameComponent
        config={mergedConfig}
        onComplete={(result) => {
          onInteractionComplete({
            interaction_type: "minigame",
            minigame_id,
            status: result.status,
            metrics: result.metrics,
            minigame_specific_data: result.minigame_specific_data,
            triggered_hooks: result.triggered_hooks,
          });
        }}
      />
    </div>
  );
}
