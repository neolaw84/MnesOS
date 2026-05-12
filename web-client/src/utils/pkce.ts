/**
 * Utilities for OAuth 2.0 PKCE with OpenRouter.
 */

// Generate a random string of 43-128 characters for the code verifier
function generateRandomString(length: number): string {
  const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  const array = new Uint8Array(length);
  window.crypto.getRandomValues(array);
  return Array.from(array, (byte) => charset[byte % charset.length]).join('');
}

// Convert a string to a base64url encoded string
function base64UrlEncode(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

/**
 * Generates a PKCE code_verifier and its S256 code_challenge.
 */
export async function generateCodeChallenge(): Promise<{ verifier: string; challenge: string; method: string }> {
  const verifier = generateRandomString(43);
  
  if (typeof window !== 'undefined' && window.crypto && window.crypto.subtle) {
    try {
      const encoder = new TextEncoder();
      const data = encoder.encode(verifier);
      const hash = await window.crypto.subtle.digest('SHA-256', data);
      const challenge = base64UrlEncode(hash);
      return { verifier, challenge, method: 'S256' };
    } catch (e) {
      // Fallback below
    }
  }

  // Fallback to 'plain' method where challenge is exactly the verifier string
  return { verifier, challenge: verifier, method: 'plain' };
}

/**
 * Initiates the OpenRouter OAuth PKCE flow by redirecting the user.
 */
export async function initiateOpenRouterLogin(): Promise<void> {
  const { verifier, challenge, method } = await generateCodeChallenge();
  
  // Save verifier for the callback
  sessionStorage.setItem('openrouter_code_verifier', verifier);
  sessionStorage.setItem('openrouter_code_method', method);

  const callbackUrl = window.location.origin + window.location.pathname; // Root or current path
  
  const url = new URL('https://openrouter.ai/auth');
  url.searchParams.set('callback_url', callbackUrl);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('code_challenge', challenge);
  url.searchParams.set('code_challenge_method', method);
  
  window.location.assign(url.toString());
}

/**
 * Exchanges the callback code for an OpenRouter API key.
 * @param code The `code` query parameter returned from OpenRouter.
 * @returns The new API key.
 */
export async function exchangeCodeForKey(code: string): Promise<string> {
  const verifier = sessionStorage.getItem('openrouter_code_verifier');
  if (!verifier) {
    throw new Error('No code_verifier found in sessionStorage');
  }
  const method = sessionStorage.getItem('openrouter_code_method') || 'S256';

  const response = await fetch('https://openrouter.ai/api/v1/auth/keys', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      code,
      code_verifier: verifier,
      code_challenge_method: method,
    }),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`API error ${response.status}: ${text}`);
  }

  const data = await response.json();
  sessionStorage.removeItem('openrouter_code_verifier');
  sessionStorage.removeItem('openrouter_code_method');
  
  if (!data.key) {
    throw new Error('API response did not contain an API key');
  }
  
  return data.key;
}
