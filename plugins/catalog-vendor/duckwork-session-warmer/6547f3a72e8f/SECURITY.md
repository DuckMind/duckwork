# Security policy

Report vulnerabilities through GitHub private vulnerability reporting if enabled, otherwise open a minimal issue requesting a private channel without including secrets or exploit data. Never post credentials or real conversation snapshots.

This is trusted in-process Python, not a sandbox. Review source before enabling. The plugin explicitly resends conversation context to a configured matching provider and may incur charges. See README for retention, transport, in-flight cancellation and unsupported-provider limitations. No telemetry or self-update exists. Only the operator-provisioned DUCKWORK_SESSION_WARMER_API_KEY is read; no host credential stores are inspected.
