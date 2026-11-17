---
name: greyridge-token-safety
description: Pre-trade safety check for any Base ERC-20 — honeypot/sellability simulation, measured transfer tax, owner/mint/pause/blacklist/proxy flags, Uniswap v3 liquidity, one SAFE/CAUTION/AVOID verdict. Free preview, $0.01/call via x402 after.
version: 0.1.0
---

# Grey Ridge token safety — check a Base token before you trade

Use before buying, swapping or approving an unknown Base (chain 8453) ERC-20.

## When to use

- User asks to buy/swap/snipe a Base token, or "is this token safe / a honeypot / a rug?"
- Autonomous trading loop needs a pre-trade gate.

## Check a token (no wallet, no key, no signup)

```bash
curl -s "https://x402-data-api.sigrunner.workers.dev/chain/token-report/preview?token=0x<TOKEN>"
```

Returns the full report as JSON: `security.isHoneypot`, `security.sellable`,
`security.transferTaxBps` (measured on a plain transfer), `security.ownerRenounced`,
`security.canMint`, `security.canPause`, `security.hasBlacklist`, `security.upgradeableProxy`,
`liquidity.wethPoolUsd`, plus `verdict`
(SAFE | CAUTION | AVOID) and `risk_score` (0-100) with `reasons[]`.

Sized go/hold/block decision for a specific swap (3 free real-token checks/day/IP):

```bash
curl -s "https://x402-data-api.sigrunner.workers.dev/gate/swap/preview?token=0x<TOKEN>&side=buy&notional_usd=500"
```

## Interpreting

- `AVOID` — do not trade; report the `reasons` to the user.
- `CAUTION` — tradeable with risk; show reasons, let the user decide.
- `SAFE` — no trap found by these checks (not a guarantee).

## Go paid (zero setup — the preview hands you everything)

Every preview response includes an `upgrade` object with the exact paid call pre-built:

```json
"upgrade": {
  "paid_url": "https://x402-data-api.sigrunner.workers.dev/chain/token-report?token=0x<TOKEN>",
  "price_usdc": "0.01",
  "pay_with": "npm i x402-fetch viem; const f=wrapFetchWithPayment(fetch, walletClient); await f(paid_url)"
}
```

Read `upgrade.paid_url` and call it with any x402 client (`x402-fetch`, `@x402/fetch`,
Cloudflare `withX402Client`) — USDC on Base settles inline, no key/account/signup. The
paid route is unmetered and works for any Base ERC-20 (the free preview is capped at
3 real tokens/IP/day). Full client docs: https://x402-data-api.sigrunner.workers.dev/llms.txt

## Limits (stated plainly)

- Base only. `buyTaxBps`/`sellTaxBps` (DEX swap tax) are **not measured** (null); only
  `transferTaxBps` is. Liquidity is Uniswap v3 WETH-pool only.
- Unattended/high-volume use: paid route `GET /chain/token-report?token=0x…` is $0.01 USDC per
  call via x402 on Base. Python helper + LangChain/CrewAI tools:
  `pip install "git+https://github.com/rezearcher/greyridge-x402-tools"`.
- Measured status (uptime/latency window): https://github.com/rezearcher/x402-data-api/blob/main/docs/STATUS.md
