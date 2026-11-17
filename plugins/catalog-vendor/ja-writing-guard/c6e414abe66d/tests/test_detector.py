"""Detector: scores, positions, masking, quotes, surfaces and determinism."""

from conftest import load_module

det = load_module("detector")
rules = load_module("rules")
surfaces = load_module("surfaces")

AI_CHAT = (
    "素晴らしい質問ですね！リモートワークで集中するには、いくつかのポイントがあります。\n\n"
    "## 1. 作業環境を整える\n\n"
    "集中できる場所を確保することが非常に重要です。様々なツールを活用することで、効率を最大化することができます。\n\n"
    "## 2. 時間を区切る\n\n"
    "時間を区切ることで、集中力を維持することが可能です。\n\n"
    "いかがでしたか？ぜひ参考にしてみてください。お役に立てれば幸いです！"
)

HUMAN_MAIL = (
    "山田様\n\nお世話になっております。株式会社みどり商事の佐藤です。\n\n"
    "先日はお打ち合わせのお時間をいただき、ありがとうございました。\n"
    "ご依頼の見積書を添付しますので、ご確認ください。\n"
    "納期は来月10日を予定しています。仕様に変更があれば、今週中にお知らせいただけると助かります。\n\n"
    "よろしくお願いいたします。\n\n佐藤 健"
)

PLAIN = "明日の会議は15時からに変更だ。資料は後で送る。場所はいつもの会議室を使う。"


def rule_ids(report):
    return {f.rule for f in report.findings}


def test_ai_chat_is_flagged_with_expected_rules():
    r = det.check(AI_CHAT, "chat")
    assert r.over_threshold and r.score >= 90
    assert {"sycophancy.great_q", "stock.ikaga", "template.hope_helpful",
            "translationese.dekiru", "template.ikutsuka"} <= rule_ids(r)


def test_natural_business_mail_is_clean():
    r = det.check(HUMAN_MAIL, "business_email")
    assert r.findings == [] and r.score == 0 and r.verdict == "ok"


def test_findings_carry_exact_positions():
    r = det.check(AI_CHAT, "chat")
    for f in r.findings:
        assert 0 <= f.start < f.end <= len(AI_CHAT)
        line_start = AI_CHAT.rfind("\n", 0, f.start) + 1
        assert f.line == AI_CHAT.count("\n", 0, f.start) + 1
        assert f.col == f.start - line_start + 1
    ikaga = next(f for f in r.findings if f.rule == "stock.ikaga")
    assert AI_CHAT[ikaga.start:ikaga.end] == "いかがでしたか"


def test_same_input_same_output():
    a = det.check(AI_CHAT, "chat").to_dict()
    b = det.check(AI_CHAT, "chat").to_dict()
    assert a == b


def test_surface_changes_the_verdict_for_the_same_text():
    chat = det.check(PLAIN, "chat")
    external = det.check(PLAIN, "external")
    assert chat.verdict == "ok"
    assert external.verdict == "rewrite"
    assert "register.plain_in_polite" in rule_ids(external)
    assert "register.plain_in_polite" not in rule_ids(chat)


def test_code_urls_and_quote_lines_are_masked():
    text = (
        "設定は次のとおりです。\n\n```python\n# いかがでしたか？することができます\nx = 1\n```\n\n"
        "詳しくは https://example.com/いかがでしたか を見てください。\n"
        "> 素晴らしい質問ですね\n"
        "`することができる` という書き方は避けます。"
    )
    r = det.check(text, "chat")
    assert not ({"stock.ikaga", "translationese.dekiru", "sycophancy.great_q"} & rule_ids(r))


def test_phrases_inside_japanese_quotes_do_not_count():
    text = "AI の文によく出る「〜と言えるでしょう」や「いかがでしたか」という結びは、読み手に嫌われやすいので、私は使わないようにしています。"
    r = det.check(text, "chat")
    assert not ({"stock.ieru_deshou", "stock.ikaga"} & rule_ids(r))


def test_em_dash_in_quotes_still_counts_as_format():
    r = det.check("この機能——つまり自動保存——は、設定を開かなくても動きます。保存の間隔は5分です。", "chat")
    assert "format.em_dash" in rule_ids(r)


def test_non_japanese_text_is_skipped():
    r = det.check("This is an English answer with no Japanese at all, so nothing to check here.", "chat")
    assert r.verdict == "not_japanese" and r.findings == []


def test_min_hits_rules_need_repetition():
    once = det.check("様々な意見がありました。会議は予定どおり終わり、次回は来週の火曜日に開きます。", "chat")
    assert "inflated.samazama" not in rule_ids(once)
    many = det.check("様々な部署から様々な意見が出て、様々な案を比べました。結論は来週に出します。", "chat")
    assert "inflated.samazama" in rule_ids(many)


def test_max_count_caps_the_score_but_reports_every_hit():
    text = "。".join(["この設定を変更することができます"] * 6) + "。"
    r = det.check(text, "chat")
    hits = [f for f in r.findings if f.rule == "translationese.dekiru"]
    assert len(hits) == 6
    assert sum(f.counted for f in hits) == rules.RULES_BY_ID["translationese.dekiru"].max_count


def test_other_verbs_with_kotoga_dekiru_need_repetition():
    once = det.check("この窓口では書類を受け取ることができます。受付は平日の9時から17時までです。", "chat")
    assert "translationese.dekiru_verb" not in rule_ids(once)
    twice = det.check("書類を受け取ることができます。控えを持ち帰ることもできます。郵送で送ることができます。", "chat")
    assert "translationese.dekiru_verb" in rule_ids(twice)
    suru = det.check("変更することができます。削除することができます。追加することができます。", "chat")
    assert "translationese.dekiru_verb" not in rule_ids(suru) and "translationese.dekiru" in rule_ids(suru)


def test_signature_lines_do_not_count_as_nominal_endings():
    text = "お世話になっております。\n資料を送ります。\n\n株式会社みどり商事\n営業部\n佐藤 健\n03-1234-5678"
    r = det.check(text, "business_email")
    assert "rhythm.taigen_run" not in rule_ids(r)


def test_mixed_register_is_reported_on_lenient_surfaces():
    text = "今日は資料を作りました。午後は会議だった。夕方に結果を共有しました。明日も続きをやる。結局まとまらなかった。"
    r = det.check(text, "chat")
    assert "rhythm.mixed_register" in rule_ids(r)


def test_casual_words_in_formal_surface():
    r = det.check("新しいプランはマジでお得です。ぜひご検討ください。料金は月額1,000円です。", "external")
    assert "register.casual_in_formal" in rule_ids(r)


def test_leaked_tool_markup_is_caught_even_inside_urls():
    r = det.check("詳しくは公式の案内をご覧ください。https://example.com/page?utm_source=chatgpt.com を参照しました。", "chat")
    assert "format.ai_leakage" in rule_ids(r)


def test_unknown_surface_raises_and_aliases_work():
    import pytest
    with pytest.raises(ValueError):
        surfaces.get_surface("newspaper")
    assert surfaces.get_surface("email").name == "business_email"
    assert surfaces.get_surface("X").name == "sns"


def test_threshold_override():
    r = det.check(PLAIN, "external", threshold=99)
    assert not r.over_threshold


def test_every_rule_compiles_and_has_known_category_and_source():
    known_sources = {"yomiyasu", "natural-japanese", "textlint-ai", "ja-technical", "jtf", "patina",
                     "geonwoo", "gonta223", "matsutouya", "original"}
    ids = [r.id for r in rules.RULES]
    assert len(ids) == len(set(ids))
    for r in rules.RULES:
        assert r.category in rules.CATEGORIES
        assert r.source in known_sources
        assert r.weight > 0 and r.label and r.hint
    for key, (cat, label, hint, source) in rules.STRUCTURAL.items():
        assert cat in rules.CATEGORIES and source in known_sources


def test_report_dict_shape():
    d = det.check(AI_CHAT, "chat").to_dict(max_findings=3)
    assert set(d) >= {"surface", "score", "threshold", "verdict", "summary", "findings", "findings_total", "by_category"}
    assert len(d["findings"]) == 3 and d["findings_total"] > 3
    assert d["summary"].startswith("AI的な言い回し")


def test_skill_examples_keep_their_published_scores():
    skill = (load_module("detector").__file__ and __import__("pathlib").Path(__file__).parent.parent
             / "skills" / "rewrite-ja" / "SKILL.md").read_text(encoding="utf-8")
    import re
    pairs = re.findall(r"元の文（(.+?), score (\d+)）:\n\n> (.+?)\n\n直した文（score (\d+)）:\n\n> (.+?)\n", skill)
    assert len(pairs) == 2
    names = {"社外向けのお知らせ": "external", "チャット": "chat"}
    for label, before_score, before, after_score, after in pairs:
        surface = names[label]
        assert det.check(before, surface).score == int(before_score)
        assert det.check(after, surface).score == int(after_score)



def test_one_resolve_phrase_alone_is_not_enough_in_ordinary_company_text():
    # Human company notices often carry one of these; only a pile-up counts.
    for text in ("このたびはご迷惑をおかけし、申し訳ございませんでした。皆様のご期待にお応えできるよう、より一層努めてまいります。",
                 "新年あけましておめでとうございます。本年もさらなる飛躍の年にしたいと考えております。本年もよろしくお願いいたします。",
                 "当店は開店から20年、地域に寄り添い、毎朝6時にパンを焼いてきました。11月から営業時間を7時からに変更します。"):
        assert det.check(text, "external").verdict == "ok", text



def test_resolve_phrases_in_one_sentence_count_once():
    one = "当社は今後も地域に寄り添い、安全で快適なまちづくりに貢献してまいります。工事は11月に始まり、来年3月に終わる予定です。"
    assert "inflated.pr_formula" not in rule_ids(det.check(one, "external"))
    two = "当社は地域に寄り添い続けます。今後も業界の発展に貢献してまいります。工事は11月に始まります。"
    assert "inflated.pr_formula" in rule_ids(det.check(two, "external"))



def test_sns_question_counts_but_a_plain_request_for_comments_does_not():
    ai_post = "新しい手帳アプリを公開しました。予定とメモを1画面で見られます。皆さんにとって理想の手帳とは何ですか？ぜひコメントで教えてください！"
    r = det.check(ai_post, "sns")
    assert r.over_threshold and "template.sns_question" in rule_ids(r)
    request_only = "新しい手帳アプリを公開しました。予定とメモを1画面で見られます。感想があれば、ぜひコメントで教えてください！"
    r2 = det.check(request_only, "sns")
    assert not r2.over_threshold and "template.sns_cta" in rule_ids(r2)



def test_a_single_question_to_followers_is_ordinary_sns_writing():
    # Written for this test (not human-collected data): people ask their followers one question all the time.
    for text in ("週末は久しぶりに山へ行きました。紅葉はまだ少し早かったけれど、空気がおいしかったです。あなたにとって秋の楽しみは何ですか？",
                 "この本、3回読み返しました。読むたびに気づくことが違います。皆さんは最近読んだ本で印象に残ったものはありますか？"):
        r = det.check(text, "sns")
        assert not r.over_threshold and "template.sns_question" not in rule_ids(r), text
