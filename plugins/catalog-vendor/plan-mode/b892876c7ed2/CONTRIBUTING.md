# Contributing to Plan Mode

Thanks for helping improve Plan Mode, a plugin for [Duckwork Agent](https://github.com/DuckMind/duckwork).

## Reporting a bug

- Use the [bug report form](https://github.com/DuckMind/duckwork). Include the plugin version and source from `duckwork plugins list --json`, and `duckwork --version`.
- Your Duckwork agent can draft the report for you: ask it to "report a problem with Plan Mode". It shows you the draft and files nothing without your yes.
- Search [existing issues](https://github.com/DuckMind/duckwork) first, and add to a matching one instead of opening a new one.
- Security problems: report them privately. See [SECURITY.md](SECURITY.md).
- Problems in Duckwork itself belong in [Fordex/duckwork-agent](https://github.com/DuckMind/duckwork).

## Pull requests

- For anything bigger than a small fix, open or comment on an issue first so we can agree on the approach.
- Keep each PR to one change, and include the commands you ran and their output.
- Please don't change version numbers, create tags, or add a release heading to `CHANGELOG.md`. Maintainers cut releases. Notes under `## Unreleased` are welcome.
- Development setup, tests and repository rules are in [AGENTS.md](AGENTS.md).

## AI-assisted contributions

AI tools are welcome here. We ask that you:

- say in the issue or PR when an agent drafted it;
- review it yourself, and stay accountable for it, including answering review questions;
- include real test output, not a description of tests that should pass;
- open issues and PRs only when a person has decided to. Agents filing on their own are not welcome.

PRs that appear to be generated without a person involved (no linked issue, no test evidence) may be closed with a link to this section.

## Conduct

Be kind and assume good faith.
