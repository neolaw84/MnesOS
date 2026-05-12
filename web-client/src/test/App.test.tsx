import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from '../App';
import * as pkce from '../utils/pkce';
import * as client from '../api/client';

// Mock child components to simplify testing
vi.mock('../components/ChatPane', () => ({ default: () => <div data-testid="chat-pane" /> }));
vi.mock('../components/ChatInput', () => ({ default: () => <div data-testid="chat-input" /> }));
vi.mock('../components/SettingsModal', () => ({ default: () => <div data-testid="settings-modal" /> }));
vi.mock('../components/StateDebugger', () => ({ default: () => <div data-testid="state-debugger" /> }));
vi.mock('../components/SaveManager', () => ({ default: () => <div data-testid="save-manager" /> }));
vi.mock('../components/CartridgeLibrary', () => ({ default: () => <div data-testid="cartridge-library" /> }));
vi.mock('../components/PersonaManager', () => ({ default: () => <div data-testid="persona-manager" /> }));
vi.mock('../components/GameInstanceManager', () => ({ default: () => <div data-testid="game-instance-manager" /> }));
vi.mock('../components/StartNewGameModal', () => ({ default: () => <div data-testid="start-new-game-modal" /> }));

vi.mock('../utils/pkce', () => ({
  exchangeCodeForKey: vi.fn(),
}));

vi.mock('../api/client', () => ({
  getOpenRouterKey: vi.fn(() => ''),
  setOpenRouterKey: vi.fn(),
  getUserId: vi.fn(() => ''),
  getInstanceId: vi.fn(() => ''),
}));

describe('App PKCE Callback Handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset window.location
    Object.defineProperty(window, 'location', {
      writable: true,
      value: {
        search: '',
      },
    });
    // Mock history.replaceState
    vi.spyOn(window.history, 'replaceState').mockImplementation(() => {});
  });

  it('renders normally when no code is present', () => {
    render(<App />);
    expect(screen.getByText('📚 Library')).toBeInTheDocument();
    expect(pkce.exchangeCodeForKey).not.toHaveBeenCalled();
  });

  it('handles PKCE callback when code is present in URL', async () => {
    window.location.search = '?code=mock_code_123&state=optional';
    vi.mocked(pkce.exchangeCodeForKey).mockResolvedValueOnce('sk-or-new-key');

    render(<App />);

    // Should show loading state
    expect(screen.getByText('Authenticating with OpenRouter...')).toBeInTheDocument();

    await waitFor(() => {
      expect(pkce.exchangeCodeForKey).toHaveBeenCalledWith('mock_code_123');
      expect(client.setOpenRouterKey).toHaveBeenCalledWith('sk-or-new-key');
      expect(window.history.replaceState).toHaveBeenCalled();
    });

    // Loading state should disappear
    expect(screen.queryByText('Authenticating with OpenRouter...')).not.toBeInTheDocument();
  });

  it('handles PKCE exchange error gracefully', async () => {
    window.location.search = '?code=mock_code_error';
    vi.mocked(pkce.exchangeCodeForKey).mockRejectedValueOnce(new Error('Auth failed'));

    render(<App />);

    await waitFor(() => {
      expect(pkce.exchangeCodeForKey).toHaveBeenCalled();
      expect(screen.getByText(/Auth failed/)).toBeInTheDocument();
    });
  });
});
