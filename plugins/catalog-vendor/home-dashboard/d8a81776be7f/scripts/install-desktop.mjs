#!/usr/bin/env node

import { access, lstat, mkdir, realpath, rename, symlink } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN_ID = "home-dashboard";

export function defaultDuckworkHome(env = process.env, platform = process.platform) {
  if (env.DUCKWORK_HOME) return path.resolve(env.DUCKWORK_HOME);
  if (platform === "win32" && env.LOCALAPPDATA) return path.join(env.LOCALAPPDATA, "duckwork");
  return path.join(os.homedir(), ".duckwork");
}

export async function installDesktopPlugin({
  repoRoot,
  duckworkHome = defaultDuckworkHome(),
  platform = process.platform,
}) {
  const source = path.resolve(repoRoot, "desktop");
  const destination = path.resolve(duckworkHome, "desktop-plugins", PLUGIN_ID);

  await access(path.join(source, "plugin.js"));
  await mkdir(path.dirname(destination), { recursive: true });

  let backup;
  try {
    const current = await lstat(destination);
    if (current.isSymbolicLink()) {
      try {
        if (await realpath(destination) === await realpath(source)) {
          return { status: "already-linked", source, destination };
        }
      } catch {
        // A broken or unreadable link is still preserved below.
      }
    }

    const stamp = new Date().toISOString().replaceAll(":", "-").replaceAll(".", "-");
    backup = `${destination}.backup-${stamp}`;
    await rename(destination, backup);
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }

  await symlink(source, destination, platform === "win32" ? "junction" : "dir");

  return { status: "linked", source, destination, backup };
}

const scriptPath = fileURLToPath(import.meta.url);
if (process.argv[1] && path.resolve(process.argv[1]) === scriptPath) {
  const repoRoot = path.resolve(path.dirname(scriptPath), "..");
  installDesktopPlugin({ repoRoot })
    .then(({ destination, backup, status }) => {
      process.stdout.write(
        status === "already-linked"
          ? `Home Desktop is already linked at ${destination}\n`
          : `Home Desktop linked at ${destination}\n`,
      );
      if (backup) process.stdout.write(`Previous manual copy preserved at ${backup}\n`);
      process.stdout.write("In Duckwork Desktop run Ctrl/Cmd+K → Reload desktop plugins.\n");
    })
    .catch((error) => {
      process.stderr.write(`Could not install Home Desktop: ${error.message}\n`);
      process.exitCode = 1;
    });
}
