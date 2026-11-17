# -*- coding: utf-8 -*-
"""matsutouya/humanizer-ja（Humanizer JP, SKILL.md）から語・型を正規表現に起こしたもの。

出典: https://github.com/matsutouya/humanizer-ja  SKILL.md
ライセンス: MIT（LICENSE: "Copyright (c) 2026 paris0001"）
原典は LLM 向けの規則で正規表現を持たない。「即削除」「機械的置換」表と各節の頻出語から文字どおり取った。
"""

RULES = [
    # 11. AI頻出語彙＋過剰強調語（1段落に2個以上で発火）
    ("mh.p11.kyouchougo", r"非常に|とても|大変|極めて|圧倒的に"),  # SKILL.md:499
    ("mh.p11.juuyougo", r"重要な役割|重要な|不可欠な"),  # :502
    ("mh.p11.aimaika", r"さまざまな|多岐にわたる|幅広い"),  # :503（「といった」「など」は誤検知が多いので外した）
    ("mh.p11.fun-iki", r"深い理解|本質的な"),  # :504
    # 4. 逃げの語尾 / 5. 観点
    ("mh.p4.to-kangaeraremasu", r"と考えられます"),  # :394, :981
    ("mh.p4.to-sareteimasu", r"とされています"),  # :394, :982
    ("mh.p5.toiu-ten-ni-oite", r"という点において"),  # :410, :984
    ("mh.p5.toiu-kanten-kara", r"という観点から"),  # :410, :983
    # 18. 否定→肯定の決め台詞
    ("mh.p18.tannaru-dewanai", r"単なる.{0,40}ではな"),  # :588
    ("mh.p18.wo-koeta-nanika", r"を超えた何か"),  # :588
    # 22. まさに〜に他なりません
    ("mh.p22.masani", r"まさに.{0,40}(?:に他なりません|です)"),  # :642, :993
    ("mh.p22.ni-hokanarimasen", r"に他なりません|にほかなりません"),  # :642, :994
    # 24. させていただきます連鎖
    ("mh.p24.sasete-itadaki", r"させていただき"),  # :666, :966
    ("mh.p24.itadakemasu-to-saiwai", r"いただけますと幸い"),  # :967
    # 34. チャットボット残滓（即削除）
    ("mh.p34.oyaku-ni-tatereba", r"お役に立てれば幸いです"),  # :809, :968
    ("mh.p34.fumei-na-ten", r"何かご不明な点があればお知らせください"),  # :809
    ("mh.p34.subarashii-goshitsumon", r"素晴らしいご質問ですね"),  # :809, :973
    ("mh.p34.ossharu-toori", r"おっしゃる通りです"),  # :809
    ("mh.p34.ika-no-you-ni-matome", r"以下のようにまとめました"),  # :809
    # 35. 前置き宣言
    ("mh.p35.soredewa-ikimashou", r"それでは.{0,40}していきましょう"),  # :824, :971
    ("mh.p35.ika-de-kuwashiku", r"以下で詳しく解説します"),  # :825, :972
    ("mh.p35.honkiji-dewa-shoukai", r"本記事では.{0,40}を紹介します"),  # :826
    ("mh.p35.tsugi-ni-mite-ikimasu", r"次に.{0,40}について見ていきます"),  # :827
    # 37. 結語の汎用化（即削除）
    ("mh.p37.kongo-tenkai-chumoku", r"今後の展開が注目されます"),  # :861, :974
    ("mh.p37.akarui-mirai", r"明るい未来が期待されます"),  # :861
    ("mh.p37.hikitsuzuki-watch", r"引き続きウォッチしていきましょう"),  # :861
    ("mh.p37.gosankou", r"ご参考になれば幸いです"),  # :861, :969
    ("mh.p37.hikitsuzuki-yoroshiku", r"引き続きよろしくお願いいたします"),  # :861, :970
    # 機械的置換表
    ("mh.repl.toshite-kinou", r"として機能している"),  # :991
    ("mh.repl.yakuwari-wo-hatashite", r"の役割を果たしている"),  # :992
    ("mh.repl.oohaba-na", r"大幅な"),  # :988
    # 40. 「！」の連打（1投稿3個以上）
    ("mh.p40.exclamation", r"[！!]"),  # :901-914（数で判定）
]
