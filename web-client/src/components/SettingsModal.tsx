/**
 * SettingsModal — BYOK configuration modal (MNS-401).
 *
 * Accepts and persists OpenRouter API key, user ID, and instance ID
 * to localStorage. The API client reads these automatically.
 */

import { useState } from "react";
import {
  getOpenRouterKey,
  setOpenRouterKey,
  getUserId,
  setUserId,
  getInstanceId,
  setInstanceId,
} from "../api/client";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export default function SettingsModal({ open, onClose }: SettingsModalProps) {
  // Initializers run once per mount; the parent uses `key` to remount on open.
  const [apiKey, setApiKey] = useState(getOpenRouterKey);
  const [userId, setUserIdLocal] = useState(getUserId);
  const [instanceId, setInstanceIdLocal] = useState(getInstanceId);

  if (!open) return null;

  const handleSave = () => {
    setOpenRouterKey(apiKey.trim());
    setUserId(userId.trim());
    setInstanceId(instanceId.trim());
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>⚙️ Settings</h2>

        <label className="modal-label">
          OpenRouter API Key (BYOK)
          <input
            type="password"
            className="modal-input"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-or-..."
          />
        </label>

        <label className="modal-label">
          User ID
          <input
            type="text"
            className="modal-input"
            value={userId}
            onChange={(e) => setUserIdLocal(e.target.value)}
            placeholder="user-uuid"
          />
        </label>

        <label className="modal-label">
          Game Instance ID
          <input
            type="text"
            className="modal-input"
            value={instanceId}
            onChange={(e) => setInstanceIdLocal(e.target.value)}
            placeholder="instance-uuid"
          />
        </label>

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave}>
            Save
          </button>
        </div>

        <p className="modal-hint">
          Your API key is stored only in this browser's localStorage and sent
          directly to OpenRouter — never to the MnesOS server.
        </p>
      </div>
    </div>
  );
}
