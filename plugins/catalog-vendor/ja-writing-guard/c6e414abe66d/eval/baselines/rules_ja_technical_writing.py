# -*- coding: utf-8 -*-
"""textlint-rule-preset-ja-technical-writing（と同梱ルール）の規則を Python 正規表現に寄せたもの。

出典: https://github.com/textlint-ja/textlint-rule-preset-ja-technical-writing（MIT, Copyright (c) 2016 azu）
同梱ルールは npm pack で取得（いずれも LICENSE 実物で MIT を確認）:
  textlint-rule-ja-no-redundant-expression 4.x (MIT, (c) 2016 azu)  https://github.com/textlint-ja/textlint-rule-ja-no-redundant-expression
  textlint-rule-ja-no-weak-phrase 2.0.0 (MIT, (c) 2016 azu)
  textlint-rule-no-double-negative-ja 2.0.1 (MIT, (c) 2015 azu)
  textlint-rule-no-dropping-the-ra 3.0.0 (MIT, (c) 2015 azu)
  textlint-rule-no-mix-dearu-desumasu 6.0.4 (MIT, (c) 2015 azu)
  textlint-rule-no-doubled-conjunction 3.0.1 (MIT, (c) 2016 takahashim)
  textlint-rule-no-exclamation-question-mark 1.1.0 (MIT, (c) 2016 azu)

重要: 原典の多くは kuromoji の形態素列（品詞・活用形）で照合する。ここにある正規表現は
その「表層形の近似」で、ID 末尾 -APPROX を付けた。原典より誤検知・見逃しが増える。
閾値系（sentence-length 100字 / max-ten 3 / max-kanji-continuous-len 6）は正規表現で書ける形にした。
"""

RULES = [
    # ja-no-redundant-expression src/dictionary.ts（形態素照合の表層近似）
    ("jtw.redundant.dict1-suru-koto-ga-kanou-APPROX", r"することが可能"),  # dictionary.ts:63（id dict1, 例: 省略することが可能）
    ("jtw.redundant.dict2-suru-koto-ga-dekiru-APPROX", r"することが(?:でき|出来)"),  # dictionary.ts:110（id dict2, 例: 解析することができます）
    ("jtw.redundant.dict3-de-aru-to-ieru-APPROX", r"であると言え(?:ます|る)"),  # dictionary.ts:167（id dict3）
    ("jtw.redundant.dict4-de-aru-to-kangaete-iru-APPROX", r"であると考えて(?:い|お)"),  # dictionary.ts:232（id dict4）
    ("jtw.redundant.dict5-wo-okonau-APPROX", r"[一-龠々]{2,}を(?:行[うわいえっ]|おこな[うわいえっ])"),  # dictionary.ts:320（原典: サ変名詞＋を＋行う。allows: 処理を行う・カタカナ/英字＋を行う）
    ("jtw.redundant.dict6-wo-jikkou-APPROX", r"[一-龠々]{2,}を実行"),  # dictionary.ts:365（allows: 処理を実行・カタカナ/英字＋を実行）
    # ja-no-weak-phrase src/dict.js（形態素照合の表層近似）
    ("jtw.weak.kamo-APPROX", r"かも(?:。|しれ)"),  # dict.js:2-62
    ("jtw.weak.omou-APPROX", r"思(?:う|います)"),  # dict.js:63-109
    ("jtw.weak.kanousei-wo-shisa", r"可能性を示唆している"),  # dict.js:110-200
    # no-double-negative-ja src/rules/*.js（メッセージに出る形の表層近似）
    ("jtw.dneg.nai-koto-wa-nai-APPROX", r"ないこと(?:は|も)ない"),  # naikotoha-nai.js:55,60
    ("jtw.dneg.nai-demo-nai-APPROX", r"ない(?:で)(?:も|は)ない"),  # naidemo-nai.js:53,58
    ("jtw.dneg.nai-mono-dewa-nai-APPROX", r"ないもので(?:も|は)ない"),  # naimonodeha-nai.js:54,59
    ("jtw.dneg.nai-to-iikirenai-APPROX", r"ないと(?:は)?(?:いいきれ|言い切れ)ない"),  # naitohaiikire-nai.js:53,58
    ("jtw.dneg.nai-to-wa-kagiranai-APPROX", r"ないと(?:は|も)限らない|ないと(?:は|も)かぎらない"),  # naitohakagira-nai.js:51,56
    ("jtw.dneg.nai-wake-dewa-nai-APPROX", r"ないわけで(?:も|は)ない"),  # naiwakedeha-nai.js:52,57
    ("jtw.dneg.naku-wa-nai-APPROX", r"なく(?:も|は)ない"),  # nakuha-nai.js:40,45
    # no-dropping-the-ra src/no-dropping-the-ra.js（原典は一段動詞未然形＋れる。表層近似は誤検知が多い）
    ("jtw.ranuki.special-APPROX", r"(?:来|こ)れる|見れる"),  # no-dropping-the-ra.js:19-23（kuromoji が1語にする特例）
    ("jtw.ranuki.ichidan-APPROX", r"(?:食べ|寝|着|起き|出|居|考え|決め|覚え|変え|答え)れ(?:る|ます|ない|た)"),  # :6-17 の近似（語は近似のための例示で原典に語リストは無い）
    # no-mix-dearu-desumasu（analyze-desumasu-dearu の近似。文書単位で両方が出たら混在）
    ("jtw.mix.desumasu-APPROX", r"(?:です|ます|でした|ました|ません|でしょう)[。！？]"),
    ("jtw.mix.dearu-APPROX", r"(?:である|だ|だった|ではない)[。！？]"),
    # no-exclamation-question-mark（既定は全角・半角とも不可）
    ("jtw.exclam-question", r"[!！?？]"),
    # 閾値ルール（textlint-rule-preset-ja-technical-writing.js rulesConfig）
    ("jtw.sentence-length-100", r"[^。！？\n]{101,}"),  # sentence-length max:100
    ("jtw.max-ten-3", r"(?:[^。、\n]*、){4,}[^。\n]*。"),  # max-ten max:3（読点4つ以上の文）
    ("jtw.max-kanji-continuous-6", r"[一-龠々〆ヵヶ]{7,}"),  # max-kanji-continuous-len max:6
]
