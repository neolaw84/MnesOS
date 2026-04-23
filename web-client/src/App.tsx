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

import { useState, useEffect } from "react";
import ChatPane from "./components/ChatPane";
import ChatInput from "./components/ChatInput";
import SettingsModal from "./components/SettingsModal";
import StateDebugger from "./components/StateDebugger";
import SaveManager from "./components/SaveManager";
import CartridgeLibrary from "./components/CartridgeLibrary";
import PersonaManager from "./components/PersonaManager";
import GameInstanceManager from "./components/GameInstanceManager";
import StartNewGameModal from "./components/StartNewGameModal";
import { useGameSession } from "./hooks/useGameSession";
import "./App.css";

type View = "game" | "library" | "personas" | "active_games";

function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [debugVisible, setDebugVisible] = useState(false);
  const [view, setView] = useState<View>("library");
  const [startNewGameOpen, setStartNewGameOpen] = useState(false);

  const session = useGameSession();

  useEffect(() => {
    const handlePlay = (e: Event) => {
      const customEvent = e as CustomEvent;
      session.resetSession(customEvent.detail?.turn_id);
      setView("game");
    };
    window.addEventListener("mnesos-play-instance", handlePlay);
    return () => window.removeEventListener("mnesos-play-instance", handlePlay);
  }, [session]);

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
            className={`btn btn-small ${view === "personas" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setView("personas")}
          >
            🎭 Personas
          </button>
          <button
            className={`btn btn-small ${view === "active_games" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setView("active_games")}
          >
            📂 Active Games
          </button>
          <button
            className="btn btn-small btn-primary"
            style={{ backgroundColor: "var(--color-success)", color: "white" }}
            onClick={() => setStartNewGameOpen(true)}
          >
            🚀 Start New Game
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
      ) : view === "personas" ? (
        <div className="app-body" style={{ padding: "1rem", overflowY: "auto" }}>
          <PersonaManager />
        </div>
      ) : view === "active_games" ? (
        <div className="app-body" style={{ padding: "1rem", overflowY: "auto" }}>
          <GameInstanceManager />
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

      <StartNewGameModal
        open={startNewGameOpen}
        onClose={() => setStartNewGameOpen(false)}
        onStart={(turnId) => {
          if (turnId) {
            window.dispatchEvent(
              new CustomEvent("mnesos-play-instance", { detail: { turn_id: turnId } })
            );
          }
        }}
      />
    </div>
  );
}

export default App;

