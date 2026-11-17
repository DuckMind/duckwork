# Hardlight UI implementation plan

> For Duckwork: use subagent-driven-development with a fresh implementer and ordered specification then quality review.

**Goal:** Publish a working, openly contributable frontend design plugin with artistic breadth and tested navigation tools.

**Architecture:** Five stateless Python tools share pure functions with a CLI. An original data atlas and lazy references supply artistic/UX depth; an optional Playwright/Chrome runner supplies real rendered evidence. Native integration uses supported Duckwork plugin APIs only.

**Tech stack:** Python 3.10+, stdlib runtime; pytest development; Playwright optional browser development; static offline HTML examples; GitHub Actions.

## Boundaries and shared contracts

Read `design.md` as the authoritative acceptance contract. No live Duckwork, incumbent skill, other-profile or system-config edits. No external publication by children. Child writers own disjoint files, do not commit or reset the shared worktree, and return exact changed paths and test outputs. Parent owns commits, integration, release and documentation. Public code never includes machine-local paths or credential material.

The native registry contract comes from installed Duckwork and official plugin docs, not a DummyContext alone. A tiny Python CLI golden shape (pure function, explicit JSON output, explicit exit codes) is applicable. TMG business-domain frozen cases are not applicable because this plugin performs no business-source operations. Adversarial paths and native fixture integration substitute for that unrelated suite.

## Task 1: Freeze native registration and content contracts

**Files:** `docs/plans/initial-release/design.md`, this plan, `implementation-notes.md`.

1. Verify public plugin APIs from current installed source and official docs, including tool-handler shape, skill registration, command callback, prompt-section signature and native load/unload fixtures.
2. Record exact verified paths and compatibility limits in implementation notes; no unsupported hook names.
3. Confirm graph/color/atlas interfaces in design are consistent and no secrets/absolute host paths are in public docs.
4. Commit the design/plan before handing them to implementation.

**Check:** All five tool names, their pure signatures and the atlas schema have one owner and a checkable contract.

## Task 2: Build native runtime and four core tool adapters (lane A)

**Owned files:** root `__init__.py`, `plugin.yaml`, `pyproject.toml`; `hardlight/__init__.py`, `__main__.py`, `library.py`, `direction.py`, `inspection.py`, `contrast.py`, `cli.py`; `tests/test_core.py`, `test_cli.py`, `test_registration.py`.

Implement after actual RED coverage in vertical slices:
1. Shipped reference lookup with strict allowlist and atlas validation; unknown topic/style diagnostics.
2. Direction packet preserves user brief, explicit surface/authority, up to three complete diverse grammar candidates, unknown-context handling and state/navigation/verification requirements. Never invent user product truth.
3. Bounded no-symlink static project inspection, CSS-token extraction and source-evidenced advisories. Handle unreadable/large/binary/unsupported files, unsafe roots and traversal exhaustion honestly.
4. Exact WCAG opaque-hex pair checks using unrounded ratio comparisons.
5. Native manifest + five tool adapters (navigation module from lane C), skill registration, help command and optional stable new-session discovery pointer. Capability absence is actionable; no hidden fallback hooks.
6. CLI `python -m hardlight styles|reference|direction|inspect|contrast|navigation|browser`, JSON output and nonzero errors. Browser import is lazy and only occurs for that subcommand. Prefer JSON input files for complex graph/pair inputs; document exact command syntax.

**Contract probes:** invalid mapping/enum/list sizes; reference traversal; duplicate schema IDs; unsupported colors; same-color 1:1 and black/white 21:1; symlink escape; file/byte/directory budgets; malformed JSON; native schema/handler signatures; help/no network at registration.

**Run:** `python -m pytest tests/test_core.py tests/test_cli.py tests/test_registration.py -q`. When another lane's module is pending, report that dependency rather than weakening tests. Save RED evidence privately; no fake success.

## Task 3: Author artistic atlas and task-sized design craft (lane B)

**Owned files:** `data/atlas.json`; `references/workflow.md`, `navigation.md`, `states.md`, `typography.md`, `color.md`, `motion.md`, `review.md`, `systems.md`, `browser.md`; `skills/frontend-design/SKILL.md`; `tests/test_library_data.py`; `docs/research.md`.

1. Research current galleries and actual product/campaign sites, primary systems/standards and art/design collections. Publish a concise source map with precise evidence labels, extraction date and gaps. No false assertion that awards prove usable UX.
2. Author sixteen original complete grammars matching the frozen schema and canonical IDs. Validate every source ID, unique style/source ID, palette shape, surface enum and required field.
3. Skill leads with task and established identity, then original art direction, meaningful alternatives, functional navigation, state completion and rendered review. Explicit no-slop rubric: product-specific thesis/asset/composition, real controls, no invented proof or generic card-grid reflex.
4. References include navigation mental models and decision tables, keyboard/APG behavior, mobile adaptation, empty/loading/error/permission/offline states, token roles and extraction, typography, authored motion/reduced motion, and a visual review rubric with evidence and tradeoffs rather than taste scores.
5. The Green Lantern reference is subtle naming only; no DC logo, character asset or green-only house aesthetic.

**Check:** `python -m pytest tests/test_library_data.py -q`; all source and grammar IDs resolve. Any unverified source remains an inspiration pointer or explicit gap, not normative evidence.

## Task 4: Build graph navigation and optional Chrome inspection (lane C)

**Owned files:** `hardlight/navigation.py`, `hardlight/browser.py`; `tests/test_navigation.py`, `test_browser.py`; `tests/fixtures/` only navigation/browser-owned fixtures.

1. RED then GREEN for BFS task paths, cycles, disconnected routes, missing link targets, ambiguous same-page labels, terminal/dead-end distinction and task-specific max-steps (edge count). Test malformed IDs/links/tasks, boolean budgets and size caps.
2. Optional browser runner takes explicit local HTML/file URI or literal-loopback HTTP target. Deny non-loopback hosts, credentials, fragments where unsafe and all external network; reject cross-origin redirects. Do not derive trust from hostname substrings or DNS assumptions.
3. Discover installed Chrome or installed Playwright Chromium; no install/network during registration. Capture 1440x1000, 390x844 and 390x844 reduced-motion. Bounded DOM checks include overflow, missing names/labels, duplicate IDs, broken images and conservative computed text contrast with unsupported painted backgrounds marked unknown.
4. Save initial-state PNGs and JSON report to explicit output dir. Record page/console errors and blocked requests. Handle unavailable Playwright/Chrome, timeouts and oversized pages; close every browser/context/server resource.

**Run:** `python -m pytest tests/test_navigation.py tests/test_browser.py -q`; browser-marked tests require explicit opt-in and report missing deps honestly. A test network guard must prove denied remote navigation.

## Task 5: Build three structurally original demonstrations (lane D)

**Owned files:** `examples/index.html`, `editorial.html`, `workspace.html`, `expressive.html`; `tests/test_examples.py`.

1. Write a short direction contract per example. Distinct topology: editorial reading/index, task-operating workspace, expressive event/cultural work. Not one template in three palettes.
2. Author original content and SVG/CSS artwork, no external fonts/assets/network/CDN. Real anchors and functioning input controls, no fake login/checkout or invented metrics/testimonials. Clearly label illustrative product/task data.
3. Support JS-off content, keyboard navigation and visible focus, mobile layouts, clear selection/current location, search/filter or sorting where relevant, recovery/empty state, reduced motion and valid form labels.
4. Test semantic source structure plus real Chrome wide/narrow/engaged states. Screenshots/evidence stay in private artifacts until parent chooses an original showcase image for publication.

**Run:** `python -m pytest tests/test_examples.py -q`; parent inspects rendered screenshots, clicks core paths, uses keyboard and checks history/mobile/reduced-motion behavior.

## Task 6: Integrate and verify the product

**Parent-owned:** README, LICENSE, CONTRIBUTING, SECURITY, CHANGELOG, `.gitignore`, `.github/` workflow/templates, implementation notes and verification report.

1. Collect child return handles; independently read source and rerun full tests. Resolve integration incompatibilities through an implementation child, not unreviewed controller code patches.
2. Exercise real isolated native discovery, tool registry dispatch for all five tools, skill visibility, command invocation and unload. Run plugin doctor/validation against the same exact candidate. Isolate both HOME and DUCKWORK_HOME before imports.
3. Run Chrome runner and real interaction tests on all three examples at wide/narrow plus reduced-motion, and visually inspect actual screenshots. Fix concrete failures before review.
4. Commit the candidate. Fresh spec reviewer checks every numbered design acceptance criterion, followed only after PASS by fresh quality/security reviewer on the exact tree. Maximum one initial plus one corrective rerun per role; batch all blockers into one remediation cycle.
5. Report remaining limitations without inventing comparative effectiveness. A loaded plugin and authored demos do not prove a statistical advantage over Impeccable.

## Task 7: Publish and verify community readiness

1. Scan only the intended public file set for secrets, private paths, copyrighted copied assets and dependency bloat. Include public docs, explicit MIT license, issue templates, PR template, contributor recipe for adding a grammar and required tests.
2. Create `nosliwhtes/hardlight-ui` explicitly public with an accurate description. Push reviewed source; no other account settings/catalog/cron changes.
3. Read back visibility, license, default branch and exact remote commit; run and inspect hosted CI for that SHA. Remote absence/failure is not local success.
4. Build a clean distributable ZIP from the public tracked tree, verify its manifest/CRC, and hand off repo URL plus observed verification. No live installation.
5. Checkpoint proper wiki project note, folder index, daily Session and Mnemosyne with readback. If activation is still pending, status says published/not-installed.
