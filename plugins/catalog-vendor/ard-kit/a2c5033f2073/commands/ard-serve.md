---
description: Serve an ARD catalog (registry on 127.0.0.1:8390 by default)
argument-hint: [catalog.json] [port]
---

Serve the ARD catalog given as `$ARGUMENTS` (first token = catalog file,
default `ai-catalog.json`; optional second token = port, default `8390`):

1. Pick the launch form this platform can actually exec:
   - **POSIX:** `ard-registry --catalog <file> --port <port>`; from a plugin
     checkout `python3 -m ard_kit.registry` or `./bin/ard-registry`, same
     arguments.
   - **Windows:** there is no `python3`. Use `bin\ard-registry.cmd` in cmd.exe
     and PowerShell, `./bin/ard-registry` in Git Bash, or
     `python -m ard_kit.registry` with `PYTHONPATH` — or the cwd — at the
     plugin root. `<file>` has to be a Windows path
     (`D:\work\ai-catalog.json`) or a UNC path
     (`\\wsl.localhost\<distro>\home\...\ai-catalog.json`): a POSIX path does
     not fail loudly there, it resolves against the current drive.

   If a token is required, pass it via `ARD_REGISTRY_TOKEN` in the environment
   — never on argv.
2. Wait for `/health` to answer, then confirm with one unauthenticated
   health check and report the bind address. The registry does not daemonize:
   the console it was started in *is* the service.
3. Preflight what was just started: `/ard-doctor` with the same catalog and
   URL. It is the only step that separates "serving" from "serving the right
   catalog".

For a deployment that outlives the shell, `systemd/ard-registry.service` is
the reference on Linux; the Windows equivalents — foreground, Task Scheduler,
NSSM — are in [`docs/windows-service.md`](../docs/windows-service.md).
