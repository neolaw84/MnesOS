/**
 * MnesOS Alpha Web Client — Main Application.
 *
 * Composes:
 *   - SettingsModal (MNS-401)
 *   - ChatPane + ChatInput (MNS-402)
 *   - StateDebugger (MNS-403)
 *   - SaveManager (MNS-404)
 */

import { useState } from "react";
import ChatPane from "./components/ChatPane";
import ChatInput from "./components/ChatInput";
import SettingsModal from "./components/SettingsModal";
import StateDebugger from "./components/StateDebugger";
import SaveManager from "./components/SaveManager";
import { useGameSession } from "./hooks/useGameSession";
import "./App.css";

function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [debugVisible, setDebugVisible] = useState(false);

  const session = useGameSession();

  return (
    <div className="app-root">
      {/* Header */}
      <header className="app-header">
        <h1 className="app-title">🎮 MnesOS</h1>
        <span className="app-subtitle">Alpha — Agentic RPG Engine</span>
        <button
          className="btn btn-small btn-secondary header-btn"
          onClick={() => setSettingsOpen(true)}
        >
          ⚙️ Settings
        </button>
      </header>

      {/* Error banner */}
      {session.error && (
        <div className="error-banner">
          <span>{session.error}</span>
          <button className="btn btn-small" onClick={session.clearError}>
            ✕
          </button>
        </div>
      )}

      {/* Main content area */}
      <div className="app-body">
        {/* Chat + Input column */}
        <main className="chat-column">
          <ChatPane messages={session.messages} loading={session.loading} />

          <SaveManager
            saves={session.saves}
            currentTurnId={session.currentTurnId}
            loading={session.loading}
            onSave={session.saveCheckpoint}
            onLoad={session.loadCheckpoint}
            onRetry={session.retryLast}
            onRefresh={session.refreshSaves}
            hasMessages={session.messages.length > 0}
          />

          <ChatInput
            onSend={session.sendTurn}
            disabled={session.loading}
          />
        </main>

        {/* Debug sidebar */}
        <StateDebugger
          botMemory={session.botMemory}
          visible={debugVisible}
          onToggle={() => setDebugVisible((v) => !v)}
        />
      </div>

      {/* Settings modal — key forces remount to re-read localStorage */}
      <SettingsModal
        key={settingsOpen ? "open" : "closed"}
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  );
}

export default App;
