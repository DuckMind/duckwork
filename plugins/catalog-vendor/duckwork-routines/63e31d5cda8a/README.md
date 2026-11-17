# duckwork-routines

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release: v0.1.0](https://img.shields.io/badge/release-v0.1.0-blue.svg)](../../releases/tag/v0.1.0)

> **Community plugin.** This is an independent, community-maintained plugin.
> It is not an official Fordex product and is not endorsed by them.
> It installs through the Duckwork Desktop plugin surface; review the source
> and the [security notes](#security-and-privacy) before installing.

A standalone Duckwork Desktop plugin that adds a **Routines** page at `/routines` — with a matching sidebar entry — for managing scheduled routines through the host's per-profile `cron.manage` API. Routine data stays in the Duckwork host; this package ships no separate service, database, or update mechanism.

![Cover image: the Duckwork Routines wordmark above the tagline "Scheduled jobs for recurring tasks"](docs/assets/hr-cover-04.png)

*Cover image — duckwork-routines for Duckwork Desktop.*

## Quick navigation

- [What it does](#what-it-does)
- [Screenshots](#screenshots)
- [Quick install](#quick-install)
- [Usage](#usage)
- [Requirements](#requirements)
- [Installation](#installation)
- [Upgrade](#upgrade)
- [Uninstall](#uninstall)
- [Security and privacy](#security-and-privacy)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Project layout](#project-layout)
- [License](#license)

## What it does

Manage scheduled routines for the active Duckwork profile from inside Duckwork Desktop — no separate service or dashboard.

Supported:

- View routines for the active Duckwork profile.
- Search and filter the routine list.
- Inspect the schedule and stored run instruction for each routine.
- Create a routine from a name, schedule, and prompt.
- Pause and resume existing routines.
- Use fail-closed profile routing: calls without a resolved profile route are
  rejected instead of being sent to an unintended gateway.
- Build a deterministic, auditable `desktop/plugin.js` artifact with no
  bundled runtime dependencies.

Limits:

- The current page intentionally provides no delete, edit-mutation, or run-now
  actions — the row Edit control only opens the read-only inspector.
- The routine backend exposes exactly five `cron.manage` actions — list, add,
  remove, pause, and resume — with no update and no run action.
- The inspector panel is a disabled, read-only mirror of the composer: it
  reflects the selected routine but offers no editable controls.

## Screenshots

The images below are captures of the plugin running inside Duckwork Desktop. Routine names, schedules, and prompts shown are examples.

![Routines page: a search field, All/Active/Paused filters, and routine cards showing each routine's schedule, next run, last run, and last result](docs/assets/duckwork-routines-01.png)

*Routines list — browse, search, and filter routines for the active profile.*

![Create Routine panel: an Active toggle, a Name field, a prompt field, and a Trigger set to Weekdays at 07:45](docs/assets/duckwork-routines-02.png)

*Composer — create a routine from a name, schedule, and prompt.*

![Routines page with the routine inspector open beside the list, showing the selected routine's schedule and stored instruction](docs/assets/duckwork-routines-03.png)

*Inspector — the selected routine's schedule and stored instruction, shown read-only beside the list.*

## Quick install

Install it with the Duckwork plugin manager:

```sh
duckwork plugins install crdesign8/duckwork-routines
```

That resolves this repository directly. It is marked as a custom,
unreviewed source until it is listed in the official catalog, so the
security scan runs and the install may ask you to confirm. To pin an
exact commit, add `--ref` followed by a full 40-character commit SHA.

Prefer to build it yourself? The manual path:

```sh
git clone https://github.com/DuckMind/duckwork
cd duckwork-routines
npm ci
npm run build
node scripts/install.mjs install
```

The installer copies the generated artifact to the single install location —
`<DUCKWORK_HOME>/desktop-plugins/duckwork-routines/plugin.js` (default home
`~/.duckwork`) — and verifies its SHA-256 before and after publishing:

```sh
sha256sum desktop/plugin.js \
  "$HOME/.duckwork/desktop-plugins/duckwork-routines/plugin.js"
```

The two hashes must match. The plugin is opt-in (`defaultEnabled: false`):
after installing, reload the Desktop app, go to Capabilities → Plugins, and
enable duckwork-routines. The Routines page is then available at `/routines`,
whichever profile is active. See [`docs/INSTALL.md`](docs/INSTALL.md) for the
full installation reference.

## Usage

1. Install the plugin, reload the profile, then go to Capabilities →
   Plugins and enable duckwork-routines (opt-in; it does not self-enable).
2. Open **Routines** from the sidebar, or navigate to `/routines`.
3. The page follows the active Desktop profile. It requires the host to expose
   a complete route for that profile; there is no profile picker in this view.
4. Use the list to inspect routines, then use the New routine control to submit a name,
   schedule, and prompt. The prompt is the instruction that the host will
   execute when the routine runs.
5. Use the pause/resume controls to change a routine's active state.

All list and mutation requests are scoped to the active profile. The plugin
requires a resolved route with a backend profile and fails closed when that
route is unavailable. It does not fall back to the active gateway.

## Requirements

Supported platforms: Linux is the only verified supported platform for
building, testing, and installing. Other operating systems are not yet
verified and are unsupported.

- Duckwork Desktop with a profile that exposes the plugin host and `cron.manage`.
- Node.js `>=22.18` for building and testing the repository. The floor is
  22.18 because the test suite imports TypeScript source files using native
  type stripping, which is only available from Node.js 22.18 — older
  releases cannot run `npm test`.
- Node.js `24` is recommended and is the version used by CI.
- npm (included with supported Node.js distributions).

The repository does not declare a separate minimum Duckwork Desktop release.
Verify that the Desktop host implements the plugin descriptor and
`@duckwork/plugin-sdk` surface used by the local type shim before installing.

## Installation

The supported installation path is from a checkout. The installer copies the
generated artifact into the app-level desktop-plugins root and verifies its
SHA-256 before and after publishing it.

```sh
git clone https://github.com/DuckMind/duckwork
cd duckwork-routines
npm ci
npm run build
node scripts/install.mjs install --duckwork-home="$HOME/.duckwork"
```

For a non-standard app home, pass an explicit home (or set `DUCKWORK_HOME`).
The default is `~/.duckwork`:

```sh
node scripts/install.mjs install \
  --duckwork-home="$HOME/.duckwork"
```

There is exactly one install location —
`<DUCKWORK_HOME>/desktop-plugins/duckwork-routines/plugin.js` — shared by all
profiles. The `--duckwork-home` / `DUCKWORK_HOME` precedence is documented in
[`docs/INSTALL.md`](docs/INSTALL.md).

After installation, reload the Desktop app (or trigger a runtime plugin
reload), then go to Capabilities → Plugins and enable duckwork-routines.
The plugin is opt-in (`defaultEnabled: false`) and does not self-enable.
Once enabled, the Routines page is available at `/routines`, whichever
profile is active.

### Verify the installed artifact

```sh
sha256sum desktop/plugin.js \
  "$HOME/.duckwork/desktop-plugins/duckwork-routines/plugin.js"
```

The two hashes must match.

## Upgrade

```sh
git fetch origin
git checkout main
git pull --ff-only origin main
npm ci
npm run build
node scripts/install.mjs update --duckwork-home="$HOME/.duckwork"
```

Then reload the Desktop app. The plugin has no local migration step;
routine state remains in the host's `cron.manage` backend. A differing
update keeps the replaced bytes as `plugin.js.prev` — restore them with
`node scripts/install.mjs rollback --duckwork-home="$HOME/.duckwork"`.

## Uninstall

The installer creates or updates exactly:

```text
<DUCKWORK_HOME>/desktop-plugins/duckwork-routines/plugin.js
```

Remove it (and its backup, if any), then reload the app:

```sh
node scripts/install.mjs uninstall --duckwork-home="$HOME/.duckwork"
```

or manually, remove the installed files and then the plugin directory.
Inside `~/.duckwork/desktop-plugins/duckwork-routines/`, delete `plugin.js`
and, if present, `plugin.js.prev`; then remove the
`duckwork-routines` directory itself if it is now empty. A plain directory
removal only succeeds on an empty directory, so it cannot delete
anything beyond this plugin.

Do not remove the shared `desktop-plugins` directory. Uninstalling this plugin does
not delete routines stored by the Duckwork host; manage those through the host's
own cron interface if you need to remove them.

Migrating from a pre-#14 release? Delete the old per-profile file too
(`rm "$HOME/.duckwork/profiles/default/plugins/routines/plugin.js"`) —
see [`docs/INSTALL.md`](docs/INSTALL.md) (Migration).

## Security and privacy

- The shipped artifact imports only the host-provided `@duckwork/plugin-sdk`
  and React externals. Build and test tooling is kept in `devDependencies`.
- The plugin has no standalone network client, telemetry, analytics, updater,
  or credential storage of its own.
- It reads and sends routine operations through the Desktop host's
  `cron.manage` API. The host remains responsible for authentication,
  authorization, and the data-retention policy for those routines.
- Routed requests fail closed when a profile route is missing or incomplete;
  the view never opts into the active-gateway fallback.
- Prompt and schedule values are sent to the host as part of the routine
  operation. Review them before creating a routine, especially when the host
  is connected to a shared or remote profile.
- The repository is MIT-licensed. See [`LICENSE`](LICENSE) and
  [`SECURITY.md`](SECURITY.md) for reporting instructions.

For installation details, profile-path resolution, hash verification, and
edge cases, see [`docs/INSTALL.md`](docs/INSTALL.md).

## Troubleshooting

- **`npm ci` or the build reports a Node version error:** use Node.js `24`,
  or another version satisfying both `engines.node` and the test runner's
  native TypeScript requirements.
- **`desktop/plugin.js is stale`:** run `npm run build`; never edit the
  generated file by hand.
- **`sha256 mismatch`:** re-run the installer and compare the two hashes
  again. The installer removes its temporary file on failure and uses an
  exclusive temporary name for concurrent installs.
- **`invalid duckwork-home`:** pass a non-empty `--duckwork-home` path or set
  `DUCKWORK_HOME`. The pre-#14 `--profile` / `--profile-home` flags are
  rejected — see `docs/INSTALL.md` (Migration).
- **The page is unavailable after install:** reload the Desktop app and
  confirm that the target profile has a usable route and the required
  `cron.manage` tool.
- **The route is present but operations fail closed:** the host did not
  provide a complete profile route. Check the host's profile configuration;
  do not bypass the route guard.

## Development

The editable source is `src/**/*.ts(x)`. `desktop/plugin.js` is generated and
must not be edited directly.

```sh
npm ci
npm run typecheck
npm test
npm run check
npm run build
```

`npm run check` runs the typecheck, import/allowlist and dynamic-evaluation
checks, version synchronization check, and generated-artifact freshness
check. Before opening a pull request, run all commands above and review the
staged diff. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution
workflow and [`docs/INSTALL.md`](docs/INSTALL.md) for the deeper install
reference.

## Project layout

- `src/` — TypeScript source of truth.
- `desktop/plugin.js` — deterministic generated Desktop artifact.
- `scripts/` — build, checks, and atomic installer.
- `tests/` — Node test suite and SDK/host stubs.
- `docs/INSTALL.md` — installation, upgrade, uninstall, and troubleshooting
  reference.

## License

Copyright (c) 2026 crdesign8. Released under the MIT License.
