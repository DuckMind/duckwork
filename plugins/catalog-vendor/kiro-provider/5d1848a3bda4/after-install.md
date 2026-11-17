# Kiro provider installed

Authenticate through Duckwork' native provider-auth surface:

```bash
duckwork auth add kiro
```

Then use `duckwork auth status|list|refresh|logout kiro`. Select Kiro in the normal main or auxiliary model picker; `/usage` shows Kiro allowances when it is active.

Restart an already-running gateway once so it imports the new provider code. Use the multiplexed gateway command:

```bash
duckwork gateway restart
```

For a non-multiplexed gateway serving one named profile:

```bash
duckwork --profile work gateway restart
```
