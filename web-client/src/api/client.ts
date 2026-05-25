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
  CreateInstanceRequest,
  CreateInstanceResponse,
  CreateSaveRequest,
  CreateSaveResponse,
  GameSave,
  HydratedStateResponse,
  Cartridge,
  CartridgeVersion,
  CreateCartridgeRequest,
  UpdateCartridgeRequest,
  Persona,
  CreatePersonaRequest,
  UpdatePersonaRequest,
  GameInstanceResponse,
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
  return localStorage.getItem(USER_ID_KEY) ?? "local-user";
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

/** §1.1 Send minigame interaction result */
export async function sendInteraction(
  instanceId: string,
  interaction: import("../types/minigames").MinigameInteractionPayload,
  parentTurnId?: string | null,
): Promise<TurnResponse> {
  return apiFetch<TurnResponse>(
    `/api/instances/${instanceId}/turn`,
    {
      method: "POST",
      body: JSON.stringify({
        parent_turn_id: parentTurnId ?? null,
        interaction,
      } satisfies TurnRequest),
    },
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

/** Bootstrap Instance */
export async function createGameInstance(
  body: CreateInstanceRequest,
): Promise<CreateInstanceResponse> {
  return apiFetch<CreateInstanceResponse>(
    `/api/instances`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function listInstances(): Promise<GameInstanceResponse[]> {
  return apiFetch<GameInstanceResponse[]>(`/api/instances`, { method: "GET" });
}

export async function deleteInstance(instanceId: string): Promise<void> {
  const headers: Record<string, string> = {};
  const userId = getUserId();
  if (userId) headers["X-User-Id"] = userId;
  const response = await fetch(`/api/instances/${instanceId}`, {
    method: "DELETE",
    headers,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }
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

// ---------------------------------------------------------------------------
// Cartridge Library API
// ---------------------------------------------------------------------------

/** Create a new cartridge shell. */
export async function createCartridge(
  body: CreateCartridgeRequest,
): Promise<Cartridge> {
  return apiFetch<Cartridge>("/api/cartridges", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** List all available cartridges. */
export async function listCartridges(): Promise<Cartridge[]> {
  return apiFetch<Cartridge[]>("/api/cartridges", { method: "GET" });
}

/** Get a specific cartridge by ID. */
export async function getCartridge(cartridgeId: string): Promise<Cartridge> {
  return apiFetch<Cartridge>(`/api/cartridges/${cartridgeId}`, {
    method: "GET",
  });
}

/** Delete a cartridge (cascades to versions). */
export async function deleteCartridge(cartridgeId: string): Promise<void> {
  const headers: Record<string, string> = {};
  const userId = getUserId();
  if (userId) headers["X-User-Id"] = userId;
  const response = await fetch(`/api/cartridges/${cartridgeId}`, {
    method: "DELETE",
    headers,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }
}

/** Update a cartridge */
export async function updateCartridge(
  cartridgeId: string,
  body: UpdateCartridgeRequest,
): Promise<Cartridge> {
  return apiFetch<Cartridge>(`/api/cartridges/${cartridgeId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

/** List all versions of a cartridge. */
export async function listCartridgeVersions(
  cartridgeId: string,
): Promise<CartridgeVersion[]> {
  return apiFetch<CartridgeVersion[]>(
    `/api/cartridges/${cartridgeId}/versions`,
    { method: "GET" },
  );
}

/** Get a specific version by ID. */
export async function getCartridgeVersion(
  cartridgeId: string,
  versionId: string,
): Promise<CartridgeVersion> {
  return apiFetch<CartridgeVersion>(
    `/api/cartridges/${cartridgeId}/versions/${versionId}`,
    { method: "GET" },
  );
}

/** Save a cartridge version from builder panes (publish endpoint). */
export async function saveCartridgeVersion(
  cartridgeId: string,
  versionTag: string,
  panes: {
    first_message: string;
    prompt_directives: string;
    yare_rules: string;
    yare_type: "yaml" | "js";
    bot_lore: string;
  },
): Promise<CartridgeVersion> {
  return apiFetch<CartridgeVersion>(
    `/api/cartridges/${cartridgeId}/versions/publish`,
    {
      method: "POST",
      body: JSON.stringify({ version_tag: versionTag, ...panes }),
    },
  );
}

/** Load the latest draft for a cartridge. */
export async function loadDraft(
  cartridgeId: string,
): Promise<{
  cartridge_id: string;
  first_message: string;
  prompt_directives: string;
  yare_rules: string;
  yare_type: "yaml" | "js";
  bot_lore: string;
}> {
  return apiFetch(`/api/cartridges/${cartridgeId}/drafts/latest`, { method: "GET" });
}

/** Save/update the current draft. */
export async function saveDraft(
  cartridgeId: string,
  panes: {
    first_message: string;
    prompt_directives: string;
    yare_rules: string;
    yare_type: "yaml" | "js";
    bot_lore: string;
  },
): Promise<{
  cartridge_id: string;
  first_message: string;
  prompt_directives: string;
  yare_rules: string;
  yare_type: "yaml" | "js";
  bot_lore: string;
}> {
  return apiFetch(`/api/cartridges/${cartridgeId}/drafts`, {
    method: "PUT",
    body: JSON.stringify(panes),
  });
}

/**
 * Upload a new cartridge version.
 * Accepts either a ZIP file or individual yare/lore/directives files.
 */
export async function uploadCartridgeVersion(
  cartridgeId: string,
  versionTag: string,
  files: {
    zipFile?: File;
    yareFile?: File;
    loreFile?: File;
    directivesFile?: File;
    firstMessageFile?: File;
  },
): Promise<CartridgeVersion> {
  const formData = new FormData();
  formData.append("version_tag", versionTag);
  if (files.zipFile) {
    formData.append("zip_file", files.zipFile);
  } else {
    if (files.yareFile) formData.append("yare_file", files.yareFile);
    if (files.loreFile) formData.append("lore_file", files.loreFile);
    if (files.directivesFile)
      formData.append("directives_file", files.directivesFile);
    if (files.firstMessageFile)
      formData.append("first_message_file", files.firstMessageFile);
  }

  const headers: Record<string, string> = {};
  const apiKey = getOpenRouterKey();
  if (apiKey) headers["X-OpenRouter-Key"] = apiKey;
  const userId = getUserId();
  if (userId) headers["X-User-Id"] = userId;

  const response = await fetch(
    `/api/cartridges/${cartridgeId}/versions`,
    { method: "POST", body: formData, headers },
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }
  return response.json() as Promise<CartridgeVersion>;
}

// ---------------------------------------------------------------------------
// Persona API
// ---------------------------------------------------------------------------

export async function listPersonas(): Promise<Persona[]> {
  return apiFetch<Persona[]>("/api/personas", { method: "GET" });
}

export async function createPersona(body: CreatePersonaRequest): Promise<Persona> {
  return apiFetch<Persona>("/api/personas", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getPersona(personaId: string): Promise<Persona> {
  return apiFetch<Persona>(`/api/personas/${personaId}`, { method: "GET" });
}

export async function updatePersona(personaId: string, body: UpdatePersonaRequest): Promise<Persona> {
  return apiFetch<Persona>(`/api/personas/${personaId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function deletePersona(personaId: string): Promise<void> {
  const headers: Record<string, string> = {};
  const userId = getUserId();
  if (userId) headers["X-User-Id"] = userId;
  const response = await fetch(`/api/personas/${personaId}`, {
    method: "DELETE",
    headers,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }
}
