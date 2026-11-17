# -*- coding: utf-8 -*-
"""textlint-rule-preset-JTF-style の記号系規則を Python 正規表現に抜き出したもの。

出典: https://github.com/textlint-ja/textlint-rule-preset-JTF-style（MIT, Copyright (c) 2015 azu）
JTF 日本語標準スタイルガイド（翻訳用）の機械化。AI検出用ではなく表記規則なので、
AIっぽさに関係する記号（ダッシュ・半角コロン・感嘆符・疑問符・セミコロン・半角句読点）だけを抜いた。
_JA は src/util/regexp.js の japaneseRegExp（サロゲートペアは Python では不要なので削った）。
"""

_JA = r"(?:[々〇〻㐀-䶿一-鿿豈-﫿\U00020000-\U0002FFFF]|[ぁ-んァ-ヶ])"  # src/util/regexp.js:3

RULES = [
    ("jtf.4.2.9.dash-after-ja", _JA + r"([‒-―])"),  # src/4.2.9.js:26 和文でダッシュ(―/—)を使わない（「——」の挿入句を拾う）
    ("jtf.4.2.7.halfwidth-colon-after-ja", _JA + r"(:)"),  # src/4.2.7.js:24 和文に半角コロン
    ("jtf.4.2.8.semicolon-after-ja", _JA + r"(;)"),  # src/4.2.8.js:22 和文にセミコロン
    ("jtf.4.2.1.halfwidth-exclam-after-ja", r"(?:[㐀-䶿一-鿿豈-﫿\U00020000-\U0002FFFF]|[ぁ-んァ-ヶ])(!)"),  # src/4.2.1.js:26
    ("jtf.4.2.1.exclam-then-no-space", r"！( )[^\n]"),  # src/4.2.1.js:39（文末！の後は全角スペース）
    ("jtf.4.2.2.halfwidth-question-after-ja", _JA + r"(\?)"),  # src/4.2.2.js:27
    ("jtf.4.2.2.question-then-halfspace", r"？( )[^\n]"),  # src/4.2.2.js:40
    ("jtf.1.2.1.period-comma-before-ja", r"([,\.])" + _JA),  # src/1.2.1.js:16-19 和文で , . を句読点に使わない
    ("jtf.1.2.1.period-comma-after-ja", _JA + r"([,\.])"),  # src/1.2.1.js:21-24
    ("jtf.4.2.4.halfwidth-nakaguro", r"(?:" + _JA + r"|[a-zA-Z])(･)(?:" + _JA + r"|[a-zA-Z])"),  # src/4.2.4.js:25
]
