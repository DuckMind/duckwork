# Contributing to Hardlight UI

Help people build interfaces with a point of view and a clear way through them. Contributions are welcome in art direction, navigation, accessibility, inspection rules, browser verification, examples, documentation and tests.

## Start here

1. Open an issue describing a real task, a concrete failure or a missing artistic approach. Include the relevant surface and what the user should be able to do.
2. Fork the repository and keep your change focused. Existing tests and public data IDs are compatibility contracts, not obstacles to delete.
3. Add a failing regression test or an observable example, implement the smallest complete improvement, and run the checks below.
4. Open a pull request with the problem, design rationale, test output and any limitations. Visual changes need wide and narrow screenshots; interaction changes need keyboard and state evidence.

## Development

The installed plugin has no third-party runtime dependencies. Use Python 3.10 or newer for the standalone tools; native integration requires a Duckwork build with the documented registration methods.

```sh
python -m venv .venv
# Activate the environment using your platform's normal command.
python -m pip install -e ".[dev]"
python -m pytest tests -q
python -m ruff check .
```

Browser development is optional. Install the browser extra and a browser explicitly in your development environment; the plugin never installs one for you.

```sh
python -m pip install -e ".[browser]"
python -m playwright install chromium
HARDLIGHT_BROWSER_TESTS=1 python -m pytest tests -q
```

On PowerShell, set `$env:HARDLIGHT_BROWSER_TESTS='1'` before running pytest. Installed Chrome is also supported. Consult `python -m hardlight --help` for the current CLI and browser options.

Native Duckwork checks are a separate layer. They must run with an isolated `HOME` and `DUCKWORK_HOME`, using the real plugin loader and tool dispatcher, not only a mock context. The native test module explains its opt-in/source-path requirements. Never point test installation or reload commands at your working profile.

## Add a design grammar

Edit `data/atlas.json`; do not add another parallel style registry. Keep IDs stable and unique. Every grammar needs a specific compositional idea, typography roles, palette roles, material/asset treatment, meaningful motion, interaction behavior, mobile adaptation, use/avoid conditions and a signature move. Link source IDs to verified primary sources or clearly labeled visual inspiration.

A new color combination is not a new grammar. Show what changes about hierarchy, composition, information flow or interaction. Do not stereotype a culture, industry or audience into one aesthetic. Do not copy a site's text, code, logo, imagery or trade dress.

Run `python -m pytest tests/test_library_data.py -q`. If your change establishes a new behavior class, extend the tests. Treat normative accessibility requirements separately from original artistic recommendations.

## Add a platform recipe

Keep capability facts in `data/platform-features.json`, not in another style registry. Name the exact subfeature, primary source, checked date, design job, detection, constraints, baseline fallback and observable verification. Adoption tiers are recommendations, not browser compatibility promises. Add an enhancement only when a concrete task benefits; test with the enhancement unavailable. Keep the topic allowlist shared between the native schema and reference lookup, and check packaged resources as well as source files.

Brief-context changes must preserve old calls and explicit style IDs, validate bounds, avoid mutating caller data and distinguish unanswered worksheets from authored design. Use the fixed-brief protocol for human assessment; static tests cannot establish prompt effectiveness or artistic superiority.

## Add an inspection rule or navigation check

Supply a positive fixture, a negative fixture and a case where the answer is unknown. Findings need an actionable explanation and source evidence. Keep scans bounded and read-only; do not execute a project's configuration, follow symlinks, inspect secrets, change files or silently access a network. Never turn heuristic findings into a claim of complete accessibility compliance.

Navigation improvements should explain the task, starting point, destination, labels and recovery path. Do not impose a universal click count. A shorter path is not automatically a clearer path.

## Visual contribution standard

- A product-specific idea, not a template with different colors.
- Real content or clearly labeled illustrative data; no fabricated customers, testimonials, metrics or benchmarks.
- Working controls, native semantics, visible focus and recoverable states.
- Mobile composition and keyboard use tested, not inferred from desktop screenshots.
- Honest performance and accessibility coverage. No numerical beauty or AI-slop score.

No automatic merge bot is used. Maintainers review contributions and retain the release decision. Opening a pull request does not authorize a live installation or any change outside this repository.

By submitting a contribution, you agree it may be distributed under the repository's MIT license. Keep attribution and provenance for any third-party material you are permitted to include.
