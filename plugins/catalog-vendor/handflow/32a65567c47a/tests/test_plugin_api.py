"""Backend routes: the pane's read and click paths, exercised through FastAPI."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from handflow import store
from handflow.tools import handflow
from helpers import call

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(hf_home):
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    spec = importlib.util.spec_from_file_location("handflow_api", ROOT / "dashboard" / "plugin_api.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["handflow_api"] = mod
    spec.loader.exec_module(mod)
    app = FastAPI()
    app.include_router(mod.router, prefix="/api/plugins/handflow")
    return TestClient(app)


def test_active_is_null_before_anything_happens(client):
    body = client.get("/api/plugins/handflow/active").json()
    assert body["ok"] is True
    assert body["plan"] is None
    assert body["state_dir"]


def test_active_returns_the_same_text_the_agent_reads(client, hf_home):
    call(handflow, action="start", goal="Ship it", steps=["one", "two"])
    body = client.get("/api/plugins/handflow/active").json()
    assert body["plan"]["goal"] == "Ship it"
    assert body["counts"]["total"] == 2
    assert body["text"] == store.render(store.active_plan())
    assert body["current_step_id"] == body["plan"]["steps"][0]["id"]


def test_the_pane_can_complete_a_step(client, hf_home):
    started = call(handflow, action="start", goal="g", steps=["one", "two"])
    step_id = started["plan_id"] and store.active_plan()["steps"][0]["id"]
    body = client.post(f"/api/plugins/handflow/plans/{started['plan_id']}/steps/{step_id}", json={"op": "complete"}).json()
    assert body["counts"]["done"] == 1
    assert store.load(started["plan_id"])["steps"][0]["status"] == store.COMPLETED


def test_completing_the_last_step_from_the_pane_closes_the_plan(client, hf_home):
    started = call(handflow, action="start", goal="g", steps=["one"])
    step_id = store.active_plan()["steps"][0]["id"]
    body = client.post(f"/api/plugins/handflow/plans/{started['plan_id']}/steps/{step_id}", json={"op": "complete"}).json()
    assert body["plan"]["status"] == "done"


def test_bad_ops_and_missing_plans_are_4xx_not_500(client, hf_home):
    started = call(handflow, action="start", goal="g", steps=["one"])
    step_id = store.active_plan()["steps"][0]["id"]
    assert client.post(f"/api/plugins/handflow/plans/{started['plan_id']}/steps/{step_id}", json={"op": "yeet"}).status_code == 400
    assert client.post("/api/plugins/handflow/plans/plan_nope/steps/s1", json={"op": "complete"}).status_code == 404
    assert client.get("/api/plugins/handflow/plans/plan_nope").status_code == 404
    assert client.post("/api/plugins/handflow/active", json={"plan_id": "plan_nope"}).status_code == 404


def test_plans_endpoint_lists_recent_work(client, hf_home):
    call(handflow, action="start", goal="first", steps=["a"])
    call(handflow, action="start", goal="second", steps=["b"])
    body = client.get("/api/plugins/handflow/plans?limit=5").json()
    assert [p["goal"] for p in body["plans"]] == ["second", "first"]
    assert body["active_plan_id"] == body["plans"][0]["plan_id"]


def test_health_reports_where_state_lives(client, hf_home):
    body = client.get("/api/plugins/handflow/health").json()
    assert body["ok"] is True
    assert body["state_dir"].endswith("handflow")
