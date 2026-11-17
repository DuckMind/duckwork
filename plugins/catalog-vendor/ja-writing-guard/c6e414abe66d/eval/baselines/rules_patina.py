# -*- coding: utf-8 -*-
"""patina (devswha/patina) の日本語規則を Python の正規表現に抜き出したもの。

出典: https://github.com/devswha/patina (MIT License, Copyright (c) 2025 devswha)
- lexicon/ai-ja.md の Multi-word phrases（`~` は原典の定義どおり「40字以内の任意」= .{0,40} に変換）
- patterns/ja-*.md の「注意語彙/高頻度語彙/注意語/頻出語」行（N・括弧注記・数字を含む語は文字どおりの語でないため除外）
- src/features/markup-leakage.js の言語非依存の漏れトークン（原典で単独ヒット＝強い証拠扱い）
注意: 原典は「単独ヒットは弱い手がかり、段落内の密度が信号」と定めている（lexicon/ai-ja.md:21-22）。
発火条件（例: 同一段落に3つ以上）は原典の各パターン節の「発火条件」を参照。ここでは語の一致だけを持つ。
"""

RULES = [
    ('patina.lex.01', 'まとめると'),  # lexicon/ai-ja.md:30  原文: まとめると
    ('patina.lex.02', '結論として'),  # lexicon/ai-ja.md:31  原文: 結論として
    ('patina.lex.03', '要するに'),  # lexicon/ai-ja.md:32  原文: 要するに
    ('patina.lex.04', '総じて'),  # lexicon/ai-ja.md:33  原文: 総じて
    ('patina.lex.05', '言い換えれば'),  # lexicon/ai-ja.md:34  原文: 言い換えれば
    ('patina.lex.06', '重要なのは'),  # lexicon/ai-ja.md:35  原文: 重要なのは
    ('patina.lex.07', '注目すべきは'),  # lexicon/ai-ja.md:36  原文: 注目すべきは
    ('patina.lex.08', '特筆すべきは'),  # lexicon/ai-ja.md:37  原文: 特筆すべきは
    ('patina.lex.09', '現代社会において'),  # lexicon/ai-ja.md:38  原文: 現代社会において
    ('patina.lex.10', 'デジタル時代において'),  # lexicon/ai-ja.md:39  原文: デジタル時代において
    ('patina.lex.11', 'テクノロジーの進化により'),  # lexicon/ai-ja.md:40  原文: テクノロジーの進化により
    ('patina.lex.12', '社会の変化に伴い'),  # lexicon/ai-ja.md:41  原文: 社会の変化に伴い
    ('patina.lex.13', '多角的に見ると'),  # lexicon/ai-ja.md:42  原文: 多角的に見ると
    ('patina.lex.14', '長期的に見ると'),  # lexicon/ai-ja.md:43  原文: 長期的に見ると
    ('patina.lex.15', '一方で.{0,40}他方で'),  # lexicon/ai-ja.md:44  原文: 一方で~他方で
    ('patina.lex.16', 'することが重要です'),  # lexicon/ai-ja.md:45  原文: ~することが重要です
    ('patina.lex.17', 'と言えるでしょう'),  # lexicon/ai-ja.md:46  原文: ~と言えるでしょう
    ('patina.lex.18', 'と言えます'),  # lexicon/ai-ja.md:47  原文: ~と言えます
    ('patina.lex.19', 'が求められます'),  # lexicon/ai-ja.md:48  原文: ~が求められます
    ('patina.lex.20', 'につながります'),  # lexicon/ai-ja.md:49  原文: ~につながります
    ('patina.lex.21', 'を実現します'),  # lexicon/ai-ja.md:50  原文: ~を実現します
    ('patina.lex.22', 'を促進します'),  # lexicon/ai-ja.md:51  原文: ~を促進します
    ('patina.lex.23', 'を支える重要な要素'),  # lexicon/ai-ja.md:52  原文: ~を支える重要な要素
    ('patina.lex.24', '重要な役割を果たします'),  # lexicon/ai-ja.md:53  原文: 重要な役割を果たします
    ('patina.lex.25', '新たな可能性を切り開く'),  # lexicon/ai-ja.md:54  原文: 新たな可能性を切り開く
    ('patina.lex.26', '新しい価値を生み出す'),  # lexicon/ai-ja.md:55  原文: 新しい価値を生み出す
    ('patina.lex.27', 'さらなる発展が期待されます'),  # lexicon/ai-ja.md:56  原文: さらなる発展が期待されます
    ('patina.lex.28', '今後ますます重要になる'),  # lexicon/ai-ja.md:57  原文: 今後ますます重要になる
    ('patina.lex.29', '持続可能な成長'),  # lexicon/ai-ja.md:58  原文: 持続可能な成長
    ('patina.lex.30', 'ユーザー体験を向上させる'),  # lexicon/ai-ja.md:59  原文: ユーザー体験を向上させる
    ('patina.lex.31', 'より良い未来'),  # lexicon/ai-ja.md:60  原文: より良い未来
    ('patina.lex.32', '課題解決に貢献する'),  # lexicon/ai-ja.md:61  原文: 課題解決に貢献する
    ('patina.lex.33', '多様なニーズに応える'),  # lexicon/ai-ja.md:62  原文: 多様なニーズに応える
    ('patina.lex.34', '柔軟に対応する'),  # lexicon/ai-ja.md:63  原文: 柔軟に対応する
    ('patina.lex.35', '効果的に活用する'),  # lexicon/ai-ja.md:64  原文: 効果的に活用する
    ('patina.lex.36', '最大限に引き出す'),  # lexicon/ai-ja.md:65  原文: 最大限に引き出す
    ('patina.lex.37', '価値を最大化する'),  # lexicon/ai-ja.md:66  原文: 価値を最大化する
    ('patina.lex.38', '本記事では'),  # lexicon/ai-ja.md:67  原文: 本記事では
    ('patina.lex.39', 'この記事では'),  # lexicon/ai-ja.md:68  原文: この記事では
    ('patina.lex.40', 'ここでは.{0,40}について解説します'),  # lexicon/ai-ja.md:69  原文: ここでは~について解説します
    ('patina.lex.41', 'ぜひ参考にしてください'),  # lexicon/ai-ja.md:70  原文: ぜひ参考にしてください
    ('patina.lex.42', '理解を深める'),  # lexicon/ai-ja.md:71  原文: 理解を深める
    ('patina.lex.43', '具体的に見ていきましょう'),  # lexicon/ai-ja.md:72  原文: 具体的に見ていきましょう
    ('patina.lex.44', 'さまざまな場面で活用できます'),  # lexicon/ai-ja.md:73  原文: さまざまな場面で活用できます
    ('patina.lex.45', '幅広い分野で注目されています'),  # lexicon/ai-ja.md:74  原文: 幅広い分野で注目されています
    ('patina.lex.46', '新たな選択肢'),  # lexicon/ai-ja.md:75  原文: 新たな選択肢
    ('patina.lex.47', '大きなメリットがあります'),  # lexicon/ai-ja.md:76  原文: 大きなメリットがあります
    ('patina.lex.48', '重要なポイントです'),  # lexicon/ai-ja.md:77  原文: 重要なポイントです
    ('patina.lex.49', '欠かせない存在'),  # lexicon/ai-ja.md:78  原文: 欠かせない存在
    ('patina.lex.50', 'ますます注目を集めています'),  # lexicon/ai-ja.md:79  原文: ますます注目を集めています
    ('patina.lex.51', '未来を切り拓く'),  # lexicon/ai-ja.md:80  原文: 未来を切り拓く
    ('patina.lex.52', '一歩踏み出すきっかけ'),  # lexicon/ai-ja.md:81  原文: 一歩踏み出すきっかけ
    ('patina.lex.53', '可能性を広げる'),  # lexicon/ai-ja.md:82  原文: 可能性を広げる
    ('patina.lex.54', '安心して利用できます'),  # lexicon/ai-ja.md:83  原文: 安心して利用できます
    ('patina.lex.55', 'より効果的な'),  # lexicon/ai-ja.md:84  原文: より効果的な
    ('patina.lex.56', '最適な方法'),  # lexicon/ai-ja.md:85  原文: 最適な方法
    ('patina.lex.57', '本質的な価値'),  # lexicon/ai-ja.md:86  原文: 本質的な価値
    ('patina.lex.58', 'これからの時代に求められる'),  # lexicon/ai-ja.md:87  原文: これからの時代に求められる
    ('patina.lex.59', '単なる.{0,40}ではなく'),  # lexicon/ai-ja.md:88  原文: 単なる~ではなく
    ('patina.lex.60', '重要な鍵となります'),  # lexicon/ai-ja.md:89  原文: 重要な鍵となります
    ('patina.ja-communication.p19.061', 'お役に立てれば幸いです'),  # patterns/ja-communication.md:18 (チャットボットの痕跡)  原文: お役に立てれば幸いです
    ('patina.ja-communication.p19.062', 'ご不明な点がございましたら'),  # patterns/ja-communication.md:18 (チャットボットの痕跡)  原文: ご不明な点がございましたら
    ('patina.ja-communication.p19.063', '以下にまとめました'),  # patterns/ja-communication.md:18 (チャットボットの痕跡)  原文: 以下にまとめました
    ('patina.ja-communication.p19.064', 'ご紹介させていただきます'),  # patterns/ja-communication.md:18 (チャットボットの痕跡)  原文: ご紹介させていただきます
    ('patina.ja-communication.p19.065', 'さらに詳しい情報が必要な場合は'),  # patterns/ja-communication.md:18 (チャットボットの痕跡)  原文: さらに詳しい情報が必要な場合は
    ('patina.ja-communication.p19.066', 'お答えします'),  # patterns/ja-communication.md:18 (チャットボットの痕跡)  原文: お答えします
    ('patina.ja-communication.p20.067', '私の知識のカットオフ時点では'),  # patterns/ja-communication.md:44 (学習データ切断日の免責)  原文: 私の知識のカットオフ時点では
    ('patina.ja-communication.p20.068', 'リアルタイム情報にはアクセスできません'),  # patterns/ja-communication.md:44 (学習データ切断日の免責)  原文: リアルタイム情報にはアクセスできません
    ('patina.ja-communication.p20.069', '最新の情報と異なる場合があります'),  # patterns/ja-communication.md:44 (学習データ切断日の免責)  原文: 最新の情報と異なる場合があります
    ('patina.ja-communication.p20.070', '具体的なデータは変動している可能性があります'),  # patterns/ja-communication.md:44 (学習データ切断日の免責)  原文: 具体的なデータは変動している可能性があります
    ('patina.ja-communication.p20.071', '最新の情報をご確認ください'),  # patterns/ja-communication.md:44 (学習データ切断日の免責)  原文: 最新の情報をご確認ください
    ('patina.ja-communication.p21.072', '素晴らしいご質問ですね'),  # patterns/ja-communication.md:70 (お世辞・追従的な語調)  原文: 素晴らしいご質問ですね
    ('patina.ja-communication.p21.073', 'おっしゃる通りです'),  # patterns/ja-communication.md:70 (お世辞・追従的な語調)  原文: おっしゃる通りです
    ('patina.ja-communication.p21.074', '非常に鋭いご指摘です'),  # patterns/ja-communication.md:70 (お世辞・追従的な語調)  原文: 非常に鋭いご指摘です
    ('patina.ja-communication.p21.075', 'とても興味深いテーマですね'),  # patterns/ja-communication.md:70 (お世辞・追従的な語調)  原文: とても興味深いテーマですね
    ('patina.ja-communication.p21.076', '大変価値のあるお考えですね'),  # patterns/ja-communication.md:70 (お世辞・追従的な語調)  原文: 大変価値のあるお考えですね
    ('patina.ja-communication.p29.077', '実はもう少し微妙な問題で'),  # patterns/ja-communication.md:92 (偽りのニュアンス（事後的な言い換え）)  原文: 実はもう少し微妙な問題で
    ('patina.ja-communication.p29.078', '正確に言えば'),  # patterns/ja-communication.md:92 (偽りのニュアンス（事後的な言い換え）)  原文: 正確に言えば
    ('patina.ja-communication.p29.079', '単純にはそう言えませんが'),  # patterns/ja-communication.md:92 (偽りのニュアンス（事後的な言い換え）)  原文: 単純にはそう言えませんが
    ('patina.ja-communication.p29.080', 'もちろん現実はもっと複雑で'),  # patterns/ja-communication.md:92 (偽りのニュアンス（事後的な言い換え）)  原文: もちろん現実はもっと複雑で
    ('patina.ja-communication.p29.081', 'より正確には'),  # patterns/ja-communication.md:92 (偽りのニュアンス（事後的な言い換え）)  原文: より正確には
    ('patina.ja-communication.p29.082', '公平に見れば'),  # patterns/ja-communication.md:92 (偽りのニュアンス（事後的な言い換え）)  原文: 公平に見れば
    ('patina.ja-communication.p29.083', 'もう少し掘り下げると'),  # patterns/ja-communication.md:92 (偽りのニュアンス（事後的な言い換え）)  原文: もう少し掘り下げると
    ('patina.ja-content.p1.084', '画期的な'),  # patterns/ja-content.md:18 (過度な重要性の強調)  原文: 画期的な
    ('patina.ja-content.p1.085', '革新的な'),  # patterns/ja-content.md:18 (過度な重要性の強調)  原文: 革新的な
    ('patina.ja-content.p1.086', 'パラダイムシフト'),  # patterns/ja-content.md:18 (過度な重要性の強調)  原文: パラダイムシフト
    ('patina.ja-content.p1.087', '歴史的な転換点'),  # patterns/ja-content.md:18 (過度な重要性の強調)  原文: 歴史的な転換点
    ('patina.ja-content.p1.088', '新たな地平を切り開く'),  # patterns/ja-content.md:18 (過度な重要性の強調)  原文: 新たな地平を切り開く
    ('patina.ja-content.p1.089', '礎を築く'),  # patterns/ja-content.md:18 (過度な重要性の強調)  原文: 礎を築く
    ('patina.ja-content.p1.090', '金字塔'),  # patterns/ja-content.md:18 (過度な重要性の強調)  原文: 金字塔
    ('patina.ja-content.p1.091', 'の先駆けとなる'),  # patterns/ja-content.md:18 (過度な重要性の強調)  原文: の先駆けとなる
    ('patina.ja-content.p1.092', 'において極めて重要な意義を持つ'),  # patterns/ja-content.md:18 (過度な重要性の強調)  原文: において極めて重要な意義を持つ
    ('patina.ja-content.p1.093', 'の幕開け'),  # patterns/ja-content.md:18 (過度な重要性の強調)  原文: の幕開け
    ('patina.ja-content.p1.094', '時代を画する'),  # patterns/ja-content.md:18 (過度な重要性の強調)  原文: 時代を画する
    ('patina.ja-content.p2.095', '大きな注目を集めている'),  # patterns/ja-content.md:41 (過度な注目度・メディア言及)  原文: 大きな注目を集めている
    ('patina.ja-content.p2.096', '世界的に認められた'),  # patterns/ja-content.md:41 (過度な注目度・メディア言及)  原文: 世界的に認められた
    ('patina.ja-content.p2.097', '国内外のメディアから高い評価を受け'),  # patterns/ja-content.md:41 (過度な注目度・メディア言及)  原文: 国内外のメディアから高い評価を受け
    ('patina.ja-content.p2.098', '各方面から称賛の声が上がっている'),  # patterns/ja-content.md:41 (過度な注目度・メディア言及)  原文: 各方面から称賛の声が上がっている
    ('patina.ja-content.p2.099', '話題を呼んでいる'),  # patterns/ja-content.md:41 (過度な注目度・メディア言及)  原文: 話題を呼んでいる
    ('patina.ja-content.p3.100', '示しながら'),  # patterns/ja-content.md:66 (～しながら/～することで 表層的分析)  原文: 示しながら
    ('patina.ja-content.p3.101', '強調しつつ'),  # patterns/ja-content.md:66 (～しながら/～することで 表層的分析)  原文: 強調しつつ
    ('patina.ja-content.p3.102', '反映しており'),  # patterns/ja-content.md:66 (～しながら/～することで 表層的分析)  原文: 反映しており
    ('patina.ja-content.p3.103', '象徴するとともに'),  # patterns/ja-content.md:66 (～しながら/～することで 表層的分析)  原文: 象徴するとともに
    ('patina.ja-content.p3.104', '促進しながら'),  # patterns/ja-content.md:66 (～しながら/～することで 表層的分析)  原文: 促進しながら
    ('patina.ja-content.p3.105', '体現しつつ'),  # patterns/ja-content.md:66 (～しながら/～することで 表層的分析)  原文: 体現しつつ
    ('patina.ja-content.p3.106', '見せながら'),  # patterns/ja-content.md:66 (～しながら/～することで 表層的分析)  原文: 見せながら
    ('patina.ja-content.p3.107', '物語っており'),  # patterns/ja-content.md:66 (～しながら/～することで 表層的分析)  原文: 物語っており
    ('patina.ja-content.p4.108', '素晴らしい'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: 素晴らしい
    ('patina.ja-content.p4.109', '世界クラスの'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: 世界クラスの
    ('patina.ja-content.p4.110', '必見の'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: 必見の
    ('patina.ja-content.p4.111', '息をのむような'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: 息をのむような
    ('patina.ja-content.p4.112', '魅力あふれる'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: 魅力あふれる
    ('patina.ja-content.p4.113', '唯一無二の'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: 唯一無二の
    ('patina.ja-content.p4.114', '圧巻の'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: 圧巻の
    ('patina.ja-content.p4.115', '感動的な'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: 感動的な
    ('patina.ja-content.p4.116', '類まれなる'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: 類まれなる
    ('patina.ja-content.p4.117', '他に類を見ない'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: 他に類を見ない
    ('patina.ja-content.p4.118', 'の宝庫'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: の宝庫
    ('patina.ja-content.p4.119', '至高の'),  # patterns/ja-content.md:91 (広告的・宣伝的言語)  原文: 至高の
    ('patina.ja-content.p5.120', '専門家によると'),  # patterns/ja-content.md:114 (曖昧な出典引用)  原文: 専門家によると
    ('patina.ja-content.p5.121', '研究によれば'),  # patterns/ja-content.md:114 (曖昧な出典引用)  原文: 研究によれば
    ('patina.ja-content.p5.122', '関係者は'),  # patterns/ja-content.md:114 (曖昧な出典引用)  原文: 関係者は
    ('patina.ja-content.p5.123', '業界では'),  # patterns/ja-content.md:114 (曖昧な出典引用)  原文: 業界では
    ('patina.ja-content.p5.124', '一部の見方では'),  # patterns/ja-content.md:114 (曖昧な出典引用)  原文: 一部の見方では
    ('patina.ja-content.p6.125', '課題はあるものの'),  # patterns/ja-content.md:139 (定型的な課題と展望)  原文: 課題はあるものの
    ('patina.ja-content.p6.126', '今後の発展が期待される'),  # patterns/ja-content.md:139 (定型的な課題と展望)  原文: 今後の発展が期待される
    ('patina.ja-content.p6.127', 'にもかかわらず前途は明るい'),  # patterns/ja-content.md:139 (定型的な課題と展望)  原文: にもかかわらず前途は明るい
    ('patina.ja-content.p6.128', 'さまざまな課題を乗り越え'),  # patterns/ja-content.md:139 (定型的な課題と展望)  原文: さまざまな課題を乗り越え
    ('patina.ja-content.p6.129', '急速に変化する現代社会において'),  # patterns/ja-content.md:139 (定型的な課題と展望)  原文: 急速に変化する現代社会において
    ('patina.ja-content.p6.130', 'の時代を迎え'),  # patterns/ja-content.md:139 (定型的な課題と展望)  原文: の時代を迎え
    ('patina.ja-filler.p22.131', '周知の通り'),  # patterns/ja-filler.md:23 (フィラー表現)  原文: 周知の通り
    ('patina.ja-filler.p22.132', '言うまでもなく'),  # patterns/ja-filler.md:23 (フィラー表現)  原文: 言うまでもなく
    ('patina.ja-filler.p22.133', '疑いなく'),  # patterns/ja-filler.md:23 (フィラー表現)  原文: 疑いなく
    ('patina.ja-filler.p22.134', '指摘すべきは'),  # patterns/ja-filler.md:23 (フィラー表現)  原文: 指摘すべきは
    ('patina.ja-filler.p22.135', '強調すべきは'),  # patterns/ja-filler.md:23 (フィラー表現)  原文: 強調すべきは
    ('patina.ja-filler.p22.136', '注目すべきは'),  # patterns/ja-filler.md:23 (フィラー表現)  原文: 注目すべきは
    ('patina.ja-filler.p22.137', '事実として'),  # patterns/ja-filler.md:23 (フィラー表現)  原文: 事実として
    ('patina.ja-filler.p22.138', 'という点は注目に値する'),  # patterns/ja-filler.md:23 (フィラー表現)  原文: という点は注目に値する
    ('patina.ja-filler.p22.139', 'に留意する必要がある'),  # patterns/ja-filler.md:23 (フィラー表現)  原文: に留意する必要がある
    ('patina.ja-filler.p23.140', 'おそらく.{0,40}かもしれない'),  # patterns/ja-filler.md:54 (過剰なヘッジング)  原文: おそらく〜かもしれない
    ('patina.ja-filler.p23.141', 'ある程度.{0,40}の可能性がある'),  # patterns/ja-filler.md:54 (過剰なヘッジング)  原文: ある程度〜の可能性がある
    ('patina.ja-filler.p23.142', 'とも考えられなくはない'),  # patterns/ja-filler.md:54 (過剰なヘッジング)  原文: とも考えられなくはない
    ('patina.ja-filler.p23.143', 'ある意味では.{0,40}とも言える'),  # patterns/ja-filler.md:54 (過剰なヘッジング)  原文: ある意味では〜とも言える
    ('patina.ja-filler.p23.144', 'と言えるかもしれない'),  # patterns/ja-filler.md:54 (過剰なヘッジング)  原文: と言えるかもしれない
    ('patina.ja-filler.p23.145', '一概には.{0,40}とは言い切れない'),  # patterns/ja-filler.md:54 (過剰なヘッジング)  原文: 一概には〜とは言い切れない
    ('patina.ja-filler.p24.146', '今後が期待される'),  # patterns/ja-filler.md:77 (空虚な楽観的結論)  原文: 今後が期待される
    ('patina.ja-filler.p24.147', '今後の展開に注目したい'),  # patterns/ja-filler.md:77 (空虚な楽観的結論)  原文: 今後の展開に注目したい
    ('patina.ja-filler.p24.148', '大きな可能性を秘めている'),  # patterns/ja-filler.md:77 (空虚な楽観的結論)  原文: 大きな可能性を秘めている
    ('patina.ja-filler.p24.149', '輝かしい未来が待っている'),  # patterns/ja-filler.md:77 (空虚な楽観的結論)  原文: 輝かしい未来が待っている
    ('patina.ja-filler.p24.150', 'ワクワクする未来'),  # patterns/ja-filler.md:77 (空虚な楽観的結論)  原文: ワクワクする未来
    ('patina.ja-filler.p24.151', '無限の可能性'),  # patterns/ja-filler.md:77 (空虚な楽観的結論)  原文: 無限の可能性
    ('patina.ja-filler.p24.152', '新たな章の幕開け'),  # patterns/ja-filler.md:77 (空虚な楽観的結論)  原文: 新たな章の幕開け
    ('patina.ja-filler.p31.153', '結論として'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 結論として
    ('patina.ja-filler.p31.154', '結局'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 結局
    ('patina.ja-filler.p31.155', '究極的には'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 究極的には
    ('patina.ja-filler.p31.156', '要するに'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 要するに
    ('patina.ja-filler.p31.157', 'まとめると'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: まとめると
    ('patina.ja-filler.p31.158', '最終的に'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 最終的に
    ('patina.ja-filler.p31.159', '総じて'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 総じて
    ('patina.ja-filler.p31.160', 'つまり'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: つまり
    ('patina.ja-filler.p31.161', '言い換えれば'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 言い換えれば
    ('patina.ja-filler.p31.162', '以上から'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 以上から
    ('patina.ja-filler.p31.163', '学びました'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 学びました
    ('patina.ja-filler.p31.164', '気づきました'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 気づきました
    ('patina.ja-filler.p31.165', '教訓は'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 教訓は
    ('patina.ja-filler.p31.166', 'が示すのは'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: が示すのは
    ('patina.ja-filler.p31.167', '物語っているのは'),  # patterns/ja-filler.md:108 (結論シグナルワードの濫用)  原文: 物語っているのは
    ('patina.ja-language.p7.168', '多様な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 多様な
    ('patina.ja-language.p7.169', '活発な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 活発な
    ('patina.ja-language.p7.170', '革新的な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 革新的な
    ('patina.ja-language.p7.171', '画期的な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 画期的な
    ('patina.ja-language.p7.172', '体系的な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 体系的な
    ('patina.ja-language.p7.173', '持続的な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 持続的な
    ('patina.ja-language.p7.174', '効果的な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 効果的な
    ('patina.ja-language.p7.175', '包括的な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 包括的な
    ('patina.ja-language.p7.176', '先進的な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 先進的な
    ('patina.ja-language.p7.177', '有機的な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 有機的な
    ('patina.ja-language.p7.178', '総合的な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 総合的な
    ('patina.ja-language.p7.179', '主導的な'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 主導的な
    ('patina.ja-language.p7.180', 'さらに'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: さらに
    ('patina.ja-language.p7.181', '加えて'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 加えて
    ('patina.ja-language.p7.182', 'これにより'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: これにより
    ('patina.ja-language.p7.183', 'こうした中'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: こうした中
    ('patina.ja-language.p7.184', '推進する'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 推進する
    ('patina.ja-language.p7.185', '促進する'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 促進する
    ('patina.ja-language.p7.186', '最大化する'),  # patterns/ja-language.md:35 (AI特有の語彙の多用)  原文: 最大化する
    ('patina.ja-language.p8.187', '革新的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 革新的
    ('patina.ja-language.p8.188', '体系的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 体系的
    ('patina.ja-language.p8.189', '効果的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 効果的
    ('patina.ja-language.p8.190', '効率的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 効率的
    ('patina.ja-language.p8.191', '先進的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 先進的
    ('patina.ja-language.p8.192', '積極的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 積極的
    ('patina.ja-language.p8.193', '総合的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 総合的
    ('patina.ja-language.p8.194', '核心的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 核心的
    ('patina.ja-language.p8.195', '戦略的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 戦略的
    ('patina.ja-language.p8.196', '実質的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 実質的
    ('patina.ja-language.p8.197', '根本的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 根本的
    ('patina.ja-language.p8.198', '画期的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 画期的
    ('patina.ja-language.p8.199', '抜本的'),  # patterns/ja-language.md:58 (〜的（てき）接尾辞の多用)  原文: 抜本的
    ('patina.ja-language.p9.200', 'にとどまらず'),  # patterns/ja-language.md:83 (否定並列構造)  原文: にとどまらず
    ('patina.ja-language.p9.201', 'のみならず.{0,40}も'),  # patterns/ja-language.md:83 (否定並列構造)  原文: のみならず〜も
    ('patina.ja-language.p9.202', '単に.{0,40}だけでなく'),  # patterns/ja-language.md:83 (否定並列構造)  原文: 単に〜だけでなく
    ('patina.ja-language.p9.203', 'を超えて'),  # patterns/ja-language.md:83 (否定並列構造)  原文: を超えて
    ('patina.ja-language.p12.204', 'イノベーション'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: イノベーション
    ('patina.ja-language.p12.205', 'ソリューション'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: ソリューション
    ('patina.ja-language.p12.206', 'パフォーマンス'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: パフォーマンス
    ('patina.ja-language.p12.207', 'ガバナンス'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: ガバナンス
    ('patina.ja-language.p12.208', 'コンセンサス'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: コンセンサス
    ('patina.ja-language.p12.209', 'シナジー'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: シナジー
    ('patina.ja-language.p12.210', 'モメンタム'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: モメンタム
    ('patina.ja-language.p12.211', 'マイルストーン'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: マイルストーン
    ('patina.ja-language.p12.212', 'トリガー'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: トリガー
    ('patina.ja-language.p12.213', 'スケールアップ'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: スケールアップ
    ('patina.ja-language.p12.214', 'オンボーディング'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: オンボーディング
    ('patina.ja-language.p12.215', 'フィードバックループ'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: フィードバックループ
    ('patina.ja-language.p12.216', 'ペインポイント'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: ペインポイント
    ('patina.ja-language.p12.217', 'ディシジョンメイキング'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: ディシジョンメイキング
    ('patina.ja-language.p12.218', 'エコシステム'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: エコシステム
    ('patina.ja-language.p12.219', 'レジリエンス'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: レジリエンス
    ('patina.ja-language.p12.220', 'サステナビリティ'),  # patterns/ja-language.md:149 (カタカナ外来語の多用)  原文: サステナビリティ
    ('patina.ja-language.p32.221', 'より\\ \\+\\ 形容詞・副詞の形\\ —\\ 「より具体的な」「より効率的な」「より深い」「より明確な」「より積極的な」「より体系的な」「より効果的な」「より慎重な」「より幅広い」「より良い」'),  # patterns/ja-language.md:173 (「より」比較副詞の濫用)  原文: より + 形容詞・副詞の形 — 「より具体的な」「より効率的な」「より深い」「より明確な」「より積極的な」「より体系的な」「より効果的な」「より慎重な」「より幅広い」「より良い」
    ('patina.ja-language.p34.222', 'データが物語っている'),  # patterns/ja-language.md:227 (無生物行為主（擬似的行為性）)  原文: データが物語っている
    ('patina.ja-language.p34.223', '数字が証明している'),  # patterns/ja-language.md:227 (無生物行為主（擬似的行為性）)  原文: 数字が証明している
    ('patina.ja-language.p34.224', '決定が自然と生まれた'),  # patterns/ja-language.md:227 (無生物行為主（擬似的行為性）)  原文: 決定が自然と生まれた
    ('patina.ja-language.p34.225', '文化が変わっていった'),  # patterns/ja-language.md:227 (無生物行為主（擬似的行為性）)  原文: 文化が変わっていった
    ('patina.ja-language.p34.226', '議論が.{0,40}へと動いた'),  # patterns/ja-language.md:227 (無生物行為主（擬似的行為性）)  原文: 議論が~へと動いた
    ('patina.ja-language.p34.227', '市場が報いる'),  # patterns/ja-language.md:227 (無生物行為主（擬似的行為性）)  原文: 市場が報いる
    ('patina.ja-language.p34.228', '市場が選択する'),  # patterns/ja-language.md:227 (無生物行為主（擬似的行為性）)  原文: 市場が選択する
    ('patina.ja-language.p34.229', 'このテクノロジーが.{0,40}を可能にする'),  # patterns/ja-language.md:227 (無生物行為主（擬似的行為性）)  原文: このテクノロジーが~を可能にする
    ('patina.ja-language.p34.230', '戦略が要求する'),  # patterns/ja-language.md:227 (無生物行為主（擬似的行為性）)  原文: 戦略が要求する
    ('patina.ja-language.p34.231', '状況が語るように'),  # patterns/ja-language.md:227 (無生物行為主（擬似的行為性）)  原文: 状況が語るように
    ('patina.ja-language.p34.232', '結果がすべてを物語る'),  # patterns/ja-language.md:227 (無生物行為主（擬似的行為性）)  原文: 結果がすべてを物語る
    ('patina.ja-structure.p26.233', 'という事実'),  # patterns/ja-structure.md:53 (翻訳調)  原文: という事実
    ('patina.ja-structure.p26.234', 'することが可能である'),  # patterns/ja-structure.md:53 (翻訳調)  原文: することが可能である
    ('patina.ja-structure.p26.235', 'によって.{0,40}される'),  # patterns/ja-structure.md:53 (翻訳調)  原文: によって〜される
    ('patina.ja-structure.p26.236', 'に関して'),  # patterns/ja-structure.md:53 (翻訳調)  原文: に関して
    ('patina.ja-structure.p26.237', 'に基づいて'),  # patterns/ja-structure.md:53 (翻訳調)  原文: に基づいて
    ('patina.ja-structure.p26.238', 'の観点から'),  # patterns/ja-structure.md:53 (翻訳調)  原文: の観点から
    ('patina.ja-structure.p26.239', 'する傾向がある'),  # patterns/ja-structure.md:53 (翻訳調)  原文: する傾向がある
    ('patina.ja-structure.p27.240', 'している'),  # patterns/ja-structure.md:82 (ている進行形の多用)  原文: している
    ('patina.ja-structure.p27.241', 'を推進している'),  # patterns/ja-structure.md:82 (ている進行形の多用)  原文: を推進している
    ('patina.ja-structure.p27.242', 'を展開している'),  # patterns/ja-structure.md:82 (ている進行形の多用)  原文: を展開している
    ('patina.ja-structure.p27.243', 'に取り組んでいる'),  # patterns/ja-structure.md:82 (ている進行形の多用)  原文: に取り組んでいる
    ('patina.ja-structure.p27.244', 'を進めている'),  # patterns/ja-structure.md:82 (ている進行形の多用)  原文: を進めている
    ('patina.ja-structure.p27.245', 'に拍車をかけている'),  # patterns/ja-structure.md:82 (ている進行形の多用)  原文: に拍車をかけている
    ('patina.ja-style.p13.246', 'これにより'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: これにより
    ('patina.ja-style.p13.247', 'こうした点で'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: こうした点で
    ('patina.ja-style.p13.248', 'こうした中'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: こうした中
    ('patina.ja-style.p13.249', '一方で'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: 一方で
    ('patina.ja-style.p13.250', 'また'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: また
    ('patina.ja-style.p13.251', 'さらに'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: さらに
    ('patina.ja-style.p13.252', '加えて'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: 加えて
    ('patina.ja-style.p13.253', 'これに伴い'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: これに伴い
    ('patina.ja-style.p13.254', 'これに関連して'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: これに関連して
    ('patina.ja-style.p13.255', 'これを踏まえて'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: これを踏まえて
    ('patina.ja-style.p13.256', 'それゆえ'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: それゆえ
    ('patina.ja-style.p13.257', 'したがって'),  # patterns/ja-style.md:18 (接続表現の過剰使用)  原文: したがって
    ('patina.ja-style.p16.258', 'でございます'),  # patterns/ja-style.md:87 (ございます／でございます敬語の過剰使用)  原文: でございます
    ('patina.ja-style.p16.259', 'ございます'),  # patterns/ja-style.md:87 (ございます／でございます敬語の過剰使用)  原文: ございます
    ('patina.ja-style.p16.260', 'いただけますと幸いです'),  # patterns/ja-style.md:87 (ございます／でございます敬語の過剰使用)  原文: いただけますと幸いです
    ('patina.ja-style.p16.261', 'させていただきます'),  # patterns/ja-style.md:87 (ございます／でございます敬語の過剰使用)  原文: させていただきます
    ('patina.ja-style.p16.262', 'いただければと存じます'),  # patterns/ja-style.md:87 (ございます／でございます敬語の過剰使用)  原文: いただければと存じます
    ('patina.ja-style.p16.263', 'いただけますでしょうか'),  # patterns/ja-style.md:87 (ございます／でございます敬語の過剰使用)  原文: いただけますでしょうか
    ('patina.ja-style.p18.264', 'と言えよう'),  # patterns/ja-style.md:135 (過剰なである調／硬質文体)  原文: と言えよう
    ('patina.ja-style.p18.265', 'であると言わざるを得ない'),  # patterns/ja-style.md:135 (過剰なである調／硬質文体)  原文: であると言わざるを得ない
    ('patina.ja-style.p18.266', 'の感が否めない'),  # patterns/ja-style.md:135 (過剰なである調／硬質文体)  原文: の感が否めない
    ('patina.ja-style.p18.267', 'と言っても過言ではない'),  # patterns/ja-style.md:135 (過剰なである調／硬質文体)  原文: と言っても過言ではない
    ('patina.ja-style.p18.268', 'の一助となれば幸いである'),  # patterns/ja-style.md:135 (過剰なである調／硬質文体)  原文: の一助となれば幸いである
    ('patina.ja-style.p18.269', '鑑みるに'),  # patterns/ja-style.md:135 (過剰なである調／硬質文体)  原文: 鑑みるに
    ('patina.ja-style.p18.270', '畢竟'),  # patterns/ja-style.md:135 (過剰なである調／硬質文体)  原文: 畢竟
    ('patina.ja-style.p18.271', '蓋し'),  # patterns/ja-style.md:135 (過剰なである調／硬質文体)  原文: 蓋し
    ('patina.ja-viral-hook.p1.272', 'ゼロ予算で'),  # patterns/ja-viral-hook.md:25 (数字ショックフック)  原文: ゼロ予算で
    ('patina.ja-viral-hook.p2.273', 'とは？'),  # patterns/ja-viral-hook.md:47 (クリックベイト末尾)  原文: とは？
    ('patina.ja-viral-hook.p2.274', 'の理由'),  # patterns/ja-viral-hook.md:47 (クリックベイト末尾)  原文: の理由
    ('patina.ja-viral-hook.p2.275', '知らないと損する'),  # patterns/ja-viral-hook.md:47 (クリックベイト末尾)  原文: 知らないと損する
    ('patina.ja-viral-hook.p2.276', 'って実は…'),  # patterns/ja-viral-hook.md:47 (クリックベイト末尾)  原文: って実は…
    ('patina.ja-viral-hook.p2.277', '見ないと後悔する'),  # patterns/ja-viral-hook.md:47 (クリックベイト末尾)  原文: 見ないと後悔する
    ('patina.ja-viral-hook.p3.278', '史上初'),  # patterns/ja-viral-hook.md:68 (出典回避の権威主張)  原文: 史上初
    ('patina.ja-viral-hook.p3.279', '過去最高'),  # patterns/ja-viral-hook.md:68 (出典回避の権威主張)  原文: 過去最高
    ('patina.ja-viral-hook.p3.280', '過去最速'),  # patterns/ja-viral-hook.md:68 (出典回避の権威主張)  原文: 過去最速
    ('patina.ja-viral-hook.p3.281', '業界初'),  # patterns/ja-viral-hook.md:68 (出典回避の権威主張)  原文: 業界初
    ('patina.ja-viral-hook.p3.282', '唯一無二'),  # patterns/ja-viral-hook.md:68 (出典回避の権威主張)  原文: 唯一無二
    ('patina.ja-viral-hook.p5.283', 'ヤバい'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: ヤバい
    ('patina.ja-viral-hook.p5.284', 'マジヤバい'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: マジヤバい
    ('patina.ja-viral-hook.p5.285', '神アプデ'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: 神アプデ
    ('patina.ja-viral-hook.p5.286', '神回'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: 神回
    ('patina.ja-viral-hook.p5.287', '神ツール'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: 神ツール
    ('patina.ja-viral-hook.p5.288', '革命'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: 革命
    ('patina.ja-viral-hook.p5.289', 'ゲームチェンジャー'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: ゲームチェンジャー
    ('patina.ja-viral-hook.p5.290', '見ないと損'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: 見ないと損
    ('patina.ja-viral-hook.p5.291', '知らないと損'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: 知らないと損
    ('patina.ja-viral-hook.p5.292', '絶対に試すべき'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: 絶対に試すべき
    ('patina.ja-viral-hook.p5.293', '圧倒的'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: 圧倒的
    ('patina.ja-viral-hook.p5.294', '爆速'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: 爆速
    ('patina.ja-viral-hook.p5.295', '神コスパ'),  # patterns/ja-viral-hook.md:119 (誇張エンゲージメント語彙)  原文: 神コスパ
    ('patina.ja-viral-hook.p6.296', 'データによれば'),  # patterns/ja-viral-hook.md:144 (偽統計引用)  原文: データによれば
    ('patina.ja-viral-hook.p6.297', '科学的に証明'),  # patterns/ja-viral-hook.md:144 (偽統計引用)  原文: 科学的に証明
    ('patina.ja-viral-hook.p6.298', '統計上'),  # patterns/ja-viral-hook.md:144 (偽統計引用)  原文: 統計上
    ('patina.ja-viral-hook.p7.299', 'スタンフォード出身'),  # patterns/ja-viral-hook.md:174 (肩書き積み上げ型の権威付け)  原文: スタンフォード出身
    ('patina.ja-viral-hook.p7.300', 'Y\\ Combinator\\ 支援'),  # patterns/ja-viral-hook.md:174 (肩書き積み上げ型の権威付け)  原文: Y Combinator 支援
    ('patina.ja-viral-hook.p7.301', '元\\ Google'),  # patterns/ja-viral-hook.md:174 (肩書き積み上げ型の権威付け)  原文: 元 Google
    ('patina.ja-viral-hook.p7.302', 'ハーバード博士'),  # patterns/ja-viral-hook.md:174 (肩書き積み上げ型の権威付け)  原文: ハーバード博士
    ('patina.ja-viral-hook.p7.303', 'Forbes\\ 掲載'),  # patterns/ja-viral-hook.md:174 (肩書き積み上げ型の権威付け)  原文: Forbes 掲載
    ('patina.ja-viral-hook.p7.304', '受賞歴'),  # patterns/ja-viral-hook.md:174 (肩書き積み上げ型の権威付け)  原文: 受賞歴
    ('patina.ja-viral-hook.p7.305', '連続起業家'),  # patterns/ja-viral-hook.md:174 (肩書き積み上げ型の権威付け)  原文: 連続起業家
    ('patina.ja-viral-hook.p7.306', 'トップ\\ CEO\\ が信頼'),  # patterns/ja-viral-hook.md:174 (肩書き積み上げ型の権威付け)  原文: トップ CEO が信頼
    ('patina.ja-viral-hook.p7.307', '業界トップ専門家'),  # patterns/ja-viral-hook.md:174 (肩書き積み上げ型の権威付け)  原文: 業界トップ専門家
    ('patina.ja-viral-hook.p8.308', '友よ'),  # patterns/ja-viral-hook.md:203 (未来の自分 / 親密な二人称の約束)  原文: 友よ
    ('patina.ja-viral-hook.p8.309', '聞いて'),  # patterns/ja-viral-hook.md:203 (未来の自分 / 親密な二人称の約束)  原文: 聞いて
    ('patina.ja-viral-hook.p8.310', '保存して'),  # patterns/ja-viral-hook.md:203 (未来の自分 / 親密な二人称の約束)  原文: 保存して
    ('patina.ja-viral-hook.p8.311', '未来のあなたが感謝する'),  # patterns/ja-viral-hook.md:203 (未来の自分 / 親密な二人称の約束)  原文: 未来のあなたが感謝する
    ('patina.ja-viral-hook.p8.312', '信じて'),  # patterns/ja-viral-hook.md:203 (未来の自分 / 親密な二人称の約束)  原文: 信じて
    ('patina.ja-viral-hook.p8.313', '後でわかる'),  # patterns/ja-viral-hook.md:203 (未来の自分 / 親密な二人称の約束)  原文: 後でわかる
    ('patina.leak.oai-citation-markup', '(?i):contentReference|oaicite|oai_citation'),  # src/features/markup-leakage.js:29
    ('patina.leak.model-tool-token', '(?i)\\bturn\\d+(?:search|view|news|image|forecast|finance|fetch)\\d*\\b|\\bgrok_card\\b'),  # src/features/markup-leakage.js:34
    ('patina.leak.object-replacement-char', '￼'),  # src/features/markup-leakage.js:21,39
    ('patina.leak.ai-tracking-param', '(?i)utm_source=(?:chatgpt\\.com|openai\\.com|perplexity\\.ai|claude\\.ai|gemini\\.google\\.com)|[?&](?:ref|utm_source)=chatgpt'),  # src/features/markup-leakage.js:44
]
