# Quickstart reference

Load this file when the developer needs the full placement matrix or framework-specific wiring details.

## Placement matrix

| Path | Where | What you write |
|------|-------|----------------|
| Browser (React) | Frontend component | `<VerifyGate gate={gate}>` around protected content |
| Browser (non-React) | Frontend redirect | `getHostedCheckoutUrl({ verifiers, returnUrl })` |
| Server | Backend route | `client.gateCheck({ gate, subject })` before granting access |
| Both (full stack) | Frontend + server | VerifyGate on the page + gateCheck on the server |
| Published listing | Optional | `gateId` when you need a persisted price, schedule, or checkout |

## Framework wiring

### Next.js App Router

Place `VerifyGate` in a client component:

```tsx
'use client';
import { defineGate } from '@proofable/sdk';
import { VerifyGate } from '@proofable/sdk/widgets';

const gate = defineGate([{ verifierId: 'proof-of-human' }]);

export default function ProtectedPage() {
  return (
    <VerifyGate gate={gate}>
      <ProtectedContent />
    </VerifyGate>
  );
}
```

Server check in a route handler or server action:

```ts
import { ProofableClient, defineGate } from '@proofable/sdk';

const gate = defineGate([{ verifierId: 'proof-of-human' }]);
const client = new ProofableClient();
const result = await client.gateCheck({
  gate,
  subject: { accountId: user.accountAddress },
});
```

### Vite / Create React App

Same component imports. `VerifyGate` works in any React 17+ app.

### Express / Fastify / other server-only

No React needed. Use the redirect flow on the frontend and `gateCheck` on the server:

```js
import { ProofableClient, defineGate } from '@proofable/sdk';

const gate = defineGate([{ verifierId: 'proof-of-human' }]);
const client = new ProofableClient();
const result = await client.gateCheck({
  gate,
  subject: { accountId: req.body.address },
});
```

## Optional listing on proofable.me

Publish a listing only when you want a persisted `gateId`, price, or schedule.

1. Sign in at proofable.me.
2. Open profile → Listings.
3. Choose the checks visitors must pass.
4. Set pricing: you pay by default, or charge visitors.
5. Publish and copy the `gateId`.

## VerifyGate props

| Prop | Type | Purpose |
|------|------|---------|
| `gate` | Gate Policy | Inline checks from `defineGate`. Preferred for new apps. |
| `gateId` | string | Optional published listing. Do not pass with `gate`. |
| `subject` | `{ accountId }` | Visitor account for reuse without Proofable sign-in. |
| `children` | ReactNode | Content to render when access is granted. |
| `onVerified` | function | Called with the proof result when access is granted. |
| `onError` | function | Called if the check fails. |
| `strategy` | string | `reuse-or-create` (default), `fresh`, or `reuse`. |
| `mode` | string | `create` (default) or `access`. |

Full reference: [docs.proofable.me/widgets/verifygate](https://docs.proofable.me/widgets/verifygate)

## ProofableClient methods

| Method | Purpose |
|--------|---------|
| `gateCheck({ gate, subject })` | Server-side allow/deny check. The primary enforcement call. |
| `getProof(qHash)` | Fetch a proof by ID. |
| `getProofsByWallet(address)` | List proofs for an address. |
| `getGate(gateId)` | Fetch gate configuration. |
| `getVerifiers()` | List what you can verify. |

Full reference: [docs.proofable.me/sdks/javascript](https://docs.proofable.me/sdks/javascript)