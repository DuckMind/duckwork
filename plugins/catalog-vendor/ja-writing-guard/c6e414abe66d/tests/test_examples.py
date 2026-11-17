"""The five before/after examples in examples/rewrite: each recorded model reply passes the
guards (numbers, names, URLs, code kept) and lowers the score. The replies were written by a
separate LLM answering the exact prompt rewrite.build_messages() produces for each text."""

from pathlib import Path

import pytest

from conftest import PLUGIN_DIR, load_module

rw = load_module("rewrite")
EXAMPLES = sorted((PLUGIN_DIR / "examples" / "rewrite").glob("*.before.txt"))


def test_there_are_five_examples_one_per_surface():
    surfaces = {p.name.split("_", 1)[1].split(".")[0] for p in EXAMPLES}
    assert surfaces == {"business_email", "external", "sns", "tech_doc", "chat"}


SURFACE_NAMES = {"business_email": "業務メール", "external": "社外文", "sns": "SNS", "tech_doc": "技術文書", "chat": "チャット"}


def run_example(before):
    """Replay the recorded replies the way Duckwork would: up to two attempts."""
    surface = before.name.split("_", 1)[1].split(".")[0]
    replies = [before.with_name(before.name.replace(".before.txt", ".model_reply.txt")).read_text(encoding="utf-8")]
    second = before.with_name(before.name.replace(".before.txt", ".model_reply2.txt"))
    if second.exists():
        replies.append(second.read_text(encoding="utf-8"))
    it = iter(replies)
    return surface, rw.rewrite(before.read_text(encoding="utf-8"), lambda messages: next(it, ""), surface=surface,
                               max_attempts=2)


@pytest.mark.parametrize("before", EXAMPLES, ids=lambda p: p.name)
def test_recorded_rewrite_lowers_the_score_and_matches_the_readme_table(before):
    surface, out = run_example(before)
    assert out.changed, out.rejected
    assert out.after.score < out.before.score
    assert out.after.register_issues == 0
    delivered = "書き直し" if not out.after.needs_rewrite else "元の返答"
    row = f"| {SURFACE_NAMES[surface]} | {out.before.score} → {out.after.score} | {out.attempts} | {delivered} |"
    readme = (PLUGIN_DIR / "README.md").read_text(encoding="utf-8")
    assert row in readme, row


def test_no_invisible_unicode_in_the_repo():
    """Duckwork' security scan flags zero-width and bidi control characters (caution)."""
    invisible = {chr(c) for c in (0x200B, 0x200C, 0x200D, 0x2060, 0x2062, 0x2063, 0x2064, 0xFEFF,
                                   0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069)}
    bad = []
    for p in PLUGIN_DIR.rglob("*"):
        if p.is_file() and ".git" not in p.parts and p.suffix in {".py", ".md", ".txt", ".json", ".yaml", ".ini"}:
            if invisible & set(p.read_text(encoding="utf-8")):
                bad.append(str(p.relative_to(PLUGIN_DIR)))
    assert bad == []


def test_our_own_docs_pass_the_tech_doc_check():
    det = load_module("detector")
    for name in ("README.md", "docs/comparison.md", "skills/rewrite-ja/SKILL.md"):
        text = (PLUGIN_DIR / name).read_text(encoding="utf-8").split("## English")[0]
        report = det.check(text, "tech_doc")
        assert report.verdict == "ok", (name, report.score, [f.rule for f in report.findings if f.counted])


def test_readme_accuracy_matches_eval_results():
    import json
    res = json.loads((PLUGIN_DIR / "eval" / "results.json").read_text(encoding="utf-8"))
    ours = res["A"]["ja-writing-guard (this plugin)"]
    own, tuned = ours["own_rule"], ours["dev_tuned"]
    readme = (PLUGIN_DIR / "README.md").read_text(encoding="utf-8")
    assert f"| AI っぽい文40本 | {own['tp']}（強め{ours['own_by_strength']['strong']}、弱め{ours['own_by_strength']['weak']}） | {own['fn']} |" in readme
    assert f"| 人の文40本 | {own['fp']} | {own['tn']} |" in readme
    row = (f"| ja-writing-guard | {own['detection_rate']:.0%} / {own['false_positive_rate']:.0%} | "
           f"{tuned['detection_rate']:.0%} / {tuned['false_positive_rate']:.0%} | {ours['auc_test']:.2f} |")
    assert row in readme, row
