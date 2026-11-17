# -*- coding: utf-8 -*-
"""gonta223/humanizer-ja（SKILL.md のチェックリスト）から語・型を正規表現に起こしたもの。

出典: https://github.com/gonta223/humanizer-ja  SKILL.md
ライセンス: MIT（LICENSE: "Copyright (c) 2025 Siqi Chen (original: blader/humanizer)" /
            "Copyright (c) 2026 SuguruKun_ai (Japanese version: humanizer-ja)"）
ローカル ~/.claude/skills/humanizer-ja はこのリポの複製（LICENSE 同一。SKILL.md は TPO 節が足されている）。
原典は LLM 向けの文章規則で、正規表現は持たない。語は原典の NG 例・NG 語・チェック項目から文字どおり取った。
"""

RULES = [
    ("hj.p2.ukibori", r"浮き彫りにしており"),  # SKILL.md:51
    ("hj.p2.kongo-tenkai-chumoku", r"今後の展開が注目されます"),  # :52 / :225
    ("hj.p2.tamenteki", r"多面的な"),  # :53
    ("hj.p2.houkatsuteki", r"包括的な"),  # :53
    ("hj.p2.kakkiteki", r"画期的な"),  # :53
    ("hj.p2.chumoku-ni-atai", r"注目に値する"),  # :54
    ("hj.p2.to-ieru-deshou", r"と言えるでしょう"),  # :55 / :227
    ("hj.p2.dewanai-deshouka", r"ではないでしょうか"),  # :56
    ("hj.p2.juuyou-na-shisa", r"重要な示唆を与えている"),  # :57
    ("hj.p1.kiwamete-juuyou", r"極めて重要な役割を果たし"),  # :38
    ("hj.p1.hakarishirenai", r"計り知れない"),  # :38,43
    ("hj.p4.senmonka-ni-yoru", r"(?:業界の)?専門家によると"),  # :74
    ("hj.p4.chousa-kekka-shimesu", r"調査結果が示すように"),  # :74
    ("hj.p4.ooku-no-kigyou", r"多くの企業が指摘しているように"),  # :74
    ("hj.p5.bold-label-colon", r"^\s*(?:[-*+]|\d+[.)])\s+\*\*[^*]+[:：]?\*\*\s*[:：]?"),  # :85-99「**ラベル:** 内容」
    ("hj.p6.mittsu-ni-matomeru", r"3つにまとめると|三つにまとめると"),  # :105
    ("hj.p7.em-dash-double", r"——|――"),  # :107-115
    ("hj.p9.koko-de-juuyou", r"ここで重要なのは"),  # :132
    ("hj.p9.rikai-shite-oku-hitsuyou", r"について理解しておく必要があります"),  # :132
    ("hj.p9.chui-subeki-ten", r"注意すべき点として"),  # :132
    ("hj.p10.conjunctions", r"一方で|しかしながら|加えて|このように|さらに|とりわけ"),  # :141（多用で発火）
    ("hj.p11.dewanai-da", r"ではない。[^。]{1,30}だ。|ではありません。[^。]{1,30}です。"),  # :145-151（2回以上で発火）
    ("hj.p12.sycophancy", r"素晴らしいご質問ですね|非常に良い指摘です|おっしゃる通り"),  # :156
    ("hj.p13.wo-shimeshite-ori", r"を示しており|を物語っています"),  # :170
    ("hj.p16.suru-koto-ga-dekimasu", r"することができます"),  # :192-197
    ("hj.p17.kongo-masumasu", r"今後ますます重要になると考えられます"),  # :202
    ("hj.p18.koko-dewa-kaisetsu", r"ここでは.{0,40}について解説します"),  # :216
    ("hj.p18.chumoku-wo-atsumete", r"が注目を集めています"),  # :217
    ("hj.p18.kinnen-kyuusoku", r"近年、.{0,40}が急速に進展しており"),  # :218
    ("hj.p19.ga-kitai-saremasu", r"が期待されます"),  # :226
]
