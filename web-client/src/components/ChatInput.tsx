/**
 * ChatInput — player action input box (MNS-402).
 *
 * Disables while loading (waiting for LLM response).
 * Submits on Enter or button click.
 */

import { useState } from "react";

interface ChatInputProps {
  onSend: (input: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="chat-input-bar">
      <textarea
        className="chat-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? "Waiting for narrator..." : "What do you do?"}
        disabled={disabled}
        rows={2}
      />
      <button
        className="btn btn-primary btn-send"
        onClick={handleSubmit}
        disabled={disabled || !text.trim()}
      >
        ⚔️ Act
      </button>
    </div>
  );
}
