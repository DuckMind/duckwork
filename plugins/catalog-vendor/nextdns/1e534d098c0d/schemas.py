"""Tool schemas for the NextDNS plugin. Descriptions are what the LLM reads -
they say when to use each tool and what it returns."""

_PROFILE = {
    "type": "string",
    "description": "NextDNS profile id. Omit to use the configured default.",
}

LOGS = {
    "name": "nextdns_logs",
    "description": (
        "Query the NextDNS DNS log for a profile. Use for 'was this domain "
        "resolved', 'what did device X look up', or 'what happened around "
        "time T'. Returns timestamp, domain, status (default/blocked), the "
        "device that asked, matched blocklists, and protocol. Devices that "
        "query NextDNS directly are named; anything behind a router-level "
        "DNS setting reports as 'unidentified'. Use nextdns_blocked when the "
        "question is specifically about blocking."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "search": {"type": "string", "description": "Match domain names, e.g. 'plex.tv'"},
            "status": {
                "type": "string",
                "enum": ["default", "blocked", "allowed", "error"],
                "description": "Filter by query outcome",
            },
            "device": {
                "type": "string",
                "description": "Device name, or __UNIDENTIFIED__ for unattributed queries",
            },
            "from": {"type": "string", "description": "Start time, ISO-8601 or relative like -1h"},
            "to": {"type": "string", "description": "End time, ISO-8601"},
            "limit": {"type": "integer", "description": "Rows to return (min 10, max 1000)"},
            "cursor": {"type": "string", "description": "Pagination cursor from a previous call"},
            "profile": _PROFILE,
        },
    },
}

BLOCKED = {
    "name": "nextdns_blocked",
    "description": (
        "Recently blocked DNS queries with the blocklist that matched each "
        "one. Use when something is not working and DNS blocking is a "
        "suspect, or to answer 'why was this domain blocked'. Accepts the "
        "same filters as nextdns_logs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "search": {"type": "string", "description": "Match domain names"},
            "device": {"type": "string", "description": "Device name"},
            "from": {"type": "string", "description": "Start time"},
            "to": {"type": "string", "description": "End time"},
            "limit": {"type": "integer", "description": "Rows to return (min 10, max 1000)"},
            "profile": _PROFILE,
        },
    },
}

ANALYTICS = {
    "name": "nextdns_analytics",
    "description": (
        "Aggregate NextDNS counts rather than individual queries. Use for "
        "'top blocked domains', 'which blocklist blocks the most', 'which "
        "devices are noisiest', or overall query/block totals. Far cheaper "
        "than paging through logs for volume questions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": ["status", "domains", "reasons", "ips", "devices", "protocols",
                         "queryTypes", "ipVersions", "dnssec", "encryption", "destinations"],
                "description": "What to aggregate (default 'status')",
            },
            "device": {"type": "string", "description": "Limit to one device"},
            "from": {"type": "string", "description": "Start time"},
            "to": {"type": "string", "description": "End time"},
            "limit": {"type": "integer", "description": "Rows (min 10, max 500)"},
            "profile": _PROFILE,
        },
    },
}

PROFILE = {
    "name": "nextdns_profile",
    "description": (
        "Profile settings: name, whether logging is enabled, retention, log "
        "storage region, and active blocklists. Check this first when log "
        "queries come back empty - logging can be off, or retention shorter "
        "than the window being asked about. With no profile configured, "
        "lists the profiles the API key can see."
    ),
    "parameters": {"type": "object", "properties": {"profile": _PROFILE}},
}
