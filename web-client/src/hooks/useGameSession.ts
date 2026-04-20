/**
 * useGameSession — manages the core gameplay loop state.
 *
 * Tracks the chat message history, current turn ID, bot_memory,
 * loading/error states, and exposes actions (sendTurn, retry, save, load).
 */

import { useCallback, useState } from "react";
import type {
  DisplayMessage,
  TurnResponse,
  HydratedStateResponse,
} from "../types";
import {
  processTurn,
  getGameState,
  createSave,
  listSaves,
  getInstanceId,
} from "../api/client";
import type { GameSave } from "../types";

export interface GameSession {
  messages: DisplayMessage[];
  botMemory: Record<string, unknown>;
  currentTurnId: string | null;
  loading: boolean;
  error: string | null;
  saves: GameSave[];
  sendTurn: (input: string) => Promise<void>;
  retryLast: () => Promise<void>;
  saveCheckpoint: (label: string) => Promise<void>;
  loadCheckpoint: (save: GameSave) => Promise<void>;
  refreshSaves: () => Promise<void>;
  clearError: () => void;
}

export function useGameSession(): GameSession {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [botMemory, setBotMemory] = useState<Record<string, unknown>>({});
  const [currentTurnId, setCurrentTurnId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saves, setSaves] = useState<GameSave[]>([]);

  // Track the parent turn ID used for the last assistant message (for retry)
  const [lastParentTurnId, setLastParentTurnId] = useState<string | null>(null);
  const [lastUserInput, setLastUserInput] = useState<string>("");

  const clearError = useCallback(() => setError(null), []);

  // -----------------------------------------------------------------------
  // Send a new turn
  // -----------------------------------------------------------------------
  const sendTurn = useCallback(
    async (input: string) => {
      const instanceId = getInstanceId();
      if (!instanceId) {
        setError("No instance ID configured. Open Settings to configure.");
        return;
      }

      setLoading(true);
      setError(null);

      // Optimistically add the user message
      const userMsg: DisplayMessage = { role: "user", content: input };
      setMessages((prev) => [...prev, userMsg]);

      try {
        const parentId = currentTurnId;
        setLastParentTurnId(parentId);
        setLastUserInput(input);

        const result: TurnResponse = await processTurn(instanceId, {
          parent_turn_id: parentId,
          user_input: input,
        });

        const assistantMsg: DisplayMessage = {
          role: "assistant",
          content: result.narrator_response,
          turnId: result.turn_id,
        };

        setMessages((prev) => [...prev, assistantMsg]);
        setCurrentTurnId(result.turn_id);

        // Refresh bot_memory from hydrated state
        try {
          const state: HydratedStateResponse = await getGameState(
            instanceId,
            result.turn_id,
          );
          setBotMemory(state.bot_memory);
        } catch {
          // Non-fatal: the chat still works
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        // Remove the optimistic user message on error
        setMessages((prev) => prev.slice(0, -1));
      } finally {
        setLoading(false);
      }
    },
    [currentTurnId],
  );

  // -----------------------------------------------------------------------
  // Retry the last turn (like Gemini chat)
  // -----------------------------------------------------------------------
  const retryLast = useCallback(async () => {
    if (!lastUserInput) return;
    const instanceId = getInstanceId();
    if (!instanceId) return;

    setLoading(true);
    setError(null);

    // Remove the last assistant message (keep the user message)
    setMessages((prev) => {
      const copy = [...prev];
      if (copy.length > 0 && copy[copy.length - 1].role === "assistant") {
        copy.pop();
      }
      return copy;
    });

    try {
      const result: TurnResponse = await processTurn(instanceId, {
        parent_turn_id: lastParentTurnId,
        user_input: lastUserInput,
      });

      const assistantMsg: DisplayMessage = {
        role: "assistant",
        content: result.narrator_response,
        turnId: result.turn_id,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setCurrentTurnId(result.turn_id);

      try {
        const state = await getGameState(instanceId, result.turn_id);
        setBotMemory(state.bot_memory);
      } catch {
        // Non-fatal
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [lastParentTurnId, lastUserInput]);

  // -----------------------------------------------------------------------
  // Save checkpoint
  // -----------------------------------------------------------------------
  const saveCheckpoint = useCallback(
    async (label: string) => {
      const instanceId = getInstanceId();
      if (!instanceId || !currentTurnId) {
        setError("No active turn to save.");
        return;
      }
      try {
        await createSave(instanceId, {
          turn_log_id: currentTurnId,
          label,
        });
        // Refresh the saves list
        const updated = await listSaves(instanceId);
        setSaves(updated);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [currentTurnId],
  );

  // -----------------------------------------------------------------------
  // Load checkpoint
  // -----------------------------------------------------------------------
  const loadCheckpoint = useCallback(async (save: GameSave) => {
    const instanceId = getInstanceId();
    if (!instanceId) return;

    setLoading(true);
    setError(null);

    try {
      const state: HydratedStateResponse = await getGameState(
        instanceId,
        save.turn_log_id,
      );

      const displayMsgs: DisplayMessage[] = state.client_messages.map(
        (m) => ({ role: m.role, content: m.content }),
      );

      setMessages(displayMsgs);
      setBotMemory(state.bot_memory);
      setCurrentTurnId(save.turn_log_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  // -----------------------------------------------------------------------
  // Refresh saves
  // -----------------------------------------------------------------------
  const refreshSaves = useCallback(async () => {
    const instanceId = getInstanceId();
    if (!instanceId) return;
    try {
      const result = await listSaves(instanceId);
      setSaves(result);
    } catch {
      // Silent — saves panel will just be empty
    }
  }, []);

  return {
    messages,
    botMemory,
    currentTurnId,
    loading,
    error,
    saves,
    sendTurn,
    retryLast,
    saveCheckpoint,
    loadCheckpoint,
    refreshSaves,
    clearError,
  };
}
