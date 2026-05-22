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
import type { MinigameInteractionPayload, PendingInteraction } from "../types/minigames";
import {
  processTurn,
  sendInteraction as apiSendInteraction,
  getGameState,
  createSave,
  listSaves,
  getInstanceId,
  setInstanceId,
} from "../api/client";
import type { GameSave } from "../types";

export interface GameSessionState {
  messages: DisplayMessage[];
  botMemory: Record<string, unknown>;
  pendingInteraction: PendingInteraction | null;
  currentTurnId: string | null;
  loading: boolean;
  error: string | null;
  saves: GameSave[];
}

export interface GameSessionActions {
  sendTurn: (input: string) => Promise<void>;
  sendInteraction: (payload: MinigameInteractionPayload) => Promise<void>;
  retryLast: () => Promise<void>;
  saveCheckpoint: (label: string) => Promise<void>;
  loadCheckpoint: (save: GameSave) => Promise<void>;
  refreshSaves: () => Promise<void>;
  clearError: () => void;
  clearSession: () => void;
  resetSession: (initialTurnId?: string) => Promise<void>;
}

export type GameSession = GameSessionState & GameSessionActions;

export function useGameSession(): GameSession {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [botMemory, setBotMemory] = useState<Record<string, unknown>>({});
  const [pendingInteraction, setPendingInteraction] = useState<PendingInteraction | null>(null);
  const [currentTurnId, setCurrentTurnId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saves, setSaves] = useState<GameSave[]>([]);

  // Track the parent turn ID used for the last assistant message (for retry)
  const [lastParentTurnId, setLastParentTurnId] = useState<string | null>(null);
  const [lastUserInput, setLastUserInput] = useState<string>("");

  const clearError = useCallback(() => setError(null), []);

  /** Extract `_pending_interaction` from a bot_memory dict and sync both states. */
  const applyBotMemory = useCallback((memory: Record<string, unknown>) => {
    console.log("Applying Bot Memory:", memory);
    setBotMemory(memory);
    
    const pending = memory["_pending_interaction"];

    let parsedPending: PendingInteraction | null = null;
    const isPendingObject = pending && typeof pending === "object" && !Array.isArray(pending);
    if (isPendingObject && Object.keys(pending as Record<string, unknown>).length > 0) {
      parsedPending = pending as PendingInteraction;
    } else if (pending !== undefined && pending !== null && !isPendingObject) {
      console.warn("Unexpected _pending_interaction payload type:", pending);
    }

    console.log("Final parsedPending for state:", parsedPending);
    setPendingInteraction(parsedPending);
  }, []);

  // -----------------------------------------------------------------------
  // Send a new turn
  // -----------------------------------------------------------------------
  const sendTurn = useCallback(
    async (input: string) => {
      const instanceId = getInstanceId();
      if (!instanceId) {
        setError("No active game. Start or resume a game from the dashboard.");
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
          applyBotMemory(state.bot_memory);
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
    [currentTurnId, applyBotMemory],
  );

  // -----------------------------------------------------------------------
  // Send a minigame interaction result
  // -----------------------------------------------------------------------
  const sendInteraction = useCallback(
    async (payload: MinigameInteractionPayload) => {
      const instanceId = getInstanceId();
      if (!instanceId) {
        setError("No active game. Start or resume a game from the dashboard.");
        return;
      }

      setLoading(true);
      setError(null);

      // Record the minigame interaction in the chat history
      const hookTextSection = payload.triggered_hooks && payload.triggered_hooks.length > 0
        ? "\n" + payload.triggered_hooks.map((txt) => `"${txt}"`).join("\n")
        : "";

      const metricsStr = Object.entries(payload.metrics || {})
        .map(([k, v]) => `${k}=${v}`)
        .join(", ");
      const interactionMsg: DisplayMessage = {
        role: "user",
        content: `[minigame:${payload.minigame_id} status=${payload.status}${metricsStr ? " " + metricsStr : ""}]${hookTextSection}`,
      };
      setMessages((prev) => [...prev, interactionMsg]);

      try {
        const result: TurnResponse = await apiSendInteraction(
          instanceId,
          payload,
          currentTurnId,
        );
        
        // Optimistically clear the interaction so the overlay disappears immediately
        setPendingInteraction(null);

        const assistantMsg: DisplayMessage = {
          role: "assistant",
          content: result.narrator_response,
          turnId: result.turn_id,
        };

        setMessages((prev) => [...prev, assistantMsg]);
        setCurrentTurnId(result.turn_id);

        // Refresh bot_memory — clears _pending_interaction server-side
        try {
          const state: HydratedStateResponse = await getGameState(
            instanceId,
            result.turn_id,
          );
          applyBotMemory(state.bot_memory);
        } catch {
          // Non-fatal
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        // Clear interaction on error too, otherwise the overlay gets stuck
        setPendingInteraction(null);
      } finally {
        setLoading(false);
      }
    },
    [currentTurnId, applyBotMemory],
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
        applyBotMemory(state.bot_memory);
      } catch {
        // Non-fatal
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [lastParentTurnId, lastUserInput, applyBotMemory]);

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
      applyBotMemory(state.bot_memory);
      setCurrentTurnId(state.current_turn_id ?? save.turn_log_id);
      if (state.last_user_input) {
        setLastUserInput(state.last_user_input);
        setLastParentTurnId(state.last_parent_turn_id ?? null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [applyBotMemory]);

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

  // -----------------------------------------------------------------------
  // Reset session
  // -----------------------------------------------------------------------
  const resetSession = useCallback(async (initialTurnId?: string | null) => {
    const instanceId = getInstanceId();
    if (instanceId) {
      setLoading(true);
      try {
        const state: HydratedStateResponse = await getGameState(
          instanceId,
          initialTurnId || undefined,
        );
        const displayMsgs: DisplayMessage[] = state.client_messages.map(
          (m) => ({ role: m.role as "user" | "assistant", content: m.content, turnId: m.role === "assistant" ? initialTurnId || undefined : undefined }),
        );
        setMessages(displayMsgs);
        applyBotMemory(state.bot_memory);
        setCurrentTurnId(state.current_turn_id ?? initialTurnId ?? null);
        if (state.last_user_input) {
          setLastUserInput(state.last_user_input);
          setLastParentTurnId(state.last_parent_turn_id ?? null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        // Clear interaction on error too, otherwise the overlay gets stuck
        setPendingInteraction(null);
      } finally {
        setLoading(false);
      }
    } else {
      setMessages([]);
      setBotMemory({});
      setPendingInteraction(null);
      setCurrentTurnId(null);
      setLoading(false);
      setError(null);
      setSaves([]);
      setLastParentTurnId(null);
      setLastUserInput("");
    }
  }, [applyBotMemory]);

  // -----------------------------------------------------------------------
  // Clear session
  // -----------------------------------------------------------------------
  const clearSession = useCallback(() => {
    setMessages([]);
    setBotMemory({});
    setPendingInteraction(null);
    setCurrentTurnId(null);
    setLoading(false);
    setError(null);
    setSaves([]);
    setLastParentTurnId(null);
    setLastUserInput("");
    setInstanceId("");
  }, []);

  return {
    messages,
    botMemory,
    pendingInteraction,
    currentTurnId,
    loading,
    error,
    saves,
    sendTurn,
    sendInteraction,
    retryLast,
    saveCheckpoint,
    loadCheckpoint,
    refreshSaves,
    clearError,
    clearSession,
    resetSession,
  };
}
