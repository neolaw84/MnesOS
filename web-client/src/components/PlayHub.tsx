import { useEffect, useState } from "react";
import type { GameInstanceResponse } from "../types";
import { listInstances, deleteInstance, setInstanceId } from "../api/client";

interface PlayHubProps {
  onStartNewGame: () => void;
}

export default function PlayHub({ onStartNewGame }: PlayHubProps) {
  const [instances, setInstances] = useState<GameInstanceResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchInstances = async () => {
    try {
      setLoading(true);
      const data = await listInstances();
      setInstances(data);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Failed to load active games.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInstances();
  }, []);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this game instance? This will also delete all its turn logs and saves.")) return;
    try {
      await deleteInstance(id);
      setInstances((prev) => prev.filter((i) => i.id !== id));
    } catch (e: any) {
      alert("Failed to delete: " + e.message);
    }
  };

  const handleResume = (id: string) => {
    setInstanceId(id);
    window.dispatchEvent(
      new CustomEvent("mnesos-play-instance", { detail: { turn_id: null } })
    );
  };

  return (
    <div className="play-hub-scroll">
      {error && (
        <div className="error-banner" style={{ margin: "0 0 1rem 0", borderRadius: "8px" }}>
          <span>{error}</span>
          <button className="btn btn-small" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <div className="play-hub-grid">
        {/* New Game card — always first */}
        <button className="play-hub-new-card" onClick={onStartNewGame}>
          <span className="play-hub-new-icon">＋</span>
          <span className="play-hub-new-label">Start New Game</span>
        </button>

        {/* Existing instance cards */}
        {loading && instances.length === 0 ? (
          <div className="play-hub-loading">Loading…</div>
        ) : (
          instances.map((instance) => (
            <div key={instance.id} className="play-hub-card">
              <div className="play-hub-card-header">
                <span className="play-hub-card-status">{instance.status}</span>
              </div>
              <div className="play-hub-card-body">
                <p className="play-hub-card-meta">
                  Started {new Date(instance.created_at).toLocaleDateString()}
                </p>
                {instance.last_played_at && (
                  <p className="play-hub-card-meta">
                    Played {new Date(instance.last_played_at).toLocaleString()}
                  </p>
                )}
              </div>
              <div className="play-hub-card-actions">
                <button className="btn btn-primary" onClick={() => handleResume(instance.id)}>
                  ▶ Resume
                </button>
                <button
                  className="btn btn-secondary play-hub-delete-btn"
                  onClick={() => handleDelete(instance.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
