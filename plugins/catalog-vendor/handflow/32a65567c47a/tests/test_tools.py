"""The agent-facing tool: one action vocabulary, no surprises."""

from __future__ import annotations

import json

from handflow import store
from handflow.tools import handflow
from helpers import call


def test_handler_accepts_the_registrys_positional_args_dict(hf_home):
    """Regression: ``entry.handler(args, **kw)`` passes the arguments as ONE positional dict.

    Written after the live registry round-trip failed while this suite was green:
    a handler signature of ``handflow(action="")`` binds the args dict to
    ``action`` and every agent call lands in the "unknown action" branch.
    """
    reply = json.loads(handflow({"action": "start", "goal": "g", "steps": ["one"]}))
    assert reply["ok"] is True, reply
    assert json.loads(handflow({"action": "plan"}))["plan_id"] == reply["plan_id"]
    # the keyword form stays valid too (CLI, tests, scripts)
    assert json.loads(handflow(action="plan"))["ok"] is True


def test_start_creates_the_plan_and_returns_it(hf_home):
    reply = call(handflow, action="start", goal="Ship the catalog entry", steps=["write it", "pin the sha", "open the PR"])
    assert reply["ok"] is True
    assert reply["counts"]["total"] == 3
    assert "1. [→] write it" in reply["plan"]
    assert reply["next_step"]["title"] == "write it"
    assert store.active_plan_id() == reply["plan_id"]


def test_start_from_a_multiline_string(hf_home):
    reply = call(handflow, action="start", goal="g", steps="- one\n- two\n* three")
    assert [s["title"] for s in store.active_plan()["steps"]] == ["one", "two", "three"]


def test_start_needs_a_goal_and_steps(hf_home):
    assert call(handflow, action="start", steps=["a"])["ok"] is False
    assert call(handflow, action="start", goal="g")["ok"] is False
    assert "goal" in call(handflow, action="start", steps=["a"])["error"]


def test_unknown_action_is_rejected_with_the_vocabulary(hf_home):
    reply = call(handflow, action="levitate")
    assert reply["ok"] is False
    assert "start" in reply["error"] and "finish" in reply["error"]


def test_actions_without_a_plan_say_so(hf_home):
    reply = call(handflow, action="complete", step=1)
    assert reply["ok"] is False
    assert "no active plan" in reply["error"]


def test_completing_every_step_closes_the_plan(hf_home):
    call(handflow, action="start", goal="g", steps=["one", "two"])
    call(handflow, action="complete", step=1, note="did it")
    reply = call(handflow, action="complete", step=2)
    assert reply["status"] == "done"
    assert reply["counts"]["done"] == 2
    assert "closed" in reply["plan"]


def test_finish_refuses_while_steps_are_open_then_honours_force(hf_home):
    call(handflow, action="start", goal="g", steps=["one", "two"])
    refused = call(handflow, action="finish")
    assert refused["ok"] is False and "still open" in refused["error"]
    forced = call(handflow, action="finish", force=True, summary="good enough")
    assert forced["status"] == "done"
    assert forced["summary"] == "good enough"


def test_block_then_reopen(hf_home):
    call(handflow, action="start", goal="g", steps=["one", "two"])
    blocked = call(handflow, action="block", step=1, note="no credentials")
    assert "1. [!] one" in blocked["plan"]
    assert "blocked" in blocked["hint"]
    reopened = call(handflow, action="reopen", step=1)
    assert reopened["status"] == "active"
    assert "1. [ ] one" in reopened["plan"]


def test_add_replans_and_reopens_a_closed_plan(hf_home):
    call(handflow, action="start", goal="g", steps=["one"])
    call(handflow, action="complete", step=1)
    assert store.active_plan()["status"] == "done"
    added = call(handflow, action="add", title="and then this")
    assert added["status"] == "active"
    assert "and then this" in added["plan"]
    assert call(handflow, action="add")["ok"] is False


def test_note_appends_without_touching_status(hf_home):
    call(handflow, action="start", goal="g", steps=["one"])
    reply = call(handflow, action="note", text="12 tables extracted")
    assert "note: 12 tables extracted" in reply["plan"]
    assert store.active_plan()["steps"][0]["status"] == store.IN_PROGRESS
    assert call(handflow, action="note")["ok"] is False


def test_notes_survive_a_reload(hf_home):
    call(handflow, action="start", goal="g", steps=["one"])
    call(handflow, action="note", text="kept")
    assert "kept" in store.render(store.active_plan())


def test_list_and_use_switch_the_active_plan(hf_home):
    first = call(handflow, action="start", goal="first task", steps=["a"])
    second = call(handflow, action="start", goal="second task", steps=["b"])
    listing = call(handflow, action="list")
    assert {p["goal"] for p in listing["plans"]} == {"first task", "second task"}
    assert listing["active"] == second["plan_id"]
    switched = call(handflow, action="use", plan_id=first["plan_id"])
    assert switched["plan_id"] == first["plan_id"]
    assert store.active_plan_id() == first["plan_id"]
    assert call(handflow, action="use", plan_id="plan_nope")["ok"] is False


def test_every_mutation_is_on_disk_afterwards(hf_home):
    reply = call(handflow, action="start", goal="g", steps=["one"])
    call(handflow, action="complete", step=1, note="done")
    on_disk = store.load(reply["plan_id"])
    assert on_disk["steps"][0]["status"] == store.COMPLETED
    assert on_disk["events"], "plan keeps an audit trail"
    assert any(ev["kind"] == "complete" for ev in on_disk["events"])
