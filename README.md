# Duckwork binary distribution

Duckwork **v0.22.13**: **macOS arm64 + x64**, **Windows x64**, and **Linux x86_64**.
Release installers bundle the compiled CLI/runtime and Desktop; no application core
source or private development Git history is included. Existing separately authorized
extension catalogs remain in this repository; they are not a source-install fallback.

## Windows (Desktop + CLI)

1. Download `Duckwork-<version>-win-x64.exe` and `SHA256SUMS` from the
   [latest release](https://github.com/DuckMind/duckwork/releases/latest) and check
   the hash: `Get-FileHash .\Duckwork-<version>-win-x64.exe` must equal its line in
   `SHA256SUMS`.
2. Run the `.exe`. It installs for the current user only (no administrator rights),
   adds Start menu and desktop shortcuts for **Duckwork Agent**, and puts the
   `duckwork` command on your user PATH. Silent install: `Duckwork-<version>-win-x64.exe /S`.
3. Open a **new** terminal: `duckwork --version`, then `duckwork setup` (Fordex Router,
   your own key, `gpt-6-luna`). In Desktop, connect the key in onboarding.

The installer is **not Authenticode-signed**: Windows SmartScreen may show
"Windows protected your PC" — choose *More info → Run anyway* only for a file whose
hash you verified. Do not disable SmartScreen or Defender. Uninstall from
*Settings → Apps*; it removes the app and its PATH entry and keeps `%LOCALAPPDATA%\duckwork`
(your profile). Update with `duckwork update` (downloads the next `.exe`, verifies
it against `SHA256SUMS` and installs it silently in place) or run the newer `.exe`.

## Duckwork Crew Desktop (new)

The new **Duckwork** desktop app (your bots, sessions, plans, automations and plugins
in one window) has its own downloads in the same release, each with the Duckwork
runtime bundled — no separate CLI install is needed for it:

- macOS: `Duckwork-Crew-Desktop-<version>-mac-arm64.dmg` — open it and drag
  **Duckwork.app** to Applications. Ad-hoc signed, not Apple notarized (see the
  macOS note below).
- Windows: `Duckwork-Crew-Desktop-<version>-win-x64.exe` — installs **Duckwork** for
  the current user (no administrator rights). Not Authenticode-signed (see the
  SmartScreen note above). Needs Microsoft Edge WebView2, which Windows 10/11
  already include; the installer downloads it if it is missing.

Check each file against `SHA256SUMS` first. It runs next to **Duckwork Agent** and
uses the same Duckwork profile; connect your Fordex Router key with `duckwork setup`
(or in Duckwork Agent onboarding). Update it by installing the newer download.

## macOS

### Install CLI

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

### Install Desktop

```sh
curl -fsSL https://raw.githubusercontent.com/DuckMind/duckwork/main/scripts/install.sh | bash -s -- --desktop
```

This installs the CLI and **Duckwork Agent.app** (checksum, bundle id, version and
code signature are verified before the app is copied to `/Applications`, or
`~/Applications` when `/Applications` is not writable; `--app PATH` chooses the
location). The installer selects this Mac’s architecture. Manual alternative: download
`Duckwork-<version>-mac-arm64.dmg` (Apple Silicon) or `Duckwork-<version>-mac-x64.dmg`
(Intel) and
`SHA256SUMS` from the latest release, verify the checksum, open the image and copy
the app. The backend is included; first launch does not clone application source.
Connect your own Fordex Router key in onboarding.

The app is **ad-hoc signed, not Apple notarized**. Keep macOS security settings
unchanged. If macOS blocks launch, review it through normal macOS approval controls;
do not disable Gatekeeper or remove quarantine as an installation requirement.

## Linux (Desktop + CLI)

Download `duckwork-agent_<version>_amd64.deb` (Debian/Ubuntu) or
`duckwork-agent-<version>-1.x86_64.rpm` (RPM distributions), plus `SHA256SUMS`.
Check `sha256sum <downloaded-file>` against its exact checksum line before installation.
Use your distribution's package installer, for example:

```sh
sudo apt install ./duckwork-agent_0.22.13_amd64.deb
# On an RPM distribution, with required system libraries available:
sudo dnf install ./duckwork-agent-0.22.13-1.x86_64.rpm
```

Packages install under `/opt/duckwork-agent`, provide `duckwork` (CLI),
`duckwork-agent` (Desktop) and a desktop-menu entry. They do not enable a background
system service or remove your profile. Upgrade by installing the newer package;
Linux automatic updates are not claimed. A standalone CLI archive
`duckwork-linux-x64.tar.gz` is also available: verify, extract into a new directory,
then run `duckwork/bin/duckwork --version`.

Requirements: x86_64, **glibc 2.39 or newer**, Electron GTK/NSS/X11/GBM/ALSA system
libraries, and a working Chromium user-namespace sandbox. Do **not** add
`--no-sandbox`, change system security policy, or set a user-writable helper setuid.
Package payloads are tested on Ubuntu; RPM-native package-manager installation,
Wayland and hardware/GPU behavior are not claimed. A `.rpm` filename alone does
not imply compatibility with older RHEL/CentOS systems.

## Packaging and updates

Python application modules are bytecode; the UI is a compiled JavaScript bundle.
These are not encryption or a promise against reverse engineering. Third-party
runtimes, permitted dependency source, licenses and notices remain included.
macOS x64 is exercised with x64 binaries under Rosetta on Apple Silicon, not on
physical Intel hardware. Windows ARM64 and Linux ARM/musl are not supplied.
Windows v0.22.13 acceptance uses isolated extracted installer payloads and the actual
PATH hook on a scratch registry key; the full NSIS upgrade/uninstall lifecycle was
not repeated, to preserve existing installations. Optional integrations may need
their own services and credentials.

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
