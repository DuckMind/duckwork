"""Shipped capability evidence and native discovery contracts, not taste tests."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys

from hardlight.library import get_reference

ROOT = Path(__file__).resolve().parents[1]


def test_modern_topics_resolve_with_evidence_and_fallbacks():
    assert {"layout", "platform", "performance"} <= set(get_reference()["topics"])
    for topic in ("layout", "platform", "performance"):
        result = get_reference(topic)
        assert result["ok"], result
        assert "fallback" in result["content"].lower()
        assert "https://" in result["content"]
    result = get_reference("platform")
    assert result["schema_version"] == 1
    assert len(result["features"]) >= 8
    ids = [item["id"] for item in result["features"]]
    assert len(ids) == len(set(ids))
    for item in result["features"]:
        assert set(item) == {"id", "feature", "tier", "checked", "source", "job", "detection", "fallback", "constraints", "verify"}
        assert item["tier"] in {"established", "enhancement", "experimental"}
        assert all(isinstance(v, str) and v.strip() for v in item.values())
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["checked"])
        assert item["source"].startswith("https://")
    assert "not a compatibility guarantee" in result["content"]


def test_platform_resources_work_in_package_layout(tmp_path):
    package = tmp_path / "hardlight"
    package.mkdir()
    shutil.copy(ROOT / "hardlight/library.py", package / "library.py")
    for directory in ("data", "references"):
        shutil.copytree(ROOT / directory, package / directory)
    spec = importlib.util.spec_from_file_location("packaged_library", package / "library.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.get_reference("platform")["ok"] is True
    assert module.get_reference("platform") == get_reference("platform")
    (package / "data/platform-features.json").write_text("{broken", encoding="utf-8")
    assert module.get_reference("platform")["ok"] is False


def test_native_topic_schema_matches_library():
    spec = importlib.util.spec_from_file_location("platform_contract_plugin", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    reference = next(tool for tool in module._TOOLS if tool[0] == "hardlight_reference")
    assert reference[3]["topic"]["enum"] == get_reference()["topics"]
    handler = module._handler(reference[1])
    assert json.loads(handler({"topic": "platform"}, task_id="context-test"))["features"]
