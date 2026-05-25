/**
 * API client for the "I'm Feeling Lucky" builder endpoint.
 *
 * [MnesOS-260525-08] Cartridge generation from text requirements.
 */

import { apiFetch } from "./client";

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
  const resp = await apiFetch("/api/builder/generate", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return resp.json();
}
