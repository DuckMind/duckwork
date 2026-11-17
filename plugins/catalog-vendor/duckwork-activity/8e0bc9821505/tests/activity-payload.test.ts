import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

const repo = process.cwd();
const duckwork = process.env.DUCKWORK_BIN || "duckwork";

test("desktop year summary stays parseable below cli.exec's output cap", () => {
  const scratch = join(process.env.DUCKWORK_HOME || join(homedir(), ".duckwork"), "cache", "scratch");
  mkdirSync(scratch, { recursive: true });
  const home = mkdtempSync(join(scratch, "duckwork-activity-test-"));
  try {
    mkdirSync(join(home, "plugins"), { recursive: true });
    symlinkSync(repo, join(home, "plugins", "duckwork-activity"), "dir");
    symlinkSync(join(process.env.HOME, ".duckwork", "state.db"), join(home, "state.db"));
    writeFileSync(join(home, "config.yaml"), "plugins:\n  enabled:\n    - duckwork-activity\n");
    const env = { ...process.env, DUCKWORK_HOME: home };
    const output = execFileSync(
      duckwork,
      ["--profile", "default", "activity", "summary", "--days", "365", "--desktop", "--json"],
      { env, encoding: "utf8", maxBuffer: 1024 * 1024, timeout: 60_000 },
    );
    assert.ok(Buffer.byteLength(output) < 48_000);
    const payload = JSON.parse(output);
    assert.equal(payload.plugin_version, "0.2.2");
    assert.equal(payload.daily.length > 0, true);
    assert.ok(payload.models.length <= 8);
    assert.ok(payload.tools.length <= 8);
    assert.ok(payload.skills.top_skills.length <= 8);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});
