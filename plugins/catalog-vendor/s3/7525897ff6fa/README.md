# s3 — Duckwork plugin

![s3](logo.png)

Back up files and directory trees to any S3-compatible object store, then
restore, list, or safely remove remote objects. It uses boto3 directly and
works with providers such as AWS S3, Cloudflare R2, and MinIO.

## Install

As a Duckwork plugin:

```sh
duckwork plugins install https://github.com/DuckMind/duckwork --enable
```

Or copy the directory to `~/.duckwork/plugins/s3/` manually.

### Plugin development (uv)

This repository *is* a Duckwork plugin — most users just run
`duckwork plugins install ...` above. The steps below are for
**contributors** working on the plugin itself (running the test
suite, building a wheel, or developing locally). With
[uv](https://docs.astral.sh/uv/):

```sh
uv sync                      # create .venv and install boto3 + pyyaml
uv run python scripts/test-s3-backup.py   # run the hermetic test suite (no network)
```

Without uv, use a venv + pip:

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/test-s3-backup.py
```

## Configure

Set these environment variables in the process environment or
`~/.duckwork/.env`. Do **not** commit credentials.

```text
S3_BACKUP_ENDPOINT=https://s3.example.com  # omit for AWS S3
S3_BACKUP_REGION=us-east-1                 # use your provider's region
S3_BACKUP_BUCKET=my-backups
S3_BACKUP_ACCESS_KEY=...
S3_BACKUP_SECRET_KEY=...
S3_BACKUP_RULES=~/.duckwork/s3-backup.rules.yaml  # optional; this is the default
```

For providers that require a custom endpoint or region value, use the values
documented by that provider. Keep access keys and secret keys only in
`~/.duckwork/.env` or the process environment; never place them in this
repository, rules files, or command arguments.

## Quick start

```sh
# Upload a file or directory to your configured bucket
duckwork s3 push ./build builds/latest

# Upload, overwriting existing objects
duckwork s3 push ./build builds/latest --force

# Download a prefix to a local directory
duckwork s3 pull builds/latest ./restored

# List objects under a prefix
duckwork s3 ls builds/

# Delete an object (--confirm is required)
duckwork s3 rm builds/old.tar.gz --confirm
```

Named flags work too: `--local` (local path) and `--remote` (remote key/prefix).

## Named rules

Define reusable push/pull targets in `~/.duckwork/s3-backup.rules.yaml`:

```yaml
daily-backup:
  prefix: backups/my-project/{date}
  source: ~/my-project

run-output:
  prefix: builds/{date}
  source: ~/build
```

**Fields:**
- `prefix` *(required)* — remote key prefix; supports `{date}`, `{ts}`,
  `{year}`, `{month}`, `{day}` placeholders (UTC)
- `source` *(optional)* — default local path; relative paths only, no `..`

Use a rule with `--rule`:

```sh
duckwork s3 push --rule daily-backup
duckwork s3 push --rule daily-backup --force   # overwrite
duckwork s3 ls   --rule run-output
```

Positional arguments override rule values when provided.

## Notes

- **push** skips objects that already exist in the bucket unless `--force` is given.
- **pull** validates every destination path (including symlink resolution) before writing.
- **rm** requires `--confirm` and deletes the exact key specified.
- All commands output JSON to stdout (`{"ok": true, ...}`).
- Requires Python 3.10+, boto3, and PyYAML (for rules).

## License

MIT — see [LICENSE](LICENSE). Contributions welcome; see [CONTRIBUTING](CONTRIBUTING.md).
