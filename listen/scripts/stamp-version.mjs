#!/usr/bin/env node
/**
 * Stamps __ASSET_VERSION__ in HTML before deploy.
 * Version = YYYYMMDD-<git short sha>, falls back to timestamp if git unavailable.
 *
 * Cloudflare build command:
 *   node scripts/stamp-version.mjs && npx wrangler deploy
 */

import { execSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const webDir = join(root, "web");
const htmlFiles = ["index.html", "series.html", "play.html"];

function createVersion() {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");

  try {
    const sha = execSync("git rev-parse --short HEAD", {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"]
    }).trim();
    if (sha) return `${date}-${sha}`;
  } catch {
    /* git unavailable */
  }

  return `${date}-${Date.now().toString(36)}`;
}

const version = createVersion();

for (const file of htmlFiles) {
  const filePath = join(webDir, file);
  const content = readFileSync(filePath, "utf8");

  if (!content.includes("__ASSET_VERSION__")) {
    console.warn(`[stamp-version] skip ${file}: no __ASSET_VERSION__ placeholder`);
    continue;
  }

  writeFileSync(filePath, content.replaceAll("__ASSET_VERSION__", version), "utf8");
}

writeFileSync(
  join(webDir, "asset-version.json"),
  `${JSON.stringify({ version, stamped_at: new Date().toISOString() }, null, 2)}\n`,
  "utf8"
);

console.log(`[stamp-version] ${version}`);
