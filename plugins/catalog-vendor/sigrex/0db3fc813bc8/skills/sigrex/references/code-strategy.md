# Code strategies and code reactions

Source: https://docs.sigrex.io/startegies/code.md and
https://docs.sigrex.io/reaction/code-reaction.md. Check the live pages if
something here looks out of date.

Code runs as sandboxed JavaScript (top-level `await` allowed) on every
scheduled run. Everything goes through the global `$` object.

## Runtime API

| API | Notes |
| --- | --- |
| `$.Action.LONG / SHORT / EXIT` | Trade actions. |
| `$.Strategy.action(action, options?)` | Sends the signal. Only works when "send signal" is enabled. Options: `id`, `size` (open in quote, close in base), `dilution` (stack on an existing same-direction position), `forceSize`. |
| `$.Strategy.lastTrigger.action / .price / .at` | Last signal sent. Use it to know whether a position is open. |
| `$.Strategy.signalSymbols` | Symbols the signal is sent for. |
| `$.Strategy.roi(percentage?, openPrice?, currentPrice?)` | ROI vs last trigger price. Negative when a short is in profit. |
| `$.Strategy.stop(notify?)` | Sets the strategy INACTIVE. Follow with `return` to stop the current run too. |
| `$.Price.price / .symbol / .exchange / .service` | Current price; only when "use price" is enabled. |
| `$.getExchangeRate($.Exchange.BINANCE, "btcusdt")` | Live rate from BINANCE, GATEIO, BITGET, HYPERLIQUID or KRAKEN. |
| `$.Storage.get()` / `$.Storage.set(obj)` | Persistent JSON, max 24 KB. `get()` returns null when empty. |
| `$.Env.NAME` | User-defined environment variables (global or folder scope). Put tunables and secrets here. |
| `$.Http.get(url, params?, headers?)`, `.post`, `.put`, `.delete` | Returns `{ status, text, cache }`. 1750 ms timeout. Responses are cached 5 s per URL. |
| `$.Http.generateSignature(payload, secret, algo?)` | HMAC (default) or ML-DSA signature. |
| `$.Http.createApiClient({ apiKey, apiSecret })` | Official Sigrex API client inside a strategy. |
| `$.Ta` | The `trading-signals` library: `new $.Ta.RSI(14)`, EMA, SMA, MACD, ATR, Bollinger Bands, etc. Feed values with `update()`, read with `getResult()` once `isStable`. |
| `$.Request.data` | Code reactions only: the raw incoming webhook payload (string). |

## Limits

- 5000 ms execution time per run; 1750 ms per HTTP request; 5 s HTTP cache.
- 24 KB storage.
- One action per run; five actions per second globally.
- Two consecutive `EXIT` actions are not allowed.
- Breaking limits can suspend the strategy temporarily.

## Forbidden identifiers

These must not appear anywhere in the code, including comments and strings
used as identifiers: `fetch`, `WebSocket`, `XMLHttpRequest`, `import`,
`require`, `eval`, `Function`, `constructor`, `globalThis`, `window`,
`document`, `process`, `setTimeout`, `setInterval`, `crypto`, `performance`,
`Reflect`, `Proxy`, `atob`, `btoa`, `console`, `Intl`, and the other
browser/Node globals listed in the docs. Use `$.Http` for network calls.
There is no `console`, so expose debug values by writing them into storage
(for example `S.dbg = {...}`).

## Patterns that work well

- Load state once: `const S = await $.Storage.get() || { ... }`, save once at
  the end with `await $.Storage.set(S)`, including on early returns.
- Derive whether a position is open from `$.Strategy.lastTrigger.action`
  rather than trusting storage alone.
- Throttle with a stored `lastRun` timestamp if the schedule is faster than
  the logic needs.
- Keep the symbol and all tunables in `$.Env` or constants at the top, so a
  duplicated strategy only needs one change.
- Check `response.status === 200` and wrap `JSON.parse` in a try/catch.

## Minimal example

```js
const S = await $.Storage.get() || { entry: null };
const px = $.Price.price;
const inPosition = $.Strategy.lastTrigger.action === $.Action.LONG;

if (!inPosition && px < Number($.Env.BUY_BELOW)) {
  await $.Strategy.action($.Action.LONG);
  S.entry = px;
} else if (inPosition && S.entry && px >= S.entry * 1.01) {
  await $.Strategy.action($.Action.EXIT);
  S.entry = null;
}

await $.Storage.set(S);
```
