# Watchline for Duckwork Agent

Watchline is an event layer for agents. This Duckwork plugin delivers matched
Watchline events into a local Duckwork gateway without exposing your laptop to
the internet.

![Watchline Duckwork delivery flow](https://github.com/DuckMind/duckwork)

Watchline uses two integration planes:

- **Hosted MCP** gives Duckwork the watch tools: `start_watch`,
  `continue_watch`, `list_watches`, `pause_watch`, `resume_watch`, and
  `delete_watch`.
- **This plugin** registers a Duckwork gateway platform named `watchline`. It
  polls a Watchline pull channel and forwards matched events as inbound Duckwork
  messages.

The plugin intentionally does not duplicate Watchline tools. Duckwork discovers
tools from the hosted MCP server, and this adapter only handles local delivery.

## Install

```bash
duckwork plugins install qordinate-ai/watchline-duckwork-plugin --enable
```

The package is also available on PyPI:

```bash
python -m pip install watchline-duckwork-plugin
```

For local development:

```bash
duckwork plugins install file:///absolute/path/to/watchline-duckwork-plugin --enable
```

## Configure

Create a Watchline API key and pull channel at <https://watch.qordinate.ai>,
then run:

```bash
duckwork watchline configure \
  --api-key wl_... \
  --channel-id ch_... \
  --user-id me \
  --delivery-channel main \
  --api-base-url https://api.watch.qordinate.ai
```

The command writes:

- `platforms.watchline` for delivery.
- `mcp_servers.watchline` for hosted watch tools.

Restart the Duckwork gateway after changing plugin or MCP config:

```bash
duckwork gateway restart
```

## Use

Ask Duckwork to use Watchline:

```text
Use the Watchline start_watch tool to watch Gmail for emails from my boss.
Ask me for the sender email address if needed.
```

When a matching event arrives, Watchline queues it on your pull channel. The
plugin polls that channel, runs Duckwork against your main/home channel, and
acknowledges the delivery only after Duckwork accepts it.

## Why a Duckwork Plugin?

Duckwork also has a built-in webhook adapter for external events. That is a good
option when your Duckwork gateway already has a public URL, reverse proxy, or
tunnel and you want Watchline to push matched events directly into Duckwork.

This plugin uses Watchline pull delivery instead. Duckwork runs locally, polls the
Watchline channel, and injects matched events into the gateway without requiring
your Duckwork agent to expose an inbound webhook endpoint online. You can still
use Duckwork webhooks separately for deployments where a public callback URL is
already part of your setup.

## Commands

```bash
duckwork watchline status
duckwork watchline install-mcp
duckwork watchline preview-delivery
```

## Configuration Reference

| Field                   | Required | Description                                      |
| ----------------------- | -------- | ------------------------------------------------ |
| `api_key`               | Yes      | Watchline project API key.                       |
| `channel_id`            | Yes      | Watchline pull channel ID.                       |
| `user_id`               | No       | Stable Watchline user id. Defaults to `me`.      |
| `api_base_url`          | No       | Watchline API base URL. Defaults to production.  |
| `poll_interval_seconds` | No       | Delivery polling interval. Minimum is 5 seconds. |
| `delivery_channel`      | No       | Duckwork delivery target. Defaults to `main`, the first configured home channel. Use `telegram`, `discord`, or `telegram:<chat_id>[:thread_id]` to override. |

## Links

- Dashboard: <https://watch.qordinate.ai>
- API: <https://api.watch.qordinate.ai>
- Source: <https://github.com/DuckMind/duckwork>
