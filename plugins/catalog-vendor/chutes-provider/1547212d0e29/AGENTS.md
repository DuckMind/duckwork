# AGENTS.md

Repository contract for human and AI contributors working on
`TheStreamCode/duckwork-chutes-provider`.

## What this project is

A standalone [Duckwork Agent](https://github.com/DuckMind/duckwork)
model-provider plugin for [Chutes](https://chutes.ai). It is a **declarative
provider profile**, not a transport. It tells Duckwork how to reach Chutes'
OpenAI-compatible API at `https://llm.chutes.ai/v1` and which models to offer,
and Duckwork' existing generic machinery does the rest.

The repository exists specifically so that Chutes-specific maintenance happens
outside the Duckwork core tree. Everything here must stay compatible with Duckwork'
public plugin surface; nothing here may require patching Duckwork.

The project is independent and unofficial. It is not affiliated with, endorsed
by, sponsored by, or approved by Chutes Global Corp or Fordex. Keep that
framing intact in every document you touch.

## Visibility and distribution

- The repository is **public** and MIT licensed.
- The distribution channel is **GitHub Releases**. The package is *not* on PyPI
  and no PyPI credentials or trusted publisher are configured. Do not attempt a
  PyPI upload, and do not add publishing workflows that imply one exists.
- Never add a license header, badge, link, statistic, or release note that you
  have not verified against the live repository or the live upstream source.

## Stack and tooling

| Item | Value |
| --- | --- |
| Language | Python, `requires-python = ">=3.11"` |
| Runtime dependencies | none, deliberately |
| Test framework | `unittest` from the standard library |
| Build backend | `setuptools>=77` via `pyproject.toml` |
| Package manager | `pip` (CI uses `python -m pip`); `uv` is fine locally but do not add a second lockfile or package manager to the repo |
| Lockfile | none, and none is needed while `dependencies = []` |
| CI | GitHub Actions, `.github/workflows/ci.yml` (3.11/3.12/3.13/3.14), plus CodeQL default setup |

There is no lint, format, or type-check step configured. Do not introduce one as
a drive-by change; the codebase is small and has a consistent internal style
(imports are grouped and sorted by module name regardless of import form).

## Repository structure

```text
__init__.py                       directory-plugin entry point; calls register() on import
duckwork_chutes_provider/__init__.py provider profile, catalog probe, register()
plugin.yaml                       Duckwork plugin manifest (name, kind, version, required env)
pyproject.toml                    packaging metadata and the duckwork_agent.model_providers entry point
CITATION.cff                      citation metadata; carries the release version
tests/test_plugin_profile.py      offline contract: profile, manifest, README, CI, version sync
tests/test_duckwork_integration.py  opt-in contract against a real Duckwork checkout
.github/workflows/ci.yml          offline matrix (3.11/3.12/3.13), Duckwork integration, wheel build
.github/workflows/dependabot-auto-merge.yml  inert today, see "Known inert configuration"
```

There are two entry points on purpose:

- `__init__.py` at the repository root serves the **directory install**
  (`$DUCKWORK_HOME/plugins/model-providers/chutes/`) and registers on import.
- `duckwork_chutes_provider:register` is the **entry-point install** declared under
  `[project.entry-points."duckwork_agent.model_providers"]`, for the pip route that
  depends on Duckwork PR #64277.

Keep both working. Removing either breaks one of the two documented install
paths.

## Commands

```bash
# Offline contract suite (no Duckwork, no API key)
python -m unittest discover -s tests -v

# Full suite including the Duckwork integration contract
DUCKWORK_SOURCE=/path/to/duckwork-agent python -m unittest discover -s tests -v

# Wheel build, exactly as CI does it
python -m pip wheel . --no-deps

# Source + wheel distribution
python -m build            # requires: python -m pip install build
```

`DUCKWORK_PYTHON` overrides the interpreter used for the integration subprocess;
point it at a virtualenv that has Duckwork and its dependencies installed.

## Anti-breaking-change rules

1. **The provider identity is frozen.** Canonical name `chutes`; aliases
   `chutes-ai` and `chutesai`. Changing or dropping any of them breaks existing
   user configurations.
2. **Environment variable names are frozen**: `CHUTES_API_KEY`,
   `CHUTES_BASE_URL`.
3. **No static concrete model IDs.** `fallback_models` intentionally holds only
   Chutes' routing aliases `default:latency` and `default:throughput`, and
   `default_aux_model` is intentionally empty. Pinning concrete model IDs was
   removed in 0.1.2 precisely because they retire; do not reintroduce them.
   Duckwork merges these curated entries with the live `/v1/models` catalog.
4. **The catalog probe must never raise.** `fetch_model_metadata` wraps
   everything in `try`/`except Exception` and returns `None` on failure. That
   blind except is deliberate: a Chutes outage or an older host must degrade to
   the routing aliases, never break the Duckwork process. Do not narrow it.
5. **Read optional `ProviderProfile` fields with `getattr`.** `models_url` and
   `default_headers` exist upstream today, but older hosts may lack them, and an
   `AttributeError` inside the probe would be silently swallowed as "no models".
6. **`fetch_models` is called with keyword arguments** by Duckwork
   (`_p.fetch_models(api_key=..., base_url=...)`). Keep the parameter names and
   keep the signature at least as permissive as the upstream base class.
7. Widening a signature or adding an attribute is safe. Removing or renaming a
   public name in `__all__` is not.

## Versioning

Semantic versioning. A version bump must update **all** of these together:

- `pyproject.toml` `version`
- `plugin.yaml` `version`
- `duckwork_chutes_provider/__init__.py` `__version__`
- `CITATION.cff` `version` and `date-released`
- the released tag in the README manual-install commands
- a new `CHANGELOG.md` section with the real release date
- `RELEASE_VERSION` and `RELEASE_DATE` in `tests/test_plugin_profile.py`

`test_release_metadata_is_consistent` fails if the version or release date drifts.

## Release procedure

`main` is protected: linear history, no force pushes, required status checks
`offline-tests (3.11)`, `offline-tests (3.14)`, `duckwork-integration`, and
`CodeQL`, enforced for administrators, plus **one approving review**.
Therefore:

1. Work on a branch, never directly on `main`.
2. Open a pull request; wait for CI and a human approval. Never self-approve and
   never use an admin bypass.
3. After the merge, tag the merge commit `vX.Y.Z` and create the GitHub Release
   from that tag.
4. The tag, `plugin.yaml`, `pyproject.toml`, `CITATION.cff`, `__version__`, and
   the changelog heading must all show the same version.

## Security rules

- Never commit, log, echo, or embed a Chutes API key, and never add one to a
  workflow, test, fixture, or example beyond the obvious `cpk_...` placeholder.
- `tests/test_plugin_profile.py` asserts that `CHUTES_API_KEY` never appears in
  the CI workflow. Keep that assertion.
- No automated test may perform paid or live inference. The catalog probe in the
  tests is stubbed; keep it stubbed.
- Outbound requests go through Duckwork' `open_credentialed_url`, which applies the
  host's URL safety checks. Do not replace it with a bare
  `urllib.request.urlopen`; that would send the bearer token to an unvalidated
  URL.
- Pin GitHub Actions by commit SHA, as `.github/workflows/ci.yml` already does.

## Documentation rules

The offline suite asserts on README content, so documentation is part of the
contract. `test_readme_documents_current_and_future_install_paths` requires the
manual install path, the reference to Duckwork PR #64277, the entry-point name,
`default:latency`, the live catalog URL, the alias guidance, the tool-calling
note, the `model.context_length` note, and the Veightor toolkit link. It also
forbids retired model IDs, the old `chutesai/chutes-agent-toolkit` link, and the
literal sequence `??` (a mojibake guard). Read that test before editing the
README.

Do not claim that `duckwork plugins install` or a pip install works in a released
Duckwork version until a canary against that release has actually passed.

## Do not modify

- `build/`, `dist/`, `*.egg-info/`, `__pycache__/`, `.pytest_cache/`,
  `.ruff_cache/` — generated, git-ignored.
- `LICENSE` and `NOTICE` — the trademark and attribution wording is deliberate.
- `.github/workflows/dependabot-auto-merge.yml` header comment — it documents
  why `pull_request_target` is used and why nothing auto-approves.

## Known inert configuration

`.github/dependabot.yml` was deliberately removed in commit `6d287d0`
("chore: stop Dependabot version-update PRs"), and Dependabot automated security
fixes are disabled on the repository. `.github/workflows/dependabot-auto-merge.yml`
therefore never fires today. It is retained because it becomes correct again the
moment Dependabot is re-enabled. Do not delete it, and do not re-add
`dependabot.yml` without the owner asking for it.

## Validation checklist before any commit

- [ ] `python -m unittest discover -s tests -v` passes
- [ ] The Duckwork integration test passes with `DUCKWORK_SOURCE` set, or CI runs it
- [ ] `python -m pip wheel . --no-deps` succeeds
- [ ] The built artifact contains no `.env`, credential, cache, or test file
- [ ] Version references are synchronized
- [ ] `CHANGELOG.md` has a real dated entry with no invented items
- [ ] No secret appears in the diff
