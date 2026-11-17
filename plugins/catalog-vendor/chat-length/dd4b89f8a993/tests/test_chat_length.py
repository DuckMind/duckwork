"""Offline tests for chat-length (no model calls).

Run: DUCKWORK_HOME=<empty dir> <duckwork-python> tests/test_chat_length.py
With the Duckwork interpreter the real Duckwork helpers (compaction limit) run as well.
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
if not os.environ.get("DUCKWORK_HOME"):
    os.environ["DUCKWORK_HOME"] = tempfile.mkdtemp(prefix="chat-length-test-")

spec = importlib.util.spec_from_file_location("chat_length", HERE / "__init__.py")
assert spec and spec.loader
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)


class Ctx:
    def __init__(self, settings=None):
        self.hooks, self.settings = {}, settings or {}

    def register_hook(self, name, cb):
        self.hooks[name] = cb

    def get_config(self, key, default=None):
        return self.settings.get(key, default)


results = []


def check(name, condition, info=""):
    results.append((name, bool(condition)))
    print(("OK   " if condition else "FAIL ") + name + (f"  ({info})" if info and not condition else ""))


def measure(ctx, sid, prompt, output=500, window=200_000, model="testmodel"):
    ctx.hooks["post_api_request"](session_id=sid, platform="cli", model=model, provider="openrouter",
                                  usage={"input_tokens": prompt - 1000, "cache_read_tokens": 1000,
                                         "cache_write_tokens": 0, "output_tokens": output,
                                         "prompt_tokens": prompt},
                                  context_length=window)


def turn(ctx, sid, text="Go on please.", platform="cli", history=None):
    return ctx.hooks["pre_llm_call"](session_id=sid, user_message=text, conversation_history=history or [],
                                     model="testmodel", platform=platform, is_first_turn=False)


# 1) Registration
ctx = Ctx({"basis": "window", "threshold_1": 0.7, "threshold_2": 0.9})
cl.register(ctx)
check("registers both hooks", set(ctx.hooks) == {"pre_llm_call", "post_api_request"})

# 2) Below threshold: no notice
measure(ctx, "s1", 100_000)
check("50 % gives no notice", turn(ctx, "s1") is None)

# 3) Level 1 exactly once
measure(ctx, "s1", 141_000)
r = turn(ctx, "s1")
check("71 % gives level 1", r and "getting long" in r["context"], str(r))
check("opener carries session id and session_search", r and "session s1" in r["context"] and "session_search" in r["context"])
check("no dashes in the template", r and "\u2014" not in r["context"] and "\u2013" not in r["context"])
measure(ctx, "s1", 150_000)
check("level 1 not a second time", turn(ctx, "s1") is None)

# 4) Level 2 exactly once
measure(ctx, "s1", 181_000)
r = turn(ctx, "s1")
check("91 % gives level 2 (urgent)", r and "Urgent" in r["context"])
measure(ctx, "s1", 185_000)
check("level 2 not a second time", turn(ctx, "s1") is None)

# 5) Re-armed after compaction
measure(ctx, "s1", 40_000)
check("quiet after compaction", turn(ctx, "s1") is None)
measure(ctx, "s1", 142_000)
check("level 1 again afterwards", "getting long" in (turn(ctx, "s1") or {}).get("context", ""))

# 6) Jump straight to level 2: a single notice, level 1 is skipped
measure(ctx, "s2", 190_000)
r1 = turn(ctx, "s2")
measure(ctx, "s2", 191_000)
r2 = turn(ctx, "s2")
check("jump to 95 %: one urgent notice, then quiet", r1 and "Urgent" in r1["context"] and r2 is None)

# 7) Background jobs never get a notice
measure(ctx, "s3", 190_000)
check("cron gets no notice", turn(ctx, "s3", platform="cron") is None)
check("subagent gets no notice", turn(ctx, "s3", platform="subagent") is None)

# 8) The new message counts (long paste)
measure(ctx, "s4", 120_000)
check("60 % plus a 90,000-char paste (about 22,500 tokens) fires", turn(ctx, "s4", text="x" * 90_000) is not None)

# 9) No measurement (restart): estimate from history, no crash
ctx_new = Ctx({"basis": "window", "threshold_1": 0.0001})
cl.register(ctx_new)
history = [{"role": "user", "content": "hello " * 200}, {"role": "assistant", "content": "answer " * 200}]
r = turn(ctx_new, "no-measurement", history=history)
check("without provider numbers: estimate, no error", r is None or "context" in r)
store = json.loads((Path(os.environ["DUCKWORK_HOME"]) / "plugin-data/chat-length/sessions.json").read_text())
check("source recorded as estimate",
      (store.get("no-measurement", {}).get("last_notice") or {}).get("source") in ("estimate", None))

# 10) Languages
de = cl.build_notice(1, 72, "abc", "Titel", "compaction", "de")
en = cl.build_notice(2, 91, "abc", "Title", "window", "en")
auto = cl.build_notice(1, 72, "abc", "", "compaction", "auto")
check("German template", "Dieser Chat wird lang" in de and "\u201eTitel\u201c" in de and "Verdichtung" in de)
check("English template", "almost full" in en and "context window" in en)
check("auto asks for the conversation language", "language of this conversation" in auto and "session abc" in auto)

# 11) Compaction basis: limit lies below the window
ctx_c = Ctx({"basis": "compaction"})
cl.register(ctx_c)
limit = cl._compaction_limit("deepseek/deepseek-v4-pro", "openrouter", 1_000_000)
check("compaction limit plausible", limit is None or 64_000 <= limit <= 1_000_000, str(limit))
print("  compaction limit at 1M window:", limit, "| at 200K:", cl._compaction_limit("x", "", 200_000))

# 12) Broken input never breaks a turn
check("empty session id is quiet", turn(ctx, "") is None)
check("broken usage is quiet", ctx.hooks["post_api_request"](session_id="k", usage="nonsense") is None)

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
