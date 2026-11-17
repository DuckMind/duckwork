# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres
to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-07-18

### Added
- Standalone Duckwork plugin that backs up files and directory trees to any
  S3-compatible object store (AWS S3, Cloudflare R2, MinIO, …) and
  restores, lists, or safely removes remote objects.
- Four structured tools: `s3-push`, `s3-pull`,
  `s3-ls`, `s3-rm`.
- A `duckwork s3` CLI subtree (`push`, `pull`, `ls`, `rm`) with
  positional and `--local`/`--remote`/`--rule` forms.
- Named backup rules via a YAML file (`{date}`, `{ts}`, `{year}`,
  `{month}`, `{day}` placeholders) for reusable push/pull targets.
- Safe-by-default behavior: `push` skips existing objects unless `--force`;
  `pull` validates destination paths (including symlink resolution); `rm`
  requires `--confirm` (and `--recursive` for prefixes).
- Hermetic test suite (`scripts/test-s3-backup.py`) using a fake S3
  client and fake plugin context — no network or real credentials required.
- Bundled `s3` skill with usage guidance and safety rules.
- Pixel-art logo.

### Notes
- Storage uses `boto3` directly (lazy-imported, so the plugin loads
  without it installed); no AWS CLI shell-outs.
- Configuration and credentials are environment-driven; secrets belong in
  `~/.duckwork/.env` or the process environment and are never committed.
