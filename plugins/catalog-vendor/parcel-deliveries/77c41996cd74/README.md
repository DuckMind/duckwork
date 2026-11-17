<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Parcel for Duckwork

Track package deliveries from [Parcel](https://parcelapp.net) in [Duckwork Agent](https://github.com/DuckMind/duckwork). Ask "what's arriving today?" or "track this UPS number", and Duckwork reads from or adds to your Parcel account.

Unofficial. It isn't affiliated with or endorsed by Parcel. It uses Parcel's public [external API](https://parcelapp.net/help/api.html).

## What you get

| Tool | What it does |
|---|---|
| `parcel_deliveries` | Lists active (or recent) deliveries: status, expected date and latest tracking event. It can filter to one tracking number and include the full event history. |
| `parcel_add_delivery` | Adds a tracking number to Parcel. |
| `parcel_carriers` | Looks up Parcel carrier codes by name (for example "amazon" gives `amzlus`). Needs no key and spends no requests. |

You also get a `/parcel` slash command (`/parcel recent` includes delivered packages) and a bundled skill, `parcel-deliveries:deliveries`, that tells the agent how to answer delivery questions.

## Requirements

- **Parcel Premium.** The API is a Premium feature.
- **An API key** from [web.parcelapp.net](https://web.parcelapp.net), saved as `PARCEL_API_KEY`. `duckwork plugins install` prompts for it.
- Duckwork 0.21.2 or later. No Python dependencies; it uses only the standard library.

## Install

```bash
duckwork plugins install promptclickrun/duckwork-parcel
duckwork plugins enable parcel-deliveries
```

The tools show up in your next session.

## Rate limits, and how the plugin respects them

Parcel's limits are strict: **20 reads an hour** and **20 adds a day**, and failed adds count too. Its deliveries endpoint also returns Parcel's server-side cache, so polling it harder never gets you fresher tracking.

To stay inside those limits, the plugin:

- caches reads for 10 minutes, so the agent re-asking in one conversation costs nothing;
- keeps a local count and refuses the 21st request instead of letting Parcel reject it;
- when the limit is used up or Parcel is down, returns the last list marked `stale`;
- checks adds locally before sending: known carrier code, postcode or email where the carrier needs one, a sane tracking number, and not already tracked. A typo doesn't burn a daily add.

The local count only covers this Duckwork host. Other apps using the same key (Home Assistant, for example) share Parcel's limit.

**Don't schedule frequent polling.** A daily "what's arriving" cron job is fine. One every five minutes will hit the hourly limit.

## Privacy and behaviour disclosure

- **Network:** it calls `https://api.parcel.app/external/` only: `deliveries/` (GET), `add-delivery/` (POST), and `supported_carriers.json` (GET, sent without your key). Redirects are refused so the key can't be forwarded anywhere else.
- **Credentials:** it reads `PARCEL_API_KEY` through Duckwork' secret lookup. It never writes, logs or returns the key.
- **Stored data:** `<DUCKWORK_HOME>/plugin-data/parcel-deliveries/state.json` (mode 0600) holds the last delivery lists (descriptions, tracking numbers, events), the carrier list, and request timestamps for the rate count. Delete the file at any time to clear it.
- **Writes to your Parcel account** happen only through `parcel_add_delivery`. There's no edit or delete; Parcel's API doesn't offer them.
- No shell commands, no background processes, no telemetry, no self-updating.

## Development

```bash
python -m unittest discover -s tests
duckwork plugins validate . --install-deps
duckwork plugins doctor . --ci
```

The tests use a fake transport and never touch the network.

## License

Apache-2.0
