"""Tests for conftest's Duckwork dependency-venv bridge.

Duckwork' plugin manager records its committed dependency venv in
``<duckwork home>/installs/<key>/facts.json`` (``packages.venv.environment``).
``_venv_site_packages`` must find it, and must never raise on malformed
records — the bridge runs at conftest import time, so a crash kills the
whole suite (the opposite of the fail-open bootstrap intent).
"""

import json

import conftest


def _make_duckwork_root(tmp_path):
    duckwork_root = tmp_path / "duckwork-agent"
    duckwork_root.mkdir()
    return duckwork_root


def _write_facts(tmp_path, payload):
    installs = tmp_path / "installs" / "somekey"
    installs.mkdir(parents=True, exist_ok=True)
    (installs / "facts.json").write_text(json.dumps(payload), encoding="utf-8")


def test_recorded_pm_venv_site_packages_is_discovered(tmp_path):
    duckwork_root = _make_duckwork_root(tmp_path)
    venv = tmp_path / "env" / "venv"
    site = venv / "Lib" / "site-packages"
    site.mkdir(parents=True)
    _write_facts(
        tmp_path,
        {"packages": {"venv": {"environment": str(venv)}}},
    )

    found = [str(p) for p in conftest._venv_site_packages(duckwork_root)]

    assert str(site) in found


def test_corrupt_facts_json_is_skipped(tmp_path):
    duckwork_root = _make_duckwork_root(tmp_path)
    installs = tmp_path / "installs" / "somekey"
    installs.mkdir(parents=True)
    (installs / "facts.json").write_text("{not json", encoding="utf-8")

    assert list(conftest._venv_site_packages(duckwork_root)) == []


def test_non_object_facts_json_is_skipped(tmp_path):
    # Valid JSON with the wrong shape must not raise AttributeError at
    # conftest import time (pm's own _recorded_venv guards the same way).
    duckwork_root = _make_duckwork_root(tmp_path)
    venv = tmp_path / "env" / "venv"
    (venv / "Lib" / "site-packages").mkdir(parents=True)
    for payload in (
        None,
        ["a", "b"],
        "just a string",
        {"packages": "not-a-dict"},
        {"packages": {"venv": "not-a-dict"}},
    ):
        _write_facts(tmp_path, payload)
        assert list(conftest._venv_site_packages(duckwork_root)) == []


def test_recorded_venv_without_site_packages_yields_nothing(tmp_path):
    duckwork_root = _make_duckwork_root(tmp_path)
    venv = tmp_path / "env" / "venv"  # exists only on paper
    _write_facts(
        tmp_path,
        {"packages": {"venv": {"environment": str(venv)}}},
    )

    assert list(conftest._venv_site_packages(duckwork_root)) == []


def test_in_tree_venv_still_discovered(tmp_path):
    duckwork_root = _make_duckwork_root(tmp_path)
    site = duckwork_root / "venv" / "Lib" / "site-packages"
    site.mkdir(parents=True)

    found = [str(p) for p in conftest._venv_site_packages(duckwork_root)]

    assert str(site) in found
