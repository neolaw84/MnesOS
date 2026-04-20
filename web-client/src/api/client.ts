/**
 * MnesOS API client wrapper.
 *
 * Automatically attaches the BYOK OpenRouter API key and mock user ID
 * from localStorage to every request.
 *
 * Aligned with docs/design/0005 §1.
 */

import type {
  TurnRequest,
  TurnResponse,
  InjectRequest,
  InjectResponse,
  CreateSaveRequest,
  CreateSaveResponse,
  GameSave,
  HydratedStateResponse,
} from "../types";

// ---------------------------------------------------------------------------
// localStorage keys
// ---------------------------------------------------------------------------

const OPENROUTER_KEY = "mnesos_openrouter_key";
const USER_ID_KEY = "mnesos_user_id";
const INSTANCE_ID_KEY = "mnesos_instance_id";

// ---------------------------------------------------------------------------
// Key / config helpers
// ---------------------------------------------------------------------------

export function getOpenRouterKey(): string {
  return localStorage.getItem(OPENROUTER_KEY) ?? "";
}

export function setOpenRouterKey(key: string): void {
  localStorage.setItem(OPENROUTER_KEY, key);
}

export function getUserId(): string {
  return localStorage.getItem(USER_ID_KEY) ?? "";
}

export function setUserId(id: string): void {
  localStorage.setItem(USER_ID_KEY, id);
}

export function getInstanceId(): string {
  return localStorage.getItem(INSTANCE_ID_KEY) ?? "";
}

export function setInstanceId(id: string): void {
  localStorage.setItem(INSTANCE_ID_KEY, id);
}

// ---------------------------------------------------------------------------
// Base fetch wrapper
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };

  const apiKey = getOpenRouterKey();
  if (apiKey) {
    headers["X-OpenRouter-Key"] = apiKey;
  }

  const userId = getUserId();
  if (userId) {
    headers["X-User-Id"] = userId;
  }

  const response = await fetch(path, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

/** §1.1 Process Turn */
export async function processTurn(
  instanceId: string,
  body: TurnRequest,
): Promise<TurnResponse> {
  return apiFetch<TurnResponse>(
    `/api/instances/${instanceId}/turn`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

/** §1.2 Inject State */
export async function injectState(
  instanceId: string,
  body: InjectRequest,
): Promise<InjectResponse> {
  return apiFetch<InjectResponse>(
    `/api/instances/${instanceId}/inject`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

/** §1.3 Create Save */
export async function createSave(
  instanceId: string,
  body: CreateSaveRequest,
): Promise<CreateSaveResponse> {
  return apiFetch<CreateSaveResponse>(
    `/api/instances/${instanceId}/saves`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

/** List saves (non-standard — extends the API for UI) */
export async function listSaves(
  instanceId: string,
): Promise<GameSave[]> {
  return apiFetch<GameSave[]>(
    `/api/instances/${instanceId}/saves`,
    { method: "GET" },
  );
}

/** §1.4 Load Game State */
export async function getGameState(
  instanceId: string,
  turnLogId?: string,
): Promise<HydratedStateResponse> {
  const params = turnLogId ? `?turn_log_id=${turnLogId}` : "";
  return apiFetch<HydratedStateResponse>(
    `/api/instances/${instanceId}/state${params}`,
    { method: "GET" },
  );
}
