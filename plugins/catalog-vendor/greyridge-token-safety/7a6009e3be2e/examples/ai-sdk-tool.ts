// Vercel AI SDK tool: pre-trade safety check for a Base token (free preview endpoint).
// npm i ai zod   — no wallet or key needed. Unattended volume: use paid GET /chain/token-report ($0.01 via x402).
import { tool } from "ai";
import { z } from "zod";

export const baseTokenSafety = tool({
  description:
    "Check a Base ERC-20 token before trading: honeypot/sellability, measured transfer tax, owner/mint/pause flags, liquidity, SAFE|CAUTION|AVOID verdict.",
  inputSchema: z.object({ token: z.string().regex(/^0x[a-fA-F0-9]{40}$/) }),
  execute: async ({ token }) => {
    const r = await fetch(`https://x402-data-api.sigrunner.workers.dev/chain/token-report/preview?token=${token}`);
    if (!r.ok) throw new Error(`token-report preview HTTP ${r.status}`);
    return r.json(); // fields: verdict, risk_score, reasons[], security{}, liquidity{}
  },
});
