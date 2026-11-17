# Security Policy

## Supported versions

The developer preview supports the latest release on the `main` branch. Update
to the newest tagged release before reporting a vulnerability.

## Reporting a vulnerability

Do not open a public issue containing a credential, exploitable detail, or
private message. Use GitHub's private vulnerability reporting for this
repository. If that surface is unavailable, contact the maintainer privately
through their GitHub profile and ask for a secure reporting channel.

Include the affected version, Duckwork version, impact, reproduction steps, and a
minimal proof of concept. Remove API keys, JWTs, user addresses, message bodies,
and private service URLs from logs.

## Operator responsibilities

Duckwork plugins execute with the privileges of the Duckwork process. Operators
should review plugin updates, protect `~/.duckwork/.env`, restrict agent API keys
by expiry and CIDR where supported, and use a sender allowlist.
