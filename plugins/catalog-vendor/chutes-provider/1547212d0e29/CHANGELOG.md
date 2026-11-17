# Changelog

All notable changes to this project are documented in this file.

## [0.1.5] - 2026-08-09

### Security

- Bound live catalog responses to 8 MiB before decoding, so a misbehaving
  endpoint cannot make the provider buffer an unbounded response.
- Stop persisting GitHub credentials in CI checkouts and enforce commit-pinned
  Actions through the offline contract.

### Changed

- Reject malformed catalog payload shapes while preserving an empty valid
  catalog and the routing-alias fallback behavior.
- Test Python 3.14 and refresh the pinned GitHub Actions and Duckwork integration
  revision to currently verified releases.
- Install the released tag by default and document `main` as a development
  checkout.
- Present the current support and distribution status before installation
  details and document the provider's relationship to Duckwork' generic
  transport.

### Added

- Regression coverage for older Duckwork provider profiles, bounded catalog
  reads, optional request metadata, and workflow pinning.
- Structured bug, compatibility, and feature-request forms with explicit
  credential-redaction guidance and a private security-reporting route.

## [0.1.4] - 2026-08-02

### Fixed

- Correct `CITATION.cff`, which still advertised version 0.1.0 and a release
  date that matched no published release.
- Read `models_url` and `default_headers` defensively in the catalog probe, so
  a Duckwork build that predates either `ProviderProfile` field returns a model
  list instead of silently swallowing an `AttributeError`.
- Match the upstream `fetch_models` signature by accepting `api_key=None`.

### Changed

- Describe `use_live_model_metadata` accurately: it is a forward-compatible
  opt-in that no released Duckwork version reads yet.
- Cover `CITATION.cff` in the release-version consistency test.
- Verify that `CHANGELOG.md` and `CITATION.cff` also carry the same real
  release date.
- Ignore `.pytest_cache/` and `.ruff_cache/` explicitly rather than relying on
  the self-ignoring caches those tools write.

### Added

- `AGENTS.md` with the repository contract for human and AI contributors.
- Verified CI, release, license, and Python-version badges plus repository
  layout, versioning, and support sections in the README.

## [0.1.3] - 2026-07-15

### Changed

- Align copyright and package author metadata with Michael Gasperini (Mikesoft).
- Clarify the project's independent, unofficial relationship with Chutes.
- Include the license and attribution notice in built distributions.
- Add contribution, security, conduct, and pull-request guidance.

## [0.1.2] - 2026-07-14

### Changed

- Filter the live Chutes catalog to models that advertise tool calling.
- Keep Chutes' `default:latency` and `default:throughput` routing aliases in the
  Duckwork model picker without pinning concrete model IDs.
- Opt in to authoritative live context metadata on compatible Duckwork builds.
- Test against a pinned Duckwork checkout and build the package in CI.
- Correct provider-alias guidance and support Windows PowerShell 5.1 installs.

## [0.1.1] - 2026-07-14

### Changed

- Point Chutes tooling documentation to the maintained Veightor toolkit.

## [0.1.0] - 2026-07-14

### Added

- Standalone Duckwork model-provider profile for Chutes.
- User-directory plugin entry point for `chutes`, `chutes-ai`, and `chutesai`.
- Live Chutes model catalog and routing aliases, without static model defaults.
- Offline profile-contract and opt-in Duckwork integration tests.
- Manual-install documentation while native standalone distribution support is pending Duckwork #64277.
