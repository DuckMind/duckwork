# Proposed core hook: tool-result card rendering (optional, upstream-shaped)

> **Status: PROPOSAL ONLY — the plugin does not patch core and never will by
> itself.** Stock Duckwork is unaffected: the plugin works as today, with the
> `::workflow{id="..."}` paste path plus the run payload's `card` / `hint` /
> `lifecycle_notice` fields. If upstream adopts the hook below, the desktop
> card additionally renders from the tool-result record and a model that
> forgets the paste still surfaces the card. This is the belt BEHIND the
> belt; the paste path stays (belt AND suspenders).

## Why (issue #157)

Card emission is model-honored, not enforced: a model that forgets to paste
the `::workflow{id="<run_id>"}` line produces a perfectly running, invisible
workflow. The plugin cannot close this plugin-side. Probed facts from the
packaged desktop SDK (`apps/desktop/src/sdk/index.ts` and its renderer):

* The transcript exposes exactly ONE plugin surface — the directive area:

  ```ts
  // sdk/index.ts
  export {
    TRANSCRIPT_DIRECTIVE_AREA,
    type TranscriptDirectiveContribution,
    type TranscriptDirectiveProps
  } from '@/lib/transcript-directives'
  ```

  and `TranscriptDirectiveContribution` is model-text-addressed only
  (`name` + `render({attrs, source, streaming})`). No tool call/result in props.

* Tool results render through `components/assistant-ui/tool/fallback.tsx`,
  whose per-tool special cases are core-internal string comparisons
  (`part.toolName === 'terminal'`, `'web_search'`, `'memory'`, …). No
  contribution registry, no slot a plugin can claim.

* `host.onEvent` hears the gateway stream (transient events), but there is no
  API to attach a component to a settled tool-call part.

So the missing primitive is a **tool-result contribution slot** — keyed by
(tool name, result shape), renderer-side, registry-backed like every other
area.

## The patch (≈30 lines, additive)

### 1. New area + payload type — `lib/tool-result-contribs.ts` (new file)

```ts
import type { ReactNode } from 'react'

/** TRANSCRIPT TOOL-RESULT contributions: a plugin claims tool calls by
 *  (toolName, result-shape) and its component renders under the tool chip.
 *  The gate is the plugin's own `claim` over the settled result — nothing
 *  renders unless a plugin claims the record. */
export const TOOL_RESULT_AREA = 'transcript.toolResults'

export interface ToolResultContribution {
  /** Claim a settled tool-result record for this tool name. Pure. */
  claim: (record: { toolName: string; args: unknown; result: unknown }) => boolean
  render: (record: { toolName: string; args: unknown; result: unknown }) => ReactNode
}

export interface ToolResultProps {
  toolName: string
  args: unknown
  result: unknown
}
```

### 2. Export from the SDK — `sdk/index.ts`

```ts
export {
  TOOL_RESULT_AREA,
  type ToolResultContribution,
  type ToolResultProps
} from '@/lib/tool-result-contribs'
```

### 3. One resolution point — `components/assistant-ui/tool/fallback.tsx`

Inside the tool-part renderer, beside the existing `part.toolName === …`
special cases, consult the registry (the same `useContributions` pattern the
directive leaf uses):

```tsx
const claims = useContributions(TOOL_RESULT_AREA).filter(c =>
  (c.data as ToolResultContribution).claim({ toolName: part.toolName, args: part.args, result: part.result }))
// …below the tool chrome:
{claims.map(c => (
  <ContribBoundary key={c.id} id={c.id} variant="chip">
    {(c.data as ToolResultContribution).render({ toolName: part.toolName, args: part.args, result: part.result })}
  </ContribBoundary>
))}
```

First claim wins per (area, toolName) if upstream prefers exclusivity; the
`ContribBoundary` isolation matches the directive leaf so a throwing plugin
degrades to an inline error, never a dead message.

## What the plugin would then register (one block, `desktop/plugin.js`)

```js
ctx.register({
  id: 'tool-result-card',
  area: TOOL_RESULT_AREA,
  data: {
    // The tool hands back a JSON STRING (`json.dumps(fn(args))`), and upstream's
    // `upsertToolPart` preserves whatever the handler returned. Normalize first:
    // match on an object, never on the raw part.result.
    claim: r => {
      if (r.toolName !== 'workflow' || r.args?.action !== 'run') return false
      const res = typeof r.result === 'string' ? _safeJson(r.result) : r.result
      return !!res && typeof res.run_id === 'string' && typeof res.card === 'string'
    },
    render: r => {
      const res = typeof r.result === 'string' ? _safeJson(r.result) : r.result
      return jsx(OwnerGatedCard, { id: String(res.run_id) })
    }
  }
})

// string -> object, never throws (a non-JSON result simply never claims)
function _safeJson(s) { try { return JSON.parse(s) } catch { return null } }

// The OWNERSHIP GUARD is ours to supply, NOT DirectiveCard's: DirectiveCard is
// only an id-validity check plus DirectiveBody — it has no owner/session logic
// (`DirectiveCard` at desktop/plugin.js ~415: `if (!ID_OK.test(id)) … else
// DirectiveBody`). A bare DirectiveCard mounted from a tool-result slot would
// render a FOREIGN-owner run's card in whatever chat happened to settle that
// tool part. Gate on `run.json owner.session_id == viewing session` exactly as
// the tray does: `ownedRuns` (desktop/plugin.js ~697) pairs
// `owner.session_id === sid` / `owner.ui_session_id === uiSid` against
// `host.state.focusedSessionId` / `focusedStoredSessionId` via the
// feature-detected `focusAtom`s — reuse that pairing here (fetch through the
// same `runQuery(id)` and render nothing until the run resolves AND is owned).
function OwnerGatedCard({ id }) {
  const runtimeSid = useValue(focusAtom(host?.state?.focusedSessionId))
  const storedSid = useValue(focusAtom(host?.state?.focusedStoredSessionId))
  const { data } = useQuery(runQuery(id))
  if (!data || !ownedRuns([data], storedSid, runtimeSid).length) return null
  return jsx(DirectiveCard, { id })
}
```

## Plugin-side readiness

The door returns `{run_id, models, routes, hint, card, lifecycle_notice}` on
`action=run` — that fresh payload is what `tests/test_card_notice_157.py` and
`tests/test_card_backend_080.py` pin, so on a FRESH launch the shape key above
(`result.run_id && result.card`) is stable contract. It is NOT stable across
every settled tool-result record the renderer will see: the lane-key dedupe
payload returns `lifecycle_notice` WITHOUT `card`, and persisted pre-#161
records likewise carry no `card`. The matcher's `typeof result?.card ===
'string'` clause therefore claims nothing on those records — correct behavior
(the dedupe still owes the paste, and the paste path is never removed), but it
means the hook covers fresh launches only. So, if upstream lands the hook, the
plugin-side delta is: the registration block above (JSON normalization +
`OwnerGatedCard` ownership guard) plus a pure matcher pin; the door and the
backend payload need no change, and the paste path is never removed.
