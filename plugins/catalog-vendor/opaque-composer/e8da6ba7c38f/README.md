<div align="center">
  <a href="https://github.com/DuckMind/duckwork"><img src="https://github.com/user-attachments/assets/ac2f5702-c842-4b2e-9340-737481fa0ece" width="96" height="96" alt="Fordex Duckwork mark" /></a>
  <h1>Opaque Composer</h1>
  <strong>Keep the message composer readable while you scroll.</strong>
  <p>Solid theme-aware fill so transcript text does not show through the input.</p>
  <p>
    <a href="plugin.yaml"><img src="https://img.shields.io/badge/version-1.0.0-2ea44f" alt="Version 1.0.0" /></a>
    <a href="../../LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license" /></a>
  </p>
</div>

<div align="center">
  <img src="docs/hero.png" width="100%" alt="Opaque Composer" />
</div>

## What You Can Do

- Get an opaque composer fill in normal and scrolled states, using the active theme's card color.
- Keep conversations and gateway behavior unchanged — only the desktop composer surface is affected.
- Disable the plugin to restore Duckwork' default translucency.

## Install

Requires [Duckwork Agent](https://github.com/DuckMind/duckwork) **0.21.0 or newer**.

```bash
duckwork plugins pack install https://github.com/DuckMind/duckwork
```

Enable **Opaque Composer** under **Capabilities → Plugins**. Reload desktop plugins from **Cmd+K** or **Ctrl+K** on Windows if needed.

## Requirements / Limits

Desktop-only. No gateway or Python runtime required. Needs the composer root surface Duckwork Desktop exposes.

## License

[MIT](../../LICENSE)
