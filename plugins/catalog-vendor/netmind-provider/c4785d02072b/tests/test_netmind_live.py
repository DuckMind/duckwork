from __future__ import annotations

import json
import os
import urllib.request

import pytest

MODEL_ID = "Qwen/Qwen3.8-Flash"
BASE_URL = "https://api.netmind.ai/inference-api/v1"
LIVE = os.environ.get("NETMIND_LIVE_TEST") == "1"
API_KEY = os.environ.get("NETMIND_API_KEY", "")


pytestmark = pytest.mark.skipif(
    not LIVE or not API_KEY,
    reason="set NETMIND_LIVE_TEST=1 and NETMIND_API_KEY to run live tests",
)


def _completion(messages: list[dict], *, tools: list[dict] | None = None) -> dict:
    payload: dict = {
        "model": MODEL_ID,
        "messages": messages,
        "max_tokens": 128,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "required"

    request = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def test_netmind_returns_assistant_text():
    result = _completion([{"role": "user", "content": "Reply with exactly: ok"}])
    content = result["choices"][0]["message"]["content"]
    assert isinstance(content, str) and content.strip()


def test_netmind_returns_tool_call():
    result = _completion(
        [
            {
                "role": "user",
                "content": "Call ping with value ok. Do not answer in plain text.",
            }
        ],
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
            },
        ],
    )
    tool_calls = result["choices"][0]["message"].get("tool_calls", [])
    assert any(call.get("function", {}).get("name") == "ping" for call in tool_calls)
