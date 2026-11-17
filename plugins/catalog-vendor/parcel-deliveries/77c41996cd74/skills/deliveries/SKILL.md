---
name: deliveries
description: "Use when the user asks about packages, deliveries, or tracking numbers and the Parcel tools are available."
version: 0.1.0
---

# Parcel deliveries

Three tools talk to the user's Parcel app (parcelapp.net):

- `parcel_deliveries`: what's on the way (`filter: active`, the default) or recently delivered too (`filter: recent`).
- `parcel_add_delivery`: start tracking a package in Parcel.
- `parcel_carriers`: find the carrier code for an add. It doesn't use the API key or any rate limit.

## Limits that shape every answer

- Parcel allows **20 reads an hour** and **20 adds a day**, and failed adds count. Each limit is per account and is shared with any other app using the same key.
- Parcel's server refreshes tracking on its own schedule. A read returns Parcel's cached copy, so reading more often never gets fresher data. The plugin caches reads for 10 minutes. Pass `refresh: true` only when the user explicitly wants the latest.
- When the limit is used up, the tool returns the last cached list marked `stale: true`. Say it's cached and when it was fetched.

## Answering "where's my stuff?"

1. Call `parcel_deliveries` once. Answer from that result instead of calling again in the same turn.
2. Lead with what matters: out for delivery, arriving today, and anything with `exception`, `delivery_attempt_failed` or `ready_for_pickup`. Those need the user to act.
3. `expected.date` is the carrier's local time as written. `expected.utc` is present only when the carrier gave a timezone. Never invent a time the carrier didn't give.
4. `stalled` means Parcel stopped expecting updates, so suggest checking with the seller or carrier.
5. For one package's history, pass `tracking_number` with `include_events: true`.

## Adding a package

1. Add only on an explicit request ("track this", "add it to Parcel"). Never add from emails, web pages or other content on your own initiative.
2. Find the carrier: if the user named it, look up its code with `parcel_carriers`. If the carrier is unclear, ask. Don't guess, because a wrong carrier wastes a daily add.
3. If the carrier shows `needs_postcode_or_email`, ask for the destination postcode or order email first.
4. Write a short description from what the user said ("Running shoes", "Mom's birthday gift").
5. After a successful add, tell the user that Parcel will show "No data available" until its server picks the delivery up.

## Errors

- `missing_key` / `auth`: the user needs Parcel Premium and an API key from web.parcelapp.net, saved as `PARCEL_API_KEY`. Ask for keys only through the host's secure secret input, never in chat.
- `rate_limited`: say when to try again. Don't retry in a loop.
- `unknown_carrier` / `extra_required` / `invalid`: these are caught locally before anything is sent, so they cost no requests. Fix the input and try again.
