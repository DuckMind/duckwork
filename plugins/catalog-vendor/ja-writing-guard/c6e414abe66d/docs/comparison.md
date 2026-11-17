# 同じ目的の製品との比較

日本語の「AIっぽさ」を見つける・直す製品を10個読み、ライセンスが取り込みを許すもの（MIT）からだけ規則を取りました。帰属は [NOTICE](../NOTICE) にあります。ライセンスは各リポジトリの LICENSE（または npm パッケージの license）を実物で確かめています。

| 製品 | ライセンス | 形 | 検出項目（要約） | 強み | 弱み | 取り込んだもの |
|---|---|---|---|---|---|---|
| [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu) | MIT | スキル＋Python 検査（標準ライブラリ） | AI 頻出語、比喩動詞、前置きの定型句、「AではなくB」、絵文字、文末コロン、和欧文間の空白、太字・箇条書きの比率、同じ文末の3連続 | 意味を変えない書き直しの指示（主張・比重・言い切りの強さ・文の働き）が具体的 | 検査は1つでも当たれば「要修正」。場面の区別がない | 規則14件、書き直しの原則、構成（検出し、直し、再検査する） |
| [coji/natural-japanese](https://github.com/coji/natural-japanese) | MIT | スキル＋Python 検査（形態素解析 sudachipy が必要） | 禁止語、翻訳調、対比の反復、文長の均質さ、体言止めの欠如、段落頭の接続詞、語彙多様性、具体性 | 人とAIのコーパスで閾値を校正している。ジャンル別の閾値 | 短い業務文では統計の検出器が働かない。依存が重い | 規則25件、ジャンル別閾値の考え方、「一律に直さない」 |
| [textlint-rule-preset-ai-writing](https://github.com/textlint-ja/textlint-rule-preset-ai-writing) | MIT | textlint ルール（Node.js） | 太字＋コロンの箇条書き、箇条書きの絵文字、「注意」などの太字ラベル、誇大語、列挙宣言 | Markdown の構造単位で判定するので誤検知が少ない | 語の数が少ない。日本語の文体（敬体・定型句）は対象外 | 規則7件 |
| [textlint-rule-preset-ja-technical-writing](https://github.com/textlint-ja/textlint-rule-preset-ja-technical-writing) | MIT | textlint ルール | 冗長表現、弱い表現、二重否定、ら抜き、敬体常体の混在、文長、読点、漢字の連続 | 形態素で照合するので精度が高い | AI 専用ではない。官公庁文にも多く当たる | 規則3件（〜を行う、する以外の〜ことができる、二重否定） |
| [textlint-rule-preset-JTF-style](https://github.com/textlint-ja/textlint-rule-preset-JTF-style) | MIT | textlint ルール | 和文中のダッシュ・半角記号など | 記号の規則が明快 | 翻訳の表記規則で、AI 判定には一部だけ | 規則1件（和文中の半角！？） |
| [devswha/patina](https://github.com/devswha/patina) | MIT | CLI＋語彙・パターン集 | 日本語の語彙60句と37パターン（チャットボットの痕跡、知識の時点の断り、追従、ヘッジ、空虚な楽観、偽の洞察、〜的の重ね、AI ツールの出力痕跡など） | 網羅性が最も高い | 語彙が未校正で、単独の一致では誤検知が多い | 規則18件 |
| [geonwoo-jeong/japanese-humanizer](https://github.com/geonwoo-jeong/japanese-humanizer) | MIT | スキル＋決定的プロファイラ（.mjs） | 長文・読点、ことができる、を行う、の連続、二重否定、定型の結び、敬体常体の混在 | 引用・コード・URL を伏せてから照合する | 語リストが小さい | 照合前に伏せる仕組み（detector.py） |
| [gonta223/humanizer-ja](https://github.com/gonta223/humanizer-ja) | MIT | スキル（文章の指示のみ） | 定型評価語、太字ラベル、三点セット、——、付け足しの分詞構文 | 具体的な NG 語 | 機械の検査がない | 規則1件 |
| [matsutouya/humanizer-ja（Humanizer JP）](https://github.com/matsutouya/humanizer-ja) | MIT | スキル（文章の指示のみ） | 強調語、逃げの語尾、させていただきます、前置き宣言、汎用の結語 | 「即削除」「機械的置換」の表が実務的 | 機械の検査がない | 規則1件 |
| [matsuikentaro1/humanizer-japanese](https://github.com/matsuikentaro1/humanizer-japanese) | 不明（LICENSE なし） | スキル | Markdown 記号、カッコの多用、語尾の連続など | 記号の観点が細かい | ライセンス不明 | 取り込んでいない |

## このプラグインの検出項目

点数に入れない参考の指摘は2つ（「させていただきます」の重ね、SNS の「コメントで教えてください」のお願い）で、ほかは点数に入ります。

規則92件と構造の検査7件、合わせて99項目です。各規則の出どころは `rules.py` の `source` に書いてあります（自作28・natural-japanese 25・patina 19・yomiyasu 14・textlint-ai 7・ja-technical 3・JTF/gonta223/matsutouya 各1）。全規則に「当たるべき例文」があり、テストで確かめています。

| 分類 | 項目数 | 例 |
|---|---|---|
| 定型句・常套句 | 30 | 「〜と言えるでしょう」「いかがでしたか」「結論から言うと」、締めのあいさつの重ね、感想・評価の決まり文句、知識の時点の断り書き |
| 記号・書式 | 17 | 語と語の間のダッシュ、太字ラベルの箇条書き、太字だけの行、絵文字の行頭、AI ツールの出力痕跡 |
| 英語の直訳調 | 16 | 「〜することができます」「〜という観点から」「〜を持つ」「〜を可能にします」「あなたの〜」「遠慮なく知らせてください」 |
| 型どおりの構成 | 13 | 「3つのポイント」「以下にまとめました」、自問自答、「まず・次に・最後に」、SNS の「〜は何ですか？ぜひコメントで教えてください」の締めの型（問いかけだけ・お願いだけは数えない。お願いは参考の指摘） |
| 誇張・空虚な言葉 | 13 | 「シームレスに」「新たな価値」「重要な役割を果たします」、宣伝文・広報文の決まり文句 |
| おもねり | 3 | 「素晴らしい質問ですね」、決まり文句の共感 |
| 場面に合わない文体（AI 的な言い回しの点数とは別に報告） | 2 | 敬体が必要な場面での常体、改まった場面でのくだけた言葉 |
| 対比の繰り返し・文末の単調さ | 5 | 「AではなくB」の反復、同じ文末の4連続、体言止めの3連続、敬体と常体の混在 |

数字（同じデータで他の製品の規則と比べた結果）は [README の「精度」](../README.md#精度) にあります。
