# Upstream historical migration note: Claude SEO v1 to v2

> **Provenance:** The material in this file concerns migration between upstream Claude SEO versions. Its CLI names, install steps, filesystem paths, release facts, test counts, and compatibility claims do not describe the Duckwork port. Consult the source project's release history for current upstream guidance.

The Duckwork fork derives from the upstream codebase and retains selected scripts, workflows, references, and extensions. It is installed as a Duckwork plugin and exposes the managed utility interface `duckwork seo setup`, `duckwork seo doctor`, and `duckwork seo run <script.py> [args...]`. Claude Code installers, settings paths, and commands are not part of the Duckwork setup. See [installation](INSTALLATION.md), [commands](COMMANDS.md), and [architecture](ARCHITECTURE.md).
