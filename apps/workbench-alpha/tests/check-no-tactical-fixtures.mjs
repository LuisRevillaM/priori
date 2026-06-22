import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const appRoot = resolve(new URL("..", import.meta.url).pathname);
const sourceRoot = join(appRoot, "src");

function walk(dir) {
  const entries = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const stat = statSync(path);
    if (stat.isDirectory()) {
      entries.push(...walk(path));
    } else if (/\.(ts|tsx|js|jsx|css|html)$/.test(name)) {
      entries.push(path);
    }
  }
  return entries;
}

const checks = [
  {
    name: "hardcoded runtime handles",
    pattern: /\b(?:result|exec|replay|bound|draft|auth)_[0-9a-f]{16}\b/g
  },
  {
    name: "hardcoded IDSSE match IDs",
    pattern: /["'`][A-Z0-9]{6}["'`]/g
  },
  {
    name: "hardcoded match timestamps",
    pattern: /\b(?:approximate_time_ms|resolved_match_time_ms|absolute_frame_time_ms)\s*:\s*(?!0\b)\d{4,}/g
  },
  {
    name: "hardcoded player coordinates",
    pattern: /\b[xy]_m\s*:\s*-?\d+(?:\.\d+)?/g
  },
  {
    name: "canned replay frames",
    pattern: /\bframes\s*:\s*\[[\s\S]*?\bentities\s*:/g
  },
  {
    name: "hidden fallback tactical moments",
    pattern: /\b(?:anchor_frame_id|frame_id|match_time_ms)\s*:\s*\d{2,}/g
  }
];

const files = walk(sourceRoot);
const violations = [];
const sourceHashes = {};

for (const file of files) {
  const content = readFileSync(file, "utf8");
  const rel = relative(appRoot, file);
  sourceHashes[rel] = createHash("sha256").update(content).digest("hex");
  for (const check of checks) {
    const matches = [...content.matchAll(check.pattern)];
    for (const match of matches) {
      const prefix = content.slice(0, match.index ?? 0);
      const line = prefix.split("\n").length;
      violations.push({
        check: check.name,
        file: rel,
        line,
        match: match[0]
      });
    }
  }
}

const report = {
  ok: violations.length === 0,
  scanned_files: files.map((file) => relative(appRoot, file)).sort(),
  source_hashes: sourceHashes,
  checks: checks.map((check) => check.name),
  violations
};

console.log(JSON.stringify(report, null, 2));

if (violations.length > 0) {
  process.exitCode = 1;
}
