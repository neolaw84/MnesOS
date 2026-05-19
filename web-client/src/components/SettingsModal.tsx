/**
 * SettingsModal — BYOK configuration modal (MNS-401).
 *
 * Accepts and persists OpenRouter API key and user ID to localStorage.
 * The API client reads these automatically.
 */

import { useState } from "react";
import {
  getOpenRouterKey,
  setOpenRouterKey,
  getUserId,
  setUserId,
} from "../api/client";
import { initiateOpenRouterLogin } from "../utils/pkce";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export default function SettingsModal({ open, onClose }: SettingsModalProps) {
  // Initializers run once per mount; the parent uses `key` to remount on open.
  const [apiKey, setApiKey] = useState(getOpenRouterKey);
  const [userId, setUserIdLocal] = useState(getUserId);

  if (!open) return null;

  const handleSave = () => {
    setOpenRouterKey(apiKey.trim());
    setUserId(userId.trim());
    onClose();
  };

  const handleDisconnect = () => {
    setOpenRouterKey('');
    setApiKey('');
  };

  const handleConnectClick = async () => {
    try {
      await initiateOpenRouterLogin();
    } catch (err: any) {
      console.error("Failed to initiate login:", err);
      alert(`Could not start OpenRouter connection: ${err.message || err}`);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>⚙️ Settings</h2>

        <div className="modal-section" style={{ marginBottom: '1.5rem', padding: '1rem', background: 'rgba(0,0,0,0.1)', borderRadius: '8px' }}>
          <h3>OpenRouter Authentication</h3>
          <p className="modal-hint" style={{ marginBottom: '1rem' }}>
            Connect your OpenRouter account securely to enable AI models.
          </p>
          {apiKey ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <span style={{ color: 'var(--color-success)', fontWeight: 'bold' }}>✅ Connected to OpenRouter</span>
              <button className="btn btn-secondary btn-small" onClick={handleDisconnect}>
                Disconnect
              </button>
            </div>
          ) : (
            <button className="btn btn-primary" onClick={handleConnectClick} style={{ width: '100%', display: 'flex', justifyContent: 'center' }}>
              🔗 Connect OpenRouter
            </button>
          )}
        </div>

        <details style={{ marginBottom: '1rem' }}>
          <summary style={{ cursor: 'pointer', color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>Advanced: Manual API Key (BYOK)</summary>
          <label className="modal-label" style={{ marginTop: '1rem' }}>
            <input
              type="password"
              className="modal-input"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-or-..."
            />
          </label>
        </details>

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
