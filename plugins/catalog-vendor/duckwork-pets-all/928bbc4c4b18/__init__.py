"""All Pets — agent half.

One read-only tool over the local pet store, so the agent can answer "what pets do I
have / which one is active" without shelling out to the CLI. The desktop half
(``desktop/plugin.js``) is the gallery pane the user picks from, which is what the
built-in 60-row preview cannot show.

No network, no credentials, no environment variables. ``list_pets`` reads
``agent.pet.store`` (the same store the desktop picker uses) and the active slug from
``display.pet.slug``; it never writes anything.
"""

from __future__ import annotations

LIST_PETS_SCHEMA = {
    "name": "list_pets",
    "description": (
        "List the animated pets (mascots) installed for this Duckwork profile: slug, display "
        "name, whether the sprite is present, and which pet is currently active. Read-only."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _active_slug() -> str:
    """``display.pet.slug`` from config, or \"\" when unset/unreadable."""
    try:
        from duckwork_cli.config import load_config

        display = load_config().get("display") or {}
        return str((display.get("pet") or {}).get("slug") or "")
    except Exception:  # noqa: BLE001 - a display preference must never break the tool
        return ""


def _handle_list_pets(args: dict, **_kwargs) -> str:  # noqa: ARG001 - tool handlers take (args, **kw)
    from agent.pet import store
    from tools.registry import tool_error, tool_result

    try:
        pets = store.installed_pets()
    except Exception as exc:  # noqa: BLE001 - normalize to one tool error
        return tool_error(f"could not read the pet store: {exc}")

    active = _active_slug()
    rows = [
        {
            "slug": pet.slug,
            "displayName": pet.display_name,
            "sprite": pet.exists,
            "active": bool(active) and pet.slug == active,
            "generated": pet.generated,
        }
        for pet in pets
    ]
    return tool_result({"count": len(rows), "active": active, "pets": rows})


def register(ctx) -> None:
    """Called once by the plugin loader."""
    ctx.register_tool(
        name="list_pets",
        toolset="duckwork-pets-all",
        schema=LIST_PETS_SCHEMA,
        handler=_handle_list_pets,
        description="List installed Duckwork pets and the active one",
        emoji="🐾",
    )
