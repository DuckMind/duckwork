"""No core patches, credential-store access, tool dispatch, or transcript writes."""
import copy
import ipaddress
import json
import math
import os
import threading
import time
import urllib.request
from urllib.parse import urlsplit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect refused")


def endpoint(value):
    """Only HTTPS or literal loopback HTTP; no URL credentials/query/fragment."""
    p = urlsplit(value)
    try:
        local = ipaddress.ip_address(p.hostname or "").is_loopback
    except ValueError:
        local = p.hostname == "localhost"
    if (not p.hostname or p.username or p.password or p.query or p.fragment
            or not (p.scheme == "https" or (p.scheme == "http" and local))):
        raise ValueError("endpoint must be HTTPS or loopback HTTP")
    return value.rstrip("/")


def number(config, key, default, low, high):
    value = config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid numeric setting")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError("setting out of range")
    return value


def settings(raw):
    if not isinstance(raw, dict) or raw.get("enabled") is not True:
        return None
    c = dict(raw)
    c["base_url"] = endpoint(c.get("base_url", ""))
    if not isinstance(c.get("models"), list) or not c["models"] or not all(
            isinstance(m, str) and m for m in c["models"]):
        raise ValueError("explicit models allowlist required")
    for key, default, low, high in [
        ("interval_seconds", 240, 30, 3600),
        ("idle_window_seconds", 1800, 30, 7200),
        ("max_requests", 7, 1, 30), ("timeout_seconds", 15, 1, 60),
        ("max_sessions", 4, 1, 16), ("max_payload_bytes", 524288, 1024, 2097152),
    ]:
        c[key] = number(c, key, default, low, high)
    if c["idle_window_seconds"] < c["interval_seconds"]:
        raise ValueError("window shorter than interval")
    for key in ("max_requests", "max_sessions", "max_payload_bytes"):
        if int(c[key]) != c[key]:
            raise ValueError("integer required")
    return c


# Fail closed on novel provider features (especially server-executed tools).
ALLOWED = {"model", "messages", "tools", "tool_choice", "parallel_tool_calls",
           "temperature", "top_p", "max_tokens", "max_completion_tokens", "stream",
           "stream_options", "stop", "seed", "frequency_penalty", "presence_penalty",
           "user", "prompt_cache_key", "prompt_cache_retention", "response_format",
           "n", "logprobs", "top_logprobs", "store"}


def payload(request):
    if not isinstance(request, dict) or set(request) - ALLOWED:
        raise ValueError("unsupported request fields")
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("chat messages required")
    # v1 deliberately excludes multimodal URLs and provider-specific blocks.
    for m in messages:
        if (not isinstance(m, dict) or m.get("role") not in
                {"system", "developer", "user", "assistant", "tool"}
                or not isinstance(m.get("content", ""), (str, type(None)))):
            raise ValueError("text-only chat required")
    for tool in request.get("tools", []):
        if tool.get("type") != "function":
            raise ValueError("server tools unsupported")
    out = copy.deepcopy(request)
    out["messages"].append({"role": "user", "content":
        "Cache maintenance only. Do no work, call no tools, reply OK."})
    out.update(stream=False, tool_choice="none", n=1, store=False)
    out.pop("stream_options", None)
    out.pop("max_tokens", None)
    out.pop("max_completion_tokens", None)
    out["max_completion_tokens" if "max_completion_tokens" in request else "max_tokens"] = 1
    if not out.get("tools"):
        out.pop("tool_choice", None)
    return out


def send(base_url, body, timeout):
    # This plugin only reads its own explicitly provisioned credential.
    token = os.environ.get("DUCKWORK_SESSION_WARMER_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base_url + "/chat/completions", body, headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=timeout) as response:
        result = json.loads(response.read(1048577))
    if not isinstance(result, dict) or not isinstance(result.get("choices"), list):
        raise ValueError("invalid response")
    usage = result.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    # Only numeric aggregate usage survives; never retain generated text.
    return {k: v for k, v in {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "cached_tokens": details.get("cached_tokens", 0),
    }.items() if type(v) in (int, float) and v >= 0 and math.isfinite(v)}


class Warmer:
    def __init__(self, config, clock=time.monotonic, transport=send):
        self.config, self.clock, self.transport = config, clock, transport
        self.lock = threading.RLock()
        self.sessions = {}
        self.stopped = threading.Event()
        self.thread = None
        self.metrics = {"attempts": 0, "successes": 0, "errors": 0, "skipped": 0,
                        "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}

    def _config(self):
        try:
            return settings(self.config())
        except (TypeError, ValueError):
            return None

    def busy(self, session_id="", **kwargs):
        with self.lock:
            self.sessions.pop(session_id, None)

    def capture(self, request=None, session_id="", base_url="", **kwargs):
        with self.lock:
            self.sessions.pop(session_id, None)
            c = self._config()
            if not c or self.stopped.is_set() or not session_id:
                return None
            try:
                if endpoint(base_url) != c["base_url"] or request.get("model") not in c["models"]:
                    raise ValueError("route mismatch")
                body = json.dumps(payload(request), ensure_ascii=False).encode()
                if len(body) > c["max_payload_bytes"] or len(self.sessions) >= c["max_sessions"]:
                    raise ValueError("capacity limit")
            except (ValueError, TypeError, AttributeError):
                self.metrics["skipped"] += 1
                return None
            self.sessions[session_id] = dict(body=body, config=c, idle=False,
                                            last=self.clock(), due=0, count=0)
        return None  # Never rewrite the real request.

    def idle(self, session_id="", assistant_response=None, **kwargs):
        with self.lock:
            s = self.sessions.get(session_id)
            if s:
                if not isinstance(assistant_response, str) or not assistant_response:
                    self.sessions.pop(session_id, None)
                    return
                body = json.loads(s["body"])
                body["messages"].insert(-1, {"role": "assistant", "content": assistant_response})
                s["body"] = json.dumps(body, ensure_ascii=False).encode()
                if len(s["body"]) > s["config"]["max_payload_bytes"]:
                    self.sessions.pop(session_id, None)
                    return
                s.update(idle=True, last=self.clock(), due=self.clock()+s["config"]["interval_seconds"])
                if self.thread is None:
                    self.thread = threading.Thread(target=self._run, daemon=True,
                                                   name="duckwork-session-warmer")
                    self.thread.start()

    def remove(self, session_id="", completed=False, failed=False, interrupted=False, **kwargs):
        # Duckwork also emits on_session_end at successful turn finalization.
        if not completed or failed or interrupted:
            self.busy(session_id=session_id)

    def tick(self):
        with self.lock:
            c = self._config()
            if not c or self.stopped.is_set():
                self.sessions.clear()
                return
            now = self.clock()
            chosen = None
            for key, s in list(self.sessions.items()):
                if c != s["config"] or now-s["last"] >= c["idle_window_seconds"] or s["count"] >= c["max_requests"]:
                    del self.sessions[key]
                elif chosen is None and s["idle"] and now >= s["due"]:
                    chosen = (key, s)
            if chosen is None:
                return
            key, s = chosen
            # Mark in flight under lock; never hold lock across network I/O.
            s["due"] = float("inf")
            s["count"] += 1
            self.metrics["attempts"] += 1
        try:
            usage = self.transport(c["base_url"], s["body"], c["timeout_seconds"])
        except Exception:
            with self.lock:
                self.metrics["errors"] += 1
                if self.sessions.get(key) is s:
                    del self.sessions[key]  # Circuit opens for this idle period; no retries.
            return
        with self.lock:
            self.metrics["successes"] += 1
            for field in ("prompt_tokens", "completion_tokens", "cached_tokens"):
                value = usage.get(field, 0)
                if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                    self.metrics[field] += value
            if self.sessions.get(key) is s:
                s["due"] = self.clock()+c["interval_seconds"]

    def _run(self):
        while not self.stopped.wait(1):
            self.tick()

    def command(self, args="", **kwargs):
        if args.strip() == "stop":
            self.stopped.set()
            with self.lock:
                self.sessions.clear()
        elif args.strip() not in ("", "status"):
            return "Usage: /warming [status|stop]"
        with self.lock:
            return json.dumps(dict(self.metrics, sessions=len(self.sessions),
                                   stopped=self.stopped.is_set(), configured=bool(self._config())))
