<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# airlock is installed

**Guardrails for Duckwork Agent** by **Otsoa Dubief** · https://github.com/otsoa-dubief/airlock

1. Restart a running gateway so it loads the plugin: `duckwork gateway restart`
2. See it work, nothing is executed: `duckwork airlock demo`
3. Check what is in force: `duckwork airlock status`

Want to watch before it acts? Put `mode: observe` in `<DUCKWORK_HOME>/airlock.yaml`, then read
`duckwork airlock log` after a few days of real work.

Policy reference, limits and threat model: https://github.com/otsoa-dubief/airlock#readme
