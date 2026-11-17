# Verification

Verified on macOS on 2026-10-25 using the official Duckwork source at `4dcef215cfe41bd2d02c2d1dad6e257a18101216`, with its PM-prepared Python 3.14.9 runtime in an isolated development home.

- `duckwork plugins validate /path/to/plugins/duckwork --install-deps --json`: passed; portable package, host ready, security scan `safe`, no warnings.
- `scripts/check-duckwork-host.py` imports the real Duckwork portable loader and remote configuration functions. It found all 15 Skills and 15 readable argument examples; both profile fixtures resolved their own authentication header, and missing or empty Keys failed closed. Strict redirect-header handling, the secret setting and `untrusted` server policy were preserved.
- `node scripts/sync-duckwork-plugin.js --check` passed. The Grok generator's check also passed after moving its unchanged task limits into the shared catalog.
- `npm run check:package` passed. The Duckwork package is distributed from Git; this change does not publish or alter an npm release.

To reproduce the host check, use the Python interpreter prepared by Duckwork PM, set `DUCKWORK_SOURCE` to that checkout, and run `python /path/to/flashdata-mcp/scripts/check-duckwork-host.py`. Select an isolated `DUCKWORK_HOME` before preparing or running Duckwork. The script uses non-secret fixtures only.

These checks made no FlashData network request, model call, paid query or customer-storage write. They verify packaging, discovery and configuration behavior, not live API results, agent task performance or storage delivery. Public source installation and catalog review are tracked separately; a source commit is not catalog approval.
