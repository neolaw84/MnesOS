import { useState, useEffect } from "react";

interface MinigameEntry {
  minigame_id: string;
  difficulty_schema?: {
    type?: string;
    properties?: Record<string, { type?: string; description?: string; default?: unknown; minimum?: number; maximum?: number }>;
  };
  output_schema?: {
    type?: string;
    properties?: Record<string, { type?: string; description?: string }>;
  };
  assets_schema?: Record<string, unknown>;
  events_schema?: string[];
}

/**
 * MinigameDirectory — displays the available minigames and their
 * difficulty/output parameters for developer reference.
 */
export function MinigameDirectory() {
  const [minigames, setMinigames] = useState<MinigameEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/minigames")
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load minigames (${res.status})`);
        return res.json();
      })
      .then((data: MinigameEntry[]) => {
        setMinigames(data);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading minigames...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="minigame-directory">
      <h2>Minigame Registry</h2>
      {minigames.length === 0 && <p>No minigames registered.</p>}
      {minigames.map((mg) => (
        <div key={mg.minigame_id} className="minigame-directory__entry">
          <h3>{mg.minigame_id}</h3>

          {mg.difficulty_schema?.properties && (
            <div className="minigame-directory__section">
              <h4>Difficulty Parameters</h4>
              <ul>
                {Object.entries(mg.difficulty_schema.properties).map(([key, val]) => (
                  <li key={key}>
                    <code>{key}</code>: {val.type ?? "unknown"}
                    {val.description && <span> — {val.description}</span>}
                    {val.default !== undefined && <span> (default: {String(val.default)})</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {mg.output_schema?.properties && (
            <div className="minigame-directory__section">
              <h4>Output Metrics</h4>
              <ul>
                {Object.entries(mg.output_schema.properties).map(([key, val]) => (
                  <li key={key}>
                    <code>{key}</code>: {val.type ?? "unknown"}
                    {val.description && <span> — {val.description}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
