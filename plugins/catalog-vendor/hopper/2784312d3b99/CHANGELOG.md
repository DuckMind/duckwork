# Changelog

All notable user-facing changes to Hopper are documented here. Dates follow
the corresponding Git commit dates. There are no release tags in this
repository, so version headings are based on the versions recorded in the
plugin manifest.

## [1.4.0] - 2026-09-21

### Removed

- Removed the Desktop half (`desktop/plugin.js`). It decorated the
  Capabilities hub row through direct DOM mutation (row selectors, folder-icon
  removal, Agent-toggle hiding, badge injection, and a `document.body` modal),
  which is outside the plugin SDK contract. Models are now managed with the
  `manage.py` CLI or by editing `plugin-data/hopper/models.txt` directly.
- Removed the Desktop settings demo (`demo/demo.gif`) and its README section;
  the README now documents model management from the terminal on Linux,
  macOS, and Windows.

### Changed

- Dropped the `Hopper by @mykeura - ` prefix from the plugin description in
  the manifest and provider profile; attribution lives in the `maintainer`
  field (renamed from `author`).

## [1.3.0] - 2026-09-21

### Changed

- Repackaged Hopper as a unified Agent+Desktop plugin directory that installs
  with `duckwork plugins install`, as required by the Duckwork plugin catalog.
  Install by copying this directory to `~/.duckwork/plugins/hopper`; the
  `install.sh` split-installer was removed.
- No visual changes except a generic **Reset defaults** button (was
  **Reset Ling defaults**); the bundled default list is now just
  `inclusionai/ling-3.0-flash-vl:free`. Same validation, same `manage.py`
  CLI (now at `plugins/hopper/`).

## [1.2.0] - 2026-09-20

### Added

- Added a **Settings** button to the Hopper row in Duckwork Capabilities.
- Added a lazy, accessible modal for editing OpenRouter model IDs.
- Added modal focus handling and close actions for Escape, the backdrop, and
  the close button; focus returns to Settings when the modal closes.
- Added DOM-level tests for mounting, remounting, saving, validation, and modal
  keyboard/mouse behavior.

### Changed

- Moved the model editor out of the plugin row and into the modal. Selecting
  the row alone no longer opens the editor.
- Kept saving, validation, duplicate removal, comments, and **Reset Ling
  defaults** available in the new modal workflow.

## [1.1.1] - 2026-09-18

### Security

- Replaced Desktop calls using `python -c` with the installed `manage.py`
  helper, avoiding Duckwork security-guard blocks on interpreter `-c`/`-e`
  execution.
- Desktop writes now use validated UTF-8/base64 payloads through the helper, so
  model IDs are not embedded as shell syntax.

### Changed

- Removed the DeepSeek V4 Flash default while preserving user-added models;
  Hopper now ships with the three Ling defaults.
- Added helper commands for clean model-list reads and validated replacement.

## [1.1.0] - 2026-09-18

### Changed

- Split Hopper into a hidden model-provider and a standalone Desktop plugin so
  Capabilities shows a Desktop switch without an unrelated Agent switch.
- Moved the user-owned model list to `plugin-data/hopper/models.txt` and added
  migration/backup handling for the earlier OpenRouter Custom and unified
  Hopper layouts.
- Reworked the Capabilities editor as a Desktop DOM integration while keeping
  CLI/file management available.

## [1.0.0] - 2026-09-18

### Added

- Initial Hopper plugin for a user-controlled OpenRouter model catalog that
  leaves Duckwork' built-in catalog unchanged.
- Added a Desktop model editor, CLI management commands, migration from the
  `openrouter-custom` prototype, and reuse of `OPENROUTER_API_KEY`.
- Shipped the initial Ling models plus the DeepSeek V4 Flash default, which was
  removed during the 1.1.1 upgrade path.
