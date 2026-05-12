import { describe, it, expect, vi, beforeEach } from 'vitest';
import { generateCodeChallenge, initiateOpenRouterLogin, exchangeCodeForKey } from '../../utils/pkce';

describe('PKCE Utility', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  describe('generateCodeChallenge', () => {
    it('generates a 43-character code challenge and verifier', async () => {
      const { verifier, challenge } = await generateCodeChallenge();
      expect(verifier.length).toBeGreaterThanOrEqual(43);
      expect(challenge.length).toBeGreaterThanOrEqual(43);
      // Ensure url-safe base64
      expect(challenge).not.toMatch(/[+/=]/);
    });
  });

  describe('initiateOpenRouterLogin', () => {
    it('saves the verifier to sessionStorage and redirects', async () => {
      // Mock window.location.assign
      const assignMock = vi.fn();
      const originalLocation = window.location;
      delete (window as any).location;
      window.location = { ...originalLocation, assign: assignMock } as any;

      await initiateOpenRouterLogin();

      // Ensure verifier is saved
      const savedVerifier = sessionStorage.getItem('openrouter_code_verifier');
      expect(savedVerifier).toBeTruthy();

      // Ensure redirect happened with correct params
      expect(assignMock).toHaveBeenCalled();
      const redirectUrl = new URL(assignMock.mock.calls[0][0]);
      expect(redirectUrl.hostname).toBe('openrouter.ai');
      expect(redirectUrl.pathname).toBe('/auth');
      expect(redirectUrl.searchParams.get('response_type')).toBe('code');
      expect(redirectUrl.searchParams.get('code_challenge_method')).toMatch(/^(S256|plain)$/);
      expect(redirectUrl.searchParams.has('code_challenge')).toBe(true);

      // Restore window.location
      // @ts-ignore
      window.location = originalLocation;
    });
  });

  describe('exchangeCodeForKey', () => {
    it('exchanges code for key and clears verifier', async () => {
      sessionStorage.setItem('openrouter_code_verifier', 'mock_verifier');
      sessionStorage.setItem('openrouter_code_method', 'S256');
      
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({ key: 'sk-or-mock-key' })
      } as Response);

      const key = await exchangeCodeForKey('mock_code');
      
      expect(key).toBe('sk-or-mock-key');
      expect(fetchMock).toHaveBeenCalledWith('https://openrouter.ai/api/v1/auth/keys', expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: 'mock_code',
          code_verifier: 'mock_verifier',
          code_challenge_method: 'S256',
        })
      }));
      
      expect(sessionStorage.getItem('openrouter_code_verifier')).toBeNull();
      expect(sessionStorage.getItem('openrouter_code_method')).toBeNull();
    });

    it('throws error if code_verifier is missing', async () => {
      await expect(exchangeCodeForKey('mock_code')).rejects.toThrow('No code_verifier found in sessionStorage');
    });

    it('throws error on API failure', async () => {
      sessionStorage.setItem('openrouter_code_verifier', 'mock_verifier');
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        text: async () => 'Invalid code'
      } as Response);

      await expect(exchangeCodeForKey('mock_code')).rejects.toThrow('API error 400: Invalid code');
    });
  });
});
