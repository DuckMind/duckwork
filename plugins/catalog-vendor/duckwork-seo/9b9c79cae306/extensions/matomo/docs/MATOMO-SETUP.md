# Matomo setup

The fork retains Matomo reporting scripts. Store `MATOMO_URL`, one of
`MATOMO_API_TOKEN` or `MATOMO_TOKEN`, and optionally `MATOMO_SITE_ID` or
`MATOMO_IDSITE` in the active Duckwork profile vault. The native tool resolves
these names through `agent.secret_scope.get_secret()` and gives them only to
`matomo_auth.py` or `matomo_report.py`. There is no plugin `matomo.json`,
ambient-environment, or CLI credential setup path. Use a read-scoped token and
never commit, pass, or print it.

Ask for approval before the external Matomo request, then call the native tool:

```json
{"script":"matomo_auth.py","args":["--check","--json"]}
{"script":"matomo_report.py","args":["check","--json"]}
{"script":"matomo_report.py","args":["organic","--json"]}
```

Other reports include `top-pages`, `device`, `country`, `referrers`, and `keywords`; check each script's `--help` for supported options. `organic` uses the Matomo `referrerType==search` segment and may not match GA4's channel grouping.

Requests pass through the shared URL safety checks. Private and loopback
targets are refused unless the exact host or host and port is stored as
`DUCKWORK_SEO_LOCAL_TARGETS` in the active Duckwork profile vault. The native tool
injects that nonsecret setting only for the two Matomo scripts. Redirects and
cloud metadata addresses remain protected. Review [SECURITY.md](../../../SECURITY.md).

A successful `matomo_auth.py --check` confirms API reachability and credentials only. This fork has not verified a live Matomo integration. Historical installer instructions and credential paths in source documentation do not apply.
