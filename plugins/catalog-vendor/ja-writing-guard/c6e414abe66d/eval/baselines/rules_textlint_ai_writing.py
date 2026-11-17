# -*- coding: utf-8 -*-
"""@textlint-ja/textlint-rule-preset-ai-writing v1.1.0 の検出規則を Python 正規表現に抜き出したもの。

出典: https://github.com/textlint-ja/textlint-rule-preset-ai-writing
ライセンス: MIT（LICENSE: "Copyright (c) 2025 azu"、package.json "license": "MIT"）
原典は Markdown AST のノード種別（ListItem / Paragraph / Header / Str）ごとに当てる。
ここでは行単位・文字列単位で当てられる形に寄せた。ノード条件は各行コメントに記す。
no-ai-colon-continuation（コロン＋直後のブロック要素。kuromoji で述語終わりのみ）は
形態素解析が要るため正規表現化できない。近似として行末コロンだけを置く（誤検知が多いので比較実験では別枠に）。
"""

# no-ai-list-formatting.ts:21-61 の絵文字リスト（ListItem 内で検出）
_FLASHY = ["✅", "❌", "⭐", "✨", "💯", "⚠️", "❗", "❓", "💥", "🔥", "⚡", "💪", "🚀",
           "💡", "🤔", "💭", "🧠", "🎯", "📈", "📊", "🏆", "👍", "👎", "😊", "😎", "🎉",
           "🌟", "📝", "📋", "✏️", "🖊️", "💼"]
_INFO = ["注意", "重要", "ポイント", "メモ", "参考", "補足", "確認", "チェック", "推奨", "おすすめ",
         "検出される例", "推奨される表現", "良い例", "悪い例", "例", "サンプル", "使用例", "設定例"]  # no-ai-emphasis-patterns.ts:24-43

import re as _re

RULES = [
    # --- no-ai-list-formatting.ts ---
    ("aiw.list.bold-colon", r"^[\s]*(?:[-*+]|\d+[.)])\s+\*\*([^*]+)\*\*(?:\s*([:：])|\s+([-—–])(?=\s))"),  # :82 ListItem
    ("aiw.list.flashy-emoji", r"^[\s]*(?:[-*+]|\d+[.)])\s+.*(" + "|".join(_re.escape(e) for e in _FLASHY) + ")"),  # :21-66 ListItem 内（原典はノード内どこでも）
    # --- no-ai-emphasis-patterns.ts ---
    ("aiw.emph.emoji-bold", r"(ℹ️|🔍|✅|❌|⚠️|💡|📝|📋|📌|🔗|🎯|🚀|⭐|✨|💯|🔥|📊|📈)\s*\*\*([^*]+)\*\*"),  # :67-68
    ("aiw.emph.info-prefix-bold", r"\*\*(" + "|".join(_INFO) + r")([：:].*?)?\*\*"),  # :90
    ("aiw.emph.bold-in-heading", r"^#{1,6}\s.*(\*\*|__)(.*?)\1"),  # :202 Header ノード（原典は (\*\*|__)(.*?)\1 を見出し内に）
    # --- no-ai-hype-expressions.ts（Str ノード）---
    ("aiw.hype.kakumeiteki", r"革命的な"),  # :24
    ("aiw.hype.game-changer", r"ゲームチェンジャー"),  # :29
    ("aiw.hype.sekaihatsu", r"世界初の"),  # :34
    ("aiw.hype.kyukyoku", r"究極の"),  # :39
    ("aiw.hype.kanzen-ni", r"完全に"),  # :43
    ("aiw.hype.kanpeki", r"完璧な"),  # :48
    ("aiw.hype.saikou", r"最高の"),  # :53
    ("aiw.hype.saisentan", r"最先端の"),  # :58
    ("aiw.hype.oohaba-ni", r"大幅に"),  # :63
    ("aiw.hype.mahou", r"魔法のように"),  # :72
    ("aiw.hype.kiseki", r"奇跡的な"),  # :77
    ("aiw.hype.kyoui", r"驚異的な"),  # :82
    ("aiw.hype.kanousei-tokihanatsu", r"可能性を解き放つ"),  # :87
    ("aiw.hype.senzai-nouryoku", r"潜在能力を引き出す"),  # :92
    ("aiw.hype.minshuka", r"民主化する"),  # :97
    ("aiw.hype.supercharge", r"スーパーチャージ"),  # :102
    ("aiw.hype.kyoutan", r"驚嘆させ"),  # :107
    ("aiw.hype.gyoukai-saiteigi", r"業界を再定義"),  # :116
    ("aiw.hype.mirai-kaeru", r"未来を変える"),  # :121
    ("aiw.hype.paradigm-shift", r"パラダイムシフト"),  # :126
    ("aiw.hype.fukahi", r"不可避の"),  # :131
    ("aiw.hype.aratana-kijun", r"新たな基準を設定"),  # :136
    ("aiw.hype.jisedai", r"次世代の"),  # :141
    ("aiw.hype.frontier", r"フロンティアを開拓"),  # :146
    ("aiw.hype.konponteki-henkaku", r"根本的に変革"),  # :151
    # --- ai-tech-writing-guideline.ts（既定 severity: info）---
    ("aiw.guide.mazu-saisho", r"まず最初に"),  # :41
    ("aiw.guide.arakajime-yosoku", r"あらかじめ予測"),  # :47
    ("aiw.guide.suru-koto-ga-dekimasu", r"することができます"),  # :52
    ("aiw.guide.suru-hitsuyou", r"する必要があります"),  # :58
    ("aiw.guide.iumademonaku", r"言うまでもなく"),  # :64
    ("aiw.guide.ga-okonaware", r"が行われ(て|る|ます)"),  # :73
    ("aiw.guide.no-henkou-wo-okona", r"の変更を行"),  # :79
    ("aiw.guide.jissou-wo-jisshi", r"の実装を実施"),  # :85
    ("aiw.guide.ni-yotte-sareru", r"によって[実行処理実施]され"),  # :90 （原典どおり文字クラス。「実行」等の2字語ではなく1字に一致する点に注意）
    ("aiw.guide.system-ni-yotte", r"がシステムによって実行される"),  # :96
    ("aiw.guide.ni-yotte-jikkou", r"によって実行され"),  # :102
    ("aiw.guide.kousoku-na", r"高速な(?:パフォーマンス|処理|動作)"),  # :112
    ("aiw.guide.oohaba-koujou", r"大幅に(?:向上|改善|削減)"),  # :118
    ("aiw.guide.kouritsuteki", r"効率的な"),  # :124
    ("aiw.guide.tekisetsu", r"適切な"),  # :130
    ("aiw.guide.hitsuyou-ni-oujite", r"必要に応じて"),  # :136
    ("aiw.guide.term-user-client", r"(ユーザー.*?(?:クライアント|顧客))|(?:(?:クライアント|顧客).*?ユーザー)"),  # :146
    ("aiw.guide.term-settings", r"(設定画面.*?(?:設定ページ|環境設定))|(?:(?:設定ページ|環境設定).*?設定画面)"),  # :152
    ("aiw.guide.desu-dearu-mix", r"(です。.*?である。)|(である。.*?です。)"),  # :158
    ("aiw.guide.mata-mata", r"また、.*?また、"),  # :168
    ("aiw.guide.first-second-third", r"(?:第一に|まず).*?(?:第二に|次に).*?(?:第三に|最後に)"),  # :173
    ("aiw.guide.connective-then-list", r"(?:例えば|具体的には|詳細には|以下|次に|また)。[\s]*$"),  # :222 Paragraph の直後が List のときだけ
    # --- no-ai-colon-continuation.ts（近似）---
    ("aiw.colon.line-end-colon-APPROX", r"[：:]\s*$"),  # :51 原典は「述語/接続詞で終わる」かつ次が CodeBlock/List/BlockQuote/Table のときだけ
]
