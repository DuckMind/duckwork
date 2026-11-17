"""Desktop routes reuse the registered plugin command and its ctx.llm facade."""
import asyncio
import json

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/status")
def status():
    return {"ok": True, "name": "Duckwork Agent Builder", "version": "1.0.0"}


@router.post("/action")
async def action(body: dict):
    from duckwork_cli.plugins import get_plugin_command_handler
    # Native discovery and enable gates are authoritative; no private manager lookup.
    handler = get_plugin_command_handler("agent-builder-action")
    if handler is None:
        raise HTTPException(503, "Enable Duckwork Agent Builder's agent component in Capabilities → Plugins, then reconnect the backend.")
    limit = {"interview": 115, "build": 165, "refine": 165, "trial": 165, "compare": 285}.get(body.get("action"), 45)
    try:
        result = json.loads(await asyncio.wait_for(asyncio.to_thread(handler, json.dumps(body)), timeout=limit))
    except asyncio.TimeoutError:
        raise HTTPException(504, "Your Duckwork model took too long to respond. Your brief is saved. Check My agents before retrying: the previous request may still finish in the background.") from None
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result
