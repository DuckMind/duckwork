# duckwork-kame-provider

The provider half of [KAME API Rotation](https://github.com/DuckMind/duckwork).

Duckwork asks a provider profile for its model client before it builds its own
(`ProviderProfile.create_client`, and `create_messages_client` for Anthropic
Messages endpoints). This `model-provider` plugin registers, for every bundled
API-key provider, a profile that inherits everything from Duckwork' own —
endpoints, models, auth, request shaping — and adds only those two client
factories, which ask `duckwork-kame-api-rotation` for a client that rotates the
provider's keys on every request: Chat Completions, Responses API and
Anthropic Messages.

- Nothing in Duckwork is replaced, wrapped or rebound: the bundled profile
  objects are copied into new ones, and Duckwork' own registry keeps them as the
  documented per-home override.
- Without `duckwork-kame-api-rotation` installed and loaded for the same profile
  home, or with KAME switched off (`KAME_ROTATION_DISABLED=1`), both answer
  `None` and Duckwork builds its own client exactly as it always does. A Duckwork
  that does not yet ask `create_messages_client` builds its own Messages
  client; the other wires still rotate.

```bash
duckwork plugins install Kame696/kame-api-rotation-for-duckwork/duckwork-kame-api-rotation
duckwork plugins install Kame696/kame-api-rotation-for-duckwork/duckwork-kame-provider
duckwork plugins enable duckwork-kame-api-rotation
```

Restart Duckwork once after installing. MIT licence.
