/**
 * AppShell — owns navigation, layout, and the primary view routing.
 *
 * Responsibilities:
 *   - Renders the header with navigation buttons.
 *   - Manages view state ("play" | "library" | "personas") and settingsOpen / startNewGameOpen.
 *   - Uses explicit play callbacks to switch to play view.
 *   - Renders the active view (CartridgeLibrary, PersonaManager, PlayHub, or Chat).
 *   - Renders SettingsModal and StartNewGameModal as overlays.
 *
 * Consumes:
 *   - useAuth()          — for auth loading/error state (rendered by AuthProvider)
 *   - useGameInstance()  — for activeInstanceId and minigameOpen
 *   - useGameSession()   — for session state and actions
 */

import { useCallback, useState } from "react";
import ChatPane from "./ChatPane";
import ChatInput from "./ChatInput";
import SettingsModal from "./SettingsModal";
import StateDebugger from "./StateDebugger";
import SaveManager from "./SaveManager";
import CartridgeLibrary from "./CartridgeLibrary";
import PersonaManager from "./PersonaManager";
import PlayHub from "./PlayHub";
import StartNewGameModal from "./StartNewGameModal";
import MinigameWrapper from "./minigames/MinigameWrapper";
import { useGameSession } from "../hooks/useGameSession";
import { useGameInstance } from "../contexts/GameInstanceContext";
import { setInstanceId } from "../api/client";
import type { PlayInstancePayload } from "../types";

type View = "play" | "library" | "personas";

export default function AppShell() {
  const session = useGameSession();
  const { activeInstanceId, setActiveInstanceId, minigameOpen, setMinigameOpen } =
    useGameInstance();

  const [view, setView] = useState<View>("library");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [startNewGameOpen, setStartNewGameOpen] = useState(false);
  const [debugVisible, setDebugVisible] = useState(false);

  const handlePlayInstance = useCallback((payload: PlayInstancePayload) => {
    setInstanceId(payload.instance_id);
    setActiveInstanceId(payload.instance_id);
    session.resetSession(payload.turn_id ?? undefined);
    setView("play");
  }, [session, setActiveInstanceId, setView]);

  return (
    <div className="app-root">
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

      {/* Session error banner (play view only) */}
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
          <main className="chat-column">
            <ChatPane
              messages={session.messages}
              loading={session.loading}
              pendingInteraction={session.pendingInteraction}
              onOpenMinigame={() => setMinigameOpen(true)}
            />

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

            <ChatInput onSend={session.sendTurn} disabled={session.loading} />
          </main>

          <StateDebugger
            botMemory={session.botMemory}
            visible={debugVisible}
            onToggle={() => setDebugVisible((v) => !v)}
          />

          {session.pendingInteraction && minigameOpen && (
            <div className="modal-overlay minigame-modal-overlay">
              <MinigameWrapper
                pendingInteraction={session.pendingInteraction as any}
                onInteractionComplete={(payload) => {
                  setMinigameOpen(false);
                  session.sendInteraction(payload);
                }}
              />
            </div>
          )}
        </div>
      ) : (
        // Play hub — no active instance
        <div className="app-body play-hub">
          <PlayHub
            onStartNewGame={() => setStartNewGameOpen(true)}
            onPlayInstance={handlePlayInstance}
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
        onPlayInstance={handlePlayInstance}
      />
    </div>
  );
}
