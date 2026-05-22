import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AppShell from '../../components/AppShell';
import { useGameInstance } from '../../contexts/GameInstanceContext';
import { useGameSession } from '../../hooks/useGameSession';
import type { GameSession } from '../../hooks/useGameSession';

// Mock child components
vi.mock('../../components/ChatPane', () => ({ default: () => <div data-testid="chat-pane" /> }));
vi.mock('../../components/ChatInput', () => ({ default: () => <div data-testid="chat-input" /> }));
vi.mock('../../components/SettingsModal', () => ({
  default: ({ open }: { open: boolean }) => open ? <div data-testid="settings-modal" /> : null,
}));
vi.mock('../../components/StateDebugger', () => ({ default: () => <div data-testid="state-debugger" /> }));
vi.mock('../../components/SaveManager', () => ({ default: () => <div data-testid="save-manager" /> }));
vi.mock('../../components/CartridgeLibrary', () => ({ default: () => <div data-testid="cartridge-library" /> }));
vi.mock('../../components/PersonaManager', () => ({ default: () => <div data-testid="persona-manager" /> }));
vi.mock('../../components/PlayHub', () => ({ default: () => <div data-testid="play-hub" /> }));
vi.mock('../../components/StartNewGameModal', () => ({
  default: ({ onStart }: { onStart: (turnId: string | null) => void }) => (
    <div data-testid="start-new-game-modal">
      <button onClick={() => onStart('turn-1')}>start-game</button>
    </div>
  ),
}));
vi.mock('../../components/minigames/MinigameWrapper', () => ({ default: () => <div data-testid="minigame-wrapper" /> }));

// Mock context hooks
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(() => ({ authLoading: false, authError: null, clearAuthError: vi.fn() })),
}));
vi.mock('../../contexts/GameInstanceContext', () => ({
  useGameInstance: vi.fn(),
}));
vi.mock('../../hooks/useGameSession', () => ({
  useGameSession: vi.fn(),
}));
vi.mock('../../api/client', () => ({
  getInstanceId: vi.fn(() => ''),
  setInstanceId: vi.fn(),
}));

const makeSessionMock = (overrides: Partial<GameSession> = {}): GameSession => ({
  messages: [],
  botMemory: {},
  pendingInteraction: null,
  currentTurnId: null,
  loading: false,
  error: null,
  saves: [],
  sendTurn: vi.fn(),
  sendInteraction: vi.fn(),
  retryLast: vi.fn(),
  saveCheckpoint: vi.fn(),
  loadCheckpoint: vi.fn(),
  refreshSaves: vi.fn(),
  clearError: vi.fn(),
  clearSession: vi.fn(),
  resetSession: vi.fn(),
  ...overrides,
});

const makeInstanceMock = (overrides = {}) => ({
  activeInstanceId: null as string | null,
  setActiveInstanceId: vi.fn(),
  minigameOpen: false,
  setMinigameOpen: vi.fn(),
  ...overrides,
});

describe('AppShell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useGameInstance).mockReturnValue(makeInstanceMock());
    vi.mocked(useGameSession).mockReturnValue(makeSessionMock());
  });

  describe('header', () => {
    it('renders the MnesOS header title', () => {
      render(<AppShell />);
      expect(screen.getByText('🎮 MnesOS')).toBeInTheDocument();
    });

    it('renders the app subtitle', () => {
      render(<AppShell />);
      expect(screen.getByText(/Alpha/)).toBeInTheDocument();
    });

    it('shows the Settings button', () => {
      render(<AppShell />);
      expect(screen.getByRole('button', { name: '⚙️ Settings' })).toBeInTheDocument();
    });

    it('shows navigation buttons for Play, Library, and Personas', () => {
      render(<AppShell />);
      expect(screen.getByRole('button', { name: '🎮 Play' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '📚 Library' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '🎭 Personas' })).toBeInTheDocument();
    });
  });

  describe('default view', () => {
    it('shows Library view by default', () => {
      render(<AppShell />);
      expect(screen.getByTestId('cartridge-library')).toBeInTheDocument();
    });

    it('does not show play hub in library view', () => {
      render(<AppShell />);
      expect(screen.queryByTestId('play-hub')).not.toBeInTheDocument();
    });
  });

  describe('navigation', () => {
    it('switches to Personas view on click', async () => {
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎭 Personas' }));
      expect(screen.getByTestId('persona-manager')).toBeInTheDocument();
      expect(screen.queryByTestId('cartridge-library')).not.toBeInTheDocument();
    });

    it('switches to Play view on click', async () => {
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      expect(screen.getByTestId('play-hub')).toBeInTheDocument();
      expect(screen.queryByTestId('cartridge-library')).not.toBeInTheDocument();
    });

    it('switches back to Library from Play', async () => {
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      await user.click(screen.getByRole('button', { name: '📚 Library' }));
      expect(screen.getByTestId('cartridge-library')).toBeInTheDocument();
    });
  });

  describe('play view — no active instance', () => {
    it('shows PlayHub when activeInstanceId is null', async () => {
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      expect(screen.getByTestId('play-hub')).toBeInTheDocument();
      expect(screen.queryByTestId('chat-pane')).not.toBeInTheDocument();
    });
  });

  describe('play view — with active instance', () => {
    beforeEach(() => {
      vi.mocked(useGameInstance).mockReturnValue(makeInstanceMock({ activeInstanceId: 'inst-123' }));
    });

    it('shows ChatPane when activeInstanceId is set', async () => {
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      expect(screen.getByTestId('chat-pane')).toBeInTheDocument();
    });

    it('shows SaveManager in active game view', async () => {
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      expect(screen.getByTestId('save-manager')).toBeInTheDocument();
    });

    it('shows ChatInput in active game view', async () => {
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      expect(screen.getByTestId('chat-input')).toBeInTheDocument();
    });

    it('shows "← My Games" back button', async () => {
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      expect(screen.getByRole('button', { name: '← My Games' })).toBeInTheDocument();
    });

    it('"← My Games" clears active instance and session', async () => {
      const clearSession = vi.fn();
      const setActiveInstanceId = vi.fn();
      vi.mocked(useGameSession).mockReturnValue(makeSessionMock({ clearSession }));
      vi.mocked(useGameInstance).mockReturnValue(makeInstanceMock({ activeInstanceId: 'inst-123', setActiveInstanceId }));
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      await user.click(screen.getByRole('button', { name: '← My Games' }));
      expect(setActiveInstanceId).toHaveBeenCalledWith(null);
      expect(clearSession).toHaveBeenCalled();
    });
  });

  describe('session error banner', () => {
    it('shows error banner in play view when session.error is set', async () => {
      vi.mocked(useGameSession).mockReturnValue(makeSessionMock({ error: 'Something went wrong' }));
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('does not show session error in library view', () => {
      vi.mocked(useGameSession).mockReturnValue(makeSessionMock({ error: 'Hidden error' }));
      render(<AppShell />);
      expect(screen.queryByText('Hidden error')).not.toBeInTheDocument();
    });

    it('can dismiss session error by calling clearError', async () => {
      const clearError = vi.fn();
      vi.mocked(useGameSession).mockReturnValue(makeSessionMock({ error: 'Dismiss me', clearError }));
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      await user.click(screen.getByRole('button', { name: '✕' }));
      expect(clearError).toHaveBeenCalled();
    });
  });

  describe('settings modal', () => {
    it('opens settings modal when Settings button is clicked', async () => {
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '⚙️ Settings' }));
      expect(screen.getByTestId('settings-modal')).toBeInTheDocument();
    });
  });

  describe('minigame modal', () => {
    it('renders MinigameWrapper when pendingInteraction is set and minigameOpen is true', async () => {
      vi.mocked(useGameSession).mockReturnValue(
        makeSessionMock({ pendingInteraction: { minigame_id: 'LightsOut' } })
      );
      vi.mocked(useGameInstance).mockReturnValue(
        makeInstanceMock({ activeInstanceId: 'inst-123', minigameOpen: true })
      );
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      expect(screen.getByTestId('minigame-wrapper')).toBeInTheDocument();
    });

    it('does not render MinigameWrapper when minigameOpen is false', async () => {
      vi.mocked(useGameSession).mockReturnValue(
        makeSessionMock({ pendingInteraction: { minigame_id: 'LightsOut' } })
      );
      vi.mocked(useGameInstance).mockReturnValue(
        makeInstanceMock({ activeInstanceId: 'inst-123', minigameOpen: false })
      );
      const user = userEvent.setup();
      render(<AppShell />);
      await user.click(screen.getByRole('button', { name: '🎮 Play' }));
      expect(screen.queryByTestId('minigame-wrapper')).not.toBeInTheDocument();
    });
  });

  describe('mnesos-play-instance event', () => {
    it('switches to play view when mnesos-play-instance is dispatched', async () => {
      render(<AppShell />);
      // Starts in library
      expect(screen.getByTestId('cartridge-library')).toBeInTheDocument();
      act(() => {
        window.dispatchEvent(
          new CustomEvent('mnesos-play-instance', { detail: { instance_id: 'inst-1', turn_id: null } })
        );
      });
      expect(screen.getByTestId('play-hub')).toBeInTheDocument();
    });

    it('calls setActiveInstanceId with the event instance_id', () => {
      const setActiveInstanceId = vi.fn();
      vi.mocked(useGameInstance).mockReturnValue(makeInstanceMock({ setActiveInstanceId }));
      render(<AppShell />);
      act(() => {
        window.dispatchEvent(
          new CustomEvent('mnesos-play-instance', { detail: { instance_id: 'inst-event', turn_id: null } })
        );
      });
      expect(setActiveInstanceId).toHaveBeenCalledWith('inst-event');
    });

    it('calls session.resetSession when play event fires', () => {
      const resetSession = vi.fn().mockResolvedValue(undefined);
      vi.mocked(useGameSession).mockReturnValue(makeSessionMock({ resetSession }));
      render(<AppShell />);
      act(() => {
        window.dispatchEvent(
          new CustomEvent('mnesos-play-instance', { detail: { instance_id: 'inst-1', turn_id: 'turn-99' } })
        );
      });
      expect(resetSession).toHaveBeenCalledWith('turn-99');
    });
  });
});
