# Verification and evidence limits

## v0.2.0 release candidate — 2026-10-23

Fresh release validation passed **163 tests and 91 subtests**, with one native test explicitly deselected and no skips, on Python 3.12.3 and installed Chrome 155. Ruff and whitespace checks passed. Wheel and source distribution builds passed; the source distribution now includes the changelog. Package, plugin, command and bundled-skill versions are aligned at 0.2.0, with `requires_duckwork: ">=0.21.0"` matching the existing catalog floor.

The native dispatch contract also passed in a fresh Python 3.14.7 process against upstream Duckwork `290080e19e8e143d35f67427e89aed662161faf8`: five tools, reference/context paths, invalid inputs, skill/command/prompt registration and clean unload. HOME, DUCKWORK_HOME and runtime paths were temporary before imports; no model or live profile was used.

Current upstream catalog admission validation with dependency preparation (`duckwork plugins validate --install-deps`, invoked through its command handler) passed **15 checks with no warnings**, including a safe install-security scan, matching registered capabilities and no core overrides. This used a clean copy of tracked plugin files and an isolated HOME/runtime. The first preparation attempt exposed unsupported Android Playwright resolution through the optional browser extra; platform markers now restrict that extra to Linux/macOS/Windows. The repeated dependency preparation completed successfully. No required runtime dependency was added.

These results support packaging and native compatibility, not a full accessibility audit, model-output benchmark or field-performance claim. The earlier implementation plans describe their original source-PR scope; the separately authorized release and catalog update follow the [official update process](https://duckwork-agent.fordex.com/docs/developer-guide/plugins/catalog-submission#updating-your-entry).

## Modern-web craft extension — 2026-10-22

The extension's local run used Python 3.12.3, pytest 9.1.1 and installed Chrome with the declared optional Playwright extra. `HARDLIGHT_BROWSER_TESTS=1 python -m pytest tests -q -m 'not native'` passed **161 tests and 91 subtests**, with **one native test explicitly deselected** and no skips. Ruff passed; wheel and source distribution built. An isolated environment installed the built wheel with no dependencies and resolved all sixteen styles, twelve craft references and eleven capability entries, plus a contextual direction packet, from outside the checkout.

The native contract in `tests/test_registration.py` was separately executed in a fresh subprocess using the installed Duckwork interpreter (Python 3.14.7) and source whose HEAD was `65edd88bf342012bbe5c64ac098f203c72f5fe3b`. HOME and DUCKWORK_HOME were temporary before host imports, discovery was suppressed, and no model was called. All five tools dispatched, new platform/context and invalid-context paths passed, skill/command/discovery registration resolved, and unload was clean. This was isolated compatibility evidence, not installation or activation in a working profile.

New Set coverage exercises 320/390/768/1440 widths, 200% root text size, an embedded 540px region, CSS-enhancement removal, RTL geometry, forced colors and actual keyboard focus. Existing search/filter/edit/history, literal note rendering, reduced-motion and JavaScript-off checks remain. Modern OKLCH and mixed-color paint fixtures return unknown rather than a fabricated contrast pass. Initial and engaged screenshots were inspected; [wide](assets/workspace-wide.png) and [narrow](assets/workspace-narrow.png) original-example captures are included.

The test harness initially exposed viewport-dependent selection behavior when a workbench was narrow inside a wide page. Set now uses the actual stacked geometry to reach the selected jacket. A focus assertion was corrected to use real Tab navigation, since programmatic focus after pointer input does not necessarily match `:focus-visible`.

Limits: Chromium only locally; no local Firefox/WebKit or translated-content review, full browser-zoom/assistive-technology audit, field performance, user study or model-output comparison. A doubled root font is a text-resizing check, not proof of every zoom mode. The direction worksheet and fixed briefs establish explicit contracts and reproducible future review inputs; they do not prove behavioral superiority of a prompt. The repository's hosted CI remains separate evidence for the PR revision.

## Initial-release evidence

These are observed local checks for the initial 0.1.0 source candidate, not a claim of comparative design effectiveness. Hosted checks for a particular revision are visible in the repository's Actions tab.

## Local checks

The final local combined run used Python 3.11.16, pytest 9.1.1 and system Chrome 155.0.8059.84:

```sh
DUCKWORK_SOURCE=/path/to/duckwork-agent HARDLIGHT_BROWSER_TESTS=1 \
HARDLIGHT_CHROME=/path/to/installed/chrome python -m pytest tests/ -q
python -m ruff check .
python -m build
```

Observed results: **133 tests passed, 81 subtests passed, no skips**; Ruff passed; wheel and source distribution built. The installed wheel was exercised from an isolated Python environment outside the checkout, with no third-party runtime dependencies. All sixteen style packets and nine craft references resolved, the CLI returned JSON, and missing optional browser dependencies produced an explicit failure instead of an installation.

A separate fresh environment installed only the declared `.[dev,browser]` extras and passed **132 tests and 81 subtests without skips**; its single native-host test was explicitly deselected and was exercised in the combined run above. The development requirement is pytest 9 because the paint regressions use its built-in subtests fixture; this adds no installed-runtime dependency.

The native test is a fresh subprocess with isolated HOME/DUCKWORK_HOME and the actual Duckwork PluginManager/registry. It dispatches all five tools, resolves the bundled skill, invokes the command, renders the discovery section and verifies unload. Native compatibility depends on registration APIs, not merely a version label. CI separately pins a public Duckwork revision for its manually requested native job.

Duckwork Doctor against a clean public staging tree loaded five tools and zero hooks. The JSON validator passed all fourteen checks without warnings. The bundled skill's selected static schema, Unicode and quality checks passed, with quality **100.0/100**. That is a documentation-quality measurement, not an artistic or security certification.

## Browser and interaction coverage

- Initial wide, narrow and reduced-motion captures cover the three authored demos; the gallery is also exercised by viewport tests.
- Interaction checks cover passage search and recovery, workspace selection/filtering/session edits, literal input rendering, cultural-program filters/disclosures, keyboard focus, direct fragments, browser Back, gallery return paths and meaningful JavaScript-off content.
- Negative browser checks cover denied targets, direct/chained cross-origin redirects, credential-bearing requests, unsupported contrast paint, missing browsers, setup/navigation failures and fresh-report replacement. Paint regressions include text-fill/stroke/SVG, inset shadows, multiple shadows and non-default background clipping on elements and ancestors, with ordinary passing/failing text and outer-shadow controls across all three captures. A denied sink must receive no request.
- A simulated cp1252 default exercises the actual example-source readers. This is regression coverage on Linux; it is not a claim that a Windows browser was run locally.
- Installed system Chrome is the real local browser path. Playwright Chromium discovery/cleanup has deterministic tests, but its real fallback launch was unavailable locally. The hosted browser job explicitly provisions Chromium and rejects skipped browser checks; inspect that run's evidence separately.

Private research captures, local project paths and test logs are not distributed. The public showcase contains only original example screenshots.

## What these checks do not establish

No user study, conversion experiment, screen-reader matrix, full WCAG audit, field Core Web Vitals measurement or statistical comparison with Impeccable was performed. The local browser runner samples initial main-document states and conservative findings; it does not click through an application or replace interaction testing. Unknown paint, iframe/shadow content, truncation and untested states are not passing results.

Source inspection needs safe POSIX no-follow/directory-relative APIs and returns an explicit unsupported-platform error otherwise. The runtime does not install itself, remove another skill, mutate a live profile, publish projects or fetch design references automatically. Source publication and successful tests are separate from activation in any running Duckwork process.
