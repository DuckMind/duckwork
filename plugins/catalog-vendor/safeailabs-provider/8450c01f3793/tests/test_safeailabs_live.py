from __future__ import annotations

import json
import os
import urllib.request

import pytest

MODEL = "sail-frontier"
BASE_URL = os.environ.get("SAFE_AI_BASE_URL", "https://us.api.safeailabs.ai/v1").rstrip("/")
LIVE = os.environ.get("SAFE_AI_LIVE_TEST") == "1"
API_KEY = os.environ.get("SAFE_AI_KEY", "")

pytestmark = pytest.mark.skipif(not LIVE, reason="set SAFE_AI_LIVE_TEST=1 to run live tests")


def _get(path: str) -> dict:
    request = urllib.request.Request(f"{BASE_URL}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _completion(messages: list[dict], *, tools: list[dict] | None = None) -> dict:
    payload: dict = {"model": MODEL, "messages": messages, "max_tokens": 512, "stream": False}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "required"
    request = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)


def test_models_endpoint_lists_the_fallback_model_with_its_context_window():
    models = {m["id"]: m for m in _get("/models")["data"]}
    assert MODEL in models
    text = next(m for m in models[MODEL]["input_modalities"] if m["type"] == "text")
    assert text["supported_inputs"]["max_context_length"]["value"] == 1_048_576


@pytest.mark.skipif(not API_KEY, reason="set SAFE_AI_KEY to send a billable request")
def test_returns_assistant_text():
    result = _completion([{"role": "user", "content": "Reply with exactly: ok"}])
    content = result["choices"][0]["message"]["content"]
    assert isinstance(content, str) and content.strip()


@pytest.mark.skipif(not API_KEY, reason="set SAFE_AI_KEY to send a billable request")
def test_returns_a_tool_call():
    result = _completion(
        [{"role": "user", "content": "Call ping with value ok. Do not answer in plain text."}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "ping",
                    "description": "Return a value.",
                    "parameters": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
    )
    tool_calls = result["choices"][0]["message"].get("tool_calls", [])
    assert any(call.get("function", {}).get("name") == "ping" for call in tool_calls)
