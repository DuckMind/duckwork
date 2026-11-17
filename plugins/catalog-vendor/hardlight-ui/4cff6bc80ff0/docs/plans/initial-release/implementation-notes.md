# Initial-release implementation notes

Created: 2026-10-20

## Runtime contracts

- Use native `plugin.yaml` and `register(ctx)` with five declared tools, one command and one namespaced bundled skill. Required registration methods fail with actionable diagnostics; the static discovery section is optional when its documented API is unavailable. There are no lifecycle hooks or request-rewriting fallbacks.
- Tool schemas are function objects, not outer OpenAI wrappers. Handlers accept one argument mapping and additive keyword arguments, returning serialized JSON. The command receives one raw string. Native loader/registry tests verify these contracts independently of the recording-context tests.
- Registration is dependency-free. The CLI and adapters share pure functions; browser imports happen only on explicit browser use. Wheel builds include the atlas, references and skill beneath the installed package. Source checkout installation remains the native-plugin path.

## Deliberate compatibility limits

- Source inspection requires POSIX no-follow and directory-relative descriptor APIs. Unsupported platforms, including Windows, return an explicit compatibility error rather than following unsafe paths. Other standalone tools remain available. Cross-platform CI distinguishes this from native-host compatibility.
- Contrast accepts only opaque hexadecimal sRGB pairs and explicit caller-supplied roles. Static markup findings, computed DOM checks and graph paths have different coverage and never certify usability, artistic quality or WCAG conformance.
- Browser evidence covers three initial-state captures. Interaction tests are a separate layer. The runner uses an installed browser, does not download one, and is not an operating-system sandbox for hostile local pages.
- Workspace example edits are session-only, not a promised backend. All examples contain visibly fictional content and original local assets.

## Discovered failure classes and verification method

- Chromium may follow an HTTP redirect without another route callback when a request is continued. Fetch with redirect following disabled, inspect `Location`, then fulfill or block. Direct and chained cross-origin tests require zero requests at the denied sink.
- CSS `color` does not always describe glyph paint. Differing/transparent/unsupported text-fill, nonzero text-stroke and non-HTML/SVG text remain unknown in the browser check. Real Chrome regressions include measured passing and failing ordinary-text controls, so disabling contrast cannot satisfy the tests.
- Opaque `background-color` does not prove the effective backdrop. Inset box shadows and non-default background clipping on the text element or bounded ancestors remain unknown with explicit reasons and no ratio. Real Chrome regressions retain ordinary black/white, low-contrast and outer-shadow controls; multiple shadows and clipping aliases are covered.
- Canonical evidence must not retain an earlier success after setup fails. Exercise invalid targets, missing browser and navigation failures against an existing recognized report, as well as a successful control. Atomic report writes and cleanup are part of the result contract.
- Test literal user-input rendering, hidden-fragment focus/scroll, mobile navigation order and Back to the initial unfragmented workspace state. A matching URL alone does not prove the selected panel became reachable.
- Run Duckwork Doctor against a clean explicit public staging tree. Passing a development checkout containing private virtual environments caused a bounded timeout; clean staging passed. Doctor copies its input directory, so never hand it private evidence or an entire development environment. Keep HOME and DUCKWORK_HOME isolated before Duckwork imports.
- Keep build tools in a project-private environment. A missing `build` module in the host development interpreter is a tooling failure, not a successful package build; use the isolated build environment and exercise installed-wheel resources outside the source checkout.
- Verify declared development extras in a fresh private environment, not just a richer host environment. Paint regressions use pytest 9's built-in subtests fixture; requesting pytest 8 produced a clean-install setup failure. The development-only requirement now matches that interface while runtime dependencies remain empty.

## Evidence and scope

`docs/research.md` records primary sources, visual observations, failed/redirected captures and interpretation limits. Third-party screenshots stay private. `docs/assets/showcase.png` contains only the original demonstrations.

The frozen release contract and public tests are the acceptance record. Reviews apply to an immutable candidate. Publication, remote CI and live activation are separate states. No live installation, existing-skill removal, Duckwork-core edit, service restart, external catalog submission or recurring job is authorized by this source release.
