# Security Policy

## Scope and trust model

ard-kit indexes **local, operator-curated directories** and proposes — never
executes — commands. The security boundary is the user account running it:

- The HTTP registry binds to loopback only by default and has no TLS. Do
  **not** bind it to a non-loopback interface or tunnel it; put a hardened
  reverse proxy in front if remote access is ever required.
- **WSL2 caveat:** on WSL the loopback boundary is softer than on bare metal —
  with mirrored networking or `localhostForwarding=true`, Windows processes
  on the host can reach a loopback-bound service inside the VM. Treat the
  combined Windows+WSL machine as the trust boundary, not the WSL distro.
- `/health` is intentionally unauthenticated (liveness only).
- Federation (`--upstreams`) is **opt-in**. Enabling it sends every search
  query to the configured peers; only add peers you trust.
- The MCP front (`mcp_server.py`) is stdio JSON-RPC: one process per client,
  no listening socket, no shared state.

## Known limitations (by design, not bugs)

- Catalog entries carry **execution-shaped strings** (`metadata.invoke`,
  inspect sidecar). Paths are shell-quoted (`shlex.quote`) and symlinked
  files inside the scan root are skipped — but a catalog is only as
  trustworthy as the directory you point it at. Scan curated trees only.
- Docstrings and skill frontmatter are indexed verbatim. A malicious file in
  the scanned tree can inject misleading text into agent context. This is
  inherent to indexing; treat catalog content as untrusted input on the
  consumer side (agents should show inspect output to a human before
  running anything).
- The scanner reads file **metadata** (paths, docstrings, argparse help,
  frontmatter). It never executes scanned files.

## Supply chain

- Runtime: Python 3.10+ standard library only — zero required third-party
  imports.
- **One optional dependency:** `cryptography`, used by the trust plane
  (`ard-verify`, `trustManifest` JWS attestations) for Ed25519 verification
  when importable. Without it the runtime does not fail and does not guess:
  every signature check degrades to the `UNSUPPORTED` verdict (exit 1 on the
  CLI, never `VERIFIED`). Install it wherever trust verdicts are consumed —
  `pip install cryptography`; there is no `[trust]` extra yet. CI runs the
  trust suite on both arms (`.gitlab-ci.yml`).
- CI downloads the official conformance CLI pinned by SHA-256
  (`.gitlab-ci.yml`).

## Reporting

Open a confidential issue on
<https://gitlab.com/ameobius-ai/ard-kit/-/issues> or contact the maintainer
through the GitLab profile.
