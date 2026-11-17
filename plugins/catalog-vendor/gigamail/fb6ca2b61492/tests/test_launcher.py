# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gigamail_launcher", ROOT / "scripts/start_server.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.fixture
def env(tmp_path):
    return {"GIGAMAIL_SERVER": sys.executable, "PLUGIN_DATA": str(tmp_path)}


def configure(env, settings):
    (Path(env["PLUGIN_DATA"]) / "config.json").write_text(json.dumps(settings), encoding="utf-8")


def test_launch_preserves_streams_without_shell_arguments(env, monkeypatch, tmp_path):
    configure(env, {"data_root": str(tmp_path / "mail data")})
    monkeypatch.setattr(launcher.os, "environ", env)
    calls = []
    monkeypatch.setattr(launcher, "run_server", lambda *args: calls.append(args) or 0)
    assert launcher.main() == 0
    executable, argv, child_env = calls[0]
    assert Path(executable) == Path(sys.executable)
    assert argv == [executable]
    assert child_env["GIGAMAIL_ROOT"] == str(tmp_path / "mail data")


def test_server_exit_code_reaches_duckwork(env, monkeypatch, tmp_path):
    configure(env, {"data_root": str(tmp_path / "mail data")})
    monkeypatch.setattr(launcher.os, "environ", env)
    monkeypatch.setattr(launcher, "run_server", lambda *args: 23)
    assert launcher.main() == 23


def test_windows_filtered_environment_uses_roaming_directory(env, tmp_path, monkeypatch):
    roaming = tmp_path / "redirected profile" / "Roaming"
    monkeypatch.setattr(launcher, "windows_appdata", lambda _: str(roaming))
    _, _, child = launcher.prepare_launch(env, platform="win32")
    assert child["GIGAMAIL_ROOT"] == str(roaming / "ADE")
    assert child["APPDATA"] == str(roaming)
    assert "APPDATA" not in env


def test_windows_existing_appdata_is_preserved(tmp_path):
    appdata = str(tmp_path / "Roaming")
    assert launcher.windows_appdata({"APPDATA": appdata}) == appdata


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_unix_default_matches_gigamail(env, tmp_path, platform):
    _, _, child = launcher.prepare_launch(env, platform=platform, home=tmp_path)
    assert child["GIGAMAIL_ROOT"] == str(tmp_path / ".ade")
    assert child["ADE_ROOT"] == child["GIGAMAIL_ROOT"]


@pytest.mark.parametrize("key", ["GIGAMAIL_ROOT", "ADE_ROOT"])
def test_existing_data_root_is_honored(env, tmp_path, key):
    env[key] = str(tmp_path / "shared data")
    _, _, child = launcher.prepare_launch(env)
    assert child["GIGAMAIL_ROOT"] == env[key]
    assert child["ADE_ROOT"] == env[key]


def test_canonical_root_wins_over_legacy_alias(env, tmp_path):
    env.update(GIGAMAIL_ROOT=str(tmp_path / "current"), ADE_ROOT=str(tmp_path / "legacy"))
    _, _, child = launcher.prepare_launch(env)
    assert child["GIGAMAIL_ROOT"] == str(tmp_path / "current")


def test_explicit_config_keeps_mail_and_approvals_together(env, tmp_path):
    env.update(GIGAMAIL_ROOT=str(tmp_path / "old"), GIGAMAIL_DATA_DIR=str(tmp_path / "old/mail"))
    configure(env, {"data_root": str(tmp_path / "chosen"), "server_command": sys.executable})
    _, _, child = launcher.prepare_launch(env)
    assert child["GIGAMAIL_ROOT"] == str(tmp_path / "chosen")
    assert "GIGAMAIL_DATA_DIR" not in child
    assert env["GIGAMAIL_DATA_DIR"] == str(tmp_path / "old/mail")


def test_separate_mail_data_directory_can_be_explicit(env, tmp_path):
    configure(env, {"data_root": str(tmp_path / "shared"), "mail_data_dir": str(tmp_path / "mail")})
    _, _, child = launcher.prepare_launch(env)
    assert child["GIGAMAIL_DATA_DIR"] == child["ADE_MAIL_DATA_DIR"] == str(tmp_path / "mail")


@pytest.mark.parametrize("settings", [[], {"password": "never-a-plugin-setting"},
                                      {"data_root": 3}, {"server_command": ""},
                                      {"data_root": "relative/path"}, {"server_command": "./relative"}])
def test_invalid_configuration_fails_before_start(env, settings):
    configure(env, settings)
    with pytest.raises(ValueError):
        launcher.prepare_launch(env)


def test_invalid_json_fails_closed(env):
    (Path(env["PLUGIN_DATA"]) / "config.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        launcher.prepare_launch(env)


def test_missing_executable_is_actionable_on_stderr(env, monkeypatch, capsys):
    monkeypatch.setattr(launcher.os, "environ", env)
    monkeypatch.setattr(launcher.shutil, "which", lambda *args, **kwargs: None)
    assert launcher.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "Install GigaMail" in output.err


def test_launch_does_not_change_consent_or_dryrun(env, tmp_path):
    env.update(ADE_MAIL_DRYRUN="1", GIGAMAIL_CONSENT_BACKEND="deny")
    _, _, child = launcher.prepare_launch(env, platform="linux", home=tmp_path)
    assert child["ADE_MAIL_DRYRUN"] == "1"
    assert child["GIGAMAIL_CONSENT_BACKEND"] == "deny"


def test_default_server_is_resolved_on_path(env, tmp_path, monkeypatch):
    env.pop("GIGAMAIL_SERVER")
    calls = []
    monkeypatch.setattr(launcher.shutil, "which", lambda name, **kwargs: calls.append(name) or sys.executable)
    launcher.prepare_launch(env, platform="linux", home=tmp_path)
    assert calls == ["gigamail-server"]


@pytest.mark.skipif(os.name != "nt", reason="Windows Known Folder API")
def test_windows_known_folder_lookup():
    assert Path(launcher.windows_appdata({})).is_absolute()
