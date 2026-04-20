/**
 * SaveManager — Timeline Branching & Save Management UI (MNS-404).
 *
 * Lists GameSave bookmarks, supports save/load checkpoints,
 * and retry of the last message.
 */

import { useState, useEffect } from "react";
import type { GameSave } from "../types";

interface SaveManagerProps {
  saves: GameSave[];
  currentTurnId: string | null;
  loading: boolean;
  onSave: (label: string) => Promise<void>;
  onLoad: (save: GameSave) => Promise<void>;
  onRetry: () => Promise<void>;
  onRefresh: () => Promise<void>;
  hasMessages: boolean;
}

export default function SaveManager({
  saves,
  currentTurnId,
  loading,
  onSave,
  onLoad,
  onRetry,
  onRefresh,
  hasMessages,
}: SaveManagerProps) {
  const [saveLabel, setSaveLabel] = useState("");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    onRefresh();
  }, [onRefresh]);

  const handleSave = async () => {
    const label = saveLabel.trim() || `Save ${new Date().toLocaleString()}`;
    await onSave(label);
    setSaveLabel("");
  };

  return (
    <div className="save-manager">
      {/* Action buttons row */}
      <div className="save-actions">
        <button
          className="btn btn-small btn-accent"
          onClick={onRetry}
          disabled={loading || !hasMessages}
          title="Retry the last narrator response"
        >
          🔄 Retry
        </button>

        <div className="save-inline">
          <input
            type="text"
            className="save-label-input"
            value={saveLabel}
            onChange={(e) => setSaveLabel(e.target.value)}
            placeholder="Save label..."
            disabled={loading || !currentTurnId}
          />
          <button
            className="btn btn-small btn-primary"
            onClick={handleSave}
            disabled={loading || !currentTurnId}
            title="Save current checkpoint"
          >
            💾 Save
          </button>
        </div>

        <button
          className="btn btn-small btn-secondary"
          onClick={() => setExpanded(!expanded)}
        >
          📂 Loads ({saves.length})
        </button>
      </div>

      {/* Expandable saves list */}
      {expanded && (
        <div className="save-list">
          {saves.length === 0 ? (
            <p className="save-empty">No saves yet.</p>
          ) : (
            saves.map((save) => (
              <div key={save.id} className="save-item">
                <div className="save-item-info">
                  <span className="save-item-label">{save.label}</span>
                  <span className="save-item-date">
                    {new Date(save.created_at).toLocaleString()}
                  </span>
                </div>
                <button
                  className="btn btn-small btn-secondary"
                  onClick={() => onLoad(save)}
                  disabled={loading}
                >
                  Load
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
