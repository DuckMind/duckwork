# Duckwork binary distribution

Duckwork **v0.22.10** for **macOS Apple Silicon (arm64)**. This repository contains
only the installer, distribution documentation and license. Release assets contain
the compiled CLI runtime and a Desktop app with its runtime bundled. Application
source and development Git history are not published here.

## Install CLI

```sh
curl -fsSL https://raw.githubusercontent.com/DuckMind/duckwork/main/scripts/install.sh | bash
```

No Git checkout or system Python is required. The installer verifies SHA-256 before
extracting, tests the staged runtime, preserves an existing launcher as a backup,
and installs `~/.local/bin/duckwork`. Add that directory to PATH if prompted.
Unsupported platforms stop explicitly; there is no source-download fallback.
`DUCKWORK_INSTALL_DIR` and `DUCKWORK_BIN_DIR` accept absolute custom paths.

Run `duckwork setup` for Quick Setup (Fordex Router), enter **your own** API key,
select `gpt-6-luna`, then run `duckwork`. This repository contains no API keys.

## Install Desktop

```sh
curl -fsSL https://raw.githubusercontent.com/DuckMind/duckwork/main/scripts/install.sh | bash -s -- --desktop
```

This installs the CLI and **Duckwork Agent.app** (checksum, bundle id, version and
code signature are verified before the app is copied to `/Applications`, or
`~/Applications` when `/Applications` is not writable; `--app PATH` chooses the
location). Manual alternative: download `Duckwork-<version>-mac-arm64.dmg` and
`SHA256SUMS` from the latest release, verify the checksum, open the image and copy
the app. The backend is included; first launch does not clone application source.
Connect your own Fordex Router key in onboarding.

The app is **ad-hoc signed, not Apple notarized**. Keep macOS security settings
unchanged. If macOS blocks launch, review it through normal macOS approval controls;
do not disable Gatekeeper or remove quarantine as an installation requirement.

## Packaging and updates

Python application modules are bytecode; the UI is a compiled JavaScript bundle.
These are not encryption or a promise against reverse engineering. Third-party
runtimes, permitted dependency source, licenses and notices remain included.
Only macOS arm64 is supplied in this release; Linux, Windows and Intel macOS are
not claimed as tested binary installations. Optional integrations may need their
own services and credentials.

## Upgrade

| Where | How |
|---|---|
| Terminal | `duckwork update` (`--check` only reports, `--no-desktop` skips the app) |
| Desktop | **Update** in the app's update notice (it downloads, verifies, quits, is replaced and reopens) |
| Roll back | `duckwork update --release v0.22.9` (reuses the kept release; no download) |

`duckwork update` reads the latest release, verifies that release's `install.sh`
against its `SHA256SUMS` and runs it for your current install location. The new
runtime is smoke-tested beside the old one before the launcher switches; your
profile, settings and sessions in `~/.duckwork` are not touched. Running gateway
services installed by this launcher are restarted on the new version
(`--no-gateway-restart` skips that and prints the command). A Desktop app that is
open is not replaced from the terminal — use its Update button, or quit it first.
The CLI checks for a new release at most once a day; `updates.check: false` in
`config.yaml` turns that off.

The current and previous releases are kept (`DUCKWORK_KEEP_RELEASES=2`, `0` keeps
all); only releases this installer created and nothing in use is removed. The
replaced Desktop app is kept in `~/.local/share/duckwork-binary/desktop-backups/`.
Installed **v0.22.8 or older?** Those releases have no `duckwork update` for binary
installs; run the install command above once, after which `duckwork update` works.

Versioned releases are immutable: existing files with different checksums are
rejected instead of overwritten. Do not replace the runtime by cloning source.
