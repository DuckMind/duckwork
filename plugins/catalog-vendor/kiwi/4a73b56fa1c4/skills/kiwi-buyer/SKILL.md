---
name: kiwi-buyer
description: Kiwi Sourcing & Negotiation Kit. Use when the user wants to source general goods, find suppliers, send RFQs, compare quotes, negotiate, or ask about lead times/MOQ. Covers discovery, RFQ, negotiation, non-binding agreements and trade handoff through the kiwi-buyer-mcp tools.
version: 0.3.0
author: harrylabsj
license: Apache-2.0
metadata:
  duckwork:
    tags: [commerce, sourcing, procurement, rfq, negotiation, mcp, kiwi, buy, shopping, 购买, 采购, 购物]
    category: commerce
---
<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->

# Kiwi Buyer (Sourcing & Negotiation Kit)

Kiwi provides cross-merchant discovery, request-for-quote and commerce
negotiation. The host agent owns the conversation and user confirmation; Kiwi
owns merchant discovery, A2A/KNP negotiation and non-binding agreements. Kiwi
never handles payments, never places orders and never locks inventory.

The buyer discovers merchants through the catalog only, then talks to the
merchant directly over A2A. Do not probe or connect to a local marketplace,
`shopping-cli`, or any `127.0.0.1` service.

A Chinese translation of this skill ships alongside it
([SKILL.zh-CN.md](SKILL.zh-CN.md)); this English file is the default and
authoritative version.

## Tool flow

| User intent | Tool |
|---|---|
| Find merchants or suppliers (Kiwi Network only) | `kiwi_search` |
| Request quotes (RFQ) | `kiwi_request_quotes` |
| Check quotes and task status | `kiwi_get_task` |
| Counter-offer or clarify | `kiwi_negotiate` |
| Accept the non-binding agreement | `kiwi_accept_agreement` |
| Read the agreement and audit digest | `kiwi_get_agreement` |
| Produce checkout, PO or contact entry point | `kiwi_handoff` |
| Approve after user confirmation | `kiwi_approve` |
| Reject an approval request | `kiwi_reject` |

Typical flow:

1. `kiwi_search` discovers candidate suppliers.
2. `kiwi_request_quotes` starts the RFQ; an idempotency key and a valid
   `CommerceIntent` are required.
3. `kiwi_get_task` shows quotes, partial failures and pending approvals.
4. Use `kiwi_negotiate` for counter-offers or clarifications when needed.
5. `kiwi_accept_agreement` accepts the terms; if it returns
   `approval_required`, first show the user the candidates, terms and amounts,
   get explicit confirmation, call `kiwi_approve`, then retry with the
   `approval_id`.
6. Verify the agreement and digest with `kiwi_get_agreement`, then call
   `kiwi_handoff`.

## Dual-source search (network merchants + internet e-commerce)

A sourcing search covers two sources by default, presented and labelled
separately — never merged into one list whose origin cannot be told:

| Source | Display name | Provided by |
|---|---|---|
| Kiwi Network | Kiwi Network · network merchants | `kiwi_search` (this tool covers only this source) |
| Internet e-commerce | Internet e-commerce · platform listings | the host's own web search / page-reading tools; if this session has none, say the internet side was not searched and do not claim a dual-source search |

- When the user restricts the source ("Kiwi Network only"), search only that
  source and never imply the other one was searched. If both are available, run
  both (in parallel when supported, otherwise in the same turn).
- Show at most 3 most-relevant results per source by default, each with its own
  query status; if one source finishes first you may show it while the other
  stays "searching".
- Internet results must carry the platform name and the original link, and only
  entries traceable to a real product or shop may be listed. Do not mark
  anything as verified unless that page was actually read, and never treat an
  internet candidate as a Kiwi Network merchant.

### Query status (`network_search`)

`kiwi_search` returns `network_search` describing the true state of the Network
path (`status`: `completed`/`partial`/`timeout`/`error`/`not_searched`;
`result_state`: `has_candidates`/`no_match`/`undetermined`):

- only `completed` + `no_match` may be worded as "no match this time";
- `timeout`/`error` are failures ("cannot query right now; showing the other
  source"), never "no suppliers";
- `partial` (including `undetermined`) means coverage is incomplete; still show
  what was found and name the differences;
- `not_searched` means that source did not run (user-restricted or capability
  unavailable) and must not be described as no match;
- older runtimes return only `merchants` + `note`: a non-empty `note` means
  incomplete coverage — say conservatively that the query did not fully
  complete.

### Price and confirmation status

Never mix price kinds: page reference price (`page_reference`), merchant-listed
price (`merchant_listed_price`), merchant quote (`merchant_quoted`), to be
quoted (`to_be_quoted`). A listed price or a page price is not a quote; when a
merchant confirmed only specifications, price, stock and lead time stay
unconfirmed. Different currencies, units or quantity conditions do not allow
picking a "lowest price", and unknown tax/shipping means no delivered total.

### Boundary between search and RFQ

Searching never sends an RFQ: internet listings have no Kiwi merchant identity —
never put them in the `merchant_ids` of `kiwi_request_quotes`, and never apply
Kiwi agreement or handoff status to them. Offer the original link or a prepared
inquiry text instead.

## CommerceIntent rules

Pass only the fields required to complete the purchase. Never put chat
history, host memory, email addresses or unrelated profile data into the
intent. Every item needs a short product query and an object-shaped quantity:

```json
{
  "intent_type": "purchase",
  "items": [{ "query": "insulated bottle", "quantity": { "value": 2, "unit": "pcs" } }],
  "constraints": { "currency": "CNY", "deadline": "<RFC3339>" },
  "context_projection": {
    "disclosure_boundary": "commerce_required",
    "projected_fields": ["items", "constraints"]
  }
}
```

Prefer short product words in the item `query`; move specifications into
`constraints` or `preferences` to avoid catalog matching failures.

## Authorization and error handling

- `kiwi_accept_agreement` and `kiwi_handoff` require user authorization by
  default; never let the model approve on its own.
- `authorization_denied` and `approval_denied` are hard refusals — do not
  retry them automatically.
- `task_not_found` and `task_expired` require re-querying or re-quoting.
- On `partial_success`, keep the successful quotes and report the failed
  items separately.
- A trade handoff only produces a next-step entry point; verify the target
  URL before the user pays, and state clearly that Kiwi itself has neither
  paid nor placed an order.
