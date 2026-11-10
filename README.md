# Duckwork binary distribution

Duckwork **v0.22.8** for **macOS Apple Silicon (arm64)**. This repository contains
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

Download `Duckwork-0.22.8-mac-arm64.dmg` and `SHA256SUMS` from release `v0.22.8`.
Verify the checksum, open the image and copy **Duckwork Agent.app** to Applications
(or your user Applications folder). The backend is included; first launch does not
clone application source. Connect your own Fordex Router key in onboarding.

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

Use a later published binary installer to update. Do not replace the runtime by
cloning source. Versioned releases are immutable: existing files with different
checksums are rejected instead of overwritten. Keep previous installations and
launcher backups until the new installation is verified.
