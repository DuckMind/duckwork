"""Shared test fixtures for duckwork-spectator."""


import pytest

from spectator.auth.auth import HostSecretManager
from spectator.config import SpectatorConfig
from spectator.db.db import SpectatorDB


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a temporary data directory for test isolation."""
    data_dir = tmp_path / "spectator"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def db(tmp_data_dir):
    """Provide an initialised SpectatorDB against a temp database."""
    db_path = tmp_data_dir / "spectator.db"
    database = SpectatorDB(db_path)
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def config(tmp_data_dir):
    """Provide a default SpectatorConfig."""
    return SpectatorConfig()


@pytest.fixture
def secret_mgr(tmp_data_dir):
    """Provide a HostSecretManager against a temp directory."""
    secret_path = tmp_data_dir / "host_secret"
    mgr = HostSecretManager(secret_path)
    return mgr