# Hardlight UI design

Created: 2026-10-20

## Product and scope

Hardlight UI is a standalone, MIT-licensed native Duckwork plugin for distinctive frontend design and demonstrably navigable websites and apps. It replaces the static-guidance role of Impeccable without copying its source, assets, or license-restricted text. The plugin uses the user's existing capable model and browser tools; it is not a second agent runtime or a component framework.

The approved conversation scope is a shareable gateway plugin, practical tools, broad artistic direction, navigation and real UI states, browser evidence, examples, tests, and a public GitHub repository. Naming settled on Hardlight UI. No live installation, incumbent-skill removal, Duckwork-core/config edit, service reload, or other-profile modification is included. Public repository ownership is the authenticated GitHub account. Source and publication are distinct from activation.

## Acceptance criteria

1. Real native `plugin.yaml` + `register(ctx)` registration; five working tools, `/hardlight`, and a bundled frontend skill. A short stable discovery pointer may be registered in new-session prompts; no per-message rewriting, blanket hooks, hidden inference, telemetry, remote fetches, or persistent daemon.
2. At least sixteen original design grammars across historical and contemporary art direction, modern product UX, editorial, commerce, and experiential work. Each supplies concrete structure, type, palette roles, imagery/material, motion, interaction, mobile adaptation, appropriate use, and failure conditions. No industry-to-style stereotypes or universal bans on glass, gradients, cards, serif, monospace, or minimal/maximal expression.
3. Research covers current curated galleries, actual product/campaign sites, primary design systems, and accessibility/interaction standards. References record URLs and distinguish visual inspiration, publisher claims, and normative requirements. Awards are not evidence of task success. No copied site templates, branded assets, testimonials, metrics, or claims of proven superiority.
4. Navigation is designed before surface polish: user jobs, destinations, labels, global/local navigation, current location, direct links, Back/Forward behavior, mobile topology, search/filter state, keyboard paths, recovery and permission states. A deterministic graph tool reveals unreachable routes, missing targets, ambiguous labels, dead ends and task-path budgets. Shortest paths are structural evidence, not usability certification.
5. No generic template composition as a default. Every new design must articulate a product-specific thesis, three structurally different alternatives when direction is open, one coherent signature idea, a real asset plan, and a navigation rationale. No invented proof or decorative nonfunctional controls. Mechanical checks never produce an 'AI-slop score' or certify artistic quality.
6. Read-only bounded local inspection returns file/line findings and existing CSS tokens. It never executes project code, reads secrets, recursively follows symlinks, changes project files, or calls the network. Truncated/unsupported coverage is explicit, not a clean pass.
7. Deterministic contrast uses the WCAG sRGB formula and unrounded thresholds. Unsupported colors are errors/unknown, not passing. Ordinary text 4.5:1, large text 3:1, UI boundaries 3:1; role selection is explicit.
8. Optional browser runner uses Playwright with installed Chrome or installed Chromium, never installs a browser automatically. It captures wide/narrow/reduced-motion evidence and bounded computed DOM findings. Local-file and literal-loopback HTTP targets only; external network blocked. It does not click destructive actions or claim WCAG conformance from partial automated checks.
9. Three authored working examples differ in structure and interaction, not just colors: editorial/reading, task-oriented workspace, and expressive/event or cultural surface. Meaningful content works without JavaScript; enhanced controls work with keyboard and pointer; mobile composition, focus, state feedback, reduced motion and real internal links hold. Examples are illustrative, not empirical before/after benchmarks.
10. Unit/CLI tests, real native loader/tool dispatch tests, Chrome visual/interaction checks, plugin doctor/validation and remote exact-head CI. Public README, MIT license, CONTRIBUTING, SECURITY, issue/PR templates and CI support community work. Source checkout and distributable archive are scanned for credentials/private paths.

## Architecture

Python 3.10+ and stdlib for installed runtime. Browser development is optional (`playwright`); testing uses pytest. No host-owned secrets are accessed. Stateless pure functions are shared by the tool adapters and `python -m hardlight` CLI. Tool errors are JSON objects with `ok:false` and an actionable error; unsupported or partial checks never masquerade as passes.

Files:
- Root `plugin.yaml`, `__init__.py`, `pyproject.toml`, documentation and license.
- `hardlight/`: small modules for references, direction packets, inspection, contrast, graph navigation and optional browser runner.
- `data/atlas.json`: one source of truth for original artistic grammars and primary-source links.
- `references/*.md` and `skills/frontend-design/SKILL.md`: task-sized, on-demand workflow guidance.
- `examples/`: offline, original HTML/CSS/SVG/JS demonstrations.
- `tests/`: pure unit tests and optional native/browser integration, each layer labeled.

### Stable pure interfaces

All return ordinary JSON-serializable dictionaries. Namespaced root plugin imports must work under Duckwork without altering `sys.path` or monkeypatching core.

- `hardlight.library.get_reference(topic='index', style=None)` reads only allowlisted shipped references. Topics: index, atlas, style, workflow, navigation, states, typography, color, motion, review, systems, browser. `style` uses an exact atlas ID; unknown IDs/topics fail with available choices.
- `hardlight.direction.make_direction(brief, surface='product', authority='greenfield', styles=None)` preserves the exact brief, accepts surface marketing/product/reading/commerce/portfolio and authority refinement/extension/redesign/greenfield. Returns up to three reference-based candidate packets, IA questions, state matrix and verification plan. This is a deterministic planning aid, not generated original artwork or a scientifically ranked taste predictor. Refinement/extension preserve the incumbent; missing context is surfaced.
- `hardlight.inspection.inspect_project(root, max_files=120)` scans only a bounded set of frontend files; emits inventory, tokens, findings, skipped reasons and `coverage`. Default file-size budget 512 KiB, total budget 8 MiB, bounded directory/entry traversal, no symlinks or hidden/build/vendor/secret files. Findings are advisory with relative path, line, rule, severity and recovery. HTML may use HTMLParser; JSX/TSX regex findings must be labeled heuristic.
- `hardlight.contrast.check_contrast(pairs)` accepts 1..100 `{foreground,background,role,label?}` pairs. Colors are opaque #RGB/#RRGGBB; role text/large_text/ui. Return each ratio and threshold with deterministic status; reject invalid shape, booleans-as-numbers, missing data and unsupported color syntaxes.
- `hardlight.navigation.analyze_navigation(pages,tasks,home=None)` accepts up to 300 pages, each `{id,label,links:[{to,label}]}`, and up to 100 tasks `{name,start,goal,max_steps?}`. Reject duplicate IDs, malformed fields, empty labels and invalid budgets. Report unknown link targets, unreachable pages from home, ambiguous labels to different targets on one page, dead ends excluding explicit task goals, BFS task paths, optional over-budget results, and clear coverage/limitations. Cycles are allowed. Default home is first supplied page. No fixed 'three click rule'.
- `hardlight.browser.audit_page(target, output_dir, executable=None)` is an optional developer CLI API. It captures three viewports/modes and a JSON report, returns handles, bounds time and DOM samples, and cleans up all browser resources. Output directory is explicit. Browser errors, blocked requests, unavailable checks, screenshot limits and uninspected frames are visible. No external network or credentials.

Native tool names mirror these functions: `hardlight_reference`, `hardlight_direction`, `hardlight_inspect`, `hardlight_contrast`, `hardlight_navigation`. Native handlers receive an argument mapping and additive kwargs, return serialized JSON, and never call a shell. `/hardlight` gives help, styles and version, not synthetic command execution.

### Atlas schema

`data/atlas.json` is `{schema_version:1, styles:[...], sources:[...]}`. A style has `id`, `name`, `family`, `surfaces` (surface enums), `thesis`, `composition` (string array), `typography` (string), `palette` (`canvas`, `text`, `accent` opaque hex), `material` (string), `motion` (string), `interaction` (string), `mobile` (string), `use_when` (string), `avoid_when` (string), `signature` (string), and `source_ids` (array resolving in sources). A source has `id`, `title`, `url` and `kind` (standard/design-system/art-reference/product/curation). Design recommendations are original interpretations, not claims that a museum mandates a UI pattern.

Canonical style IDs: swiss-editorial, bauhaus-play, editorial-luxe, neo-brutalist, organic-humanist, kinetic-poster, cinematic-gallery, quiet-craft, deco-geometric, retro-future, systemic-product, data-atelier, wayfinding, illustrated-world, spatial-technical, expressive-material. Atlas author may refine labels, but keep IDs/interfaces stable.

## Verification and release boundaries

The smallest complete product is these tools plus authored guidance and working examples. Do not add a hosted service, design editor, Figma connector, browser extension or new model route. Existing Impeccable remains intact until a separately approved migration.

Native integration must load the plugin in an isolated HOME/DUCKWORK_HOME using actual Duckwork discovery/registration/tool dispatch, then unload cleanly. Test missing capabilities with actionable diagnostics; do not silently register unsupported hooks. An installed version string alone does not prove API presence, so check callable registration surfaces.

Browser proof uses system Chrome if available. Static lint, graph reachability and computed contrast each have separate statuses. A screenshot is evidence to inspect, not automatic evidence of beauty or usability. Capture real initial states before engaged states.

Publication uses an explicit file set, no private evidence/history/user data, the authenticated owner's GitHub noreply identity, public visibility and MIT license. Verify remote tree SHA, repository visibility/license and exact-head CI after pushing. Do not enable cron/automated merges, submit to another owner's catalog, change account-wide settings or install the plugin without a separate request.
