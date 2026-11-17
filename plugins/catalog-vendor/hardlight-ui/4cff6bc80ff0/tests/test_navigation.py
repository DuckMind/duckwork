"""Structural navigation tests; no browser or network required."""
import importlib
import json
import pytest
from copy import deepcopy
from pathlib import Path


INVALID = json.loads((Path(__file__).parent / "fixtures/nav-invalid.json").read_text())


@pytest.mark.parametrize("arguments", INVALID)
def test_invalid_inputs_return_actionable_json(arguments):
    result = analyze(**arguments)
    assert result["ok"] is False
    assert isinstance(result["error"], str) and result["error"]
    json.dumps(result, allow_nan=False)


def test_bounds_types_tie_breaking_and_no_mutation():
    page = {"id": "a", "label": "A", "links": []}
    task = {"name": "T", "start": "a", "goal": "a"}
    for args in [
        ([page] * 301, []), ([page], [task] * 101),
        ([{**page, "id": "x" * 201}], []),
        ([{**page, "label": "x" * 501}], []),
        ([{**page, "links": [{"to": "a", "label": "A"}] * 1001}], []),
        ([{**page, "links": [None]}], []),
        ([None], []), ([page], [None]), ((page,), []),
        ([page], [{**task, "max_steps": 1000001}]),
    ]:
        assert analyze(*args)["ok"] is False
    chain = [{"id": str(i), "label": str(i), "links": [{"to": str(i + 1), "label": "Next"}] if i < 299 else []} for i in range(300)]
    original = deepcopy(chain)
    result = analyze(chain, [{"name": "Long", "start": "0", "goal": "299"}])
    assert result["tasks"][0]["steps"] == 299
    assert result["tasks"][0]["over_budget"] is None
    assert chain == original
    assert analyze([page], [task] * 100)["ok"] is True
    diamond = [{"id": "s", "label": "S", "links": [{"to": "b", "label": "B"}, {"to": "a", "label": "A"}]},
               {"id": "a", "label": "A", "links": [{"to": "g", "label": "G"}]},
               {"id": "b", "label": "B", "links": [{"to": "g", "label": "G"}]},
               {"id": "g", "label": "G", "links": []}]
    assert analyze(diamond, [{"name": "T", "start": "s", "goal": "g"}])["tasks"][0]["path"] == ["s", "b", "g"]


def analyze(*args, **kwargs):
    return importlib.import_module("hardlight.navigation").analyze_navigation(*args, **kwargs)


def test_shortest_paths_cycles_and_explicit_budgets():
    pages = [
        {"id": "home", "label": "Home", "links": [{"to": "a", "label": "A"}, {"to": "goal", "label": "Finish"}]},
        {"id": "a", "label": "A", "links": [{"to": "home", "label": "Home"}, {"to": "goal", "label": "Finish"}]},
        {"id": "goal", "label": "Goal", "links": []},
    ]
    result = analyze(pages, [
        {"name": "Finish", "start": "home", "goal": "goal", "max_steps": 0},
        {"name": "Already there", "start": "home", "goal": "home"},
    ])
    assert result["ok"] is True
    assert result["tasks"][0]["path"] == ["home", "goal"]
    assert result["tasks"][0]["steps"] == 1
    assert result["tasks"][0]["over_budget"] is True
    assert result["tasks"][1]["path"] == ["home"]
    assert result["tasks"][1]["steps"] == 0
    assert result["tasks"][1]["over_budget"] is None
    assert result["coverage"]["edge_count"] == 4
    assert "usability" in " ".join(result["limitations"]).lower()
    json.dumps(result, allow_nan=False)


def test_unknown_targets_ambiguity_unreachable_and_dead_ends():
    pages = [
        {"id": "home", "label": "Home", "links": [
            {"to": "b", "label": "More"}, {"to": "a", "label": "More"},
            {"to": "b", "label": "More"}, {"to": "missing", "label": "Broken"}]},
        {"id": "a", "label": "A", "links": []},
        {"id": "b", "label": "B", "links": []},
        {"id": "island", "label": "Island", "links": []},
    ]
    result = analyze(pages, [{"name": "Isolated", "start": "home", "goal": "island", "max_steps": 2}])
    assert result["unknown_targets"] == [{"source": "home", "to": "missing", "label": "Broken"}]
    assert result["ambiguous_labels"] == [{"source": "home", "label": "More", "targets": ["b", "a"]}]
    assert result["unreachable_pages"] == ["island"]
    assert result["dead_ends"] == ["a", "b"]
    assert result["tasks"][0]["path"] is None
    assert result["tasks"][0]["steps"] is None
    assert result["tasks"][0]["over_budget"] is None
    assert result["coverage"]["edge_count"] == 4
    assert result["coverage"]["known_edge_count"] == 3
    assert analyze(pages, [], home="island")["unreachable_pages"] == ["home", "a", "b"]
    assert result == analyze(pages, [{"name": "Isolated", "start": "home", "goal": "island", "max_steps": 2}])
