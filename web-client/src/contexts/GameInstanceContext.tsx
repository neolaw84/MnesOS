/**
 * GameInstanceContext — owns active game instance state and minigame modal state.
 *
 * Responsibilities:
 *   - Tracks activeInstanceId (which game is currently being played).
 *   - Tracks minigameOpen (whether the minigame modal is open).
 *   - Exposes setters consumed by AppShell, PlayHub, ChatPane, and MinigameWrapper.
 */

import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";

interface GameInstanceContextValue {
  activeInstanceId: string | null;
  setActiveInstanceId: (id: string | null) => void;
  minigameOpen: boolean;
  setMinigameOpen: (open: boolean) => void;
}

const GameInstanceContext = createContext<GameInstanceContextValue | null>(null);

export function useGameInstance(): GameInstanceContextValue {
  const ctx = useContext(GameInstanceContext);
  if (!ctx) {
    throw new Error("useGameInstance must be used within a GameInstanceProvider");
  }
  return ctx;
}

interface GameInstanceProviderProps {
  children: ReactNode;
}

export function GameInstanceProvider({ children }: GameInstanceProviderProps) {
  const [activeInstanceId, setActiveInstanceId] = useState<string | null>(null);
  const [minigameOpen, setMinigameOpen] = useState(false);

  return (
    <GameInstanceContext.Provider
      value={{ activeInstanceId, setActiveInstanceId, minigameOpen, setMinigameOpen }}
    >
      {children}
    </GameInstanceContext.Provider>
  );
}
