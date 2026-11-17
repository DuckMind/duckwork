"""Duckwork Agent Builder. All model calls use the host's credential-aware facade."""
import json
from pathlib import Path

from .builder import Builder


def register(ctx):
    def action(raw="", **kwargs):
        try:
            return json.dumps(Builder(ctx.llm).dispatch(json.loads(raw)), ensure_ascii=False)
        except Exception as exc:
            # The desktop shows failures inline; never substitute a canned model response.
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    def build(raw="", **kwargs):
        result = json.loads(action(json.dumps({"action": "build", "brief": raw})))
        if result.get("error"):
            return result["error"]
        draft = result["draft"]
        return (f"Draft created: {draft['plan']['name']} ({draft['id']}).\n"
                "Open Duckwork Agent Builder to edit, try, and save it.\n\n"
                + draft["plan"]["instructions"])

    ctx.register_command(name="build-agent", handler=build,
                         description="Build a specialist agent from a plain-language brief")
    ctx.register_command(name="agent-builder-action", handler=action,
                         description="Duckwork Agent Builder's structured desktop actions")
    ctx.register_tool(
        name="agent_builder", toolset="duckwork_agent_builder",
        schema={"name": "agent_builder", "description":
                "Create or refine a reusable specialist agent draft. Does not create a profile until the user saves it in Duckwork Agent Builder.",
                "parameters": {"type": "object", "properties": {
                    "brief": {"type": "string", "description": "The job the specialist should perform"},
                    "draft_id": {"type": "string", "description": "Existing draft ID, for refinement"}},
                    "required": ["brief"], "additionalProperties": False}},
        handler=lambda args, **kw: action(json.dumps({
            "action": "refine" if args.get("draft_id") else "build",
            "id": args.get("draft_id"), "brief": args.get("brief", "")})),
    )
    ctx.register_skill("agent-building", Path(__file__).parent / "skills" / "agent-building" / "SKILL.md")
