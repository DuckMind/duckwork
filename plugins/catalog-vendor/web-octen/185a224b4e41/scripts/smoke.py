"""Exercise the installed provider through Duckwork in a disposable profile.

Run with Duckwork' Python interpreter. DUCKWORK_SOURCE may point at a source checkout.
Only OCTEN_API_KEY is required; no LLM call is made.
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

source = os.environ.get("DUCKWORK_SOURCE")
if source:
    sys.path.insert(0, source)


def main():
    if not os.environ.get("OCTEN_API_KEY", "").strip():
        raise SystemExit("Set OCTEN_API_KEY before running the live smoke check.")
    with tempfile.TemporaryDirectory(prefix="duckwork-octen-") as directory:
        home = Path(directory)
        os.environ["DUCKWORK_HOME"] = str(home)
        os.environ.pop("DUCKWORK_ENABLE_PROJECT_PLUGINS", None)
        plugin = home / "plugins" / "web-octen"
        plugin.mkdir(parents=True)
        for filename in ("plugin.yaml", "__init__.py", "provider.py"):
            shutil.copy2(Path(__file__).resolve().parents[1] / filename, plugin / filename)
        (home / "config.yaml").write_text(
            "plugins:\n  enabled: [web-octen]\nweb:\n  backend: octen\n  keyless_fallback: false\n",
            encoding="utf-8",
        )
        from duckwork_cli.plugins import _ensure_plugins_discovered
        from agent.web_search_registry import get_active_search_provider, get_active_extract_provider
        from tools.registry import registry
        import tools.web_tools  # noqa: F401 — register the real web tool handlers

        _ensure_plugins_discovered()
        assert get_active_search_provider().name == "octen"
        assert get_active_extract_provider().name == "octen"
        search = json.loads(registry.get_entry("web_search").handler({"query": "Octen search API", "limit": 3}))
        assert search.get("success"), search.get("error", "Search failed")
        hits = search["data"]["web"]
        assert hits and all(hit["url"] and hit["description"] for hit in hits)
        extract = registry.get_entry("web_extract").handler({"urls": ["https://octen.ai/"], "format": "markdown"})
        if hasattr(extract, "__await__"):
            extract = asyncio.run(extract)
        pages = json.loads(extract)
        assert pages.get("results"), pages.get("error", "Extract failed")
        page = pages["results"][0]
        assert not page.get("error"), page.get("error")
        assert "octen" in page.get("content", "").lower(), "Expected page content was not returned"
        print(json.dumps({
            "provider": "octen",
            "search_results": len(hits),
            "search_urls": [hit["url"] for hit in hits],
            "extract_url": page["url"],
            "extract_chars": len(page["content"]),
            "status": "passed",
        }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
