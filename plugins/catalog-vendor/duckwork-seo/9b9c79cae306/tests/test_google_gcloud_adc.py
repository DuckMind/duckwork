"""Google authenticated routes remain unavailable until Duckwork injects a bridge."""

from __future__ import annotations

import builtins
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_auth  # noqa: E402


def test_authenticated_google_routes_fail_closed_without_reading_credential_files(monkeypatch):
    def deny_file_access(*_args, **_kwargs):
        raise AssertionError("credential files must not be read")

    monkeypatch.setattr(builtins, "open", deny_file_access)

    assert google_auth.get_oauth_credentials(["scope"]) is None
    status = google_auth.check_credentials("gsc")

    assert status["available"] is False
    assert "Duckwork route" in status["error"]


@pytest.mark.parametrize("service", ("gsc", "ga4", "indexing"))
def test_authenticated_google_services_report_the_same_unavailable_route(service):
    status = google_auth.check_credentials(service)

    assert status["available"] is False
    assert status["method"] == "duckwork_route"
    assert "Duckwork route" in status["error"]
