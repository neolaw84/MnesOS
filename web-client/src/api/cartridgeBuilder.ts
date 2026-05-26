/**
 * API client for the "I'm Feeling Lucky" builder endpoint.
 *
 * [MnesOS-260525-08] Cartridge generation from text requirements.
 */

import { getOpenRouterKey, getUserId } from "./client";

export interface GenerateCartridgeRequest {
  requirements: string;
  existing_content?: {
    bot_lore?: string;
    first_message?: string;
    prompt_directives?: string;
    yare_spec?: string;
  };
}

export interface GenerateCartridgeResponse {
  bot_lore: string;
  first_message: string;
  prompt_directives: string;
  yare_spec: string;
}

export async function generateCartridge(
  body: GenerateCartridgeRequest,
): Promise<GenerateCartridgeResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const apiKey = getOpenRouterKey();
  if (apiKey) {
    headers["X-OpenRouter-Key"] = apiKey;
  }

  const userId = getUserId();
  if (userId) {
    headers["X-User-Id"] = userId;
  }

  const response = await fetch("/api/builder/generate", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }

  return response.json() as Promise<GenerateCartridgeResponse>;
}
