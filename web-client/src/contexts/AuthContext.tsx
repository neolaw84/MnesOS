/**
 * AuthContext — owns PKCE OAuth state and exposes it via useAuth().
 *
 * Responsibilities:
 *   - Detects the ?code= PKCE callback on mount and exchanges it for an API key.
 *   - Maintains authLoading and authError state.
 *   - Renders the auth loading overlay and auth error banner so App.tsx stays clean.
 */

import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { exchangeCodeForKey } from "../utils/pkce";
import { setOpenRouterKey } from "../api/client";

interface AuthContextValue {
  authLoading: boolean;
  authError: string | null;
  clearAuthError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const code = searchParams.get("code");

    if (code) {
      setAuthLoading(true);
      setAuthError(null);

      exchangeCodeForKey(code)
        .then((key) => {
          setOpenRouterKey(key);
          window.history.replaceState({}, document.title, window.location.pathname);
        })
        .catch((err: unknown) => {
          console.error("Failed to exchange code:", err);
          setAuthError(err instanceof Error ? err.message : "Auth failed");
        })
        .finally(() => {
          setAuthLoading(false);
        });
    }
  }, []);

  const clearAuthError = () => setAuthError(null);

  return (
    <AuthContext.Provider value={{ authLoading, authError, clearAuthError }}>
      {authLoading && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ textAlign: "center" }}>
            <h2>Authenticating with OpenRouter...</h2>
            <p className="modal-hint">
              Please wait while we exchange your code for an API key.
            </p>
          </div>
        </div>
      )}

      {authError && (
        <div className="error-banner">
          <span>{authError}</span>
          <button className="btn btn-small" onClick={clearAuthError}>
            ✕
          </button>
        </div>
      )}

      {children}
    </AuthContext.Provider>
  );
}
