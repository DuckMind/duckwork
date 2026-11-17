# Signal payload

Source: https://docs.sigrex.io/getting-started/signal-payload-format.md and
https://docs.sigrex.io/prediction-signal-bot-beta/payload-format.md.

A Bot Webhook accepts a JSON signal and forwards it to every active Signal
Bot attached to it. The `send_bot_hook_order_message` tool sends one.

| Field | Required | Meaning |
| --- | --- | --- |
| `symbol` | Yes | Trading pair, e.g. `BTCUSDT`, `BTCUSDC`. Must match what the bot expects. |
| `side` | Yes | `BUY` opens a long or closes a short; `SELL` closes a long or opens a short. |
| `size` | No | Amount: open in quote currency, close in base currency. Defaults to the bot's configured amount. |
| `dilution` | No | `true` stacks onto an existing same-direction position instead of replacing it. |
| `key` | Safe mode only | The webhook key. A credential: never display it in full. |
| `id` | No | Custom label for the signal. |
| `flag` | No | `TEST` (no real trade), `DEBUG`, `REVERSE`; a string or an array. |
| `debug` | No | Free-form diagnostic data; not used by bots. |
| `callback` | No | URL that receives the execution result. |

Prediction (Polymarket) bots use their own payload: `BUY` opens or increases
a position and `SELL` closes or reduces it, with the market identified by
slug or token. Read the prediction payload page before sending one.

## Before sending a live signal

1. Send it with `flag: "TEST"` first if the user has not done so.
2. Restate symbol, side, size, target webhook and the bots that will receive
   it, and wait for explicit approval.
3. After sending, report the response and remind the user where to see the
   execution (signal logs in the Sigrex app).
