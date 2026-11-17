import pytest
import duckwork_env


def test_env_var_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("DUCKWORK_AGENT_DIR", str(tmp_path))
    assert duckwork_env.agent_dir() == tmp_path


def test_default_candidates_are_checked_in_order(monkeypatch, tmp_path):
    monkeypatch.delenv("DUCKWORK_AGENT_DIR", raising=False)
    monkeypatch.setattr(duckwork_env, "CANDIDATES", lambda: [tmp_path / "nope", tmp_path / "duckwork-agent"])
    (tmp_path / "duckwork-agent").mkdir()
    (tmp_path / "duckwork-agent" / "duckwork_constants.py").write_text("", encoding="utf-8")
    assert duckwork_env.agent_dir() == tmp_path / "duckwork-agent"


def test_missing_checkout_says_how_to_fix_it(monkeypatch, tmp_path):
    monkeypatch.delenv("DUCKWORK_AGENT_DIR", raising=False)
    monkeypatch.setattr(duckwork_env, "CANDIDATES", lambda: [tmp_path / "ghost"])
    with pytest.raises(RuntimeError) as exc:
        duckwork_env.agent_dir()
    assert "DUCKWORK_AGENT_DIR" in str(exc.value)
