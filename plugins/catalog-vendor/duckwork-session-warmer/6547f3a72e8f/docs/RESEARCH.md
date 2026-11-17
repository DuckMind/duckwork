# Design research and benchmark protocol

Research used WebXNG/SearXNG discovery plus direct official documentation and GitHub source reads.

## Sources

- [OpenCode warming](https://opencode.ai/v2/docs/warming/): default-off, four-minute idle interval, 30-minute active window, temporary prompt, discarded output, explicit billing warning. Unlike OpenCode's periodic retry after failure, this plugin stops after the first warming failure for an idle period.
- [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching): reuse depends on matching rendered prefixes, model, cache availability and routing. Tool definitions, parallel-tool settings and structured output settings can affect that prefix. Provider features and pricing vary by model; do not infer cache effectiveness just from receiving HTTP 200.
- [Claude prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching): provider-native retention and explicit caching have separate rules. Native Claude is deliberately outside v0.1 scope; prefer supported retention controls to blind periodic replay.
- [Duckwork middleware](https://duckwork-agent.fordex.com/docs/developer-guide/middleware): capture provider kwargs through a supported extension rather than monkeypatching core.
- [Duckwork plugin LLM access](https://duckwork-agent.fordex.com/docs/developer-guide/plugin-llm-access): a one-shot auxiliary completion is supported but not an exact replay of the current wire request with its tool schemas. It is not interchangeable with session warming.
- [Duckwork PR 57019](https://github.com/DuckMind/duckwork): unmerged local-backend shared-prefix/post-compaction warmer at inspection. This standalone plugin neither copies that implementation nor changes core, and warms a successful conversation's captured context instead of only a shared prefix.
- [Catalog admission policy](https://github.com/DuckMind/duckwork): owner submission, public repo, release/tag, exact SHA pin, matching capabilities, validator/security scan, no self-update.

## Decisions

Opt-in twice (plugin enablement plus warming config), explicit endpoint/model allowlists, independent credential provisioning, bounded attempts/window/payload/session count, one worker, no SDK retries, circuit break on error, privacy-safe numeric status, memory-only snapshots and profile-bound configuration. Keep system/messages/tool schema order unchanged. Preserve parallel-tool and structured-output settings; force no tool selection and one output token. Hidden provider prompt construction may still diverge, so effectiveness must be measured.

The final assistant text is appended to the copied request before the transient user maintenance message. The original request/history is never changed. Responses never enter the agent loop. Unknown provider fields, media blocks, and server-side tools are rejected instead of approximated.

## Effectiveness experiment (not yet performed)

Use a dedicated non-sensitive test account/model and an explicit spend ceiling. Keep provider account/project, model, endpoint, routing, message/tool ordering and all relevant settings constant. Use prompts above the provider's documented minimum cacheable length. Avoid cross-contamination: independent equivalent sessions and randomized paired warm/control trials, not two concurrent arms accidentally sharing the same cache prefix.

Record cold prefill baseline, normal follow-up baseline, an idle-expired control, and a warming arm with identical pauses. Measure real follow-up time-to-first-token and total latency (p50/p95 across repeated trials), actual provider cached-input/cache-write/uncached-input/output/reasoning token usage, total billed cost including every warm call, errors/429s, and foreground overlap. Separate cache-read success from first-request prefill. The plugin status reports warm-call counters only, not TTFT.

Compare total cost of all warm requests plus the real resumed turn against the unwarmed resumed turn. Enable only if the measured latency benefit and/or net cost reduction justify added load. Re-test after changing providers, models, schemas, tool choice, cache retention or routing. Do not publish fixture counters as provider measurements.
