# duckwork-nextdns

A [Duckwork Agent](https://duckwork-agent.fordex.com/) plugin for DNS triage against [NextDNS](https://nextdns.io): query logs, blocked queries with the blocklist that matched, and aggregate analytics by domain, device, blocklist or protocol.

Read-only. Every endpoint it uses is a `GET`; the plugin makes no configuration changes to your NextDNS profile.

## Tools

| Tool | What it does |
|------|--------------|
| `nextdns_logs` | Query the DNS log. Filter by domain search, status, device, and time range |
| `nextdns_blocked` | Recently blocked queries with the blocklist that matched each one |
| `nextdns_analytics` | Aggregate counts: top domains, blocklists, devices, protocols, status |
| `nextdns_profile` | Profile settings, including whether logging is enabled and its retention |

Also registers a `/nextdns` slash command for query totals.

## Setup

### 1. Create an API key

At the bottom of your account page: [my.nextdns.io/account](https://my.nextdns.io/account).

### 2. Find your profile ID

It is the path segment of your DNS-over-HTTPS URL, `https://dns.nextdns.io/<id>`, and is shown at the top left of my.nextdns.io. The dashboard tab can also list the profiles a key can see.

### 3. Configure

Either from the **NextDNS** tab in the Duckwork dashboard, or by environment:

```env
NEXTDNS_API_KEY=<your key>
NEXTDNS_PROFILE_ID=<your profile id>
```

Settings resolve as file, then environment, then default. The dashboard writes `$DUCKWORK_HOME/nextdns_settings.json` (mode 0600), and a value stored there takes precedence over the environment. Clearing a field in the dashboard returns it to the environment rather than storing a blank.

The API key is never sent back to the browser once saved - the dashboard only reports whether one is present.

### 4. Install

```bash
duckwork plugins install shanelord01/duckwork-nextdns
```

Or clone into `~/.duckwork/plugins/nextdns/` (`/opt/data/plugins/nextdns/` in the Docker image) and restart the gateway.

### 5. Verify

The dashboard tab has a **Test connection** button that reports the profile name, whether logging is enabled, retention, and the log storage region, then shows a sample of recent blocks to confirm data is flowing.

## Device attribution

Devices that query NextDNS directly - through the NextDNS apps, or a DNS-over-HTTPS/TLS endpoint configured on the device itself - appear in logs by name. Queries arriving through a router-level DNS setting all share the router's identity and appear as `__UNIDENTIFIED__`, because NextDNS sees only the WAN address.

Both `nextdns_logs` and `nextdns_analytics` accept a device **name** and resolve it to the id the API expects, since names are what appear in the logs. Ids and `__UNIDENTIFIED__` are passed through unchanged.

## Notes on the API

- **Logging must be enabled** on the profile, with retention covering the window you ask about. If it is off, the log endpoints return nothing at all rather than an error. `nextdns_profile` reports this, and is the first thing to check when a query comes back empty.
- **`limit` has a floor of 10.** The API rejects anything lower with a 400. The plugin raises small values to 10 rather than surfacing an error for it.
- **A custom `User-Agent` is required.** Requests using Python's default are rejected with 403.
- Errors are surfaced with the API's own `detail` text rather than a bare status code, so a malformed query says what was wrong with it.

Output is capped per call so a broad query cannot swamp the agent's context.

## Requirements

- A NextDNS account with an API key
- Duckwork Agent with plugin support
- Python stdlib only - no extra dependencies

## License

MIT
