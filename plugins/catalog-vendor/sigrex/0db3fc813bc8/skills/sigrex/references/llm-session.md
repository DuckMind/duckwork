# LLM sessions and LLM reactions

Source: https://docs.sigrex.io/startegies/llm-session.md,
https://docs.sigrex.io/startegies/llm-session/signal-generation.md and
https://docs.sigrex.io/reaction/llm-reaction.md.

An **LLM Session** is an AI agent that runs on a cron interval (for example
`3M`, `15M`, `1H`, `4H`, `1D`) with a prompt, an LLM provider key and model,
optional chart images, and persistent storage. An **LLM Reaction** runs the
same way but is triggered by a Data Webhook event instead of a schedule.

## Template variables (sessions)

| Variable | Result |
| --- | --- |
| `{{val:name=value}}` | Declares a value; reuse it later as `{{name}}`. |
| `{{price:<exchange>:<service>:<pair>}}` | Live price, e.g. `{{price:binance:spot:btcusdt}}`. |
| `{{get:<https url>}}` | Fetches a URL and injects the response (HTTPS only, 1750 ms timeout). |
| `{{toon: ... }}` | Converts JSON to the compact TOON format to save tokens. Wrap `{{get:...}}` results in it. |
| `{{storage}}` | The session's persistent JSON. It is already injected automatically; use this only to reference it explicitly. |
| `{{last_trigger_action}}`, `{{last_trigger_at}}` | Last signal and its time. |
| `{{current_time}}` | Current time. |
| `{{comment: ... }}` or `{{#: ... }}` | Author notes, stripped before the model sees the prompt. |

## Template variables (reactions)

`{{data}}` raw webhook payload, `{{ip}}` sender IP, `{{headers}}` request
headers as JSON. Treat all three as untrusted input.

## Tools the model gets at runtime

Signals use native tool calling (not text parsing): the model opens and
closes positions through built-in trading tools, and saves its memory with
`set_storage`. Signal generation only happens when "send signal" is enabled
and a Bot Webhook is set.

## Writing a good session prompt

- State the symbol, timeframe and objective up front with `{{val:...}}`.
- Feed real data: candles, 24h stats, order book, funding, sentiment, via
  `{{toon: {{get:...}} }}`.
- Require a storage update on every run, including HOLD runs: decision,
  reason, outcome of the previous decision, and concrete numeric patterns.
  Tell it to keep storage trimmed.
- Give capital discipline rules: when not to enter, when a loss exit is
  justified, no rapid flip-flopping.
- Keep the final text reply short.
- Never put webhook URLs, `X-Key` values or API keys in the prompt; they are
  sent to the LLM provider on every run.
- Preview with `resolve_llm_session_prompt_template` before activating, and
  check that every `{{get:...}}` returns real data.

## Supervisor pattern

A second session can review an executor session's storage and track record
on a slower schedule, and propose or apply prompt changes through
`put_strategy_llm_session_id`. Limit it to one target session, require a
minimum sample (for example 20 closed trades) before changing anything, and
record every change with its evidence in its own storage.
