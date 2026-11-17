import pytest

from helpers import load_plugin


@pytest.fixture(scope="session")
def plugin():
    return load_plugin()


@pytest.fixture(autouse=True)
def charts_home(tmp_path, monkeypatch):
    """Write PNGs into a temp DUCKWORK_HOME, never the user's real one."""
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path / "duckwork"))
    return tmp_path
