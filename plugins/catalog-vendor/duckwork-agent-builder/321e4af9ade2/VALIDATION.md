# Validation — 1 October 2026

Tested against local Duckwork source `449fae030a` and Duckwork Desktop `0.21.5+4477` on macOS.

- Native plugin validation passed: manifest, isolated registration, declared tool, security scan, Desktop SDK surface.
- The desktop module parses as ESM. Its cleaned-up layout and BOTS-only navigation were observed in the running macOS app. The Sessions sidebar entry is removed; the BOTS titlebar entry preserves native window controls.
- The running authenticated plugin API generated three real interview questions after the malformed-suggestions fix. No additional provider API key was needed with the user's existing model connection.
- Real model calls generated Launchsmith, refined its blueprint, compared two versions on the same prompt, and produced a grounded announcement using the supplied release brief.
- Native profile creation/configuration saved `launchsmith`. Native `profiles.describe` confirmed an explicit empty tool selection and only Duckwork's mandatory core skill enabled. Native session APIs confirmed exactly one canonical hidden `Bot Chat` in that profile.
- The conversational Builder companion has the plugin installed and enabled in its own profile. Its `agent_builder` tool creates drafts; native teammate messaging is available only when enabled in Duckwork. A live teammate-message exchange was not exercised.
- Twelve backend tests passed using Duckwork's managed interpreter. These cover profile storage isolation, stale-response protection, optional malformed suggestions, model failure handling, versioned trials/comparisons, publish lifecycle, portable installation with spaces, and exact capability selections through the native runtime resolver.

## Platform limits

The installer and renderer avoid OS-specific runtime dependencies and support macOS/Windows home resolution. A native Windows Desktop run has not been performed. This is a locally validated plugin, not a claim of complete cross-platform certification.

## Demo evidence

The video records the actual plugin React UI in an isolated demo shell. It replays model responses captured from the real Launchsmith run so long model waits can be shortened. The final bot screen presents the separately verified native profile; it is not a recording of a live native Bot Chat. These boundaries are labeled in the film. No personal account names, credentials, unrelated sessions, or desktop content appear in the demo.

The music and Foldmark logo are original assets created for this project. The supplied Bot Mode video was used as a reference for purpose and pacing; its images and soundtrack were not reused.

## Idea context

Specialist-agent builders and Duckwork bot creation already exist. This package does not claim the general concept is new or make an unsupported performance comparison with GPT Builder. Its particular workflow combines a guided interview, editable references/capabilities, version comparisons, trials, and native BOTS handoff.

Relevant existing work: [Duckwork Bot Forge documentation](https://duckwork-agent.fordex.com/docs/plugins/bot-forge), [Botmaker](https://github.com/techjanitor/botmaker), and [Duckwork Bots](https://duckworkbots.dev).
