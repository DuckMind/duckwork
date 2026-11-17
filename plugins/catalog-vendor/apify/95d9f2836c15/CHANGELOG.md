# Changelog

All notable changes to this project will be documented in this file.

## [0.1.5](https://github.com/DuckMind/duckwork) (2026-10-05)

### 🚀 Features

- Add actor-routing skill for Duckwork Agent ([#8](https://github.com/DuckMind/duckwork)) ([1ac1fea](https://github.com/DuckMind/duckwork)) by [@JanHranicky](https://github.com/JanHranicky)
- Web fetch ([#14](https://github.com/DuckMind/duckwork)) ([591992a](https://github.com/DuckMind/duckwork)) by [@JanHranicky](https://github.com/JanHranicky)

### 🐛 Bug Fixes

- Move dev deps out of pyproject so Duckwork can enable the plugin ([#17](https://github.com/DuckMind/duckwork)) ([d1fb3ef](https://github.com/DuckMind/duckwork)) by [@JanHranicky](https://github.com/JanHranicky)


## [0.1.4](https://github.com/DuckMind/duckwork) (2026-09-18)

### 🐛 Bug Fixes

- Marketplace insall entry point ([#9](https://github.com/DuckMind/duckwork)) ([07b2146](https://github.com/DuckMind/duckwork)) by [@JanHranicky](https://github.com/JanHranicky)


## [0.1.3](https://github.com/DuckMind/duckwork) (2026-09-17)

### 🚀 Features

- Add CONTRIBUTING.md ([#7](https://github.com/DuckMind/duckwork)) ([2e920b8](https://github.com/DuckMind/duckwork)) by [@JanHranicky](https://github.com/JanHranicky)


## [0.1.2](https://github.com/DuckMind/duckwork) (2026-09-17)

### 🚀 Features

- Introduce apify house CI  ([#5](https://github.com/DuckMind/duckwork)) ([3812d43](https://github.com/DuckMind/duckwork)) by [@JanHranicky](https://github.com/JanHranicky)
- Plugin marketplace dependencies ([#6](https://github.com/DuckMind/duckwork)) ([bd5862e](https://github.com/DuckMind/duckwork)) by [@JanHranicky](https://github.com/JanHranicky)


# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.1] - 2026-08-12

### Changed

- README: added a troubleshooting section for `duckwork plugins enable apify` failing with
  "not installed or bundled" on `duckwork-agent` versions before `0.18.1`.

## [0.1.0] - 2026-08-11

### Added

- Initial release.
- `apify_discover` tool — search the Apify Store by keyword, or fetch an Actor's input schema and README by `actor_id`.
- `apify_start` tool — fire-and-forget batch Actor runs (up to 10 per call).
- `apify_collect` tool — poll run statuses and return completed dataset results.
- `duckwork apify-setup` CLI command — prompt for (or accept via `--token`) the `APIFY_API_TOKEN` and enable the Apify toolset.
