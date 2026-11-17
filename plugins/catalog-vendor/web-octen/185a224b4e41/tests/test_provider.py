"""Octen's boundary contracts, exercised through Duckwork' real plugin discovery."""

import asyncio
import json
import shutil
from pathlib import Path

import httpx
import pytest
import yaml


@pytest.fixture
def provider(tmp_path, monkeypatch):
    home = tmp_path / "profile"
    plugin_dir = home / "plugins" / "web-octen"
    plugin_dir.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    for filename in ("plugin.yaml", "__init__.py", "provider.py"):
        if (root / filename).exists():
            shutil.copy2(root / filename, plugin_dir / filename)
    (home / "config.yaml").write_text(
        yaml.safe_dump({"plugins": {"enabled": ["web-octen"]}, "web": {"backend": "octen"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("DUCKWORK_HOME", str(home))
    monkeypatch.setenv("DUCKWORK_BUNDLED_PLUGINS", str(tmp_path / "empty-bundled"))
    monkeypatch.delenv("OCTEN_API_KEY", raising=False)
    from duckwork_cli.plugins import _ensure_plugins_discovered
    from agent.web_search_registry import get_provider

    _ensure_plugins_discovered(force=True)
    result = get_provider("octen")
    return result


def transport(monkeypatch, handler):
    sync_client, async_client = httpx.Client, httpx.AsyncClient
    mock = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "Client", lambda **kw: sync_client(transport=mock, **kw))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: async_client(transport=mock, **kw))


def test_profile_key_drives_availability_and_setup_without_network(provider, tmp_path):
    from duckwork_constants import get_duckwork_home
    from agent.web_search_registry import get_active_search_provider, get_active_extract_provider

    assert provider is not None, "Installed plugin must register the Octen provider"
    assert not provider.is_available()
    assert not provider.is_keyless_available()
    assert provider.search("test")["success"] is False
    (get_duckwork_home() / ".env").write_text("OCTEN_API_KEY=profile-test-key\n", encoding="utf-8")
    assert provider.is_available()
    assert get_active_search_provider() is provider
    assert get_active_extract_provider() is provider
    schema = provider.get_setup_schema()
    assert schema["env_vars"][0]["key"] == "OCTEN_API_KEY"
    assert provider.supports_search() and provider.supports_extract()


def test_search_dispatch_sends_contract_and_returns_ranked_highlights(provider, monkeypatch):
    monkeypatch.setenv("OCTEN_API_KEY", "test-key")
    requests = []

    def respond(request):
        requests.append(request)
        payload = json.loads(request.content)
        assert str(request.url) == "https://api.octen.ai/search"
        assert request.headers["x-api-key"] == "test-key"
        assert payload["query"] == "Duckwork 搜索"
        assert 3 <= payload["count"] <= 100
        assert payload["highlight"]["enable"] is True
        assert payload["full_content"]["enable"] is False
        return httpx.Response(200, json={"code": 0, "data": {"results": [
            {"url": "https://example.com/a", "title": "Alpha", "highlight": "Evidence A"},
            {"url": "https://example.com/b", "title": "Beta", "highlight": "Evidence B"},
        ]}})

    transport(monkeypatch, respond)
    from tools.registry import registry
    import tools.web_tools  # noqa: F401 — real handler registration

    entry = registry.get_entry("web_search")
    result = json.loads(entry.handler({"query": "Duckwork 搜索", "limit": 3}))
    assert result["success"] is True
    assert result["data"]["web"] == [
        {"title": "Alpha", "url": "https://example.com/a", "description": "Evidence A", "position": 1},
        {"title": "Beta", "url": "https://example.com/b", "description": "Evidence B", "position": 2},
    ]
    assert len(requests) == 1


@pytest.mark.parametrize("response", [
    httpx.Response(401, json={"msg": "private diagnostic"}),
    httpx.Response(403, json={"msg": "private diagnostic"}),
    httpx.Response(429, json={"msg": "private diagnostic"}),
    httpx.Response(500, text="private diagnostic"),
    httpx.Response(200, json={"code": 403, "msg": "private diagnostic"}),
    httpx.Response(200, text="not JSON"),
    httpx.Response(200, json={"data": {"results": None}}),
    httpx.Response(200, json={"data": {"results": ["not a result"]}}),
])
def test_search_failures_never_become_empty_success(provider, monkeypatch, response):
    monkeypatch.setenv("OCTEN_API_KEY", "test-key")
    transport(monkeypatch, lambda request: response)
    result = provider.search("test")
    assert result["success"] is False
    assert "Octen" in result["error"]
    assert "test-key" not in result["error"]
    assert "private diagnostic" not in result["error"]


def test_search_timeout_returns_actionable_error(provider, monkeypatch):
    monkeypatch.setenv("OCTEN_API_KEY", "test-key")

    def timeout(request):
        raise httpx.ReadTimeout("private diagnostic", request=request)

    transport(monkeypatch, timeout)
    result = provider.search("test")
    assert result["success"] is False
    assert "timed out" in result["error"]
    assert "private diagnostic" not in result["error"]


def test_extract_batches_keep_input_order_and_per_url_failures(provider, monkeypatch):
    monkeypatch.setenv("OCTEN_API_KEY", "test-key")
    urls = [f"https://example.com/{i}" for i in range(21)]
    batches = []

    def respond(request):
        payload = json.loads(request.content)
        assert str(request.url) == "https://api.octen.ai/extract"
        assert request.headers["x-api-key"] == "test-key"
        assert payload["format"] == "text"
        assert "query" not in payload
        batches.append(payload["urls"])
        return httpx.Response(200, json={"code": 0, "data": {"results": [
            {"url": url, "status": "failed", "error_message": "Page unavailable"}
            if url == urls[3] else
            {"url": url, "status": "success", "title": "Page", "full_content": f"Content for {url}"}
            for url in payload["urls"]
        ]}})

    transport(monkeypatch, respond)
    results = asyncio.run(provider.extract(urls, format="text", unknown_future_option=True))
    assert batches == [urls[:20], urls[20:]]
    assert [row["url"] for row in results] == urls
    assert results[3]["error"]
    assert results[0]["content"] == "Content for https://example.com/0"
    assert results[0]["raw_content"] == results[0]["content"]
    assert results[-1]["content"] == "Content for https://example.com/20"


def test_extract_missing_items_and_failed_batch_are_reported(provider, monkeypatch):
    monkeypatch.setenv("OCTEN_API_KEY", "test-key")
    urls = [f"https://example.com/{i}" for i in range(21)]

    def respond(request):
        batch = json.loads(request.content)["urls"]
        if batch == urls[:20]:
            return httpx.Response(503, text="private diagnostic")
        return httpx.Response(200, json={"data": {"results": []}})

    transport(monkeypatch, respond)
    results = asyncio.run(provider.extract(urls))
    assert [row["url"] for row in results] == urls
    assert all(row.get("error") for row in results)
    assert all(not row["content"] for row in results)
