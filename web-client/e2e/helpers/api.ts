import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { expect, request } from "@playwright/test";

const BASE_API = "http://127.0.0.1:8000/api";

export interface SeededSmokeState {
  apiKey: string;
  userId: string;
  instanceId: string;
}

const FIXTURE_ROOT = resolve(process.cwd(), "e2e", "fixtures", "cartridge");

const SMOKE_USER_ID = "local-user";

async function createFixtureCartridgeVersion(
  apiCtx: Awaited<ReturnType<typeof request.newContext>>,
  userId: string,
): Promise<{ versionId: string }> {
  const cartridgeTitle = `E2E Fixture Cartridge ${randomUUID().slice(0, 8)}`;
  const cartridgeResponse = await apiCtx.post(`${BASE_API}/cartridges`, {
    headers: { "X-User-Id": userId, "Content-Type": "application/json" },
    data: {
      title: cartridgeTitle,
      description: "E2E smoke fixture",
      genre: "Test",
      visibility: "PUBLIC",
    },
  });

  expect(cartridgeResponse.ok()).toBe(true);
  const cartridge = await cartridgeResponse.json();

  const versionResponse = await apiCtx.post(`${BASE_API}/cartridges/${cartridge.id}/versions`, {
    headers: { "X-User-Id": userId },
    multipart: {
      version_tag: "1.0.0-e2e-smoke",
      yare_file: {
        name: "yare.yaml",
        mimeType: "text/yaml",
        buffer: readFileSync(resolve(FIXTURE_ROOT, "yare.yaml")),
      },
      lore_file: {
        name: "bot_lore.md",
        mimeType: "text/markdown",
        buffer: readFileSync(resolve(FIXTURE_ROOT, "bot_lore.md")),
      },
      directives_file: {
        name: "prompt_directives.yaml",
        mimeType: "text/yaml",
        buffer: readFileSync(resolve(FIXTURE_ROOT, "prompt_directives.yaml")),
      },
    },
  });

  expect(versionResponse.ok()).toBe(true);
  const version = await versionResponse.json();
  return { versionId: version.id as string };
}

async function createPersona(
  apiCtx: Awaited<ReturnType<typeof request.newContext>>,
  userId: string,
): Promise<{ personaId: string }> {
  const personaName = `E2E Hero ${randomUUID().slice(0, 8)}`;
  const response = await apiCtx.post(`${BASE_API}/personas`, {
    headers: { "X-User-Id": userId, "Content-Type": "application/json" },
    data: {
      name: personaName,
      pronoun_sub: "they",
      pronoun_obj: "them",
      pronoun_poss: "their",
      pronoun_poss_obj: "theirs",
      appearance: "Traveler with a weathered cloak",
      background: "Wanders from village to village",
      personality: "Calm and observant",
    },
  });

  expect(response.ok()).toBe(true);
  const persona = await response.json();
  return { personaId: persona.id as string };
}

async function createGameInstance(
  apiCtx: Awaited<ReturnType<typeof request.newContext>>,
  userId: string,
  versionId: string,
  personaId: string,
): Promise<string> {
  const response = await apiCtx.post(`${BASE_API}/instances`, {
    headers: { "X-User-Id": userId, "Content-Type": "application/json" },
    data: {
      version_id: versionId,
      persona_id: personaId,
    },
  });

  expect(response.ok()).toBe(true);
  const instance = await response.json();
  return instance.instance_id as string;
}

export async function seedSmokeSession(): Promise<SeededSmokeState> {
  const apiCtx = await request.newContext();
  try {
    const userId = SMOKE_USER_ID;
    const { versionId } = await createFixtureCartridgeVersion(apiCtx, userId);
    const { personaId } = await createPersona(apiCtx, userId);
    const instanceId = await createGameInstance(apiCtx, userId, versionId, personaId);

    return {
      apiKey: "sk-or-mock",
      userId,
      instanceId,
    };
  } finally {
    await apiCtx.dispose();
  }
}
