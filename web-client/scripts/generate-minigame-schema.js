import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

function isObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function walk(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await walk(fullPath)));
    } else if (entry.isFile()) {
      files.push(fullPath);
    }
  }
  return files;
}

export async function collectMinigameManifests(minigamesRootDir) {
  let files = [];
  try {
    files = await walk(minigamesRootDir);
  } catch (err) {
    if (err && typeof err === "object" && err.code === "ENOENT") return [];
    throw err;
  }

  const manifestFiles = files
    .filter((f) => f.endsWith(`${path.sep}manifest.json`) || f.endsWith("/manifest.json"))
    .sort();

  const manifests = [];
  for (const file of manifestFiles) {
    const raw = await fs.readFile(file, "utf-8");
    const parsed = JSON.parse(raw);
    if (!isObject(parsed) || typeof parsed.minigame_id !== "string" || !parsed.minigame_id) {
      throw new Error(`Invalid minigame manifest at ${file}: missing minigame_id`);
    }
    manifests.push(parsed);
  }

  return manifests;
}

export function buildAggregatedMinigameSchema(manifests) {
  return {
    minigames: manifests,
  };
}

export async function writeAggregatedMinigameSchema({
  minigamesRootDir,
  webPublicOutPath,
  docsOutPath,
}) {
  const manifests = await collectMinigameManifests(minigamesRootDir);
  const payload = buildAggregatedMinigameSchema(manifests);
  const json = JSON.stringify(payload, null, 2) + "\n";

  await fs.mkdir(path.dirname(webPublicOutPath), { recursive: true });
  await fs.writeFile(webPublicOutPath, json, "utf-8");

  await fs.mkdir(path.dirname(docsOutPath), { recursive: true });
  await fs.writeFile(docsOutPath, json, "utf-8");
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const webClientRoot = process.cwd();
  await writeAggregatedMinigameSchema({
    minigamesRootDir: path.join(webClientRoot, "src", "components", "minigames"),
    webPublicOutPath: path.join(webClientRoot, "public", "schemas", "minigames.json"),
    docsOutPath: path.join(webClientRoot, "..", "docs", "minigames.schema.json"),
  });
}
