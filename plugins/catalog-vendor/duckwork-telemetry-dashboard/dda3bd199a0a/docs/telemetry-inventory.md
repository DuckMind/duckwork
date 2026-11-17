# Duckwork Shared Metrics — Data Inventory (canonical reference)

> HER-27 — frozen 2026-09-30. Authoritative sources:
> - Schema: `duckwork_cli/observability/schemas/duckwork.shared_metrics.v3.schema.json` (76 `$defs`)
> - Contract: `duckwork_cli/observability/shared_metrics_contract.py`
> - Fields: `duckwork_cli/observability/shared_metrics_fields.py`
> - Live DB: `~/.duckwork/telemetry/shared_metrics/metrics.sqlite3`
>
> If the shipped schema changes, re-derive this file from the schema JSON — never from memory.

## 1. Where the data lives

| Path | What |
|---|---|
| `~/.duckwork/telemetry/shared_metrics/metrics.sqlite3` | Collection DB (live-writer; read with `mode=ro` + busy_timeout or copy first) |
| `~/.duckwork/telemetry/shared_metrics/outbox/*.json` | Packaged payloads staged for export (one file per package) |
| `~/.duckwork/telemetry/shared_metrics/process_markers/` | Crash markers per CLI process |
| `~/.duckwork/telemetry/shared_metrics/desktop_onboarding/` | Consent + first-message stamps |
| `~/.duckwork/config.yaml` → `telemetry.shared_metrics.{enabled,send}` | Collection / sending toggles |

Current state on this machine: `enabled: true, send: false` — collecting locally, **nothing has ever been sent** (`package_outbox.send_attempts = 0`). Send endpoint (only used when `send: true`): `https://telemetry.fordex.com/v1/telemetry`.

## 2. SQLite tables

| Table | Role |
|---|---|
| `counter_aggregates` | Period-batched counters. PK: `(period_start, metric_name, duckwork_version, os_family, architecture, install_method, dimensions_json)`. Columns: `value`, `packaged_value` |
| `package_outbox` | Export packages: `payload_json` (v3), `period_start/end`, `send_state`, `send_attempts`, `sent_at`, `claim_token` |
| `telemetry_state` | Install identity + milestones + daily-once flags + engagement state (key/value) |
| `send_consent_windows` | Consent window bookkeeping (empty while send is off) |
| `consent_marks` | `obs` + `data` consent stamps |

Retention: exported history kept 30 days; pending deltas until exported. With `send: false`, packages accumulate indefinitely.

## 3. Payload envelope (schema v3)

Top-level: `schema_version` (`duckwork.shared_metrics.v3`), `package_id` (uuid), `install_id` (random profile-scoped, stable until the telemetry dir is deleted — NOT derived from hardware/account), `period_start`, `period_end`, `generated_at`, `resource` (`architecture`, `duckwork_version`, `install_method`, `os_family`), `metrics[]`.

Each metric: `{name, type: "counter", value, dimensions{}}` — all values are **bucketed or closed-enum**; raw free-text never leaves the machine (skill/plugin/command names outside the shipped catalogs report as `custom`).

## 4. Metric catalog (from schema v3 — 76 defs, 69 emissive counters)

All counters carry `{name, type, value}`; only `dimensions` differ. Bucket conventions: `*_bucket` = closed buckets (`0`, `1`, `2`, `3_to_5`, `6_to_10`, `26_to_100`, ...), `*_family`/catalog names = shipped public-catalog identifiers, `unknown` = could not be measured.

| Metric | Dimensions |
|---|---|
| `duckwork.client.active` | — |
| `duckwork.model_call.count` | call_role, locality, model_family, outcome, provider_family |
| `duckwork.model_route.count` | model, provider, call_role, error_class, outcome, ttft_bucket |
| `duckwork.model_tokens.sum` | aux_task, call_role, model, provider, token_type |
| `duckwork.task_run.started` | entrypoint, execution_surface, platform |
| `duckwork.task_run.finished` | — |
| `duckwork.task_run.duration` | duration_bucket, execution_surface, outcome, retry_count_bucket |
| `duckwork.task_cost.count` | api_calls_bucket, model, outcome, provider, tokens_bucket, tool_calls_bucket |
| `duckwork.tool_call.count` | approval_outcome, latency_bucket, outcome, retry_count_bucket, tool_category |
| `duckwork.tool_call.latency` | latency_bucket, retry_count_bucket, tool_category |
| `duckwork.tool.usage.count` | error_class, outcome, tool_name |
| `duckwork.tool_approval.count` | attribution, outcome |
| `duckwork.tool_recovery.count` | model, next_outcome, next_tool, provider, tool |
| `duckwork.tool_unavailable.count` | model, provider, tool_name |
| `duckwork.tool_output_truncation.count` | original_size_bucket, tool, truncated |
| `duckwork.tool_overhead.count` | enabled_tool_count_bucket, execution_surface, tool_schema_tokens_bucket |
| `duckwork.tool_enabled_unused.count` | toolset, used |
| `duckwork.file_edit.count` | match_strategy, mode, outcome, tool |
| `duckwork.terminal.outcome.count` | backend, command_kind, outcome |
| `duckwork.session.count` | active_duration_bucket, entrypoint, execution_surface, failed_turn_count_bucket, last_outcome, platform, turn_count_bucket, message_count_bucket, model_call_count_bucket, tool_call_count_bucket |
| `duckwork.skill.lifecycle.count` | action, provenance |
| `duckwork.skill.load.count` | post_patch_state, provenance, reuse_state, use_count_bucket, skill_name |
| `duckwork.slash_command.count` | command, execution_surface |
| `duckwork.extension.install.count` | kind, name, outcome, source |
| `duckwork.install.milestone` | install_age_bucket, milestone |
| `duckwork.install.snapshot` | cron_job_count_bucket, mcp_server_count_bucket, memory_provider, plugin_count_bucket, profile_count_bucket, skill_count_bucket, display_language, install_age_bucket, main_provider, messaging_platform_count_bucket, terminal_backend, behind_bucket, gpu_class, local_model_provider_used, ram_bucket, release_channel, version_age_bucket |
| `duckwork.setup.completed` | provider, surface |
| `duckwork.compression.count` | context_fill_bucket, outcome, trigger |
| `duckwork.model_switch.count` | execution_surface, from_provider, to_provider |
| `duckwork.model_switch_after.count` | model, provider, turns_before_switch_bucket |
| `duckwork.fallback.count` | error_class, from_provider, to_provider |
| `duckwork.memory.op.count` | op, origin, outcome, provider |
| `duckwork.curator.run.count` | archived_bucket, created_bucket, merged_bucket, outcome, patched_bucket, trigger |
| `duckwork.delegation.run.count` | depth, mode, outcome, subagent_count_bucket |
| `duckwork.execution_backend.count` | backend, error_class, kind, outcome |
| `duckwork.model_tool_quality.count` | call_role, issue, model, provider |
| `duckwork.model_friction.count` | model, provider, signal |
| `duckwork.model_reply_issue.count` | issue, model, provider |
| `duckwork.context_peak.count` | limit_hit, model, peak_fill_bucket, provider, window_bucket |
| `duckwork.startup.latency` | latency_bucket, surface |
| `duckwork.engagement.day.count` | active_minutes_bucket, active_profile_count_bucket, primary_model, primary_provider, surfaces_used_count |
| `duckwork.engagement.surface_day.count` | active_minutes_bucket, surface |
| `duckwork.feature_adoption.count` | days_since_install_bucket, feature |
| `duckwork.feature_disabled.count` | event, kind, name, surface |
| `duckwork.cache_break.count` | cause, model, provider |
| `duckwork.loop_guard.count` | detector, model, provider, signal |
| `duckwork.wasted_tokens.count` | model, provider, reason, tokens_bucket |
| `duckwork.cron.run` | delivery_kind, duration_bucket, outcome |
| `duckwork.gateway.reply_latency` | first_response_bucket, platform |
| `duckwork.platform.health` | error_class, event, platform |
| `duckwork.platform.delivery` | failure_class, outcome, platform |
| `duckwork.process.exit` | crash_class, exit_kind, process_kind |
| `duckwork.update.run` | apply_mode, duration_bucket, failed_stage, from_version_age_bucket, kind, outcome |
| `duckwork.update.stage` | duration_bucket, outcome, stage |
| `duckwork.provider_setup.count` | event, failure_class, provider, surface |
| `duckwork.desktop.feature_use` | area |
| `duckwork.desktop.friction` | detail, kind |
| `duckwork.desktop.onboarding` | event, step |
| `duckwork.desktop.mode_use` | active_minutes_bucket, bot_count_bucket, messages_sent_bucket, mode |
| `duckwork.desktop.action_use` | action, count_bucket, via |
| `duckwork.desktop.dislike` | direction, setting, signal, target |
| `duckwork.install.snapshot` | (same as above — emitted on first run + daily) |

## 5. Dimension vocabularies (constants to know for rendering)

- **Buckets**: `size_bucket`: `0|1|2|3_to_5|6_to_10|11_to_25|26_to_100|101_to_500|gte_501`; `duration_bucket`/`latency_bucket`/`ttft_bucket`/`install_age_bucket`/`active_duration_bucket`: closed ms/s thresholds ending `lt_*|*_to_*|gte_*`; `count_bucket`: `0|1|2|3_to_5|6_to_10|gte_11`; `long_size_bucket` for schema sizes.
- **Provider/model names**: shipped provider ids + model ids; anything user-defined → `custom`.
- **Install snapshot** renders human table: ram_bucket (`16g_to_32g`), gpu_class (`intel|nvidia|amd|...`), main_provider, terminal_backend, counts of skills/plugins/profiles/MCP/cron/messaging.

## 6. Privacy invariants (what the GUI must respect)

1. All identifiers bucketed or catalog-closed; GUI should display buckets verbatim (no raw values exist in the DB beyond these).
2. `install_id` is profile-scoped and random; GUI may display it locally (it's yours) but the plugin must never send it anywhere.
3. The plugin reads ONLY. Never write to `metrics.sqlite3`, never touch `telemetry.*` config, never call the sender.
4. DB is live-written → read with `mode=ro` + `busy_timeout`, or copy to a scratch path when locked (observed on this machine).