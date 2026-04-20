/**
 * MnesOS Alpha Web Client — Main Application.
 *
 * Composes:
 *   - SettingsModal (MNS-401)
 *   - ChatPane + ChatInput (MNS-402)
 *   - StateDebugger (MNS-403)
 *   - SaveManager (MNS-404)
 *   - CartridgeLibrary (MNS-Cartridge)
 */

import { useState } from "react";
import ChatPane from "./components/ChatPane";
import ChatInput from "./components/ChatInput";
import SettingsModal from "./components/SettingsModal";
import StateDebugger from "./components/StateDebugger";
import SaveManager from "./components/SaveManager";
import CartridgeLibrary from "./components/CartridgeLibrary";
import { useGameSession } from "./hooks/useGameSession";
import "./App.css";

type View = "game" | "library";

function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [debugVisible, setDebugVisible] = useState(false);
  const [view, setView] = useState<View>("game");

  const session = useGameSession();

  return (
    <div className="app-root">
      {/* Header */}
      <header className="app-header">
        <h1 className="app-title">🎮 MnesOS</h1>
        <span className="app-subtitle">Alpha — Agentic RPG Engine</span>
        <div style={{ display: "flex", gap: "0.5rem", marginLeft: "auto" }}>
          <button
            className={`btn btn-small ${view === "game" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setView("game")}
          >
            🕹 Play
          </button>
          <button
            className={`btn btn-small ${view === "library" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setView("library")}
          >
            📚 Library
          </button>
          <button
            className="btn btn-small btn-secondary"
            onClick={() => setSettingsOpen(true)}
          >
            ⚙️ Settings
          </button>
        </div>
      </header>

      {/* Error banner */}
      {session.error && view === "game" && (
        <div className="error-banner">
          <span>{session.error}</span>
          <button className="btn btn-small" onClick={session.clearError}>
            ✕
          </button>
        </div>
      )}

      {/* Main content area */}
      {view === "library" ? (
        <div className="app-body" style={{ padding: "1rem" }}>
          <CartridgeLibrary />
        </div>
      ) : (
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
      )}

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

