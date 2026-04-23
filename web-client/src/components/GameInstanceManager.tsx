import { useEffect, useState } from "react";
import type { GameInstanceResponse } from "../types";
import { listInstances, deleteInstance, setInstanceId } from "../api/client";

export default function GameInstanceManager() {
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
    if (!confirm("Are you sure you want to delete this game instance? This will also delete all its turn logs and saves.")) return;
    try {
      await deleteInstance(id);
      setInstances((prev) => prev.filter((i) => i.id !== id));
    } catch (e: any) {
      alert("Failed to delete instance: " + e.message);
    }
  };

  const handleResume = (id: string) => {
    setInstanceId(id);
    window.dispatchEvent(
      new CustomEvent("mnesos-play-instance", { detail: { turn_id: null } })
    );
  };

  return (
    <div className="cartridge-library">
      <div className="library-header">
        <h2>Active Games</h2>
        <button className="btn btn-secondary" onClick={fetchInstances} disabled={loading}>
          Refresh
        </button>
      </div>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button className="btn btn-small" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {loading && instances.length === 0 ? (
        <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>
          Loading active games...
        </div>
      ) : instances.length === 0 ? (
        <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)", border: "1px dashed var(--border-color)", borderRadius: "8px", marginTop: "1rem" }}>
          No active games. Start a new game!
        </div>
      ) : (
        <div className="library-grid" style={{ marginTop: "1rem" }}>
          {instances.map((instance) => (
            <div key={instance.id} className="cartridge-card">
              <div className="cartridge-header">
                <h3 style={{ fontSize: "1rem", margin: 0 }}>
                  Game Instance
                </h3>
                <span className="cartridge-badge">
                  {instance.status}
                </span>
              </div>
              <p className="cartridge-desc" style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: "0.5rem 0" }}>
                Created: {new Date(instance.created_at).toLocaleString()}<br />
                {instance.last_played_at && <>Last Played: {new Date(instance.last_played_at).toLocaleString()}</>}
              </p>
              
              <div className="cartridge-actions" style={{ marginTop: "auto", paddingTop: "1rem", borderTop: "1px solid var(--border-color)", display: "flex", justifyContent: "space-between" }}>
                <button className="btn btn-small btn-primary" onClick={() => handleResume(instance.id)}>
                  Resume
                </button>
                <button className="btn btn-small btn-secondary" style={{ color: "var(--color-error)" }} onClick={() => handleDelete(instance.id)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
