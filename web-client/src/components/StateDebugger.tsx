/**
 * StateDebugger — developer tools panel (MNS-403).
 *
 * Displays the current bot_memory as formatted JSON in a sidebar/panel.
 * Provides a quick at-a-glance view of live stats.
 */

import type { GameSessionState } from "../hooks/useGameSession";

interface StateDebuggerProps {
  botMemory: GameSessionState["botMemory"];
  visible: boolean;
  onToggle: () => void;
}

/** Safely extract a nested value from an object by dot-path. */
function deepGet(obj: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((acc, key) => {
    if (acc && typeof acc === "object" && key in (acc as Record<string, unknown>)) {
      return (acc as Record<string, unknown>)[key];
    }
    return undefined;
  }, obj);
}

/** Render a quick-stat if the value exists. */
function QuickStat({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null) return null;
  return (
    <span className="debug-stat">
      {label}: <strong>{String(value)}</strong>
    </span>
  );
}

export default function StateDebugger({
  botMemory,
  visible,
  onToggle,
}: StateDebuggerProps) {
  // Try to extract common stats
  const hp = deepGet(botMemory, "player.hp");
  const gold = deepGet(botMemory, "player.gold");
  const level = deepGet(botMemory, "player.level");
  const location = deepGet(botMemory, "current_location");
  const inventory = deepGet(botMemory, "player.inventory");

  return (
    <div className={`debug-panel ${visible ? "debug-open" : "debug-closed"}`}>
      <button className="debug-toggle" onClick={onToggle}>
        {visible ? "▶ Hide Debug" : "◀ Debug"}
      </button>

      {visible && (
        <div className="debug-content">
          <h3>🔧 State Debugger</h3>

          {/* Quick stats bar */}
          <div className="debug-stats-bar">
            <QuickStat label="❤️ HP" value={hp} />
            <QuickStat label="💰 Gold" value={gold} />
            <QuickStat label="⭐ Level" value={level} />
            <QuickStat label="📍 Location" value={location} />
            {Array.isArray(inventory) && (
              <QuickStat
                label="🎒 Items"
                value={inventory.length}
              />
            )}
          </div>

          {/* Full JSON tree */}
          <pre className="debug-json">
            {JSON.stringify(botMemory, null, 2) || "{}"}
          </pre>
        </div>
      )}
    </div>
  );
}
