# Security

## Scope

Duckwork SEO is a local plugin that processes user-selected URLs and may use provider credentials or external services when explicitly configured. The runtime launcher (`duckwork seo run`) restricts script execution to its allowlist and uses an isolated Python environment under Duckwork plugin data storage. Fetching code uses the source project's URL safety protections. The JSON-LD post-write hook is advisory and does not block or undo writes.

Local validation does not establish the safety or compatibility of external MCP providers, their credentials, or live endpoints. Keep credentials in Duckwork' secret/config mechanism; never commit them or include them in logs shared with others. Review data sharing and costs before enabling providers. Obtain approval before paid API calls, public submissions, or other externally mutating operations.

## URL and network safety

The bundled URL-fetching utilities use `scripts/url_safety.py` for URL validation and DNS protections. Read [the implementation](scripts/url_safety.py) and its tests before relying on a particular edge-case guarantee. Browser rendering has a different network stack and residual DNS-rebinding risk; do not use it against untrusted targets when that risk matters. Private-network targets are blocked by default. `CLAUDE_SEO_LOCAL_TARGETS` remains the source runtime's narrowly scoped top-level target allowlist; it does not make redirects or embedded requests generally safe. Do not broaden it casually.

## Installation and updates

This fork has no published release or catalog. Install from a reviewed local checkout and validate it with Duckwork. No `curl | bash` installer is shipped or recommended. The plugin tree should be treated as code and reviewed before updating.

## Reporting

Report vulnerabilities through the security reporting mechanism of the repository that supplied your checkout. The upstream source project is [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo); its security policy applies to that upstream repository, not automatically to this fork.
