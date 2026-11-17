# Hardlight UI

**Frontend design, shaped by imagination.**

A native [Duckwork Agent](https://github.com/DuckMind/duckwork) plugin for distinctive websites and apps that people can find their way through. Hardlight pairs artistic direction with working inspection, contrast and navigation tools. It is not a component library, a template reskinner or a second model service.

[Explore the examples](examples/index.html) · [Research and sources](docs/research.md) · [Contribute](CONTRIBUTING.md)

![Three original Hardlight demonstrations: Intertidal's asymmetric journal, Set's work list and inspector, and Afterimage's optical event poster.](docs/assets/showcase.png)

## Design a point of view. Keep the path clear.

Most frontend guidance stops at a list of aesthetic rules. Hardlight adds inspectable structure:

| Tool | What it returns |
| --- | --- |
| `hardlight_reference` | Task-sized craft references and an original artistic atlas, loaded on demand |
| `hardlight_direction` | A brief-preserving direction packet: structural alternatives, constraints, navigation questions, state coverage and a verification plan |
| `hardlight_inspect` | Bounded, read-only frontend findings and existing CSS tokens with file/line evidence |
| `hardlight_contrast` | Deterministic WCAG contrast calculations for explicit text, large-text and UI pairs |
| `hardlight_navigation` | Reachability, task paths, missing destinations, ambiguous link labels, dead ends and explicit path-budget overruns |

The bundled `hardlight-ui:frontend-design` skill makes these tools part of a complete design workflow. `/hardlight` shows help, styles and version. An optional local Chrome/Playwright runner captures responsive screenshots and computed DOM findings without a hosted service.

Modern-web craft is loaded on demand through the `layout`, `platform` and `performance` reference topics. The [platform ledger](data/platform-features.json) pairs exact capabilities with dated primary sources, detection, constraints and useful fallbacks. It covers container queries, subgrid, modern color, typography and optional native interactions without making experimental effects prerequisites for the task.

The installed runtime uses Python's standard library. No API key, extra model subscription, telemetry, hidden inference or background service is required. Browser development has an explicit optional dependency for Linux, macOS and Windows; mobile Python environments do not install Playwright.

## Artistic breadth without a house-style trap

The atlas spans Swiss editorial structure, Bauhaus-derived geometry, expressive typography, contemporary editorial, neo-brutalism, organic craft, cinematic storytelling, quiet restraint, Deco geometry, retro-futurism, productive workbenches, analytical displays, wayfinding, illustration, spatial/technical work and expressive material design.

These are **compositional grammars**, not color presets. Each connects layout, type, material, imagery, motion, interaction, mobile behavior and failure conditions. Select the task structure first, then a dominant grammar. A brand, platform convention or established design system takes precedence over a new style suggestion.

Research draws on actual websites, current curated galleries, design history, primary design-system guidance and W3C interaction/accessibility standards. Sources distinguish visual inspiration from usability evidence. An award does not prove task success, and an attractive screenshot does not prove a working interface.

## The no-slop standard

A design needs a product-specific idea that changes visible decisions. For an open direction, compare materially different structures rather than three accent colors.

- Let the actual product, content, original artwork or meaningful interaction carry the identity.
- Make navigation labels, location, primary task and recovery paths explicit.
- Build controls and real states, not decorative buttons or imaginary dashboards.
- Use real claims or clearly labeled illustrative content. Never invent customers, testimonials, metrics or benchmarks.
- Inspect the rendered result at wide and narrow sizes, with keyboard use and reduced motion. Fix observed failures.

Hardlight does not assign a numerical beauty or “AI-slop” score. Tools can expose concrete defects; artistic distinction and task clarity still require thoughtful design and rendered review. There is no blanket ban on cards, gradients, glass, serif, monospace, minimalism or maximalism. Ban failures, not styles.

## Install into Duckwork

Requires **Duckwork >=0.21.0** with native tool, command and bundled-skill registration. The plugin checks required registration methods and reports an actionable compatibility error rather than patching Duckwork internals. The optional stable discovery pointer uses the documented new-session prompt-section API when present.

Review the source before enabling any native plugin. The [official catalog](https://duckwork-agent.fordex.com/docs/plugins/hardlight-ui) installs its reviewed commit; a source release can be newer while its catalog update awaits maintainer review. Repository shorthand below installs directly from the source repository.

```sh
duckwork plugins install nosliwhtes/hardlight-ui --no-enable
duckwork plugins enable hardlight-ui
```

For a reproducible install, add `--ref` followed by the full 40-character commit SHA you reviewed. Use a new session or your Duckwork version's supported plugin reload path. Enabling on disk does not prove an already-running conversation loaded it; do not restart active work blindly.

Nothing in the installer removes Impeccable or edits another skill. If migrating, update your own project/agent instructions to use `hardlight-ui:frontend-design`, verify a real design task, then separately decide whether to archive the old skill.

## Use it

Ask Duckwork:

> Use Hardlight UI to design a cultural journal. Compare an asymmetric editorial direction with a typographic poster direction and an illustrated field-guide direction. Keep reading and section navigation obvious on mobile.

> Audit this existing app without rebranding it. Start with the three most important user tasks, inspect the current tokens, and identify broken navigation, inaccessible states and visual inconsistencies.

> Show whether users can reach the invoice export from the home screen. Report ambiguous labels, missing destinations and the exact task path. Do not assume fewer clicks always means better navigation.

For direct use from a source checkout:

```sh
python -m hardlight --help
python -m hardlight styles
```

The CLI shares the plugin's pure functions. Subcommand help documents direction, reference, inspection, contrast, graph input and optional browser arguments. Errors are explicit JSON with nonzero exits. No command automatically publishes a project or installs a browser.

### Supply context; author the design

`hardlight_direction` accepts optional explicit context alongside its existing arguments:

```json
{
  "brief": "Improve this print-room workbench while keeping its identity.",
  "surface": "product",
  "authority": "extension",
  "context": {
    "audience": "Print-room operators on shared tablets",
    "tasks": ["Find a job", "Leave a useful handoff note"],
    "identity": "Preserve the job-jacket structure and existing tokens",
    "browsers": "Current desktop and mobile browsers; functional fallback required",
    "constraints": ["Offline assets", "Session-only edits"]
  }
}
```

Omit unknown fields. String fields `audience`, `identity` and `browsers` accept up to 2,000 characters each. Lists `tasks`, `content`, `assets` and `constraints` accept 1–12 nonblank strings of up to 1,000 characters each, with a 16,000-character total context limit. Supplied facts are preserved; missing fields remain visible.

The returned `design_contract` is explicitly **awaiting host authorship**: the model must complete a subject-specific thesis, structural decision, visual rules, useful signature, mobile transformation, budget and critique. The verification matrix starts **not run**. Candidate grammars remain deterministic references; neither the context object nor a completed schema proves originality. See the [fixed-brief review protocol](docs/design-evaluation.md).

### Navigation input

`hardlight_navigation` accepts an explicit page graph and user tasks. For example:

```json
{
  "home": "home",
  "pages": [
    {"id": "home", "label": "Home", "links": [{"to": "reports", "label": "Reports"}]},
    {"id": "reports", "label": "Reports", "links": [{"to": "export", "label": "Export invoices"}]},
    {"id": "export", "label": "Export invoices", "links": [{"to": "reports", "label": "Back to reports"}]}
  ],
  "tasks": [{"name": "Export invoices", "start": "home", "goal": "export", "max_steps": 2}]
}
```

The path is a graph result, not a user-study result. Supply a budget when it serves the task; Hardlight does not impose a universal three-click rule. Cycles are valid, and explicit task goals are distinguished from accidental dead ends.

## Working examples

The offline examples are authored demonstrations, not before/after benchmarks:

- [Editorial](examples/editorial.html): reading, indexing and content hierarchy.
- [Workspace](examples/workspace.html): repeated tasks, selection and working state.
- [Expressive](examples/expressive.html): an art-directed cultural surface with explicit wayfinding.

Open `examples/index.html` in a browser. The pages use original local HTML/CSS/SVG and vanilla JavaScript, without external fonts, frameworks or network assets. Illustrative content is labeled.

[Read the example decisions and fallbacks](examples/README.md). Set demonstrates a container-responsive workbench, shared metadata alignment, text resizing and forced-colors treatment while preserving its existing task paths.

## Data access and execution disclosure

The `hardlight_inspect` tool reads frontend source files under the local directory supplied by the model, including directories outside the plugin. It scans at most 500 files and 8 MiB, skips hidden, symlinked, vendor/build and secret-named paths, and returns tokens and findings to the calling model. Choose the project scope accordingly.

The five native tools make no network calls, run no subprocesses and write no files. The plugin registers a short, stable system-prompt section naming its tools when the host supports that API. It does not access credential stores, run background services or self-update. The optional `hardlight browser` shell command launches a separately installed Chromium against local file or loopback pages, blocks external requests, and writes reports and screenshots to the explicitly chosen output directory.

## Verification and limits

Bounded source inspection requires POSIX no-follow, directory-relative file APIs. On unsupported platforms, including Windows, `hardlight_inspect` returns an explicit compatibility error rather than scanning unsafely; the reference, direction, contrast and navigation tools remain available.

Static source inspection is heuristic, especially for JSX/TSX and framework-generated semantics. File, byte and traversal limits are explicit; skipped coverage is not a clean pass. Contrast supports explicit opaque hexadecimal colors; gradients, transparency, imagery and unresolved colors need further inspection.

The optional browser runner accepts explicit local HTML or literal-loopback HTTP targets and blocks external network access. Reports and screenshots stay in the chosen output directory. Treat them as potentially private project evidence. Automated DOM checks do not establish full WCAG conformance, screen-reader usability, field performance or artistic quality. Review keyboard behavior, important states and real task completion separately.

These releases establish working capabilities, not an empirical claim that one plugin or model always produces better art than another. [Observed checks and limits](docs/verification.md) describe the local evidence; [the release contract](docs/plans/initial-release/design.md) makes the requirements and exclusions inspectable.

## Community

Contributions can improve artistic grammars, navigation analysis, accessibility rules, browser evidence and examples. Start with [CONTRIBUTING.md](CONTRIBUTING.md), include a concrete user task and a reproducible check, and open a pull request. CI runs for contributions; maintainers decide what ships. There is no automatic merge or live-profile mutation.

[Security policy](SECURITY.md) · [MIT license](LICENSE)
