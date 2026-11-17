---
name: linkedcamp-outreach
description: Use when the user wants to work with LinkedCamp campaigns, sequences, leads, sending accounts, inbox conversations, analytics, content, AI agents, or account automations.
version: 1.0.0
author: LinkedCamp
license: MIT
---

# LinkedCamp outreach

Use the LinkedCamp MCP server as the source of truth for account data and
supported actions. This plugin registers it as the `linkedcamp` server, so
Duckwork lists each tool under that server; the bare names used below
(`whoami`, `campaign_create`, ...) are the tool names on the server.

If no `linkedcamp` tools are available, the server has not finished signing
in. The first start opens a browser at the LinkedCamp authorization page, where
the user pastes the API key from Settings → Integrations. Ask the user to
complete that and run `/reload-mcp`; never ask for the key in chat.

The plugin marks the server `untrusted`, so Duckwork asks the user before every
tool that is not read-only, and refuses those tools in unattended runs such as
cron jobs. That prompt is a backstop, not the confirmation this skill asks
for: still show the specifics and get a yes in the conversation first.

## Start safely

1. Call `whoami` once near the start of a new conversation. `_derived` reports
   the plan, `isPro`, `permissions`, and which Pro-only steps are locked.
2. Call `reference` before authoring sequence content or filtering by a status
   or enum. The vocabulary is not guessable — campaign daily limits live under
   `campaginLimits`, spelled that way.
3. Read existing records before changing them. Use returned IDs; never
   fabricate IDs, metrics, prospects, messages, or account state.
4. State clearly whether an operation is a proposal, a draft, or a completed
   change.

## Campaign workflow

1. `campaign_create` — a draft.
2. `search_url_build` — turn the described audience into a search URL. It
   generates job titles and keywords for basic LinkedIn and Sales Navigator
   searches. It cannot generate geography, industry, company size, seniority or
   years-in-role: Sales Navigator accepts those only as its own numeric ids,
   which cannot be derived from a name, and a wrong id silently searches the
   wrong people. Ask the user to paste a URL with those filters set, or for the
   ids. Recruiter (`/talent/`) URLs always come from the user.
3. `campaign_set_source` — set it. Show the user the URL first; it decides who
   gets messaged.
4. `campaign_update` — attach the sending account, schedule and limits. A
   campaign sends from exactly ONE LinkedIn account and may use SEVERAL
   mailboxes. If there is more than one of either, ask which; do not pick.
5. `flow_set` — write the sequence from an ordered list of steps. This is the
   only tool that authors one. `flow_from_template` applies a prebuilt one
   instead.
6. `campaign_get` — `_readiness.blockers` must be empty.
7. `campaign_launch` — only after the user has seen the sequence and the
   audience and said yes. See Human confirmation.

Never start a campaign by duplicating another one. `campaign_duplicate` is only
for when the user names a campaign to duplicate.

### Do not copy settings between campaigns

Reading an existing campaign to understand intent is fine; copying its
configuration is not. Set only what the user asked for, plus what
`campaign_get` reports as a blocker.

- The **lead source URL** is the worst thing to copy, because it decides who
  gets messaged. Two campaigns on the same search are not two campaigns:
  `uniqueProfiles` skips any prospect already held by another campaign, so one
  takes the audience and the other finds almost nothing.
- The **campaign tag** identifies that campaign's leads. Sharing one makes two
  campaigns' leads indistinguishable. Mint a short campaign-specific tag with
  `tag_create` (`interest: "NEUTRAL"`) instead of reusing an existing one. The
  reusable tags — Interested, Not Interested, Replied, Meeting Booked, Deal,
  Maybe — classify replies and do not belong in campaign settings.
- An **agent** is offered, never assumed. See below.

### Editing a sequence

To change a draft's copy, call `flow_set` again. Do **not** use
`sequence_update` on a draft: launching rebuilds every step from the saved flow
graph, so the edit is silently reverted. `sequence_update` is for a campaign
that is already ACTIVE or PAUSED.

### InMail

`INMAILS` steps need a Sales Navigator or Recruiter seat on the sending
account, and InMail credits to reach anyone who is not an Open Profile member.
Neither the seat nor the credit balance is exposed over this API, so neither can
be checked — say so rather than assuming. Without credits an InMail reaches a
small fraction of recipients and the rest fall through to the next branch.

A Recruiter (`/talent/`) source supports InMail only; it has no connect request
or ordinary message step.

## Replies: ask before attaching an agent

An agent attached to a campaign answers real prospects by itself, so never
attach one unprompted. Ask whether the user wants one and offer both routes:

- an existing agent — `agent_list`, then `agent_get` to show its personality,
  intent and instructions so the user can judge the fit;
- a new one — `agent_upsert`, then `kb_upsert` and `kb_attach` for its source
  material, then `agent_train`. Create it with `isActive: false` while the
  instructions are still being worked out, and use `agent_query` to test it
  before it touches a real conversation.

No agent is a normal outcome: replies simply arrive in the inbox for a human.

## Human confirmation

These reach real people. Show the user exactly what will happen and get an
explicit yes first:

- `campaign_launch` — begins real outreach from the connected LinkedIn account
  and mailboxes on the campaign's schedule. Show the full sequence and the
  audience.
- `campaign_send_test_email` — show the recipient, subject and body.
- `post_upsert` with a due `scheduledAt` — show the exact post; it may publish
  publicly.

`flow_set` on a campaign that is already ACTIVE re-evaluates every lead against
the new graph and can cancel or reschedule pending actions. `flow_audit`
reports what moved.

`campaign_delete` moves a campaign to DELETED. Nothing is erased, but it stops
appearing and there is no tool to bring it back, so confirm first. It also
removes still-active "add prospects" child campaigns.

## Plan entitlements

The plan gate is enforced by the MCP server, so a refusal is real and has no
workaround. Both the Pro and Agency plans carry `isPro: true`; Turbo does not.

- Pro only: `persona_*`, connecting an email account, and the `EMAIL`, `EVENT`,
  `GPT`, `FINDER` and `QUALIFIER` sequence steps, the `If_Interested` and
  `CUSTOM` triggers, and the `ENGAGEMENT.commentsToAdd` field.
- Permission-scoped: `agent_*` and `kb_*` need `Agents`; `post_*` needs
  `Publish`; `QUALIFIER` additionally needs `Personas`.

Check `whoami._derived` before proposing any of these. If a tool refuses on
plan grounds, say so plainly and do not look for a substitute.

## Agency sub-accounts

An agency owner can read any sub-account they own from their own key. Two steps,
and the first is not optional.

**Get the ids from `subaccount_list`.** It returns the active sub-accounts under
that agency — id, name, email, plan. Never construct or guess a `userId`: a
wrong id does not fail, it answers for a different account. If the tool comes
back empty, that means either no active sub-accounts or a key that is not an
owner; the two are indistinguishable from here, so say so rather than assuming.

**Then pass one as `userId`.** Seven tools take it:

- reads — `campaign_list`, `linkedin_account_list`, `email_account_list`,
  `analytics_campaign`, `analytics_reporting`, `tag_list`
- write — `agent_duplicate`, which copies an agent **into** that account. Name
  the client and get a yes first.

Omit `userId` for the user's own data. An id outside their agency is refused by
the server, not merely hidden, so there is nothing to retry and no phrasing that
widens it.

Record ids reach sub-account records too: once an owner has a `campaignId`,
`leadId`, `conversationId` or `linkedAccountId` from one of their sub-accounts,
the tools taking those arguments work on it — **including writes** such as
`campaign_update` and `flow_set`. Treat an id for a client account with the same
care as the client's own data, and say which account you are about to change.

When you report numbers across several accounts, label which account each
number belongs to. The tools answer per account; nothing returns a combined
roll-up, so an unlabelled comparison is your own construction and the user
cannot check it.

## Confirm before every destructive call

These reach real people or destroy records that cannot be recovered. Each is
flagged destructive so the client asks — but the prompt is not the safeguard.
Say in specifics what will happen, get an explicit yes in the conversation, and
never put several of them behind one confirmation:

- `message_send` — delivers to a real person on LinkedIn or by email
  immediately and cannot be recalled. Show the exact text and the recipient. It
  also stands a CHAT agent down on that thread when the agent has
  `pauseBotOnManualMessage` set.
- `lead_delete` — removes leads and their pending actions. Prefer `lead_update`
  with `isExcluded: true` when the user only wants sending to stop.
- `lead_blacklist` — excludes someone from every future campaign on the
  account, and nothing removes that. Right for an opt-out, wrong for "stop
  messaging them in this campaign".
- `message_delete` — edits your own record only. It does NOT unsend; the
  recipient keeps the message.
- `agent_delete` — campaigns using it lose automated replies silently, so
  prospects mid-conversation stop getting answers. `agent_upsert` with
  `isActive: false` stops it without destroying it.
- `kb_delete` — the source material is gone; a crawled page must be crawled
  again. `kb_attach` can exclude an entry instead.
- `persona_delete` — breaks every QUALIFIER step pointing at it, and that
  campaign's flow then fails to save. Check `usageCount` first.
- `tag_delete` — leads lose the classification and past reply-sentiment
  reporting changes. Deleting a campaign's identity tag makes its leads
  indistinguishable in `lead_list`.
- `blacklist_delete` — people the rule was blocking become targetable again.
  Read the rule out before removing it.
- `placeholder_delete` — copy using `{{key}}` then renders empty with no error,
  so a live campaign sends messages with a hole in them.

Also confirm `campaign_launch`, `campaign_send_test_email`, `campaign_delete`,
`flow_set` on an ACTIVE campaign, and `post_upsert` with a due `scheduledAt`.

One that needs asking for the opposite reason: `campaign_set_status` with
`ACTIVE` restarts real outreach on a paused campaign, but it is not flagged
destructive — it toggles a reversible field — so Duckwork's approval prompt shows
it as an ordinary write, with nothing to mark it as risky. Ask before
resuming; the campaign may have been paused for a reason the user has not
mentioned. Pausing needs no ceremony. It takes `PAUSED` and `ACTIVE` only and
refuses to resume anything not already paused; a campaign that has never run is
started with `campaign_launch`.

## Still unavailable

Do not claim or attempt these, and do not look for a substitute mutation:

- deleting a saved reply or a lead note
- archiving or completing a campaign — that is web-app housekeeping
- deleting a sequence, or saving a raw unvalidated flow graph
- deleting an integration, appointment or notification
- rotating the API key
- creating or editing an appointment by hand
- connecting, reading or configuring a CRM integration, and pushing a lead to one
- deprecated webhooks — event delivery goes through automations
- connecting a LinkedIn account; that flow takes a password and a verification
  PIN

Never request a LinkedIn password, session cookie, verification PIN, API key, or
reviewer credential in chat. Authentication belongs in the plugin's OAuth flow.
CRM integrations are not exposed at all, so never offer to connect one or ask
for a third-party API key. Integrations, including connecting an AI provider,
are configured in the web app under Settings - Integrations.

Billing, agency administration, tenant configuration, credential read-back and
team management are outside this plugin's scope.

## Never invent a real-world value

Anything identifying something real — a profile or company URL, a search URL,
an account id, a tag, a sender address, a webhook endpoint — comes from the user
or from a read tool. Never fill one in from memory, from another campaign, or
with a plausible guess. These do not fail loudly; a wrong URL sends real
messages to the wrong people.

## Responses

Ground summaries and recommendations in MCP results. When data is missing,
stale, inaccessible or plan-restricted, say so and give the next useful step.
Keep generated outreach copy clearly separated from observed account data.
