"""Standalone ASGI entrypoint for the Spectator plugin namespace.

WHY THIS EXISTS (integration note)
----------------------------------
The plugin's ``router`` is normally mounted by the Duckwork host at
``/api/plugins/spectator/`` inside the dashboard web server, where every
``/api/`` route is gated by the dashboard's session-token auth middleware
(``auth_middleware`` in ``duckwork_cli/web_server.py``). A guest browser holds
only a guest token — it can never pass that host gate. WebSocket upgrades are
exempt (the gate is a BaseHTTPMiddleware, which does not wrap WS), but the
plain-HTTP routes the guest needs (``/guest.html``, ``/invites/join``,
``/feed``, ``/suggestions``) would 401 before reaching the plugin router.

So the plain-browser guest flow requires the namespace to be served on its own
loopback port with NO host auth in front. The plugin's own auth layers remain
the security boundary:

  * WS ``/events`` — first-frame HMAC guest-token auth (token never in URL)
  * REST data routes — bearer ``guest_token`` (verify_guest_token)
  * ``/guest.html`` / ``/invites/join`` — public (the invite token is the
    credential)

The DB + host_secret live in ``$DUCKWORK_HOME/data/spectator/``
(``~/.duckwork/data/spectator/`` when ``DUCKWORK_HOME`` is unset), shared with the
host-mounted plugin, so invites minted by the host CLI are joinable by guests
here. SQLite WAL + busy_timeout=5000 make the cross-process access safe.

Run:

    python -m spectator.serve                # binds 127.0.0.1:8788
    uvicorn spectator.serve:app --port 8788  # same, via uvicorn CLI

Expose for a two-device demo (loopback bind stays intact):

    tailscale serve --bg https+insecure://127.0.0.1:8788
"""

from __future__ import annotations

from fastapi import FastAPI

# Tests and clone-style directory plugins historically import the dashboard API
# as a flat module. Wheels install it as the ``dashboard`` package. Prefer the
# existing flat module when present so both paths share one state singleton.
try:
    import plugin_api as plugin_api  # type: ignore[no-redef]
except ModuleNotFoundError:
    from dashboard import plugin_api

app = FastAPI(title="spectator", version="0.2.0")
app.include_router(plugin_api.router, prefix="/api/plugins/spectator")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8788, log_level="warning")


if __name__ == "__main__":
    main()
