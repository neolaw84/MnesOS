// @vitest-environment node

import { describe, it, expect } from "vitest";
import fs from "fs/promises";
import os from "os";
import path from "path";

// @ts-ignore
import { collectMinigameManifests } from "../../../scripts/generate-minigame-schema.js";

describe("generate-minigame-schema", () => {
  it("collects manifest.json files recursively", async () => {
    const tmp = await fs.mkdtemp(path.join(os.tmpdir(), "mnesos-minigame-schema-"));
    const root = path.join(tmp, "src", "components", "minigames", "lights_out");
    await fs.mkdir(root, { recursive: true });
    await fs.writeFile(
      path.join(root, "manifest.json"),
      JSON.stringify(
        {
          minigame_id: "lights_out",
          difficulty_schema: {},
          assets_schema: {},
          events_schema: ["on_combo"],
          output_schema: {},
        },
        null,
        2,
      ),
      "utf-8",
    );

    const manifests = await collectMinigameManifests(path.join(tmp, "src", "components", "minigames"));
    expect(manifests).toHaveLength(1);
    expect(manifests[0].minigame_id).toBe("lights_out");
  });

  it("throws when a manifest is missing minigame_id", async () => {
    const tmp = await fs.mkdtemp(path.join(os.tmpdir(), "mnesos-minigame-schema-"));
    const root = path.join(tmp, "src", "components", "minigames", "bad_game");
    await fs.mkdir(root, { recursive: true });
    await fs.writeFile(path.join(root, "manifest.json"), JSON.stringify({}), "utf-8");

    await expect(
      collectMinigameManifests(path.join(tmp, "src", "components", "minigames")),
    ).rejects.toThrow("missing minigame_id");
  });
});

