/**
 * MnesOS E2E Smoke: boot + fixture-cartridge play loop.
 *
 * Scope is intentionally minimal:
 *   1) App shell loads.
 *   2) Credentials can be saved.
 *   3) A seeded instance (created from uploaded fixture cartridge) can play 3 turns.
 *
 * The LLM path is fully mocked by `e2e/mock-openrouter.py`.
 */

import { expect, test } from "@playwright/test";
import { seedSmokeSession, type SeededSmokeState } from "./helpers/api";

let seeded: SeededSmokeState;

test.describe("Smoke - Uploaded Fixture Cartridge + Mock LLM", () => {
  test.beforeAll(async () => {
    seeded = await seedSmokeSession();
  });

  test("app shell loads and navigates", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("MnesOS")).toBeVisible();

    await page.getByRole("button", { name: /play/i }).click();
    await expect(page.getByText("Start New Game")).toBeVisible();

    await page.getByRole("button", { name: /library/i }).click();
    await expect(page.getByText("Cartridge Library")).toBeVisible();
  });

  test("settings accepts manual BYOK values", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /settings/i }).click();
    await page.getByText("Advanced: Manual API Key (BYOK)").click();
    await page.getByPlaceholder("sk-or-...").fill(seeded.apiKey);
    await page.getByPlaceholder("user-uuid").fill(seeded.userId);
    await page.getByRole("button", { name: /^save$/i }).click();

    await expect(page.getByPlaceholder("sk-or-...")).not.toBeVisible();
  });

  test("plays a few turns against the seeded fixture instance (mock LLM)", async ({ request }) => {
    const turnInputs = ["Look around the crossroads.", "Draw your weapon.", "Strike the goblin."];
    let parentTurnId: string | null = null;

    for (const input of turnInputs) {
      const response = await request.post(`/api/instances/${seeded.instanceId}/turn`, {
        headers: {
          "Content-Type": "application/json",
          "X-User-Id": seeded.userId,
          "X-OpenRouter-Key": seeded.apiKey,
        },
        data: {
          parent_turn_id: parentTurnId,
          user_input: input,
        },
      });

      expect(response.ok()).toBe(true);
      const body = await response.json();
      expect(typeof body.turn_id).toBe("string");
      expect((body.narrator_response as string).length).toBeGreaterThan(0);
      expect(body.narrator_response).toContain("Mock narrator");
      parentTurnId = body.turn_id as string;
    }
  });
});
