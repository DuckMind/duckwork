"""Rewrite guards, the transform_llm_output hook in each mode, tool, command and registration."""

import json
from pathlib import Path

from conftest import PLUGIN_DIR, load_module, load_plugin

det = load_module("detector")
rw = load_module("rewrite")
hook = load_module("hook")
tools = load_module("tools")

FLAGGED = (
    "素晴らしい質問ですね！結論から言うと、毎日15分続けることが非常に重要です。"
    "まず最初に、朝の時間を確保することが大切です。"
    "いかがでしたか？お役に立てれば幸いです。"
)
GOOD = "毎日15分続けるのが大事です。最初は朝の時間を確保しましょう。"


def fake_llm(reply_text):
    calls = []

    def call(messages):
        calls.append(messages)
        return reply_text if isinstance(reply_text, str) else reply_text(len(calls))

    call.calls = calls
    return call


# ------------------------------------------------------------------ rewrite

def test_rewrite_accepts_a_good_candidate():
    llm = fake_llm(f"<rewritten>{GOOD}</rewritten>")
    out = rw.rewrite(FLAGGED, llm, surface="chat")
    assert out.changed and out.text == GOOD
    assert out.after.score < out.before.score and not out.after.over_threshold
    assert len(llm.calls) == 1


def test_prompt_carries_findings_surface_and_original():
    llm = fake_llm(f"<rewritten>{GOOD}</rewritten>")
    rw.rewrite(FLAGGED, llm, surface="business_email", threshold=10)
    system, user = llm.calls[0]
    assert "意味を変えない" in system["content"] and "<rewritten>" in system["content"]
    assert "業務メール" in user["content"] and FLAGGED in user["content"]
    assert "いかがでしたか" in user["content"]  # a finding excerpt


def test_rewrite_refuses_changed_numbers_and_retries_with_feedback():
    bad = GOOD.replace("15", "20")
    llm = fake_llm(lambda n: f"<rewritten>{bad if n == 1 else GOOD}</rewritten>")
    out = rw.rewrite(FLAGGED, llm, surface="chat")
    assert out.changed and out.text == GOOD and out.attempts == 2
    assert any("numbers" in p for p in out.rejected[0])
    assert "numbers" in llm.calls[1][1]["content"]


def test_rewrite_keeps_original_when_every_attempt_fails():
    llm = fake_llm("書き直しました！")  # no <rewritten> block
    out = rw.rewrite(FLAGGED, llm, surface="chat", max_attempts=2)
    assert not out.changed and out.text == FLAGGED and len(out.rejected) == 2


def test_rewrite_keeps_original_when_model_call_raises():
    def boom(messages):
        raise TimeoutError("slow")
    out = rw.rewrite(FLAGGED, boom, surface="chat")
    assert not out.changed and "model call failed" in out.rejected[0][0]


def test_rewrite_does_nothing_under_threshold():
    llm = fake_llm("<rewritten>x</rewritten>")
    out = rw.rewrite(GOOD, llm, surface="chat")
    assert not out.changed and llm.calls == []


def test_guards_protect_code_urls_handles_and_words():
    original = ("`npm install` を実行することができます。詳しくは https://example.com を見てください。"
                "@sato さんの Duckwork 設定を使います。")
    rep = det.check(original, "chat", threshold=1)
    assert rw.guard_problems(original, original.replace("することができます", "できます"), rep) == []
    assert any("inline code" in p for p in rw.guard_problems(original, original.replace("`npm install`", "npm"), rep))
    assert any("URL" in p for p in rw.guard_problems(original, original.replace("https://example.com", "公式サイト"), rep))
    assert any("handle" in p for p in rw.guard_problems(original, original.replace("@sato", "佐藤"), rep))
    assert any("word dropped" in p for p in rw.guard_problems(original, original.replace("Duckwork ", ""), rep))
    assert any("length" in p for p in rw.guard_problems(original, original[:20], rep))


def test_numbers_inside_a_flagged_span_may_go():
    original = "上達のコツは3つのポイントがあります。毎日10分だけ練習することが大切です。週に2回は録音を聞き返します。"
    rep = det.check(original, "chat", threshold=1)
    assert rw.guard_problems(original, "毎日10分だけ練習するのが大切です。週に2回は録音を聞き返します。", rep) == []
    problems = rw.guard_problems(original, "毎日だけ練習するのが大切です。週に2回は録音を聞き返します。", rep)
    assert any("numbers dropped" in p for p in problems)


# --------------------------------------------------------------------- hook

def make_guard(ctx):
    ctx.guard = hook.Guard(ctx)
    return ctx.guard


def g_last(ctx):
    return ctx.guard.last


class FakeState:
    def __init__(self):
        self.data = {}

    def set(self, key, value):
        self.data[key] = json.loads(json.dumps(value))

    def get(self, key, default=None):
        return self.data.get(key, default)


class FakeLlm:
    def __init__(self, text):
        self.text, self.calls = text, []

    def complete(self, **kw):
        self.calls.append(kw)
        return type("R", (), {"text": self.text})()


class FakeCtx:
    def __init__(self, settings=None, llm_text=f"<rewritten>{GOOD}</rewritten>"):
        self.settings = settings or {}
        self.state = FakeState()
        self.llm = FakeLlm(llm_text)
        self.tools, self.hooks, self.commands, self.skills = {}, {}, {}, {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_tool(self, name, toolset, schema, handler, **kw):
        self.tools[name] = (toolset, schema, handler)

    def register_hook(self, name, cb):
        self.hooks.setdefault(name, []).append(cb)

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands[name] = handler
        self.command_meta = getattr(self, "command_meta", {})
        self.command_meta[name] = {"description": description, "args_hint": args_hint}

    def register_skill(self, name, path):
        self.skills[name] = path


def test_report_mode_never_changes_the_answer_and_records_the_report():
    ctx = FakeCtx()
    g = make_guard(ctx)
    assert g.on_output(response_text=FLAGGED, platform="cli") is None
    assert ctx.llm.calls == []
    last = g_last(ctx)
    assert last["mode"] == "report" and last["report"]["verdict"] == "rewrite"


def test_enforce_mode_rewrites_over_threshold_answers():
    ctx = FakeCtx({"mode": "enforce"})
    out = make_guard(ctx).on_output(response_text=FLAGGED, platform="cli")
    assert out == GOOD
    call = ctx.llm.calls[0]
    assert call["purpose"] == "ja-writing-guard.rewrite" and 0 < call["timeout"] <= 20
    assert g_last(ctx)["rewrite"]["changed"] is True


def test_enforce_mode_leaves_clean_answers_alone():
    ctx = FakeCtx({"mode": "enforce"})
    assert make_guard(ctx).on_output(response_text=GOOD * 3) is None
    assert ctx.llm.calls == []


def test_enforce_mode_delivers_original_when_rewrite_is_refused():
    ctx = FakeCtx({"mode": "enforce"}, llm_text="<rewritten>短い</rewritten>")
    assert make_guard(ctx).on_output(response_text=FLAGGED) is None
    assert g_last(ctx)["rewrite"]["changed"] is False


def test_off_mode_and_non_japanese_and_short_answers_are_skipped():
    assert make_guard(FakeCtx({"mode": "off"})).on_output(response_text=FLAGGED) is None
    ctx = FakeCtx({"mode": "enforce"})
    g = make_guard(ctx)
    assert g.on_output(response_text="Sure! Here is the answer you asked for, in English only.") is None
    assert g.on_output(response_text="はい、そうです。") is None
    assert ctx.llm.calls == []


def test_platform_surface_mapping_is_used():
    text = "明日の会議は15時からに変更だ。資料は後で送る。場所はいつもの会議室を使う。参加者は5人の予定だ。"
    ctx = FakeCtx({"platform_surfaces": {"tui": "business_email"}})
    g = make_guard(ctx)
    g.on_output(response_text=text, platform="tui")
    assert g_last(ctx)["report"]["surface"] == "business_email"
    g.on_output(response_text=text, platform="cli")
    assert g_last(ctx)["report"]["surface"] == "chat"


def test_bad_settings_fall_back_safely():
    ctx = FakeCtx({"mode": "loud", "surface": "newspaper", "max_attempts": 99})
    g = make_guard(ctx)
    conf = g.settings()
    assert conf["mode"] == "report" and conf["max_attempts"] == 3
    assert g.on_output(response_text=FLAGGED) is None  # unknown surface -> chat, report only


def test_hook_never_raises():
    class Broken(FakeCtx):
        def get_config(self, key, default=None):
            raise RuntimeError("config store down")
    assert make_guard(Broken()).on_output(response_text=FLAGGED) is None


# ------------------------------------------------------- tool and command

def test_tool_returns_json_with_findings():
    data = json.loads(tools.ja_writing_check({"text": FLAGGED, "surface": "chat", "max_findings": 2}))
    assert data["verdict"] == "rewrite" and len(data["findings"]) == 2
    assert json.loads(tools.ja_writing_check({"text": ""}))["error"]
    assert "unknown surface" in json.loads(tools.ja_writing_check({"text": FLAGGED, "surface": "fax"}))["error"]


def test_slash_command_checks_text_and_shows_last_report():
    ctx = FakeCtx()
    g = make_guard(ctx)
    cmd = tools.make_command(g)
    empty = cmd("")
    assert empty.startswith("No checked answer")
    assert "まだ検査した返答がありません" in empty
    assert "AI的な言い回し" in cmd("external " + FLAGGED)
    g.on_output(response_text=FLAGGED)
    assert "直前の返答" in cmd("")
    help_text = cmd("help")
    assert help_text.startswith("Usage:")
    assert "使い方" in help_text


def test_ja_check_user_facing_strings_english_first():
    plugin = load_plugin()
    ctx = FakeCtx()
    plugin.register(ctx)
    desc = ctx.command_meta["ja-check"]["description"]
    assert desc.startswith("Check Japanese text")
    assert "日本語" in desc
    assert tools.USAGE.lstrip().startswith("Usage:")
    empty = tools.make_command(make_guard(FakeCtx()))("")
    assert empty.startswith("No checked answer")


def test_slash_command_shows_changed_lines_after_a_local_rewrite():
    ctx = FakeCtx({"mode": "enforce"})
    g = make_guard(ctx)
    g.on_output(response_text=FLAGGED, platform="cli")
    shown = tools.make_command(g)("")
    assert "変わった行:" in shown and "+" + GOOD in shown


# ------------------------------------------------------------- registration

def _manifest_list(manifest: str, key: str) -> set:
    """Items of a top-level YAML list in plugin.yaml (block style), without a YAML dependency."""
    items, inside = set(), False
    for line in manifest.splitlines():
        if line.startswith(key + ":"):
            inside = True
            continue
        if inside:
            if line.startswith("  - "):
                items.add(line[4:].strip())
            elif line.strip():
                break
    return items


def test_register_matches_manifest():
    plugin = load_plugin()
    ctx = FakeCtx()
    plugin.register(ctx)
    manifest = (PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8")
    assert "name: ja-writing-guard\n" in manifest
    assert set(ctx.tools) == {"ja_writing_check"} == _manifest_list(manifest, "provides_tools")
    assert set(ctx.hooks) == {"transform_llm_output", "post_tool_call"} == _manifest_list(manifest, "provides_hooks")
    assert set(ctx.commands) == {"ja-check"}
    assert set(ctx.skills) == {"rewrite-ja"}
    assert "requires_env" not in manifest and "provides_middleware" not in manifest


def test_guards_protect_japanese_names_and_negation():
    original = ("株式会社ミナトリンク\n営業部 佐伯様\n\nいつもお世話になっております。カナデシステムの中川です。"
                "次回の日程をご提案させていただきたく、ご連絡しました。お客様の声も「スマイル便」に反映します。")
    rep = det.check(original, "business_email", threshold=1)
    ok = original.replace("ご提案させていただきたく", "ご提案したく")
    assert rw.guard_problems(original, ok, rep) == []
    assert any("name" in p for p in rw.guard_problems(original, ok.replace("佐伯様", "佐藤様"), rep))
    assert any("company" in p for p in rw.guard_problems(original, ok.replace("株式会社ミナトリンク", "ミナト社"), rep))
    assert any("name" in p for p in rw.guard_problems(original, ok.replace("中川です", "中山です"), rep))
    assert any("quoted" in p for p in rw.guard_problems(original, ok.replace("「スマイル便」", "新サービス"), rep))
    assert any("negation" in p for p in rw.guard_problems(original, ok.replace("ご提案したく", "ご提案できず"), rep))
    # まず・必ず are not negation
    assert rw.guard_problems("まず、資料を読みます。必ず確認します。結論は月末に出します。",
                             "まず、資料を読みます。必ず確認します。結論は月末に出します。",
                             det.check("まず、資料を読みます。必ず確認します。結論は月末に出します。", "chat")) == []


def test_gateway_answers_are_not_stored_for_other_users_to_see():
    ctx = FakeCtx()
    g = make_guard(ctx)
    g.on_output(response_text=FLAGGED, platform="telegram")
    assert g_last(ctx) is None and g.recall() is None
    empty = tools.make_command(g)("")
    assert empty.startswith("No checked answer")
    assert "まだ検査した返答がありません" in empty


def test_enforce_stays_inside_the_time_budget():
    import time as _time

    class SlowLlm(FakeLlm):
        def complete(self, **kw):
            self.calls.append(kw)
            _time.sleep(0.3)
            return type("R", (), {"text": "<rewritten>短い</rewritten>"})()

    ctx = FakeCtx({"mode": "enforce", "time_budget": 5, "max_attempts": 3})
    ctx.llm = SlowLlm("")
    started = _time.monotonic()
    assert make_guard(ctx).on_output(response_text=FLAGGED, platform="cli") is None
    assert _time.monotonic() - started < 5
    for call in ctx.llm.calls:
        assert call["timeout"] <= 5


def test_result_after_the_budget_is_dropped_and_recorded_as_abandoned(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(hook.time, "monotonic", lambda: now[0])

    class LateLlm(FakeLlm):
        def complete(self, **kw):
            self.calls.append(kw)
            now[0] += 60  # the model answered, but only after the budget ran out
            return type("R", (), {"text": f"<rewritten>{GOOD}</rewritten>"})()

    ctx = FakeCtx({"mode": "enforce", "time_budget": 25})
    ctx.llm = LateLlm("")
    assert make_guard(ctx).on_output(response_text=FLAGGED, platform="cli") is None
    rec = g_last(ctx)["rewrite"]
    assert rec["reason"].startswith("abandoned") and rec["changed"] is False



# ------------------------------------------------- coexistence on transform_llm_output

def first_string_wins(callbacks, text, **kw):
    """What agent/turn_finalizer.apply_llm_output_transform does with several callbacks."""
    for cb in callbacks:
        out = cb(response_text=text, **kw)
        if isinstance(out, str) and out:
            return out
    return text


def charts_like_appender(path):
    """Stand-in for jp-charts: on a gateway, append the MEDIA line the model forgot."""
    def cb(response_text="", platform="", **kw):
        if platform in ("", "cli", "tui") or path in response_text:
            return None
        return response_text.rstrip() + "\n\nMEDIA:" + path
    return cb


def test_report_mode_leaves_room_for_a_plugin_that_appends_media():
    g = make_guard(FakeCtx())  # default mode: report
    out = first_string_wins([g.on_output, charts_like_appender("/tmp/chart.png")], FLAGGED,
                            session_id="s1", turn_id="t1", platform="telegram")
    assert out.endswith("MEDIA:/tmp/chart.png")


def test_enforce_skips_turns_where_a_tool_returned_media():
    ctx = FakeCtx({"mode": "enforce"})
    g = make_guard(ctx)
    g.on_tool_result(tool_name="chart_bar", result='{"media": "MEDIA:/tmp/chart.png"}', session_id="s1", turn_id="t1")
    out = first_string_wins([g.on_output, charts_like_appender("/tmp/chart.png")], FLAGGED,
                            session_id="s1", turn_id="t1", platform="telegram")
    assert out.endswith("MEDIA:/tmp/chart.png")
    assert ctx.llm.calls == []
    # another turn of the same session without media is rewritten as usual
    assert g.on_output(response_text=FLAGGED, session_id="s1", turn_id="t2", platform="cli") == GOOD


def test_enforce_keeps_media_lines_already_in_the_answer():
    ctx = FakeCtx({"mode": "enforce"})
    answer = FLAGGED + "\n\nMEDIA:/tmp/report.png"
    out = make_guard(ctx).on_output(response_text=answer, session_id="s2", turn_id="t1", platform="cli")
    assert out == GOOD + "\n\nMEDIA:/tmp/report.png"
    sent = ctx.llm.calls[0]["messages"][1]["content"]
    assert "MEDIA:" not in sent  # the model never sees (and cannot mangle) the attachment line



def test_nothing_is_written_to_plugin_state_and_reports_stay_in_process():
    ctx = FakeCtx()
    make_guard(ctx).on_output(response_text=FLAGGED, platform="cli")
    assert ctx.state.data == {}  # nothing on disk for another process (e.g. a gateway) to read
    other_process = hook.Guard(ctx)  # same profile, different process
    assert other_process.recall() is None


def test_guards_close_the_holes_found_in_review():
    original = ("株式会社ミナトリンク\n営業部 佐伯様\n\nいつもお世話になっております。\n"
                "次回は10月14日（水）の午前10時からです。資料の事前送付は必要ありません。オンラインでも参加できます。\n"
                "ご確認のほど、何卒よろしくお願い申し上げます。\n\n"
                "株式会社カナデシステム\n営業部 中川一郎\n")
    rep = det.check(original, "business_email", threshold=1)
    ok = original.replace("何卒よろしくお願い申し上げます", "よろしくお願いいたします")
    assert rw.guard_problems(original, ok, rep) == []
    holes = {
        "company stretched": ok.replace("株式会社ミナトリンク", "株式会社ミナトリンクス"),
        "weekday": ok.replace("（水）", "（木）"),
        "am/pm": ok.replace("午前10時", "午後10時"),
        "department": ok.replace("営業部 佐伯様", "経理部 佐伯様"),
        "signature name": ok.replace("中川一郎", "中山一郎"),
        "negation swap": ok.replace("必要ありません", "必要あります").replace("参加できます", "参加できません"),
    }
    for name, candidate in holes.items():
        assert rw.guard_problems(original, candidate, rep), name



def test_partial_rewrites_are_held_back_unless_accept_partial():
    partial = "結論から言うと、毎日15分続けるのが大事です。最初は朝の時間を確保しましょう。"  # still has a tell
    for accept, expected in ((False, None), (True, partial)):
        ctx = FakeCtx({"mode": "enforce", "threshold": 10, "accept_partial": accept, "max_attempts": 1},
                      llm_text=f"<rewritten>{partial}</rewritten>")
        assert make_guard(ctx).on_output(response_text=FLAGGED, platform="cli") == expected


def test_budget_shrinks_under_the_host_hook_timeout(monkeypatch):
    monkeypatch.setattr(hook, "host_hook_timeout", lambda: 12.0)
    assert hook.effective_budget(25) == 9.0
    monkeypatch.setattr(hook, "host_hook_timeout", lambda: None)
    assert hook.effective_budget(25) == 25



def test_adverbs_that_look_negative_are_not_negation():
    original = "設定は自動で保存されます。既存のシステムと連携できます。結論は月末に出します。"
    rep = det.check(original, "chat", threshold=1)
    candidate = "設定は自動で保存されます。既存のシステムとも無理なく連携できます。間もなく結論を出します。"
    assert not any("negation" in p for p in rw.guard_problems(original, candidate, rep))
