#!/usr/bin/env node
// Showly's static-report entrypoint. scripts/vendor/am.mjs is vendored, not
// source: read references/upstream.md before changing it.
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { spawnSync } from "node:child_process";

const usage = `Showly reports — local static HTML (Node.js 20+)
  node report.mjs render <draft.md|-> -o <index.html> [--theme auto|blueprint|shadcn|paper]
  node report.mjs patch <index.html> --panel <title> --from <panel.md>
  node report.mjs lint <draft.md|-> [--style off|80|strict]
  node report.mjs help <format|flow|sequence|tree|timeline|limits|annot|kv|callout|patch|theme>
  node report.mjs list
Rendering also accepts --template sheet|doc, --mode auto|light|dark and --style.
Files stay local; use Showly hosting to share them. Video and configuration commands
are not supported by this entrypoint. The renderer updates with Showly.`;

function main(args) {
  if (Number(process.versions.node.split(".")[0]) < 20) {
    console.error(
      "Showly reports requires Node.js 20 or newer. Hosting installation still supports Node.js 18.",
    );
    return 2;
  }
  if (!args.length || args[0] === "--help") {
    console.log(usage);
    return 0;
  }
  const { values, positionals } = parseArgs({
    args,
    allowPositionals: true,
    options: {
      out: { type: "string", short: "o" },
      "no-open": { type: "boolean" },
      theme: { type: "string" },
      template: { type: "string" },
      mode: { type: "string" },
      style: { type: "string" },
      panel: { type: "string" },
      from: { type: "string" },
    },
  });
  const [command, topic] = positionals;
  if (!["render", "patch", "lint", "help", "list"].includes(command)) {
    throw new Error(`Unsupported report command: ${command}\n${usage}`);
  }
  if (command === "help" && (!topic || topic === "video")) {
    console.log(usage);
    return topic ? 2 : 0;
  }
  // Explicit output keeps files out of the temporary upstream configuration home.
  if (command === "render" && !values.out?.trim()) {
    throw new Error(
      "render requires -o <path>, usually a dedicated report directory's index.html",
    );
  }
  if (command === "patch" && topic && topic !== "-") {
    const root = readFileSync(topic, "utf8").match(/<html\b[^>]*>/)?.[0] ?? "";
    if (/\sdata-video\b/.test(root)) {
      throw new Error(
        "Video pages cannot be patched by Showly's static report renderer.",
      );
    }
  }
  const configHome = mkdtempSync(join(tmpdir(), "showly-report-"));
  try {
    const child = spawnSync(
      process.execPath,
      [
        fileURLToPath(new URL("./vendor/am.mjs", import.meta.url)),
        ...args,
        "--no-open",
      ],
      {
        stdio: "inherit",
        env: {
          ...process.env,
          AM_HOME: configHome,
          AM_NO_OPEN: "1",
        },
      },
    );
    if (child.error) throw child.error;
    return child.status ?? 1;
  } finally {
    rmSync(configHome, { recursive: true, force: true });
  }
}

try {
  process.exitCode = main(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  process.exitCode = 2;
}
