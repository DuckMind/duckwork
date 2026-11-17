"""Credential-boundary tests for static API-key provider scripts."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "script",
    [
        "youtube_search.py",
        "crux_history.py",
        "pagespeed_check.py",
        "nlp_analyze.py",
        "lighthouse_agentic.py",
    ],
)
def test_google_cli_rejects_api_key_arguments(
    script: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    if script == "youtube_search.py":
        package = types.ModuleType("googleapiclient")
        package.__path__ = []
        discovery = types.ModuleType("googleapiclient.discovery")
        discovery.build = lambda *_args, **_kwargs: None
        monkeypatch.setitem(sys.modules, "googleapiclient", package)
        monkeypatch.setitem(sys.modules, "googleapiclient.discovery", discovery)
        module = _load("youtube_cli_without_key_arg", "scripts/youtube_search.py")
        monkeypatch.setattr(sys, "argv", [script, "--api-key", "fake-key"])
        with pytest.raises(SystemExit) as exc:
            module.main()
        assert exc.value.code == 2
        assert "invalid choice" in capsys.readouterr().err
        return

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), "--api-key", "fake-key"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 2
    assert "unrecognized arguments:" in result.stderr


def _public_instruction_markdown() -> list[Path]:
    paths = [ROOT / "README.md"]
    for directory in ("docs", "skills", "extensions"):
        paths.extend((ROOT / directory).rglob("*.md"))
    return paths


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("script", ["generate.py", "edit.py"])
def test_banana_cli_has_no_api_key_argument(script: str) -> None:
    source = (ROOT / "extensions" / "banana" / "scripts" / script).read_text()
    assert "--api-key" not in source


@pytest.mark.parametrize("script", ["generate.py", "edit.py"])
def test_banana_ignores_legacy_google_api_key_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], script: str
) -> None:
    module = _load(f"banana_{script[:-3]}", f"extensions/banana/scripts/{script}")
    def unexpected_call(*_args, **_kwargs):
        pytest.fail("provider call attempted with legacy ambient credential")

    monkeypatch.setattr(
        module,
        "generate_image" if script == "generate.py" else "edit_image",
        unexpected_call,
    )
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "legacy-key-must-not-be-used")
    argv = [script, "--prompt", "test", "--model", "test-model"]
    if script == "edit.py":
        argv[1:1] = ["--image", "missing.png"]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert exc.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] is True
    assert "GOOGLE_AI_API_KEY" in payload["message"]
    assert "--api-key" not in payload["message"]


def test_indexnow_cli_has_no_key_argument() -> None:
    source = (ROOT / "scripts" / "indexnow_submit.py").read_text()
    assert '"--key"' not in source


def test_indexnow_reads_key_only_from_injected_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load("indexnow_env_auth", "scripts/indexnow_submit.py")
    monkeypatch.setenv("INDEXNOW_KEY", "k" * 32)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "indexnow_submit.py",
            "--host",
            "example.com",
            "--key-location",
            "https://example.com/key.txt",
            "--verify-only",
            "--json",
        ],
    )
    seen: dict[str, str] = {}

    def verify(host: str, key: str, location: str) -> dict[str, bool]:
        seen.update(host=host, key=key, location=location)
        return {"ok": True}

    monkeypatch.setattr(module, "verify_key_published", verify)
    assert module.main() == 0
    assert seen["key"] == "k" * 32


def test_banana_setup_uses_injected_env_without_reading_claude_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".claude.json").write_text("not valid json", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "profile-scoped-secret")
    monkeypatch.delenv("NANOBANANA_MODEL", raising=False)
    module = _load("banana_validate_env", "extensions/banana/scripts/validate_setup.py")
    monkeypatch.setattr(module, "OUTPUT_DIR", output)
    monkeypatch.setattr(module.shutil, "which", lambda _name: "/usr/bin/npx")
    monkeypatch.setattr(sys, "argv", ["validate_setup.py", "--model", "gemini-test-image"])

    assert module.main() == 0
    output_text = capsys.readouterr().out
    assert "profile-scoped-secret" not in output_text
    assert ".claude.json" not in output_text
    assert "GOOGLE_AI_API_KEY is available" in output_text


def test_banana_setup_fails_cleanly_without_injected_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    monkeypatch.delenv("NANOBANANA_MODEL", raising=False)
    module = _load("banana_validate_missing", "extensions/banana/scripts/validate_setup.py")
    monkeypatch.setattr(module, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(module.shutil, "which", lambda _name: "/usr/bin/npx")
    monkeypatch.setattr(sys, "argv", ["validate_setup.py", "--model", "gemini-test-image"])

    assert module.main() == 1
    output_text = capsys.readouterr().out
    assert "GOOGLE_AI_API_KEY is available" in output_text
    assert "FAIL" in output_text


def test_dataforseo_credentials_require_exact_injected_env_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load("dataforseo_env_auth", "scripts/dataforseo_merchant.py")
    for name in ("DATAFORSEO_USERNAME", "DATAFORSEO_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATAFORSEO_LOGIN", "legacy-user")
    monkeypatch.setenv("DATAFORSEO_API_KEY", "legacy-key")

    with pytest.raises(SystemExit) as exc:
        module._get_credentials()

    assert exc.value.code == 1


def test_authenticated_documentation_uses_native_tool_with_valid_schema() -> None:
    contract = _load("auth_contract_docs", "scripts/auth_contract.py")
    scripts = set(contract.SCRIPT_SECRETS)
    scripts.update(script for _extension, script in contract.EXTENSION_SECRETS)
    script_pattern = "|".join(re.escape(name) for name in sorted(scripts))
    forbidden_cli = re.compile(
        rf"duckwork\s+seo\s+run(?:\s+--extension\s+banana)?\s+(?:{script_pattern})\b"
    )
    decoder = json.JSONDecoder()

    for path in _public_instruction_markdown():
        text = path.read_text(encoding="utf-8")
        assert not forbidden_cli.search(text), path.relative_to(ROOT)
        assert "duckwork_seo_run(" not in text, path.relative_to(ROOT)
        for match in re.finditer(r"duckwork_seo_run\s+(?=\{)", text):
            payload, _end = decoder.raw_decode(text[match.end():])
            assert set(payload) <= {"script", "args", "extension"}, path.relative_to(ROOT)
            assert set(payload) >= {"script", "args"}, path.relative_to(ROOT)
            assert payload["script"] in scripts, path.relative_to(ROOT)
            assert isinstance(payload["args"], list), path.relative_to(ROOT)
            assert all(isinstance(arg, str) for arg in payload["args"]), path.relative_to(ROOT)
            if "extension" in payload:
                assert payload["extension"] == "banana", path.relative_to(ROOT)
