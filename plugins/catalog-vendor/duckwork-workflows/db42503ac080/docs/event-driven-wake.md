# Event-driven wakes: replacing cron polls with a push spine

Agents in this plugin are usually driven by a session that is already awake.
When the thing they should notice is an external occurrence — a delivery from a
code-hosting webhook, a queue insert, a finished build — the usual way to make an
agent notice it is a poll: a scheduler entry that wakes the bot every minute to
ask "anything new?". At fleet scale that is the dominant cost of the whole
system, because most of those wakes find nothing.

This document is the pattern we use instead: an external process publishes, a
durable consumer holds the queue position, and the agent is woken only when there
is something to do. It is written to be portable — no host names, no private
addresses, no estate vocabulary — so it can be lifted into any deployment.

## Why a poll is expensive

A poll pays for three things at once: a process wake, a provider call to decide
"nothing to do", and a watermark read. The provider call is the expensive one and
it is spent almost entirely on the empty case. A fleet of a few dozen per-minute
polls is thousands of wakes a day whose overwhelmingly likely outcome is a
no-op — and the poll's latency is still the poll interval, so the fastest
possible reaction to an occurrence that arrives one second after a tick is a
minute away.

Push inverts both: the cost is paid on the rare non-empty case, and latency drops
to the publish path.

## The shape

```
external occurrence
  -> receiver          verifies, de-duplicates, spools one artifact per delivery
  -> pump              forwards the artifact where agents can see it, then publishes
  -> stream            one subject per occurrence kind, durable storage
  -> consumer          durable pull consumer, holds ack position
  -> hub               long-running process; on message, wakes the right agent
  -> reconciling work  the agent's normal job, which re-reads the source of truth
```

Three parts carry the whole design:

**The pump forwards before it publishes.** The artifact must be visible to the
agent before the wake message exists, or the wake arrives pointing at a file that
isn't there yet and the agent reads an empty inbox. Forwarding first collapses
the ordering race entirely, and the forward is idempotent (exists-check, write to
a temp file, fsync, rename) so a re-run is free.

**De-duplication is a header, not a database.** Publish with a
`Nats-Msg-Id` header set to the delivery's own unique id (for webhooks, the
delivery GUID the sender already provides). The stream collapses duplicates for
its dedupe window, so at-least-once republish becomes one stored message per
occurrence without any state in the pump.

**The consumer is durable and the queue position lives on the server.** A pull
consumer with an explicit config (`durable_name`, `deliver_group`, `ack_wait`,
`max_deliver`, `filter_subject`) survives a hub restart without losing or
re-reading position, and the subject filter is what lets one stream serve many
lanes.

## The one law that makes this safe

**The bus is an accelerator, never the source of truth.** A wake is a hint to
look. The message payload never decides what work exists — the same tick's
authoritative read (an API sweep, a database query, a directory scan) does. If
the bus is down, a slow scheduled pass still runs and everything converges.
Losing a message costs latency. It never costs correctness. Forgery changes
nothing, because the payload is not trusted for content.

Get this backwards and every broker bug becomes a data-integrity bug. Get it right
and the broker can be flaky, replay, duplicate, or stall, and the estate still
arrives at the same state.

Keep the poll. Reduce it to a safety net — scheduled, infrequent, and still
authoritative. Retiring the poll is the mistake that turns a latency problem into
a reliability problem.

## Coalescing bursts without a queue

Wakes arrive in bursts (a pushed branch, a bulk import, a retry storm). Do not put
a queue in front of the agent to smooth them out. Use the scheduler's own
mutual-exclusion instead: invoke the job *synchronously*, so a wake executes the
work and waits, and a second wake that lands mid-work returns immediately because
the fire is already claimed. N deliveries then cost one sweep and N-1 instant
no-ops.

Two consequences worth naming:

- Set the wake's timeout to the work's real ceiling, not to a polite default. A
  client-side timeout shorter than the work kills the caller but leaves the work
  running, and the next wake then finds the fire claimed and no-ops forever. If
  that happens silently, look for the live worker process and its elapsed time
  before you look at the broker.
- Coalescing rows that read like failures ("fire claim lost") are the mechanism
  working. A steady per-minute stream of them, however, means one run is wedged
  and holding the claim.

## Poison, bounded by construction

A failed dispatch nacks with a delay so the server redelivers. At the delivery
ceiling, publish an artifact to a dead-letter subject *in the same stream* and ack
the poison so it leaves the queue. The control stream is an event spine, not a
work queue — the dead-letter row is the artifact a human or a lane goes to look
at. Redelivery pressure is bounded by `max_deliver` rather than by a human
noticing a hot loop, so a poison message can never wake the fleet in a tight
circle.

## Operational notes

- Wake the agent as its own user. Running the scheduler's fire command as a
  privileged user trips file-ownership footguns in anything the job writes.
- Green ticks print nothing. Silence is the healthy signal for every no-agent
  script on this path; anything it prints is a finding.
- Only the reconciling work inside the agent holds external credentials. The
  receiver, the pump and the hub hold none, which is what keeps a compromised or
  confused pump harmless.
- When the source of truth is an external API, sweep that API and let the spooled
  artifacts be hints. Never let a spooled artifact mint work by itself.
