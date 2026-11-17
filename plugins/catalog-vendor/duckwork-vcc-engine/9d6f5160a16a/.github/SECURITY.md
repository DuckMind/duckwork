<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Security policy

## Reporting a vulnerability

Please report security problems privately, not in a public issue. Use GitHub's **Report a vulnerability** button on the [Security tab](https://github.com/DuckMind/duckwork) of this repository. Include the Duckwork version, the plugin version, and the steps or input that trigger the problem.

## Supported versions

Fixes go into the latest release. The Duckwork plugin catalog pins an exact commit, so a fix reaches catalog users when the pin is updated and they run `duckwork plugins update duckwork-vcc-engine`.

## Scope

The plugin's runtime code is `__init__.py` and the `vcc/` folder. By design it makes no network calls of its own, runs no shell commands or subprocesses, reads no credentials or environment variables, and writes no files. Anything that makes it do one of these, or lets tool output change the summary's structure or inject instructions, is in scope. The full list of what the plugin does and doesn't do is in the README's [Security and privacy](../README.md#security-and-privacy) section.

The `bench/` scripts are run by hand and are not loaded by Duckwork. They read `~/.duckwork/state.db` read-only and write results to `~/.cache/duckwork-vcc-engine/`. Problems there are in scope too.
