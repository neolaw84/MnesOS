/**
 * ChatPane — scrollable message history (MNS-402).
 *
 * Displays Player and Narrator messages in a chat-style layout.
 * Auto-scrolls to the bottom on new messages.
 */

import { useEffect, useRef } from "react";
import type { GameSessionState } from "../hooks/useGameSession";
import type { PendingInteraction } from "../types/minigames";

interface ChatPaneProps {
  messages: GameSessionState["messages"];
  loading: GameSessionState["loading"];
  pendingInteraction?: PendingInteraction | null;
  onOpenMinigame?: () => void;
}

export default function ChatPane({
  messages,
  loading,
  pendingInteraction,
  onOpenMinigame,
}: ChatPaneProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className="chat-pane">
      {messages.length === 0 && !loading && (
        <div className="chat-empty">
          <p>🎲 No messages yet. Type an action below to begin your adventure!</p>
        </div>
      )}

      {messages.map((msg, idx) => (
        <div
          key={idx}
          className={`chat-bubble ${msg.role === "user" ? "chat-user" : "chat-narrator"}`}
        >
          <div className="chat-role">
            {msg.role === "user" ? "🗡️ Player" : "📜 Narrator"}
          </div>
          <div className="chat-text">{msg.content}</div>
          {idx === messages.length - 1 &&
            msg.role === "assistant" &&
            pendingInteraction && (
              <div className="chat-actions" style={{ marginTop: "0.5rem" }}>
                <button
                  className="btn btn-primary btn-small"
                  onClick={onOpenMinigame}
                >
                  🧩 Play {pendingInteraction.minigame_id}
                </button>
              </div>
            )}
        </div>
      ))}

      {loading && (
        <div className="chat-bubble chat-narrator chat-loading">
          <div className="chat-role">📜 Narrator</div>
          <div className="chat-text">
            <span className="loading-dots">Thinking</span>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
