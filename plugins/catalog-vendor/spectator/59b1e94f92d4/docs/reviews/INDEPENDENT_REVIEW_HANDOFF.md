# Spectator 0.2.0 — independent review handoff

> Give this file, unchanged, to a fresh terminal-capable reviewer agent. The reviewer must have no context from the implementation session.
>
> This is a read-only review. Assume every producer claim is wrong until independently reproduced. A failed command is evidence. Do not repair the candidate during review.

## 1. Objective and authority

Independently decide whether the frozen Spectator 0.2.0 engineering candidate is fit to:

1. merge into the canonical repository;
2. serve as the source of a release wheel; and
3. proceed to a separately approved installation/deployment decision.

The review must assess correctness, security, privacy, harness neutrality, packaging, runtime behaviour, integration honesty, regression risk and release-document accuracy.

The reviewer owns the verdict. The producer's `CONDITIONAL`, `LOW risk`, test counts and review records are claims, not approval. The reviewer may return only:

- `READY`
- `NEEDS CORRECTION`
- `NOT READY`

A `READY` verdict applies only to the exact frozen code commit below. It does not authorise commit/push, publication, installation, migration, restart or deployment.

## 2. Frozen candidate and materials

### Review repository

- Review clone: `/tmp/spectator-independent-review-20260826.pfNtvk/repo`
- Branch: `rebuild/harness-neutral-core`
- Original baseline: `a802c7b58fb37450c629720c2466ab4c45cf5fb7`
- Frozen code/evidence commit: `91f82ba369ffd8e35155c17cb0db7eb5e13a3ce7`
- Expected review HEAD: any descendant of the frozen commit whose delta touches only `docs/reviews/INDEPENDENT_REVIEW_HANDOFF.md`
- Canonical mutable workspace, provenance only: `/home/kensei/.duckwork/kanban/workspaces/t_169a8919/duckwork-spectator`

Review the disposable clone, not the mutable canonical workspace. The local snapshot commit exists only to freeze the independent-review target. It has not been pushed and is not a release commit.

### Release artefact

- Provided wheel: `/tmp/spectator-independent-review-20260826.pfNtvk/artifacts/duckwork_spectator-0.2.0-py3-none-any.whl`
- Expected SHA-256: `809d0a49aab0fddea4cbbb4d6f2b6a13b49d2bfecd35a38d93b1fbc60a42773f`
- Expected size: 75,541 bytes
- Producer comparison record: `/tmp/spectator-independent-review-20260826.pfNtvk/artifacts/wheel-source-comparison.json`
- Comparison-record SHA-256: `efa93c6dae801922f9cf6f6ae5f4385d561a9eef61be1b7aa7eaf07ecd27d0bb`

### Runtime probe

- Probe: `/tmp/spectator-independent-review-20260826.pfNtvk/materials/spectator_live_probe.py`
- Expected SHA-256: `4d4732aadc20d69dbecd658080fca32ffd8b93076d114297fa93ebedd874c3f7`
- Expected size: 6,690 bytes

Inspect the probe before running it. It binds only to loopback, uses disposable state, creates no external account and does not publish anything.

### Producer evidence records — untrusted until reproduced

- `docs/REBUILD.md`
- `docs/reviews/SECURITY_REVIEW.md`
- `docs/reviews/HERMAGUARD_REBUILD.md`
- `docs/reviews/HERMAGUARD_REBUILD.json`
- `docs/reviews/RELEASE_GATE.md`

If any `/tmp` material has disappeared, record it as a `GAP`. Do not substitute a different artefact and pretend it is the reviewed one.

## 3. Delivered scope to examine

The candidate claims to provide:

1. a harness-neutral core with no harness-specific imports;
2. a live, privacy-safe session event stream;
3. continuously updated summary entries;
4. read-only queries against the exact committed branch snapshot;
5. authenticated HTTP and WebSocket guest transport;
6. approval-gated guest suggestions;
7. native Duckwork and portable bridge adapters;
8. integration templates for Claude Code, Codex, Command Code, OpenCode and Pi;
9. an installable Python wheel and Duckwork plugin entry point;
10. profile-local private runtime state and actionable degraded responses.

The functional three-view guest frontend is in scope for correctness, security, accessibility basics and API integration. A full visual redesign is explicitly out of scope and must not be invented during this review.

## 4. Locked decisions and boundaries

Do not re-open these as implementation tasks during review:

- Canonical plugin name: `spectator`.
- Version: `0.2.0`.
- Licence: MIT.
- `spectator.core` must remain harness-neutral.
- Harness-specific behaviour belongs in adapters or bridge integrations.
- Suggestion injection may be exposed only when a configured native context can accept it.
- Runtime state defaults to `$DUCKWORK_HOME/data/spectator`, not the plugin-source directory.
- Fresh profile-local state may invalidate legacy invite URLs because it creates a new host secret.
- UI/UX redesign is deferred.
- Build, merge, push, publish, install, migrate and deploy are separate Sahil approval gates.

Do not modify source, tests, docs, Git refs, live Duckwork configuration, credentials, legacy state or permissions. Temporary virtual environments, build directories, runtime state and review outputs under `/tmp` are allowed.

Do not log in to external harnesses, rotate credentials, request secrets, launch a GUI, install into live Duckwork, start a gateway, push a branch or publish a package.

## 5. Known open issues and questions register

Treat these as starting hypotheses, not accepted conclusions.

| ID | Class | Current producer status | Independent decision required |
|---|---|---|---|
| P1-01 | Gate | Independent review has not occurred | This review must own the verdict for the frozen commit |
| P1-02 | Verification recipe | Duckwork auto-detection chooses `uvicorn main:app`, which is not Spectator's app | Decide whether the missing saved verification manifest is a release-blocking project defect |
| P1-03 | Test dependency | Fresh `.[dev]` install passes 291 tests but emits a Starlette warning recommending `httpx2`; producer's no-warning run used an augmented disposable environment | Reproduce and classify; do not silently install around it before recording initial evidence |
| P1-04 | Legacy state | Existing live legacy parent is `0777`, legacy directory `0755`, DB `0644`, host secret `0600` | Recommend fresh state versus an explicit migration/permission repair; do not change it |
| P2-01 | Harness proof | OpenCode, Pi and Claude lifecycle hooks ran but assistant turns were blocked by provider/login state | Decide whether lifecycle/conformance proof is sufficient for 0.2.0's support claim |
| P2-02 | Harness proof | Command Code CLI/settings were inspected, but authentication blocked hook execution | Decide whether this must block release or remain a documented optional-integration gap |
| P2-03 | Review tooling | Hermaguard companion CLIs are not installed | Compensate with available scanners/manual review and report the residual assurance gap |
| R-01 | Artefact provenance | Producer reports 38 packaged source files byte-identical to the frozen source and 43 wheel entries | Reproduce independently; do not trust the comparison JSON |
| R-02 | Historical docs | Producer review docs describe an earlier dirty-worktree count and timing | Check active claims for staleness or contradiction against the frozen snapshot |
| Q-01 | Deferred scope | Full visual redesign is not built | Confirm it is honestly deferred, not required for core engineering approval |

No P0 defect is currently declared. That is not proof that none exists.

## 6. State verification — run first

```bash
export REVIEW_ROOT=/tmp/spectator-independent-review-20260826.pfNtvk
export REPO="$REVIEW_ROOT/repo"
export BASE_SHA=a802c7b58fb37450c629720c2466ab4c45cf5fb7
export CODE_FINAL_SHA=91f82ba369ffd8e35155c17cb0db7eb5e13a3ce7
export PROVIDED_WHEEL="$REVIEW_ROOT/artifacts/duckwork_spectator-0.2.0-py3-none-any.whl"
export LIVE_PROBE="$REVIEW_ROOT/materials/spectator_live_probe.py"

cd "$REPO"
git status --short
git branch --show-current
git rev-parse HEAD
git merge-base --is-ancestor "$CODE_FINAL_SHA" HEAD && echo 'code ancestry: OK'
git diff --name-only "$CODE_FINAL_SHA"..HEAD
git merge-base --is-ancestor "$BASE_SHA" "$CODE_FINAL_SHA" && echo 'baseline ancestry: OK'
git diff --shortstat "$BASE_SHA".."$CODE_FINAL_SHA"
git diff --check "$BASE_SHA"..HEAD
```

Expected:

- `git status --short`: empty.
- Branch: `rebuild/harness-neutral-core`.
- Code ancestry and baseline ancestry: `OK`.
- `CODE_FINAL_SHA..HEAD`: only `docs/reviews/INDEPENDENT_REVIEW_HANDOFF.md`.
- Baseline to code-final: `58 files changed, 4370 insertions(+), 1185 deletions(-)`.
- `git diff --check`: exit 0.

If state differs, stop. Report a moving or unverifiable candidate. Do not review a substitute tree.

Verify supplied material identities:

```bash
printf '%s  %s\n' \
  809d0a49aab0fddea4cbbb4d6f2b6a13b49d2bfecd35a38d93b1fbc60a42773f \
  "$PROVIDED_WHEEL" | sha256sum -c -
printf '%s  %s\n' \
  4d4732aadc20d69dbecd658080fca32ffd8b93076d114297fa93ebedd874c3f7 \
  "$LIVE_PROBE" | sha256sum -c -
printf '%s  %s\n' \
  efa93c6dae801922f9cf6f6ae5f4385d561a9eef61be1b7aa7eaf07ecd27d0bb \
  "$REVIEW_ROOT/artifacts/wheel-source-comparison.json" | sha256sum -c -
```

## 7. Independent verification protocol

### A. Fresh declared-development environment

Do not use the producer's existing virtual environments for the primary test claim.

```bash
export AUDIT_ROOT="$(mktemp -d /tmp/spectator-independent-audit.XXXXXX)"
export DEV_VENV="$AUDIT_ROOT/dev-venv"
uv venv --seed "$DEV_VENV" --python python3
cd "$REPO"
uv pip install --python "$DEV_VENV/bin/python" -e '.[dev]'
PYTHONDONTWRITEBYTECODE=1 "$DEV_VENV/bin/python" -m pytest \
  --collect-only -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 "$DEV_VENV/bin/python" -m pytest \
  -q -p no:cacheprovider
```

Producer-observed reference, not an entitlement:

- Python 3.13.14.
- 291 tests collected.
- 291 passed in roughly 26 seconds.
- One `StarletteDeprecationWarning`: `httpx` support is deprecated in favour of `httpx2`.

Record the warning. Judge whether dependencies or documentation need correction. If the declared environment fails, that is a finding. Only after recording the initial result may you use a second disposable environment to test a proposed dependency diagnosis.

The producer's canonical environment was Python 3.11.15 at `/home/kensei/repos/KenseiAgent/.venv/bin/python` and also passed 291 tests. That is secondary evidence only.

### B. Static, type and security gates

```bash
cd "$REPO"
uvx ruff check src dashboard tests demo.py
uvx --with pydantic --with fastapi --with PyYAML \
  mypy --explicit-package-bases --ignore-missing-imports \
  src/spectator dashboard/plugin_api.py
uvx bandit -q -r src dashboard -ll
uvx semgrep scan --config p/security-audit --error --quiet \
  src dashboard __init__.py demo.py
uvx detect-secrets scan src dashboard __init__.py demo.py
git diff --check "$BASE_SHA"..HEAD
git status --short
```

Producer-observed reference:

- Ruff passed.
- mypy reported no issues in 30 source files.
- Bandit reported no medium/high findings.
- Semgrep exited 0.
- detect-secrets exited 0 with no findings.
- Final Git status remained clean in the frozen clone.

If a scanner cannot run because of network/tool availability, report the exact gap. Do not convert an unrun lane into a pass.

### C. Focused adversarial regressions

Run at least these exact tests separately, then inspect whether they genuinely exercise the claimed seam:

```bash
PYTHONDONTWRITEBYTECODE=1 "$DEV_VENV/bin/python" -m pytest -q -p no:cacheprovider \
  tests/test_c01_scaffold.py::TestSchemaCreation::test_runtime_storage_permissions_are_private \
  tests/test_c01_scaffold.py::TestSchemaCreation::test_runtime_storage_rejects_world_writable_non_sticky_parent \
  tests/test_c01_scaffold.py::TestConfigPrecedence::test_default_runtime_paths_honor_duckwork_home_and_separate_plugin_source \
  tests/test_c01_scaffold.py::TestHostRealisticIntegration::test_lazy_init_unsafe_storage_parent_degrades_to_503 \
  tests/test_rebuild_portable.py::test_branch_query_excludes_secret_files_untracked_files_and_redacts_inline_values \
  tests/test_bridge_hooks.py::test_hook_transport_rejects_non_http_urls_before_opening_them \
  tests/test_integration_templates.py::test_codex_session_end_hook_is_synchronous \
  tests/test_c06_p7_structural.py::TestP7ZeroDuckworkImports::test_zero_duckwork_imports
```

Then review the changed source adversarially. At minimum cover:

- host and guest authentication boundaries;
- cross-guest and cross-session authorisation;
- invite expiry/revocation and token handling;
- raw-content, path and credential leakage;
- branch-root/commit validation, symlinks, untracked files and secret-file exclusions;
- SQL parameterisation and transaction/partial-write behaviour;
- concurrent suggestion approval, cancellation and retry identity;
- WebSocket auth-first flow, revocation and cursor reset;
- resource limits and unbounded input/query/event paths;
- degraded-state error exposure and observability;
- unsafe parent, ownership, symlink and permission handling;
- XSS or unsafe dynamic HTML sinks in `guest.html`;
- hook URL scheme validation and SSRF boundaries;
- adapter capability honesty and false-success paths;
- rollback safety after the runtime-state path change.

For every finding, provide a concrete trigger, exact file/line, impact, reproducible evidence and a specific correction. Do not fabricate low-value findings to fill a quota.

### D. Wheel/source consistency and package contents

First verify the provided wheel directly:

```bash
sha256sum "$PROVIDED_WHEEL"
python3 - "$REPO" "$PROVIDED_WHEEL" <<'PY'
import sys, zipfile
from pathlib import Path
repo = Path(sys.argv[1])
wheel = Path(sys.argv[2])
compared = []
mismatches = []
unmapped = []
with zipfile.ZipFile(wheel) as z:
    names = sorted(z.namelist())
    for name in names:
        if name.endswith('/') or '.dist-info/' in name:
            continue
        if name.startswith('spectator/'):
            source = repo / 'src' / name
        elif name.startswith('dashboard/'):
            source = repo / name
        elif name == 'spectator_plugin.py':
            source = repo / '__init__.py'
        else:
            unmapped.append(name)
            continue
        compared.append(name)
        if not source.is_file() or z.read(name) != source.read_bytes():
            mismatches.append((name, str(source)))
print({'entries': len(names), 'compared': len(compared),
       'mismatches': mismatches, 'unmapped': unmapped})
assert len(names) == 43
assert len(compared) == 38
assert not mismatches
assert not unmapped
PY
```

Expected producer claim: 43 entries, 38 source payloads compared, no mismatches and no unmapped non-metadata entries.

Now rebuild independently into a temporary directory. Wheel archive hashes may differ because of build metadata/timestamps; compare payload bytes and metadata semantics rather than demanding an identical archive hash.

```bash
export BUILD_DIR="$AUDIT_ROOT/build"
mkdir -p "$BUILD_DIR"
cd "$REPO"
uv build --wheel --out-dir "$BUILD_DIR"
find "$BUILD_DIR" -maxdepth 1 -type f -name '*.whl' -print
```

Inspect both wheels for:

- version `0.2.0`;
- 43 expected entries;
- no tests, `.env`, auth data, host secrets or machine-specific paths;
- `spectator.duckwork_plugin` Duckwork entry point;
- console scripts `spectator-hook`, `spectator-integrations`, `spectator-serve`;
- `websockets>=12.0` runtime dependency;
- all five external integration templates.

### E. Fresh wheel installation, dependency audit and entry points

```bash
export WHEEL_VENV="$AUDIT_ROOT/wheel-venv"
uv venv --seed "$WHEEL_VENV" --python python3
uv pip install --python "$WHEEL_VENV/bin/python" "$PROVIDED_WHEEL"
"$WHEEL_VENV/bin/python" - <<'PY'
import importlib.metadata as m
from pathlib import Path
import sys
entry = [e for e in m.entry_points(group='duckwork_agent.plugins')
         if e.name == 'spectator']
assert len(entry) == 1
module = entry[0].load()
scripts = [Path(sys.executable).with_name(n) for n in
           ('spectator-hook', 'spectator-integrations', 'spectator-serve')]
print({'version': m.version('duckwork-spectator'),
       'plugin_module': module.__name__,
       'has_register': hasattr(module, 'register'),
       'scripts': {p.name: p.is_file() for p in scripts}})
assert m.version('duckwork-spectator') == '0.2.0'
assert module.__name__ == 'spectator.duckwork_plugin'
assert hasattr(module, 'register')
assert all(p.is_file() for p in scripts)
PY
"$WHEEL_VENV/bin/spectator-hook" --help >/dev/null
"$WHEEL_VENV/bin/spectator-integrations" list
SITE_DIR=$("$WHEEL_VENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')
uvx pip-audit --path "$SITE_DIR"
```

Expected integration list: `claude-code`, `codex`, `commandcode`, `opencode`, `pi`.

Expected dependency audit: no known dependency vulnerabilities; the unpublished `duckwork-spectator` package itself may be listed as unauditable because it is not on PyPI.

### F. Installed-wheel HTTP/WebSocket runtime proof

```bash
export RUNTIME_HOME="$(mktemp -d /tmp/spectator-independent-runtime.XXXXXX)"
export RUNTIME_DIR="$RUNTIME_HOME/data/spectator"
export SERVER_LOG="$AUDIT_ROOT/spectator-server.log"
DUCKWORK_HOME="$RUNTIME_HOME" SPECTATOR_SESSION_ID=independent-review \
  "$WHEEL_VENV/bin/spectator-serve" >"$SERVER_LOG" 2>&1 &
export SERVER_PID=$!

for _ in $(seq 1 50); do
  "$WHEEL_VENV/bin/python" - <<'PY' >/dev/null 2>&1 && break
import urllib.request
with urllib.request.urlopen(
    'http://127.0.0.1:8788/api/plugins/spectator/guest.html', timeout=1
) as response:
    assert response.status == 200
PY
  sleep 0.1
done

RUNTIME_DIR="$RUNTIME_DIR" REPO_ROOT="$REPO" \
  "$WHEEL_VENV/bin/python" "$LIVE_PROBE"
stat -c '%n|%a|%U:%G' \
  "$RUNTIME_HOME" "$RUNTIME_HOME/data" "$RUNTIME_DIR" \
  "$RUNTIME_DIR/spectator.db" "$RUNTIME_DIR/host_secret"
kill "$SERVER_PID"
wait "$SERVER_PID" 2>/dev/null || true
```

Expected probe result:

- HTTP passed.
- WebSocket passed.
- Branch query passed.
- Session lifecycle passed.
- Host secret mode `0600`.
- Runtime directories mode `0700`.
- Database mode `0600`.

Inspect `$SERVER_LOG`. Confirm teardown and no surviving process. A successful unit suite is not a substitute for this proof.

### G. Real Duckwork plugin-loader proof

Use only disposable Duckwork state:

```bash
export LOADER_HOME="$(mktemp -d /tmp/spectator-independent-loader.XXXXXX)"
mkdir -p "$LOADER_HOME/bundled-empty"
printf 'plugins:\n  enabled:\n    - spectator\n' >"$LOADER_HOME/config.yaml"
export WHEEL_SITE=$("$WHEEL_VENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')

DUCKWORK_HOME="$LOADER_HOME" \
DUCKWORK_BUNDLED_PLUGINS="$LOADER_HOME/bundled-empty" \
PYTHONPATH="$WHEEL_SITE:/home/kensei/repos/KenseiAgent" \
/home/kensei/repos/KenseiAgent/.venv/bin/python - <<'PY'
from pathlib import Path
from duckwork_constants import set_duckwork_home_override
set_duckwork_home_override(Path(__import__('os').environ['DUCKWORK_HOME']))
from duckwork_cli.plugins import PluginManager
manager = PluginManager()
manager.discover_and_load(force=True)
rows = [row for row in manager.list_plugins() if row.get('name') == 'spectator']
print(rows)
assert len(rows) == 1
assert rows[0]['version'] == '0.2.0'
assert rows[0]['source'] == 'entrypoint'
assert rows[0]['enabled'] is True
assert rows[0]['error'] is None
PY
```

Expected: one enabled `spectator` entry-point plugin, version 0.2.0, with no loader error.

### H. Duckwork verification-recipe issue

Independently reproduce the auto-detection before reading the producer narrative:

```bash
/home/kensei/.local/bin/duckwork verify "$REPO" --detect-only --json
```

Producer-observed output selected `uvicorn main:app --host 0.0.0.0 --port 8000`, but the real app is `spectator.serve:app`. A temporary external manifest using the real app and `/api/plugins/spectator/guest.html` returned `ok: true`, 291 tests passed and HTTP 200 readiness.

Decide whether the candidate must ship a repository-local `.duckwork/environment.json`, change project layout, or merely document that generic detection is not authoritative for this plugin. Do not add a manifest during review.

### I. Harness conformance and evidence honesty

Verify from source/tests that:

- every named harness maps lifecycle/input/tool events to neutral events;
- raw prompt/tool content is not forwarded;
- stable event IDs or deterministic occurrence markers prevent duplicates;
- Codex `SessionEnd` is synchronous;
- OpenCode uses the real `chat.message` shape and `content_size`;
- hook transport rejects non-HTTP schemes;
- the core imports no harness modules;
- missing capabilities fail honestly rather than returning false success;
- integration templates contain no credentials or machine-specific paths.

Classify support evidence separately:

| Harness | Producer-reported real evidence | Independent expectation without credentials |
|---|---|---|
| Duckwork | Directory and exact-wheel plugin loading | MUST reproduce |
| Generic portable sidecar | Full HTTP/WebSocket/session flow | MUST reproduce |
| Codex | Authenticated successful turn and lifecycle events | Verify conformance; real turn is reported unless independently available |
| OpenCode | Lifecycle event delivery; provider unavailable | Verify conformance; mark assistant turn gap |
| Pi | Start/input/shutdown delivery; credentials unavailable | Verify conformance; mark assistant turn gap |
| Claude Code | Shutdown hook; not logged in | Verify conformance; mark assistant turn gap |
| Command Code | CLI/settings only; auth blocked start | Verify static contract; explicitly judge release impact |

Do not request or type credentials. Do not upgrade a reported external run to independently verified without reproducing it.

### J. Legacy-state and deployment review

Read-only inspection may be performed:

```bash
stat -c '%n|%a|%U:%G' \
  /home/kensei/.duckwork/plugins \
  /home/kensei/.duckwork/plugins/spectator \
  /home/kensei/.duckwork/plugins/spectator/spectator.db \
  /home/kensei/.duckwork/plugins/spectator/host_secret
```

Producer-observed modes on 26/08/2026:

- plugins parent: `0777`;
- legacy Spectator directory: `0755`;
- legacy database: `0644`;
- legacy host secret: `0600`.

Determine whether:

1. fresh `$DUCKWORK_HOME/data/spectator` state is the safe default;
2. migration is required for existing users;
3. an explicit permission/migration runbook is required before release; and
4. rollback after first 0.2.0 start is operationally safe.

Do not chmod, move, copy, delete or open the database contents. Never expose the host secret.

## 8. Architecture and document map

Recommended read order:

1. `docs/REBUILD.md` — intended scope and declared limitations.
2. `pyproject.toml`, `plugin.yaml`, `dashboard/manifest.json`, root `__init__.py` — package/loader contract.
3. `src/spectator/core/` — neutral contracts, registry, service and summary projection.
4. `src/spectator/adapters/` — stored, Duckwork metadata and native-context adapters.
5. `src/spectator/bridge/` and `src/spectator/integrations/` — portable hook transport and harness templates.
6. `src/spectator/code/query.py` — exact-commit branch query and privacy exclusions.
7. `src/spectator/db/`, `auth/`, `feed/`, `suggest/`, `config.py`, `serve.py` — persistence and runtime behaviour.
8. `dashboard/plugin_api.py` — host/guest HTTP and WebSocket boundary.
9. `dashboard/static/guest.html` — functional client shell.
10. `tests/` — verify that tests assert the claims rather than merely exercise happy paths.
11. Producer review records — read last and reconcile against live results.

Important architecture assertions to challenge:

- `spectator.core` and generic contracts have zero Duckwork imports.
- Native suggestion injection is impossible without configured native context.
- A portable adapter can own a session end to end.
- Guest code queries never read the mutable working tree or untracked files.
- Privacy masking applies to event summaries and code snippets.
- DB/storage initialisation fails closed without leaking internals.
- Directory-style and wheel-entry-point loading are compatible.

## 9. Time-box guidance

| Lane | Budget | Requirement |
|---|---:|---|
| Frozen-state and material identity | 5 min | MUST run first |
| Fresh install, collection and full suite | 10 min | MUST run |
| Static/type/security gates | 15 min | MUST run where tools are available |
| Manual adversarial and blast-radius review | 30–45 min | MUST perform |
| Wheel build/install/source comparison | 15 min | MUST run |
| HTTP/WebSocket and Duckwork loader proof | 15 min | MUST run |
| External authenticated harness turns | Unbounded | SKIP unless already authenticated without configuration changes; record gaps |
| Full visual redesign/browser polish | Out of scope | SKIP |

Do not spend the review installing unavailable Hermaguard companion tooling. Record its absence and use available deterministic scans plus direct adversarial inspection.

## 10. Expected deliverables

Write outputs outside the repository:

- `/tmp/spectator-independent-review-20260826.pfNtvk/review-output/INDEPENDENT_REVIEW_REPORT.md`
- `/tmp/spectator-independent-review-20260826.pfNtvk/review-output/INDEPENDENT_REVIEW_REPORT.json`

The Markdown report must contain:

```text
VERDICT: READY | NEEDS CORRECTION | NOT READY

Candidate reviewed:
  frozen code SHA, review HEAD, branch, clean-state result

Scope:
  what was reviewed and what was explicitly out of scope

Verified claims:
  claim -> exact command/probe -> observed result -> provenance

Refuted or questionable claims:
  expected -> observed -> why the difference matters

Findings:
  ID, severity, class, file:line, concrete trigger, impact,
  reproduction evidence, recommended correction, release effect

Coverage ledger:
  auth, authorisation, privacy, path handling, SQL/transactions,
  races/partial writes, resources, errors/observability, XSS,
  SSRF/transport, packaging, loader, rollback, harness contracts

Harness matrix:
  independently verified | producer-reported | gap | not applicable

Wheel/source verdict:
  supplied hash, payload consistency, rebuilt-wheel result,
  package contents and dependency-audit result

Legacy-state recommendation:
  fresh state | migrate | block, with rationale and rollback impact

Regression and tech-debt assessment:
  adjacent flows, hidden workarounds, warning/dependency debt

Release recommendation:
  exact conditions before merge and exact conditions before deployment

Release state:
  committed/pushed/published/installed/deployed must remain separate
```

The JSON must include at minimum:

- `candidate` with base SHA, code-final SHA, review HEAD and material hashes;
- `verdict`;
- `verified_claims[]`;
- `questionable_claims[]`;
- `findings[]` with severity, file, lines, evidence and recommendation;
- `coverage[]`;
- `harness_matrix[]`;
- `wheel_review`;
- `legacy_state_recommendation`;
- `gaps[]`;
- `release_conditions[]`.

If the verdict is `NEEDS CORRECTION`, end with a minimal repair contract: each blocker, required RED witness, exact correction seam and acceptance proof. Do not apply the fixes.

If the verdict is `READY`, state plainly that this means engineering-review ready only. It still does not authorise merge, push, publish, live installation, state migration or deployment.

## 11. Final integrity check before returning

Immediately before writing the verdict, rerun:

```bash
cd "$REPO"
git status --short
git rev-parse HEAD
git merge-base --is-ancestor "$CODE_FINAL_SHA" HEAD
git diff --name-only "$CODE_FINAL_SHA"..HEAD
git diff --check "$BASE_SHA"..HEAD
```

If the tree or HEAD moved, the verdict is void. Report `NOT READY — candidate mutated during review` and stop.

No fixes are to be applied by this review.
