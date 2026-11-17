# SPEC — `s3` Duckwork plugin

A standalone **Duckwork plugin** that is a general **S3-compatible object-store
control plane**. It moves files and directory trees to and from any
S3-compatible store (AWS S3, Cloudflare R2, MinIO, …) and lists or safely
removes remote objects.

> **Backup is one use case, not the only one.** The plugin's verbs are
> `push` / `pull` / `ls` / `rm` against an object store. Scheduled backups
> are the headline example (see *Named rules* + the host's cron), but the
> same surface serves restores, ad-hoc archival, promotion between buckets,
> and any other object-store workflow.

- **Command:** `duckwork s3` (subcommands `push`, `pull`, `ls`, `rm`)
- **Tools:** `s3-push`, `s3-pull`, `s3-ls`, `s3-rm`
- **Skill:** `s3`
- **Version:** `0.1.0`
- **License:** MIT — Copyright (c) 2026 Tane Piper <me@tane.dev>

---

## 1. Architecture

Duckwork loads the plugin from `<plugin-dir>/__init__.py`. That file is a
**thin shim** that re-exports `register` from the `s3_backup` package, which
holds all logic:

```
<plugin-dir>/
├── __init__.py            # Duckwork entry shim → from s3_backup import register
├── plugin.yaml            # manifest (name, provides_tools, author)
├── s3_backup/
│   ├── __init__.py        # register(ctx): wires tools + CLI + skill
│   ├── config.py          # env-driven Config + load_config()
│   ├── storage.py         # boto3 client; push/pull/ls/rm + traversal guards
│   ├── rules.py           # named-rule resolution + safe template expansion
│   ├── schemas.py         # closed JSON input schemas for the 4 tools
│   ├── cli.py             # argparse subtree for `duckwork s3`
│   └── tools.py           # JSON-returning tool handlers (s3-push … s3-rm)
├── skills/s3/SKILL.md     # bundled skill (usage + safety)
├── scripts/test-s3-backup.py  # hermetic FakeS3/FakeCtx test suite
└── pyproject.toml, requirements.txt, README.md, CONTRIBUTING.md, CHANGELOG.md, LICENSE
```

`register(ctx)` performs three registrations:

1. **Four tools** — `s3-push`, `s3-pull`, `s3-ls`, `s3-rm`, all in toolset `s3`,
   each with a closed JSON schema, a handler, and a `check_fn` (`tools.available`)
   that reports whether the plugin can run (boto3 installed + bucket configured).
2. **One CLI command** — `duckwork s3`, built from `cli.register`, with
   `push` / `pull` / `ls` / `rm` subparsers.
3. **One skill** — `s3`, loaded from `skills/s3/SKILL.md` if present.

`boto3` is **lazy-imported**: registration succeeds even if boto3 is missing;
the `check_fn` / handlers report the missing dependency clearly at call time.
No AWS CLI shell-outs; no `forge` / Duckwork-core imports.

---

## 2. Tools reference

All tools accept a JSON object and return a JSON string `{"ok": bool, …}`.

### `s3-push`
Upload a file or directory tree to the bucket.

| field | required | notes |
|-------|----------|-------|
| `local` | one of | local file or directory (also positional) |
| `remote` | one of | remote key / prefix (also positional) |
| `rule` | optional | named rule supplying `source`/`prefix` |
| `force` | optional | bool, default `false` — overwrite existing objects |

Behavior: skips objects that already exist **unless** `force`. Returns
`{"ok": true, "files": N, "bytes": M, "skipped": K, "failed": [...]}`.

### `s3-pull`
Download a remote prefix (or key) to a local directory.

| field | required | notes |
|-------|----------|-------|
| `remote` | one of | remote key / prefix |
| `local` | one of | local destination directory |
| `rule` | optional | named rule |

Safety: every destination path is validated (no absolute paths, no `..`,
symlink targets resolved and contained) before writing.

### `s3-ls`
List objects under a prefix.

| field | required | notes |
|-------|----------|-------|
| `prefix` | one of | remote prefix |
| `rule` | optional | named rule |

Returns `{"ok": true, "keys": [...], "sizes": {...}}`.

### `s3-rm`
Delete a remote object (or prefix).

| field | required | notes |
|-------|----------|-------|
| `key` / `prefix` | one of | object key, or prefix with `recursive` |
| `recursive` | optional | bool, default `false` — required to delete a prefix |
| `confirm` | required | bool — must be `true` (guard against accidental deletion) |

Returns `{"ok": true, "files": N, "deleted": N}`.

---

## 3. CLI reference — `duckwork s3`

```
duckwork s3 push  <local>  <remote> [--force] [--rule NAME]
duckwork s3 pull  <remote> <local>  [--rule NAME]
duckwork s3 ls    <prefix>           [--rule NAME]
duckwork s3 rm    <key|prefix> --confirm [--recursive] [--rule NAME]
```

Positional args may be given as `--local` / `--remote` instead.
`--rule NAME` supplies omitted values from a named rule (see below);
explicit positionals override the rule.

---

## 4. Named rules

Reusable push/pull targets live in a YAML file (default
`~/.duckwork/s3-backup.rules.yaml`, overridable via `S3_BACKUP_RULES`).

```yaml
daily-backup:
  prefix: backups/my-project/{date}
  source: ~/my-project

run-output:
  prefix: builds/{date}
  source: ~/build
```

- `prefix` *(required)* — remote key prefix; supports `{date}`, `{ts}`,
  `{year}`, `{month}`, `{day}` (UTC).
- `source` *(optional)* — default local path; **relative paths only** (no `..`).

A rule is invoked with `--rule NAME`; the tool expands placeholders and
fails safely if a required value is missing or escapes the safe path set.

---

## 5. Configuration

All configuration is **environment-driven** (typically `~/.duckwork/.env` on a
Duckwork host, or the process environment). Never commit credentials.

| variable | required | default | meaning |
|----------|----------|---------|---------|
| `S3_BACKUP_ENDPOINT` | for non-AWS | — | custom endpoint URL (omit for AWS S3) |
| `S3_BACKUP_REGION` | recommended | — | provider region |
| `S3_BACKUP_BUCKET` | **yes** | — | target bucket |
| `S3_BACKUP_ACCESS_KEY` | **yes** | — | access key |
| `S3_BACKUP_SECRET_KEY` | **yes** | — | secret key |
| `S3_BACKUP_RULES` | optional | `~/.duckwork/s3-backup.rules.yaml` | rules file path |

Secrets belong only in `~/.duckwork/.env` or the process environment — never in
this repository, rules files, or tool arguments.

---

## 6. Safety invariants

- `push` never overwrites unless `--force`.
- `pull` validates every destination path (including symlink resolution) and
  rejects absolute / parent-escape / symlink-escaping targets.
- `rm` requires `--confirm`; deleting a prefix additionally requires
  `--recursive`.
- All commands emit JSON to stdout for machine consumption.
- The plugin imports **only** `boto3` (+ `pyyaml` for rules); no shell-outs,
  no external framework dependencies.

## 7. Non-goals

- Not a replacement for provider-native tooling; it is a thin, hermetic
  control surface inside Duckwork.
- Does not manage buckets, IAM, lifecycle, or replication.
- Does not encrypt at rest (relies on the provider / transport TLS).
