# Disclosure verification — clause-by-clause evidence

Verification of the catalog submission disclosure for `duckwork-workflows`
(fix for Fordex/duckwork-agent#122099). Every clause below is checked
against the source at this commit; `file:line` cites are exact at audit time.

**Verdict: verified — with one correction.** An earlier draft disclosure said
the plugin makes "no network calls of its own". Unqualified, that is
misleading: the run/amend submit path issues one provider liveness ping per
distinct explicitly-pinned route through Duckwork' core auxiliary client, and
child agents make provider calls with the inherited environment. The
corrected disclosure text (below) is what the catalog PR body must quote.
No other clause needed correction.

## 1. Detached runner

> "each `workflow run` starts a detached `wf.py run <id>` process, independent
> of the originating session and gateway; disabling the plugin does not stop an
> already-running process."

- Verified (#8, caller-tree escape): the door spawns the runner DAEMONIZED
  through a transient double-fork hop — `Popen([sys.executable, "-c", <hop>,
  wf.py, "run", <run_id>, <ready_fd>], stdin=DEVNULL, start_new_session=True)`;
  the hop forks the real `wf.py run` in its own session (`setsid`) and exits at
  once, so the runner leaves the caller's process tree before the tool call
  returns (`_spawn_runner`, `_DAEMON_INTERMEDIATE`). The admitted runner stamps
  its own `wf.pid` at flock admission (`wf.py ready_stamp`) and announces it on
  the door's ready pipe; the door never writes `wf.pid` (it may return the
  observed pid). No plugin-disable kill hook exists (`register()` registers only
  skill/tool/command; `plugin.yaml` provides only `workflow`).
- Claim boundary (verified limitation): double-fork + `setsid` changes parenting
  and session, NOT cgroup membership. A cleanup that kills by process-tree
  membership (the process_registry completion sweep; a service's process-tree
  SIGTERM) no longer reaches the runner; a cleanup that kills by unit-cgroup
  membership (e.g. an ExecStopPost SIGKILL over the gateway unit's cgroup on
  restart) still reaches caller, runner and children alike. Surviving an
  enclosing service/cgroup cleanup is out of scope for this claim.
- A run ends at a graph boundary (`held`/`done`/`failed`/`stopped`) or on
  `workflow stop`: the door writes `stop.request` (`__init__.py:1185-1192`),
  the runner's stop watcher consumes it and kills child process groups
  (`wf.py:1672-1694`, re-checked at boundaries `wf.py:1722-1730`).
- Qualification kept honest: host shutdown or a process supervisor can still
  kill the detached runner; interrupted runs resume via an explicit `wait`
  (respawn), not an external scheduler.

## 2. Agent-child argv and environment

> "Each agent node launches an operator-configured `duckwork chat --query-file
> … --oneshot -Q …` child, with optional routing/budget flags and a copy of
> the runner environment plus workflow IPC variables."

- Verified: base argv `[…, "chat", "--query-file", <prompt>, "--oneshot",
  "-Q", "--source", "workflow"]` at `wf.py:851`; conditional
  `--continue/--create-if-missing`, `-m`, `--provider`, `--reasoning`, `-t`,
  `--max-turns`, `--run-budget` at `wf.py:855-865`.
- Environment: `dict(os.environ, DUCKWORK_HOME=…, DUCKWORK_QUIET_TURN_REPORT_FILE=…,
  DUCKWORK_WF_STEER_* IPC, DUCKWORK_WF_RUN_ID)` at `wf.py:875-882`; optional
  `DUCKWORK_WRITE_SAFE_ROOT` extension at `wf.py:886-889`; spawn with
  `env=env, cwd=<child work dir>, start_new_session=True` at `wf.py:904-908`.
- The launcher comes ONLY from operator plugin settings or
  `DUCKWORK_WF_DUCKWORK_BIN` (`__init__.py:117-137`); the tool schema has no
  `duckwork_bin` and `handle()` rejects the argument fail-closed
  (`__init__.py:1214-1217`), covered by `tests/test_launcher_config.py`.

## 3. Machine gate `wait.until_argv`

> "A graph-authored gate `wait.until_argv` executes a fixed argv command
> without a shell directly in the runner, outside Duckwork tool approval."

- Verified: validation requires a non-empty argv LIST, never a shell string
  (`wfcommon.py:658-683`); execution is
  `subprocess.run(w["until_argv"], capture_output=True, text=True,
  timeout=…, cwd=<run>)` in-process at `wf.py:1595-1596` (`shell` defaults
  to false). It does not pass through Duckwork tool approval; the graph author
  is the trust boundary — flagged explicitly for reviewers.

## 4. State location

> "Run state is stored under `$DUCKWORK_HOME/workflows/`."

- Verified: `runs_root()` = `$DUCKWORK_HOME/workflows` (`__init__.py:626-628`),
  same resolution in the runner (`wf.py:27-29`) and the dashboard read model
  (`dashboard/plugin_api.py:37-39`).

## 5. Network, cron, credentials — the corrected clause

> "The plugin registers no cron and does not directly open network sockets or
> read a credential store; however, run/amend may issue one provider liveness
> request per distinct explicitly routed model through Duckwork' core auxiliary
> client, child agents may make provider/tool calls with inherited
> environment, Desktop uses the Duckwork plugin REST API, and gate commands
> inherit the runner environment."

- No direct network: zero `urllib`/`socket`/`requests` imports and zero
  `fetch(`/`urlopen` in shipped code (`__init__.py`, `wf.py`, `wfcommon.py`,
  `desktop/plugin.js`, `dashboard/plugin_api.py`; `urlopen` appears only in
  `tests/`). Verified by grep at audit time.
- Auxiliary liveness ping: soft-imported `agent.auxiliary_client.call_llm`
  (`__init__.py:446-450`) with `max_tokens=1` per distinct explicit
  (provider, model) route (`__init__.py:492-505`), invoked from the shared
  run/amend submit tail (`__init__.py:549-557`). This uses the core client,
  i.e. core's network path and seat configuration — the qualification the
  original draft omitted.
- No cron: zero cron/scheduler registration anywhere (grep verified).
- No credential-store access: the plugin never reads a secret store or
  credential file; children merely inherit the runner's environment
  (`wf.py:875`), and ping error notes are key-redacted
  (`__init__.py:444`, `__init__.py:475-476`).
- Desktop talks only to the plugin's own dashboard API through the SDK
  (`desktop/plugin.js:1670` — `ctx.rest`); no direct HTTP.

## 6. Desktop gate answer (maintainer ask #122099, teknium1)

> Session-addressed visible SDK submit; `insertText` draft fallback; fail
> closed with an informational toast; no document composer lookup and no
> private composer event.

- Verified: `nudgeOwner` (`desktop/plugin.js:749-772`) resolves the run
  owner's `session_id`, calls SDK `host.composer.submit(sid, text)`, falls
  back to SDK `host.composer.insertText(sid, text)`, and otherwise returns
  `no-sdk`/`no-owner`/`unavailable` — each mapped to an informative
  `host.notify` toast telling the user to type the resume line manually
  (`desktop/plugin.js:775-790`).
- Matches the upstream SDK contract (`apps/desktop/src/sdk/composer.ts`
  `composerHost.submit(sessionId, text): boolean` visible/fail-closed;
  `insertText(sessionId, text, {mode?}): Promise<boolean>`).
- Grep-verified at audit time: zero `document.`, zero `querySelectorAll`
  outside the component's own `el` subtree (`desktop/plugin.js:914,925`),
  zero `window.dispatchEvent`, zero `duckwork:composer-submit`, zero
  `localStorage` writes, in the gate path.
- Behavior test: `tests/test_composer_owner.mjs` (submit → drafted fallback →
  fail-closed, all branches).
