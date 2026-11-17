# Developing the Duckwork memory provider

This directory imports the OpenViking provider from
[`Fordex/duckwork-plugin-openviking`](https://github.com/DuckMind/duckwork),
commit `5dca75f4d3dcef9467ce2ff32e170d84c679de5f`.

At the initial import, `__init__.py`, `_setup.py`, and `plugin.yaml` matched that
handoff and `plugins/memory/openviking/` in Duckwork Agent commit
`d177b119e9c56c9ddc0b7379ffce52341ec06584`. The original MIT license is retained
in this directory. Original contributor history is available in
[Duckwork Agent](https://github.com/DuckMind/duckwork).

Contributions to this directory are provided under its [MIT license](LICENSE).
Preserve the existing copyright and permission notice.

The distribution name is `duckwork-plugin-openviking`. The provider, plugin, and
Duckwork catalog key remain `openviking`. Existing `memory.openviking`
settings, environment variables, linked `ovcli.conf` files, data paths, and
`viking_*` tools keep their current behavior.

The active-session commit lifecycle was ported from
[KoNit-K's Duckwork PR #112533](https://github.com/DuckMind/duckwork),
with the original author retained. The OpenViking adaptation uses a configurable
pending-token threshold instead of the original six-turn trigger.

Native memory mirroring is adapted from
[Duckwork PR #100187](https://github.com/DuckMind/duckwork),
commit `32f75a9e6728a9a3d2f50a870dab3715a1f34fd7`, which continues
[austinlaw076's PR #85860](https://github.com/DuckMind/duckwork).
The external plugin uses relative imports and Duckwork's context-preserving worker
helper. Its connection cache and session-commit lifecycle retain the later
OpenViking fixes.

Gateway sender attribution and recall scope adapt
[Duckwork PR #105812](https://github.com/DuckMind/duckwork),
including liuhao1024's capture change from
[PR #98506](https://github.com/DuckMind/duckwork), with the
original author retained. The adaptation uses Duckwork's existing per-turn author
hooks and preserves the original sender-ID encoding and Personal/Shared setup
presets. Shared Agent changes gateway session settings only after confirmation;
Personal Agent preserves them. An upgrade with no recall scope set retains the
previous recall requests. No Duckwork core patch is required.

Profile-bound connection and recall settings adapt
[starship-s's Duckwork PR #83647](https://github.com/DuckMind/duckwork),
with the original author retained. This port leaves memory URI handling as it
is: the original PR's UID-less `viking://user/memories/...` rewrite is not
accepted by current OpenViking servers.

Quick Local adapts [Duckwork PR #94851](https://github.com/DuckMind/duckwork)
(head `d15e0e65d67a2dd6d3f3ab09a382c1f1684e2560`). Provisioning remains separate
from the setup UI. The port uses current Duckwork PM, authenticated server reuse,
and paths derived from the provider's bound home. On Python 3.14, the private
server uses LiteLLM 1.83.7, within OpenViking's supported range; some other
releases in that range exclude Python 3.14. The profile server controller verifies
the PID, creation time, executable and config path before stopping a process.
It repairs permissions on plugin-owned private files after backup restoration;
no Duckwork backup changes are required.

`local_packages.py` selects compatible OpenViking wheels from PyPI and reviewed
llama-cpp-python binaries, with SHA-256 verification before installation. Both PM
and pre-PM installers receive verified local wheel files. Setup records the applied
requirements so that a newer server release or native package pin updates an
existing private runtime. Change native package pins only after installation,
model and service checks pass on the listed platforms. Source builds require
explicit consent. Platform CI runs real installation, local embedding, capture,
restart and port-recovery checks. It uses a static test LLM configuration and
does not establish live memory extraction; that remains a release check.
The OpenViking hash comes from PyPI at setup time; llama-cpp-python hashes are
fixed in this plugin. PM/uv resolve the other dependencies; this is not a fully
locked server runtime.
Source builds use package version pins without reviewed binary hashes. A platform
needs a tested OpenViking/embedding-wheel pair for the prebuilt path.
Setup also checks LLM access through the installed OpenViking backend. The CI
fixture must serve an actual completion; an unreachable LLM must fail setup.

## Migration coordination

Duckwork publishes this provider through `plugin-catalog/openviking.yaml`. The
entry must contain:

- `name: openviking`
- `repo: https://github.com/volcengine/OpenViking`
- `subdir: examples/duckwork-plugin`
- `sha`: the full reviewed OpenViking commit SHA
- `category: memory`
- `tier: community`

Include the required `capabilities` block for tools, hooks, middleware, and
environment variables. Its declarations must match the plugin at the reviewed
SHA. Follow the [Duckwork catalog entry schema](https://github.com/DuckMind/duckwork)
and validate the pinned installation directory:

```bash
duckwork plugins validate /path/to/duckwork-profile/plugins/openviking
```

Duckwork PR [#131267](https://github.com/DuckMind/duckwork)
published the catalog entry. Duckwork PR
[#114569](https://github.com/DuckMind/duckwork) added catalog
recovery for configured providers that no longer resolve. Keep the reviewed
catalog pin and migration path valid. Duckwork PR
[#134350](https://github.com/DuckMind/duckwork) removed the
bundled OpenViking provider from main. Older releases still load their bundled
copy first.

This plugin does not add a Desktop `config_schema.py`.
The wizard uses private helpers from `duckwork_cli.memory_setup`; changes to
those helpers require compatibility checks. The plugin uses HTTP. Quick Local installs the server in a separate
profile runtime through Duckwork PM, or the earlier Duckwork uv installer on the
tested release baseline. It does not add server dependencies to Duckwork.
Explicit Quick Local setup resolves the latest stable, Python/platform-compatible
OpenViking 0.5 release from PyPI and verifies the wheel against PyPI's download
hash. The native embedding package remains pinned and hash-verified. The resolved
requirements are recorded per profile; unchanged requirements reuse the runtime,
while a new release follows the existing validation and restart path. Chat and
recovery do not resolve or upgrade packages.

Installation records a runtime-validation-pending marker that only setup consumes.
After validation passes, setup uses the existing server controller to request a
restart and clears the validation marker. Chat therefore keeps using a healthy
existing server while it keeps running. If that process stops, recovery can start
the installed runtime without clearing pending validation. Local status reports
`runtime_validation_pending` separately from readiness and `restart_required`.

## Validation

The `Duckwork Plugin Tests` workflow runs this directory's complete external-provider
suite on plugin changes, pushes to `main`/`develop`, and manual dispatch.
It uses Python 3.14 and a reviewed Duckwork commit, with test retries disabled.
The release-host job runs the complete provider suite on Duckwork v2026.9.24
with Python 3.13, selected explicitly by `uv sync --python` rather than the
release checkout's `.python-version`. Legacy autostart uses Duckwork's profile
environment helper and credential scrubber on both hosts. Unrelated process and
profile secrets are removed; missing helpers or secret-scope errors prevent spawning.
When updating the host SHA in `.github/workflows/duckwork-plugin-tests.yml`, check
the host dependency pins and run the suite before submitting the change.
These regression tests use mock responses and local test servers; live-service
validation remains part of release testing.
The reviewed current host builds its test environment through Duckwork PM.
Fixtures use the host's YAML implementation, so they do not need a separate
PyYAML install on current Duckwork. The older release retains its uv installer.
Native edit tests select the action advertised by the host tool schema:
`patch` on current Duckwork and `replace` on the release baseline. Both must
update the same mapped file. Patch-specific tests also check that text outside
the edited span is preserved in the native entry and its remote copy.

CI also runs `scripts/check-duckwork-plugin-install.py` through the real Duckwork
CLI in an isolated profile. It installs this repository's plugin subdirectory,
enables it through Duckwork's dependency manager, validates the installed directory,
and checks that the external provider loads. The bundled OpenViking copy is
temporarily removed from the test checkout. This catches dependency conflicts
across supported platforms that runtime tests alone do not exercise.

Use a Duckwork checkout with its development dependencies installed.

The complete mirror tests require the committed-entry event contract introduced
in [Duckwork PR #118903](https://github.com/DuckMind/duckwork)
and merged through [#120003](https://github.com/DuckMind/duckwork)
(commit `5908e1aaa83e82aaf12541d7a9d90762d0b46a64`):
`MemoryManager` forwards `previous_content` for each successful replacement or
removal. Current native `patch` calls become provider `replace` events containing
the complete updated entry; older native `replace` calls use that event directly.
The legacy compatibility tests verify that missing metadata skips these remote
mutations. Do not substitute a guessed match in tests or production.

From that checkout, run its canonical test runner against this directory:

```bash
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" DUCKWORK_TEST_FILE_RETRIES=0 \
  scripts/run_tests.sh /path/to/OpenViking/examples/duckwork-plugin/tests \
  --confcutdir=/path/to/OpenViking/examples/duckwork-plugin/tests -q
```

`--confcutdir` keeps pytest from importing the plugin as a test package before
Duckwork loads it under its own namespace. The tests use temporary profile homes
and remove bundled-provider discovery.
They cover external loading, profile isolation, setup, tools, session commits,
and native memory mirroring. The mirror suite includes ordered writes, restart
continuity, registry failures, connection isolation, and concurrent workers.
Gateway tests use mock events through Duckwork's turn hooks and memory manager.
They cover sender changes, capture retries, commits, recall scopes, compression
fallback, and missing sender metadata. Setup tests cover both presets,
confirmation, cancellation, profile-local persistence, connection routes, and
actual Duckwork session keys.
Provider-specific regression tests belong here and must use the shared external
loader fixture. Generic Duckwork framework tests remain in Duckwork.

For compatibility checks against a Duckwork release that bundles OpenViking,
also run its provider tests. These load the bundled copy unless explicitly
routed through the external loader; they do not replace this directory's tests:

```bash
DUCKWORK_TEST_FILE_RETRIES=0 scripts/run_tests.sh \
  tests/plugins/memory/test_openviking_provider.py \
  tests/plugins/memory/test_openviking_optional_peer.py \
  tests/plugins/memory/test_openviking_shutdown.py \
  tests/plugins/memory/test_openviking_endpoint_always_blocked.py \
  tests/openviking_plugin/test_openviking.py -q
```
