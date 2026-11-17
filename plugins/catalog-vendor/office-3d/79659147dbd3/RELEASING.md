# Duckwork bundled Office 3D release notes

Upstream source is pinned in `UPSTREAM.json` (MIT, v1.4.4); preserve LICENSE.
Do not use upstream standalone installers or publish this package independently.
The parent release integrates the desktop entry through the existing bundled
loader, audits the allowed public plugins tree, and repins the catalog to the
actual DuckMind public commit/subdirectory. Never invent a future SHA.

Before release, run the focused backend suite, real SDK registration tests,
admission validator and isolated Canvas/browser tests documented in README.md.
The browser runner accepts `CHROME_BIN` for an already-provisioned PM browser.
The pose negative control requires an uncommitted upstream fixture and is
explicitly skipped without it; it is not a passing pose test.

The agent tool remains opt-in; never broaden untrusted plugin loading or alter
approval/consent gates in order to show the bundled office page.
