# ElizaOS / any HTTP-capable agent
Call `GET https://x402-data-api.sigrunner.workers.dev/chain/token-report/preview?token=0x…` before any buy action and
refuse to trade when `verdict == "AVOID"`. Same JSON shape as the paid route.
