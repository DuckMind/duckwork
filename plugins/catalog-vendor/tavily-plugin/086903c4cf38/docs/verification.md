# Verification record

Checked 2026-10-21 on macOS with Python 3.14.6.

## Current package

The bundle contains MCP-adapted Tavily skills from `tavily-ai/skills` at
`778122e5f9c680f541eeceda5a5b36405eb7980c`: Search, Extract, Map, Crawl,
Research, and Best Practices. CLI setup, Dynamic Search, and use-case skills
are outside this bundle. See [provenance](skill-provenance.md).

## Package checks

Eleven integration checks pass against:

- Duckwork stable 0.22.2: `d923a5eb487a17c0a68801bba9ef0f56c81040a8`.
- Duckwork development: `baf24532a1b95a07fd5505aadbe1faf169b4586b`.
- Additional development checkout: `46b5cfde4f120485183f447a22a75735e5e0b0e2`
  (upstream base `3f2afed3eb813cb00bd381d29b084d0e01de048f` plus a local,
  data-only catalog entry; submission remains paused).

The suite uses the real Duckwork admission validator, portable loader, plugin
manager, and `skill_view`. It verifies all bundled skill names, authoring metadata,
enabled/disabled discovery, every skill and reference file, the OAuth and
API-key examples, profile credential isolation, missing credentials under
multiplexing, attribution, and redirect boundaries.

A separate contract check validates the operational JSON examples against the
hosted MCP schemas captured on 2026-10-21. Schema discovery used the actual
OAuth connection and made no paid tool calls. The snapshot is test data, not
a runtime parameter allowlist; the connected server remains authoritative.

The example contract check covers all bundled skills and their reference guides,
including tool names, required fields, argument types, enum values, and numeric
minimums. Every executable example is an MCP argument object; no Tavily CLI or
SDK client programs remain. The rewritten Best Practices guides document the
same hosted interface, not direct API application development.

The exact `duckwork plugins validate . --install-deps --json` command passed
with `ok: true`, security verdict `safe`, no warnings, and `host_ready: true`.
Independent review found no remaining concrete correctness/security issue
after correcting the README's native-only connection-test instructions.

## Existing authentication and transport evidence

The MCP connection and authentication examples are unchanged from the
previously live-tested package. That verification covered real browser OAuth
login, fresh-process cached-token reuse, a real successful refresh after
simulated local expiry, and successful calls to all five tools. Every captured
MCP RPC used the stored OAuth token and exact `X-Client-Name: duckwork plugin`
header. API-key Search, Extract, Map, and Research also returned useful content;
its earlier Crawl run encountered empty results and HTTP 429, while the OAuth
Crawl run returned content.

## Actual CLI acceptance test

Package commit `53a4b3429eb8c51f20435c2bd2cd14565471632d` was installed from
GitHub into the dedicated `tavily-plugin-test` profile with `--force --no-enable`,
and confirmed enabled through the actual Duckwork CLI. Installation and the
earlier initial enablement passed; replacement preserved the enabled selection.
The native OAuth connection reused the user's completed login, and
`duckwork mcp test tavily` discovered all five hosted tools without browser consent.

A fresh CLI conversation using `mcp-tavily,skills`, `--query-file`, and
`--format stream-json` listed all qualified Tavily skills plus the separate
core `duckwork-agent` skill. It loaded the rewritten Best Practices skill and its
new `references/mcp.md` and `references/workflows.md` guides, discovered the
Search/Extract schemas, and made exactly one Search followed by one Extract on the
returned official URL. Both returned usable payloads, Extract had no failed
URLs, and the process exited 0 with a cited answer. Assertions inspected the
actual persisted tool results, rather than accepting the model's completion
claim or HTTP status alone. The loaded skill and guides matched the installed
candidate's full file contents.

- Search request: `4bf4ae62-4da1-4f98-914b-5e5ad37654af`.
- Extract request: `414f74f3-6197-4f96-9da4-ecf7f89d9d4b`.
- Source: `https://www.iana.org/domains/reserved`.

An earlier CLI test at `a2066f070625e61ef3d6fad1dd78b1c99d2a9038` also
loaded the Search/Extract skills and completed one request to each. That test
preceded the Best Practices rewrite; the test above covers the final content.

A separate live discovery observation checked outgoing requests against the
stored OAuth token and exact attribution header. It made no paid tool calls;
the CLI conversation itself was not instrumented to capture HTTP headers.

All twelve CI jobs for this package commit passed: Linux, macOS, and Windows
against the pinned stable/development versions, on both push and PR workflows.

### Local test environment repairs

The user's first manual test completed OAuth but failed to enable the plugin
because the machine's private package index returned HTTP 401. This did not
establish a package dependency conflict. A working native MCP connection alone
did not expose the disabled plugin's skills. The dedicated local launcher now
selects PyPI for that test process; global index settings are unchanged.

After successful admission, Duckwork selected a managed dependency environment
without its optional MCP SDK. Installing the host's declared feature through
`duckwork pm install --extra mcp` restored HTTP MCP support. This is a host
dependency, not a Tavily CLI requirement or a plugin runtime dependency.
An initial chat command was rejected before model execution because this
development revision's gateway does not accept `--run-budget`; the successful
test omitted that unsupported flag. Neither setup failure made paid Tavily calls.

## Evidence limits

- Check the draft PR's exact commit and CI status before release.
- A successful MCP connection test does not prove plugin enablement or skill
  discovery; verify those separately in a fresh session.
- Revoked-token/consent-denial behavior and long `pro` Research were not live-tested.
- Attribution is verified on outgoing requests; production analytics ingestion
  was not queried.
- Skills guide model behavior; they do not enforce deterministic request quotas.
- The examples are checked against captured hosted schemas. Not every example
  or error branch has been exercised with a paid live call.

The repository remains internal. The public-clone prerequisite and maintainer
catalog review are not complete, so catalog submission remains paused.
