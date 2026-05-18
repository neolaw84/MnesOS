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
import PlayHub from "./components/PlayHub";
import StartNewGameModal from "./components/StartNewGameModal";
import { useGameSession } from "./hooks/useGameSession";
import { exchangeCodeForKey } from "./utils/pkce";
import { setOpenRouterKey, getInstanceId } from "./api/client";
import "./App.css";

type View = "play" | "library" | "personas";

function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [debugVisible, setDebugVisible] = useState(false);
  const [view, setView] = useState<View>("library");
  const [activeInstanceId, setActiveInstanceId] = useState<string | null>(null);
  const [startNewGameOpen, setStartNewGameOpen] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const session = useGameSession();

  // PKCE OAuth callback handling
  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const code = searchParams.get("code");
    
    if (code) {
      setAuthLoading(true);
      setAuthError(null);
      
      exchangeCodeForKey(code)
        .then((key) => {
          setOpenRouterKey(key);
          // Remove the code from the URL without reloading the page
          window.history.replaceState({}, document.title, window.location.pathname);
        })
        .catch((err) => {
          console.error("Failed to exchange code:", err);
          setAuthError(err.message || "Auth failed");
        })
        .finally(() => {
          setAuthLoading(false);
        });
    }
  }, []);

  useEffect(() => {
    const handlePlay = (e: Event) => {
      const customEvent = e as CustomEvent;
      const instanceId = customEvent.detail?.instance_id || getInstanceId();
      setActiveInstanceId(instanceId || null);
      session.resetSession(customEvent.detail?.turn_id);
      setView("play");
    };
    window.addEventListener("mnesos-play-instance", handlePlay);
    return () => window.removeEventListener("mnesos-play-instance", handlePlay);
  }, [session]);

  return (
    <div className="app-root">
      {/* Auth overlay */}
      {authLoading && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ textAlign: 'center' }}>
            <h2>Authenticating with OpenRouter...</h2>
            <p className="modal-hint">Please wait while we exchange your code for an API key.</p>
          </div>
        </div>
      )}

      {/* Auth error banner */}
      {authError && (
        <div className="error-banner">
          <span>{authError}</span>
          <button className="btn btn-small" onClick={() => setAuthError(null)}>
            ✕
          </button>
        </div>
      )}

      {/* Header */}
      <header className="app-header">
        <h1 className="app-title">🎮 MnesOS</h1>
        <span className="app-subtitle">Alpha — Agentic RPG Engine</span>
        <div style={{ display: "flex", gap: "0.5rem", marginLeft: "auto" }}>
          <button
            className={`btn btn-small ${view === "play" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setView("play")}
          >
            🎮 Play
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
            className="btn btn-small btn-secondary"
            onClick={() => setSettingsOpen(true)}
          >
            ⚙️ Settings
          </button>
        </div>
      </header>

      {/* Error banner */}
      {session.error && view === "play" && (
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
      ) : activeInstanceId ? (
        // Play view with active instance — show chat
        <div className="app-body">
          {/* Back to games button */}
          <div style={{ padding: "0.5rem 1rem", borderBottom: "1px solid var(--border-color)" }}>
            <button
              className="btn btn-small btn-secondary"
              onClick={() => {
                setActiveInstanceId(null);
                session.clearSession();
              }}
            >
              ← My Games
            </button>
          </div>
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
      ) : (
        // Play hub — no active instance
        <div className="app-body play-hub">
          <PlayHub onStartNewGame={() => setStartNewGameOpen(true)} />
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
          // Always dispatch — turnId may be null if cartridge has no first_message
          window.dispatchEvent(
            new CustomEvent("mnesos-play-instance", { detail: { turn_id: turnId } })
          );
        }}
      />
    </div>
  );
}

export default App;

