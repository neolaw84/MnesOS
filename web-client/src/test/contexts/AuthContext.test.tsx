import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, renderHook, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider, useAuth } from '../../contexts/AuthContext';
import * as pkce from '../../utils/pkce';
import * as client from '../../api/client';

vi.mock('../../utils/pkce', () => ({
  exchangeCodeForKey: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  setOpenRouterKey: vi.fn(),
  getOpenRouterKey: vi.fn(() => ''),
  getUserId: vi.fn(() => ''),
  getInstanceId: vi.fn(() => ''),
}));

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { search: '', pathname: '/' },
    });
    vi.spyOn(window.history, 'replaceState').mockImplementation(() => {});
  });

  describe('useAuth outside provider', () => {
    it('throws when used outside AuthProvider', () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
      expect(() => {
        renderHook(() => useAuth());
      }).toThrow();
      consoleError.mockRestore();
    });
  });

  describe('default state', () => {
    it('provides authLoading=false initially', () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      });
      expect(result.current.authLoading).toBe(false);
    });

    it('provides authError=null initially', () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      });
      expect(result.current.authError).toBeNull();
    });
  });

  describe('PKCE callback', () => {
    it('shows auth loading overlay when code is in URL', async () => {
      window.location.search = '?code=test_code';
      vi.mocked(pkce.exchangeCodeForKey).mockReturnValue(new Promise(() => {}));
      render(<AuthProvider><div>child</div></AuthProvider>);
      expect(screen.getByText('Authenticating with OpenRouter...')).toBeInTheDocument();
    });

    it('calls setOpenRouterKey on successful exchange', async () => {
      window.location.search = '?code=test_code';
      vi.mocked(pkce.exchangeCodeForKey).mockResolvedValueOnce('sk-new-key');
      render(<AuthProvider><div>child</div></AuthProvider>);
      await waitFor(() => {
        expect(client.setOpenRouterKey).toHaveBeenCalledWith('sk-new-key');
      });
    });

    it('cleans URL after successful exchange', async () => {
      window.location.search = '?code=test_code';
      vi.mocked(pkce.exchangeCodeForKey).mockResolvedValueOnce('sk-new-key');
      render(<AuthProvider><div>child</div></AuthProvider>);
      await waitFor(() => {
        expect(window.history.replaceState).toHaveBeenCalled();
      });
    });

    it('hides loading overlay after successful exchange', async () => {
      window.location.search = '?code=test_code';
      vi.mocked(pkce.exchangeCodeForKey).mockResolvedValueOnce('sk-new-key');
      render(<AuthProvider><div>child</div></AuthProvider>);
      await waitFor(() => {
        expect(screen.queryByText('Authenticating with OpenRouter...')).not.toBeInTheDocument();
      });
    });

    it('sets authError on failed exchange', async () => {
      window.location.search = '?code=bad_code';
      vi.mocked(pkce.exchangeCodeForKey).mockRejectedValueOnce(new Error('Exchange failed'));
      render(<AuthProvider><div>child</div></AuthProvider>);
      await waitFor(() => {
        expect(screen.getByText(/Exchange failed/)).toBeInTheDocument();
      });
    });

    it('does not trigger PKCE flow when no code in URL', () => {
      render(<AuthProvider><div>child</div></AuthProvider>);
      expect(pkce.exchangeCodeForKey).not.toHaveBeenCalled();
    });
  });

  describe('clearAuthError', () => {
    it('clears the auth error via the dismiss button', async () => {
      window.location.search = '?code=bad_code';
      vi.mocked(pkce.exchangeCodeForKey).mockRejectedValueOnce(new Error('Oops'));
      const user = userEvent.setup();
      render(<AuthProvider><div>child</div></AuthProvider>);
      await waitFor(() => screen.getByText(/Oops/));
      await user.click(screen.getByRole('button', { name: '✕' }));
      expect(screen.queryByText(/Oops/)).not.toBeInTheDocument();
    });

    it('clearAuthError hook method clears the error', async () => {
      window.location.search = '?code=bad_code';
      vi.mocked(pkce.exchangeCodeForKey).mockRejectedValueOnce(new Error('Hook error'));
      const { result } = renderHook(() => useAuth(), {
        wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
      });
      await waitFor(() => {
        expect(result.current.authError).toBe('Hook error');
      });
      act(() => {
        result.current.clearAuthError();
      });
      expect(result.current.authError).toBeNull();
    });
  });

  describe('rendering', () => {
    it('renders children', () => {
      render(<AuthProvider><div data-testid="child">Hello</div></AuthProvider>);
      expect(screen.getByTestId('child')).toBeInTheDocument();
    });

    it('does not show loading overlay when no code in URL', () => {
      render(<AuthProvider><div>child</div></AuthProvider>);
      expect(screen.queryByText('Authenticating with OpenRouter...')).not.toBeInTheDocument();
    });

    it('does not show error banner initially', () => {
      render(<AuthProvider><div>child</div></AuthProvider>);
      expect(screen.queryByRole('button', { name: '✕' })).not.toBeInTheDocument();
    });
  });
});
