"""The ``handflow`` agent tool — one tool, one plan, twelve actions.

Why one tool and not twelve: the whole point is that the plan comes back in the
same call that changes it, so the model never has to spend a turn asking "where
am I". Every action returns the rendered plan plus counts and a next-step hint.

Nothing here fetches, spawns, or calls a model — it edits JSON under
``$DUCKWORK_HOME/handflow`` and hands back text.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any, Dict, List, Optional

from . import store

TOOL_NAME = "handflow"

# "- one", "* one", "• one", "1. one", "2) one" — bullets get pasted at us in all
# of these shapes, and a plan with "*" left in a step title looks broken.
_BULLET = re.compile(r"^\s*(?:[-*•·]|\d+[.)])\s+")

ACTIONS = (
    "start",     # create the plan (goal + steps) and begin step 1
    "plan",      # read the active plan
    "begin",     # mark a step in progress (other in-progress steps auto-close)
    "complete",  # mark a step done, with an optional note of what it produced
    "block",     # mark a step blocked, note required in practice
    "reopen",    # put a completed/blocked step back to not_started
    "note",      # append a note without touching status
    "add",       # insert a step mid-flight (replanning)
    "finish",    # close the plan as done, optional summary note
    "abort",     # close the plan as abandoned, optional reason
    "list",      # recent plans
    "use",       # pin a different plan as active
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _fail(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


def _payload(plan: Dict[str, Any], action: str, extra: Optional[Dict[str, Any]] = None) -> str:
    store.reindex(plan)
    tally = store.counts(plan)
    body: Dict[str, Any] = {
        "ok": True,
        "action": action,
        "plan_id": plan.get("id"),
        "status": plan.get("status"),
        "counts": {k: tally[k] for k in ("done", "total", store.BLOCKED, store.IN_PROGRESS)},
        "plan": store.render(plan),
    }
    nxt = store.find_step(plan, None)
    if plan.get("status") == "active" and nxt is not None:
        body["next_step"] = {"id": nxt.get("id"), "title": nxt.get("title"), "status": nxt.get("status")}
    if tally[store.BLOCKED]:
        body["hint"] = "a step is blocked — resolve it, or add a step that unblocks it, before finishing"
    if extra:
        body.update(extra)
    return json.dumps(body, ensure_ascii=False, indent=1)


def _require_active() -> Any:
    plan = store.active_plan()
    return plan


def _clean_steps(raw: Any) -> List[str]:
    """Accept a list of titles or the same text as bullets ("- a", "2. b")."""
    if isinstance(raw, str):
        parts = [_BULLET.sub("", line).strip() for line in raw.splitlines()]
        return [p for p in parts if p]
    if isinstance(raw, (list, tuple)):
        return [str(s).strip() for s in raw if str(s).strip()]
    return []


# --------------------------------------------------------------------------- #
# the tool
# --------------------------------------------------------------------------- #


def handflow(args: Any = None, **kwargs: Any) -> str:
    """Dispatch one Handflow action. See ``ACTIONS`` for the vocabulary.

    The tool registry calls handlers as ``handler(args_dict, **kw)``, so the
    first positional parameter is the model's arguments object — a signature of
    ``handflow(action="")`` binds that dict to ``action`` and every call falls
    through to the "unknown action" branch. Keyword calls stay supported (tests,
    CLI), but the dict form is the one the agent uses.
    """
    params: Dict[str, Any] = dict(args) if isinstance(args, Mapping) else {}
    params.update(kwargs)
    act = str(params.get("action") or "").strip().lower()
    if act not in ACTIONS:
        return _fail(f"action must be one of: {', '.join(ACTIONS)}")
    kwargs = params

    if act == "start":
        goal = str(kwargs.get("goal") or "").strip()
        steps = _clean_steps(kwargs.get("steps"))
        if not goal:
            return _fail("start needs a goal")
        if not steps:
            return _fail("start needs steps (list of step titles)")
        plan = store.new_plan(goal, steps, executor=str(kwargs.get("executor") or ""))
        store.save(plan)
        store.set_active(plan["id"])
        return _payload(plan, act)

    if act == "list":
        plans = store.list_plans(limit=int(kwargs.get("limit") or 10), include_closed=True)
        return json.dumps(
            {
                "ok": True,
                "action": act,
                "active": store.active_plan_id(),
                "plans": [
                    {
                        "plan_id": p.get("id"),
                        "goal": p.get("goal"),
                        "status": p.get("status"),
                        "counts": {k: v for k, v in store.counts(p).items() if k in ("done", "total")},
                        "updated_at": p.get("updated_at"),
                    }
                    for p in plans
                ],
            },
            ensure_ascii=False,
            indent=1,
        )

    if act == "use":
        plan_id = str(kwargs.get("plan_id") or "").strip()
        plan = store.load(plan_id) if plan_id else None
        if plan is None:
            return _fail(f"no plan {plan_id!r}")
        store.set_active(plan_id)
        return _payload(store.reindex(plan), act)

    plan = _require_active()
    if plan is None:
        return _fail("no active plan — call handflow with action='start' (goal + steps) first")
    store.reindex(plan)

    if act == "plan":
        return _payload(plan, act)

    if act in ("begin", "complete", "block", "reopen"):
        status = {
            "begin": store.IN_PROGRESS,
            "complete": store.COMPLETED,
            "block": store.BLOCKED,
            "reopen": store.NOT_STARTED,
        }[act]
        step_ref = kwargs.get("step") or kwargs.get("step_id")
        try:
            step = store.mark_step(plan, step_ref, status, str(kwargs.get("note") or ""))
        except ValueError as exc:
            return _fail(str(exc))
        store.close_if_done(plan)
        if status == store.NOT_STARTED:
            store.reopen(plan)
        store.save(plan)
        return _payload(plan, act, {"step": {"id": step.get("id"), "title": step.get("title")}})

    if act == "note":
        text = str(kwargs.get("text") or kwargs.get("note") or "").strip()
        if not text:
            return _fail("note needs text")
        step = store.find_step(plan, kwargs.get("step"))
        if step is None:
            return _fail("no step to attach the note to")
        step.setdefault("notes", []).append(text)
        store._log_event(plan, "note", text[:60])
        store.save(plan)
        return _payload(plan, act, {"step": {"id": step.get("id")}})

    if act == "add":
        title = str(kwargs.get("title") or "").strip()
        if not title:
            return _fail("add needs a title")
        step = store.add_step(plan, title, kwargs.get("position"))
        store.reopen(plan)
        store.save(plan)
        return _payload(plan, act, {"step": {"id": step.get("id"), "title": step.get("title")}})

    # finish / abort
    summary = str(kwargs.get("summary") or kwargs.get("note") or "").strip()
    if act == "finish":
        open_steps = store.open_work(plan)
        if open_steps and not kwargs.get("force"):
            titles = "; ".join(str(s.get("title")) for s in open_steps[:4])
            return _fail(
                f"{len(open_steps)} step(s) still open ({titles}) — close them, or pass force=true to finish anyway"
            )
    plan["status"] = "done" if act == "finish" else "aborted"
    plan["closed_at"] = store._now()
    if summary:
        plan.setdefault("events", []).append({"ts": store._now(), "kind": act, "detail": summary})
    store._log_event(plan, act, summary[:80])
    store.save(plan)
    return _payload(plan, act, {"summary": summary} if summary else None)


HANDLERS = {TOOL_NAME: handflow}

SCHEMAS: Dict[str, Dict[str, Any]] = {
    TOOL_NAME: {
        "name": TOOL_NAME,
        "description": (
            "Keep a visible plan for a multi-step task, the way a Manus-style agent does. "
            "Call action='start' with the goal and the step list BEFORE you begin work, then "
            "action='complete' / 'block' / 'begin' each step as you go, with a short note. "
            f"Actions: {', '.join(ACTIONS)}. "
            "Every call returns the rendered plan. Steps can be referenced by 1-based number, "
            "id, title substring, or omitted for the current step. 'add' replans mid-flight; "
            "'finish' closes it. State is local JSON — no network, no model call."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": list(ACTIONS), "description": "what to do"},
                "goal": {"type": "string", "description": "start: the outcome the user asked for"},
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "start: ordered step titles (3-8 is the sweet spot)",
                },
                "step": {
                    "type": "string",
                    "description": "which step: 1-based number, id, title substring, or omit for current",
                },
                "note": {"type": "string", "description": "short note; what produced, or why blocked"},
                "title": {"type": "string", "description": "add: title of the new step"},
                "position": {"type": "integer", "description": "add: insert at this 1-based position"},
                "text": {"type": "string", "description": "note: text to append"},
                "summary": {"type": "string", "description": "finish/abort: one line on the outcome"},
                "force": {"type": "boolean", "description": "finish: close even with steps still open"},
                "plan_id": {"type": "string", "description": "use: plan to make active"},
                "limit": {"type": "integer", "description": "list: how many plans"},
                "executor": {"type": "string", "description": "start: label for who works the plan"},
            },
            "required": ["action"],
        },
    }
}
