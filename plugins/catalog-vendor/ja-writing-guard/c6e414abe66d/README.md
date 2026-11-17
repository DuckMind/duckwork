# ja-writing-guard：日本語の業務文の「AI 的な言い回し」を見つけて直す Duckwork プラグイン

日本語の業務文によく出る AI 的な言い回しを、規則で見つけて直す校正の道具です。見るのは次の4種類です。

- 定型句: 「〜と言えるでしょう」「いかがでしたか」「シームレスに」
- 語尾の単調さ: 同じ文末が何文も続く
- 記号の乱用: メールに残った `**太字**`、語と語の間の「——」
- 直訳調: 「〜することができます」「〜という観点から」

Duckwork Agent が返す日本語のどこにこれらがあるかを、行と位置まで示し、直し方を添えます。

見るのは言い回しだけで、書いたのが人かモデルかは見分けません。人が書いた文でも、この癖があれば指摘します。

## 先に知っておいてほしい限界

- いまのモデルがふだんどおりに書いた文は、ほとんど拾いません（未見の40本中1本）。拾えるのは、上の癖がはっきり出ている文です。
- 誤検知を測った人の文は、官公庁の文が多いです（ライセンス上公開できる文に限ったため）。民間の業務メールや個人の SNS 投稿では測っていません。
- AI 側の評価用の文は、全部同じ系列のモデル（Anthropic の Claude）が書きました。他社のモデルが書いた文では、結果が下がるかもしれません。

数字（未見の test 80本）: 典型的な癖を入れた文40本のうち60%を拾い、人の文40本の誤検知は7.5%でした。目標の80%には届いていません。誤検知を10%以下にそろえて同じデータで比べると、拾えた割合は yomiyasu 50%、natural-japanese 20%、このプラグイン 60% です（この比較の閾値は test の上で選んだ参考値）。点数の並べ方の正しさ（AUC）は yomiyasu 0.79、このプラグイン 0.77 で、ほぼ同じです。詳しくは[精度](#精度)にあります。

## 何をするか

検査は機械で行うので、同じ文には毎回同じ結果が出ます。規則92件と構造の検査7件を持ち、検査ではモデルを呼びません。数百字の返答なら1回の検査はおよそ1ミリ秒、1万字でも20ミリ秒ほどです（手元の Mac での中央値は、数百字で0.9ミリ秒、1万字で13〜16ミリ秒）。

基準は行き先で変わります。業務メールと社外文では「です・ます」を必須にし、チャットは緩めにします。SNS では絵文字を数えず、技術文書では見出しやコードを数えません。

既定は「検査して記録するだけ」で、返答は変えません。

届く前に直すこともできます（任意。既定では切ってあります）。`mode: enforce` にすると、基準を超えた返答を利用者自身のモデルで書き直します。差し替えるのは、数字・曜日・宛名・会社名・署名や見出しの行・「」で囲んだ名前・英字の製品名・URL・コードが元のままで、否定の向きが変わらず、点数が基準を下回ったときだけです。それ以外は元の返答を届けます。

意味が変わらないことは、機械では保証しません。関門が守るのは、いま挙げた決まった項目だけです。業務メールで使うなら、CLI・TUI・Desktop で `/ja-check` を打ち、変わった行を確かめてから送ってください。Telegram やメールなどのゲートウェイでは、変わった行を後から見る手段がありません。

English summary: [below](#english).

## 導入（3手）

Duckwork v0.21.4以上が必要です（古ければ `duckwork update`）。

```bash
duckwork plugins install TakeshiTGAL/duckwork-plugin-ja-writing-guard --enable
duckwork config set plugins.entries.ja-writing-guard.settings.mode enforce   # 任意。省くと検査と記録だけ
duckwork gateway restart                                                      # ゲートウェイを使う場合。CLI は次の起動から
```

プラグインカタログに載った後は `duckwork plugins install ja-writing-guard --enable` でも入ります。手元のコピーで試すときは、clone したフォルダで `duckwork plugins install "file://$PWD" --enable` を実行します。

場面を変えるときは `duckwork config set plugins.entries.ja-writing-guard.settings.surface business_email` のように指定します。Desktop アプリでは Plugins タブの歯車から同じ設定ができます。

## 使い方

### モデルに使わせる

ツール `ja_writing_check` が登録されます。「このメールを自然な日本語に直して」と頼むと、モデルは検査し、指摘された所だけを直し、もう一度検査します。同梱スキル `ja-writing-guard:rewrite-ja` に直し方の手順と例があります。

### 自分で検査する

チャットで `/ja-check` を使います。

```text
/ja-check external 平素より格別のご高配を賜り、厚く御礼申し上げます。本サービスは、配送業務をシームレスに効率化し、お客様のビジネスに新たな価値を提供します。
/ja-check            ← 引数なしで、直前の返答の検査結果を表示。書き直したときは変わった行も出す（CLI・TUI・Desktop のみ）
```

ツールの返り値（抜粋）:

```json
{"surface": "chat", "score": 96, "threshold": 40, "verdict": "rewrite", "reasons": ["ai_like"],
 "summary": "AI的な言い回し 96/100（chat の基準 40）。指摘 5 件（多い順: 定型句・常套句・おもねり・決まり文句の応対・型どおりの構成）。書き直しの対象です。",
 "findings": [{"rule": "sycophancy.great_q", "label": "「素晴らしい質問ですね」", "line": 1, "col": 1,
               "excerpt": "素晴らしい質問ですね！結論から言うと、毎日少…", "hint": "前置きを削り、答えから書く。", "source": "original"}]}
```

### 場面（surface）

| surface | 行き先 | 基準 | 文体の基準 | 緩めるもの・厳しくするもの |
|---|---|---|---|---|
| `chat`（既定） | チャットの返答 | 40 | 常体も可 | 前置き・締めの決まり文句とおもねりに厳しい |
| `business_email` | 社内外の業務メール | 35 | 「です・ます」必須 | Markdown と絵文字に厳しい |
| `external` | お知らせ・リリース・案内 | 40 | 「です・ます」必須 | 宣伝調の言葉に厳しい |
| `sns` | X・note などの投稿 | 35 | 常体も可 | 絵文字・感嘆符は数えない |
| `tech_doc` | README・設計メモ・手順書 | 45 | 常体も可 | 見出し・箇条書き・太字・コードは数えない |

`platform_surfaces` で配信先ごとに場面を変えられます（例: `{"email": "business_email", "slack": "chat"}`）。

「AI 的な言い回しの点数」と「場面の文体の基準（です・ます必須など）」は別々に報告します。人が「である調」で書いた通知は、AI 的な言い回しの点数は低くても、社外文の場面では基準に合わないので、`reasons` に `register` が付き、書き直しの対象になります。人もよく書くものや、書き直しでも残すべき依頼の文は、指摘はしても点数には入れません（`counted: false`）。いまは「させていただきます」の重ねと、SNS の「コメントで教えてください」のお願いの2つです（問いかけの直後にコメントのお願いが続く「〜は何ですか？ぜひコメントで教えてください」の型は点数に入れます。問いかけだけ、お願いだけなら数えません）。

### 設定

| 設定 | 既定 | 意味 |
|---|---|---|
| `mode` | `report` | `report`: 検査して記録だけ（返答は変えない）。`enforce`: 基準を超えたら書き直して届ける。`off`: 何もしない |
| `surface` | `chat` | 既定の場面 |
| `platform_surfaces` | `{}` | 配信先ごとの場面 |
| `threshold` | `0` | 0なら場面の既定値 |
| `max_attempts` | `2` | 書き直しで呼ぶモデルの回数（1〜3） |
| `rewrite_timeout` | `20` | 1回の呼び出しの上限秒数 |
| `time_budget` | `25` | 書き直し全体の持ち時間。5秒未満を指定しても5秒として扱う。Duckwork の `plugins.hook_callback_timeout`（既定30秒）より3秒短くなるよう自動で縮める（こちらが優先） |
| `accept_partial` | `false` | 書き直しで点数は下がったが基準を下回らなかったとき、`false` は元の返答を、`true` は書き直した文を届ける |
| `min_chars` | `40` | これより短い返答は検査しない |

## 書き直しの前後

5本とも `examples/rewrite/` にあります。書き直しは、プラグインがモデルへ送る文面そのものに、別の LLM がモデル役として答えたものです（2回目は、1回目が基準を下回らなかったときに Duckwork と同じ手順で送る、理由つきの依頼への返答）。`tests/test_examples.py` が毎回この表の数字を実測し直します。

| 場面 | 点数（前 → 最良の書き直し） | 試行 | 既定で届く文 | 検出した主な癖と結果 |
|---|---|---|---|---|
| 業務メール | 39 → 0 | 1 | 書き直し | 締めのあいさつの重ね。「させていただきます」の重ねは参考の指摘で、点数には入れない |
| 社外文 | 100 → 0 | 2 | 書き直し | 太字ラベルの箇条書き、「〜ことができます」×4、宣伝語。1回目は「新たな価値」を「新しい価値をつくり続けて」と言い換えただけで基準40を超えたため、理由を添えた2回目で基準を下回った |
| SNS | 82 → 11 | 1 | 書き直し | 「——」、「通過点にすぎません」、「〜は何ですか？ぜひコメントで教えてください」の締めの型。お願いの文そのものは依頼なので残す |
| 技術文書 | 91 → 0 | 1 | 書き直し | 「3つの原則」の宣言、「〜について説明します」の予告、「〜することが可能です」、「シンプルかつ堅牢」 |
| チャット | 98 → 31 | 1 | 書き直し | 「素晴らしい質問ですね」、「結論から言うと」、太字だけの行の見出し、「以下にご紹介します」 |

5本とも、既定（`accept_partial: false`）で書き直しが届きます。社外文の2回目は「シームレスに」を「途切れずに」、「連携できます」を「無理なく連携できます」と言い換えていて、言い回しの細かな足し算までは関門で止めていません（否定の形をした副詞「無理なく」「途切れず」は否定として数えません）。2回とも基準を下回らない場合、既定では元の返答が届き、`accept_partial: true` なら点数が下がった最良の書き直しが届きます。

チャットの例（前）:

> 素晴らしい質問ですね！仕事と資格の勉強を両立させたいというその姿勢、本当に素敵だと思います。
>
> 結論から言うと、\*\*「毎日の短い時間を積み重ねること」\*\*が最も重要です。以下に、具体的な方法をご紹介します。
>
> \*\*1. 朝の30分を確保する\*\*
> 出勤前は、一日の中でも集中力が高い時間帯です。まずは毎朝6時半から7時までの30分を、勉強時間として固定してみましょう。
>
> （中略）
>
> あなたならきっと合格できます！応援しています。ほかにも気になることがあれば、いつでも気軽に聞いてくださいね😊

（後）:

> いちばん大事なのは、毎日の短い時間を積み重ねることです。
>
> まず、朝の30分を確保しましょう。出勤前は、一日の中でも集中力が高い時間帯です。毎朝6時半から7時までの30分を、勉強時間として固定してみてください。
>
> （中略）
>
> 応援しています。ほかにも気になることがあれば、いつでも聞いてくださいね😊

「6時半から7時」「30分」「1日20問」「来年3月」「StudyPocket」はすべて残り、主張（短い時間の積み重ねがいちばん大事）も変わっていません。削られたのは、おもねり・前置き・根拠のない励ましです。最後の「いつでも聞いてください」は呼びかけの文なので残しています。

## 強制モードの仕組み

`transform_llm_output` hook を使います。Duckwork がこの hook を呼ぶのは、ツールの呼び出しが終わって最終の返答ができた後、利用者に届けて会話記録に保存する前です。差し替えた文が会話記録にも残ります。

1. 返答が日本語で `min_chars` 以上なら検査します。
2. `enforce` で、点数が基準以上か文体の基準に合わないときだけ、`ctx.llm`（利用者が設定したモデル）に書き直しを頼みます。指摘の位置と直し方を渡し、「意味を変えない・足さない・数字や名前やコードはそのまま・依頼や約束の文は消さない」を指示します。
3. 返ってきた文を検査し直し、次の関門を全部通ったときだけ差し替えます。
   - コードブロック・インラインコード・URL・@ と # が元のまま
   - 指摘箇所の外の数字が全部残り、新しい数字が増えていない
   - 宛名（〜様・〜さん）、名乗り（〜の中川です）、会社名（株式会社〜。前後の文字まで一致）、「」で囲んだ短い名前、英字の語（製品名など）が残っている
   - 曜日（（水）など）と午前・午後が変わっていない
   - 句点のない行（件名・宛名・部署・署名・見出し）で指摘のないものが一字も変わっていない
   - 否定の向きが変わっていない（指摘の外で否定されていた語は否定のまま、新しく否定される語がない）
   - 長さが極端に変わっておらず、点数が下がり、文体の基準も悪化していない
   - 点数が基準を下回っている（`accept_partial: true` なら、下がっていれば可）
4. 通らなければ理由を添えてもう1回だけ頼み、それでも駄目なら元の返答を届けます。モデルの呼び出しが失敗・時間切れでも元の返答を届けます。

承認の仕組みには触れません（ツールを呼ばず、人の入力も待ちません）。cron やゲートウェイの無人実行でも止まりません。

### 知っておいてほしい制約

- **返答が遅れます**: `enforce` では、基準を超えた返答は書き直しにかかった時間（モデル次第で数秒〜最大25秒）だけ遅れて届きます。Duckwork は hook を `plugins.hook_callback_timeout`（既定30秒）で打ち切るため、書き直し全体を `time_budget`（既定25秒。ホストの設定より3秒短く自動で縮める）に収め、持ち時間を過ぎた結果は使いません（`abandoned` と記録）。本物のプロバイダでの所要時間は、この版ではまだ測っていません。
- **ストリーミング**: CLI で表示のストリーミング（`display.streaming: true`、CLI の既定）を使うと、元の返答が先に流れ、書き直し後の文はその後に「post-stream transformation」として表示されます。届く前に差し替えたい場合は `duckwork config set display.streaming false` にしてください。ゲートウェイ（Telegram など）のストリーミングでは、流した発言を書き直し後の文で上書きします。
- **同じ hook を使う他のプラグインとの共存**: Duckwork は `transform_llm_output` で最初に返された文字列だけを使います。たとえば jp-charts は、モデルが添付し忘れたグラフの `MEDIA:` 行を返答に足しますが、こちらが書き換えるとその追加が捨てられます。そこで、(1) 既定の report では返答を書き換えません。(2) enforce でも、返答にすでにある `MEDIA:` 行は書き直しから外して末尾にそのまま戻します。(3) enforce でも、その回にツールが `MEDIA:` 行を返していたら書き換えません（観察だけの `post_tool_call` hook で記録）。添付を落とすより、言い回しの直しを見送るほうを選びます。CJK の文字を消す `cjk_sanitizer` は漢字も消すため、日本語の返答では併用しないでください。
- **関門の範囲**: 関門が守るのは上に挙げたものだけです。「堅牢」のような主張の言葉を宣伝語として削ることはあり、意味の細部まで機械で保証するものではありません。大事な文書は、差し替えの前後を `/ja-check` で確かめてください。

## 精度

誤検知は、人が書いた文のうち「書き直しの対象」と判定された割合です。

人の文と AI の文を同じ数ずつ用意し、場面ごとの既定の基準で「書き直しの対象」と判定された割合を測りました。規則と基準は別の120本（dev・tune）で決め、test の120本は規則を変えずに測りました（作成の経緯は [eval/README.md](eval/README.md)）。

- 人の文40本: 官公庁・自治体のお知らせや Q&A、青空文庫の随筆、日本語で書かれた OSS の文書、国会会議録の発言（2023年以前のものを優先。出典とライセンスは [eval/data/README.md](eval/data/README.md)）。
- A. AI っぽい文40本: LLM に「生成AIが書きがちな典型的な書き方」で書かせたもの。癖が何か所も出る「強め」20本と、1〜2か所だけの「弱め」20本。書き手は検出の規則を見ていません。
- B. 既定の AI 出力40本: LLM がふだんどおりに書いたもの。

### 結果（A: AI っぽい文 対 人の文）

| | 書き直しの対象 | 対象外 |
|---|---|---|
| AI っぽい文40本 | 24（強め20/20、弱め4/20） | 16 |
| 人の文40本 | 3 | 37 |

検出率（典型的な癖を入れた文のうち、書き直しの対象になった割合）60%、誤検知7.5%。文体の基準（です・ます必須など）も含めた判定では、検出率62.5%・誤検知10%（官公庁の「である調」の文1本が業務メールの基準に合わない）。

**目標にしていた「検出率80%以上・誤検知10%以下」には届いていません**（誤検知は満たし、検出率が60%）。癖が何か所も出る文は全部拾えます。1か所だけの弱い癖（「心よりお詫び申し上げます」のような、人も普通に使う丁寧表現が1つ浮いている程度）は20本中4本しか拾えません。人の業務文でも使う言い回し1つで書き直しの対象にすると、人の文の誤検知が増えるためです。

人の文の誤検知3本の中身: 青空文庫の随筆の「――」（文学では普通の記号）、消費者庁のメールの半角「!」と「〜することが可能です」、技術ガイドラインの「特に重要なのは」「〜することができます」「〜という点で」。

測定の経緯: この test を規則を固めて初めて測ったときは、検出率60%・誤検知7.5%でした（これが未見のデータでの数字です）。その後、第三者のレビュー5回で見つかった点（規則の不具合3件、「させていただきます」の重ねと SNS のお願いを点数から外す、広報文の決まり文句の規則を足し、決意の定型句は別々の文に2回以上で数える）を直して測り直したのが上の数字で、初回と同じになりました。ただし、もう未見のデータとは言えません。test の中身を見て規則を足したことはありません。また、この test の前に一度、別の40本を test として使い、検出率50%・誤検知18%で不合格だったため、それを分析して規則を直し（そのデータは tune に回した）、新しく作った40本を今の test にしています。

### 他の製品の規則と、同じデータで比べる

各製品の規則（正規表現で抜き出せたものはそれを、yomiyasu と natural-japanese は同梱の検査スクリプトそのもの）を同じ80本に掛けました。

| 製品の規則 | 製品自身の判定基準での検出率／誤検知 | dev で決めた閾値での検出率／誤検知 | AUC | 誤検知10%以下での検出率（参考） |
|---|---|---|---|---|
| ja-writing-guard | 60% / 8% | 62% / 15% | 0.77 | 60% |
| yomiyasu | 70% / 25% | 48% / 2% | 0.79 | 50% |
| natural-japanese | 0% / 0% | 20% / 8% | 0.70 | 20% |
| textlint-rule-preset-ai-writing | 32% / 10% | 22% / 5% | 0.62 | 32% |
| humanizer-ja（gonta223） | 50% / 25% | 50% / 18% | 0.66 | 28% |
| Humanizer JP（matsutouya） | 48% / 28% | 38% / 28% | 0.60 | 22% |
| patina | 57% / 57% | 5% / 5% | 0.50 | 8% |
| 参考: ja-technical-writing（AI 的な言い回し用ではない） | 100% / 100% | 5% / 5% | 0.57 | 15% |
| 参考: japanese-humanizer（geonwoo。同上） | 100% / 100% | 5% / 5% | 0.59 | 15% |
| 参考: JTF-style（表記規則。同上） | 15% / 18% | 15% / 18% | 0.49 | 10% |

- 製品自身の判定基準: このプラグインは場面の基準。yomiyasu は指摘が1件でもあれば、natural-japanese は diagnose.md の機械スコアが70未満で「AI っぽい」。規則を抜き出した製品には判定の基準がないため、こちらで「1か所でも一致すれば」としました。参考の3製品は文章の校正用で、この基準で並べると100%/100%のように意味のない値になります。
- dev で決めた閾値: dev と tune の120本で人の文の誤検知が10%以下になる閾値を選び、そのまま test に当てた値。このプラグインはこの方法だと誤検知が15%になります。
- AUC: AI っぽい文と人の文を点数で並べたとき、正しく上下が付く割合（0.5が当てずっぽう、1.0が完全）。
- 誤検知10%以下での検出率: **test の上で閾値を選んだ値**で、どの製品にとっても上限の目安です（参考）。
- natural-japanese は長い文書向けの統計の検査が主で、数百字の業務文ではほとんど発火しません（想定している文書の長さの違いです）。

このプラグインは、製品自身の基準で誤検知10%以下を保ったまま、最も多く拾えました。並べ方の正しさ（AUC）は yomiyasu（0.79）とほぼ同じで、上回ってはいません。

### 参考: B. 既定の AI 出力

いまのモデルがふだんどおりに書いた業務メールやお知らせは、人の文の誤検知を10%以下に抑えると、どの製品の規則でも2割ほどまでしか拾えませんでした（yomiyasu は製品自身の基準なら45%を拾いますが、人の文の誤検知も25%です）。このプラグインは40本中1本（2.5%）で、AUC は0.39と、むしろ人の官公庁文のほうが高い点数になります。癖のない文は書き直す必要がない、という設計です。書いたのが人かモデルかを見分ける用途には使えません。

### 限界

- 規則づくりの AI 文も test の AI 文も、同じ生成元（Claude）に同じ種類の指示で書かせたものです。規則がこの書き手の癖に合っている分、他社のモデルの文では結果が下がる可能性があります。
- 人の文はライセンス上公開できるものに限ったため、官公庁の文が多く、民間の業務メールや個人の SNS 投稿は入っていません。民間の業務メールでの誤検知は測れていません。
- 規則の多くは語や型の一致です。言い回しを少し変えた癖は拾えません。
- SNS の「〜は何ですか？よかったらコメントで教えてください」の締めは、人も書く型です。この型1つで基準を超えるため、個人の SNS 投稿では誤検知があり得ます（個人の SNS 投稿での誤検知は測っていません）。

## 先発との差

日本語の AI 的な言い回しを直す道具では、[yomiyasu](https://github.com/nanaism/yomiyasu) と [natural-japanese](https://github.com/coji/natural-japanese) がよく使われています。どちらも Agent Skill（モデルへの指示）で、規則に基づく Python の検査も同梱しています。このプラグインは両者の構造（規則を表で持つ、直し方の指示と例文を持つ、検出は機械・判断は書き手）を写し、Duckwork の中で自動で動く形にしました。

| | yomiyasu | natural-japanese | ja-writing-guard |
|---|---|---|---|
| 形 | Agent Skill＋検査スクリプト | Agent Skill＋検査スクリプト | Duckwork プラグイン（ツール＋hook＋スキル） |
| 検査が走るとき | モデルがスキルに従ってスクリプトを呼んだとき | 同左 | すべての日本語の返答で自動（hook）。ツールとしても呼べる |
| 返答を届く前に直す | なし（モデル任せ） | なし（モデル任せ） | `mode: enforce`。数字・名前・URL・コード・否定を守る関門つき。失敗時と時間切れは元の返答 |
| 既定の動き | ― | ― | 検査と記録だけ（返答を変えない） |
| 場面ごとの基準 | 分野（tech/business/essay）を指示文で切り替え | ジャンル（essay/tech/business）で閾値を切り替え | 行き先（メール/社外文/SNS/技術文書/チャット）で重み・基準・敬体必須を切り替え。配信先ごとの自動切り替え |
| 文体の基準（敬体必須など） | 指示文で判断 | なし | AI 的な言い回しとは別に機械で判定・報告 |
| 位置の報告 | 行番号 | 行番号 | 文字位置・行・桁・抜粋・直し方 |
| 依存 | 標準ライブラリ | sudachipy と辞書 | 標準ライブラリのみ |
| 規則の数 | 約60（語33・型18・書式と文末の検査） | 約60語＋統計の検査 | 92件＋構造の検査7件。全規則に当たるべき例文とテスト（MIT の9製品から取り込み、[比較表](docs/comparison.md)） |
| 誤検知の数字 | 自前のコーパスで計測 | 人103本・AI 81本で校正 | 人の文40本（未見）で計測。同じデータで他製品の規則とも比較（上の「精度」） |

## 開示

- ネットワークへは自分からは接続しません。環境変数も読みません。
- `enforce` のときだけ、基準を超えた返答1件につき1回（1回目が関門を通らないか基準を超えたままのときだけ2回目。`max_attempts` で1〜3回）、`ctx.llm` で利用者が設定したモデル（プロバイダ）にその返答の本文を送ります。プロバイダの利用料がかかり、その返答は書き直しの時間だけ遅れて届きます。
- 直前の返答の検査結果（点数と、指摘の短い抜粋）は、CLI・TUI・Desktop のときだけ、そのプロセスのメモリに持ちます（`/ja-check` で表示するため）。ディスクには書きません。ゲートウェイのプロセスは何も持たないので、共有のチャットで `/ja-check` を打っても誰の返答も見えません。Duckwork のログには、場面・点数・指摘の件数・モードを1行書きます（書き直したときは結果と秒数も1行）。返答の本文は書きません。
- `enforce` は、`transform_llm_output` を推論なしの変換に使うという Duckwork の想定から外れ、`ctx.llm` で推論を1〜2回使います。既定では無効で、利用者が明示的に選んだときだけ動きます。
- Duckwork の設定のうち `plugins.hook_callback_timeout` の1項目だけを読みます（読むだけ。持ち時間をそれより短くするため）。読むのに使う `duckwork_cli.config.load_config_readonly` は公開のプラグイン API ではないので、将来の版で読めなくなった場合は `time_budget` の値をそのまま使います。
- `post_tool_call` hook はツールの結果に `MEDIA:` が含まれるかだけを見て、その回の印（セッションと回の ID）をメモリに15分だけ持ちます。結果の中身は保存しません。
- 自己更新はしません。シェルコマンドは実行しません。

## 開発

```bash
pytest -q                                   # 単体テスト（オフライン）
duckwork plugins validate . --install-deps    # カタログの CI と同じ検証
python eval/run_eval.py                     # 精度の再計測（eval/README.md）
```

Python 3.11以上（Duckwork の要件）。実行時の依存はありません。

## 帰属とライセンス

MIT（[LICENSE](LICENSE)）。規則と書き直しの原則は、yomiyasu・natural-japanese ほか MIT の9製品から取り込みました。帰属は [NOTICE](NOTICE)、評価データの出典とライセンスは [eval/data/README.md](eval/data/README.md) にあります。

## English

**ja-writing-guard** is rule-based proofreading for Japanese business text in Duckwork Agent. It finds and fixes the AI-style phrasing that often shows up in Japanese emails, notices and docs: stock phrases, monotonous sentence endings, overused symbols and Markdown (em dashes, `**bold**` in emails), and English-calque grammar. It checks wording, not authorship: it does not tell whether a person or a model wrote a text, and it flags human text that has the same habits.

Limits, up front:

- It rarely flags today's models when they write plainly (1 of 40 unseen texts).
- The human texts used to measure false positives are mostly Japanese government pages (texts that can be republished); private business email and personal social posts were not measured.
- Every AI-side evaluation text was written by one model family (Anthropic's Claude); results on other vendors' models may be lower.

Accuracy on the unseen test split: 60% of 40 texts written with typical AI-style habits caught, at 7.5% false positives on 40 human texts; the 80% target was not reached. With the cut-off set for at most 10% false positives on the same data (chosen on the test split, a reference value), yomiyasu catches 50%, natural-japanese 20% and this plugin 60%; ranking quality (AUC) is about the same (yomiyasu 0.79, this plugin 0.77). Details are in the Japanese section above.

- `ja_writing_check` tool: deterministic, offline checker (92 rules + 7 structural checks, standard library only; about 1 ms for a few hundred characters and about 15 ms for 10,000, median on a Mac). Returns a 0-100 score, the surface threshold, and each finding with character offsets, line, column, excerpt and a fix hint.
- `transform_llm_output` hook: checks every final Japanese answer. Default `mode: report` only logs (and, on CLI/TUI/Desktop, keeps the latest report in memory); the answer is never changed. Opt-in `mode: enforce` rewrites an answer over the threshold (or one that breaks the surface's register policy, e.g. です・ます required in emails) with the user's own model via `ctx.llm`. The rewrite is delivered only if code, URLs, handles, numbers outside the flagged spans, addressee/company/quoted names, ASCII names, weekdays, 午前/午後 and unflagged signature/heading lines survive, negation keeps its direction, the length stays sane, and the score drops under the threshold (or merely goes down, with `accept_partial: true`); otherwise the original is delivered. These checks do not prove that the meaning is unchanged. For business email, use enforce on CLI/TUI/Desktop and run `/ja-check` to see the changed lines before sending; on gateways (Telegram, email and others) the changed lines cannot be viewed afterwards.
- `post_tool_call` hook (read-only): notes turns in which a tool returned a `MEDIA:` line; enforce mode leaves those answers alone so attachments added by other plugins (e.g. jp-charts) or the gateway are never dropped. `MEDIA:` lines already in an answer are kept verbatim.
- Surfaces: `chat`, `business_email`, `external`, `sns`, `tech_doc` change rule weights, thresholds and register checks; `platform_surfaces` maps delivery platforms to surfaces.
- `/ja-check` slash command and a bundled `rewrite-ja` skill.

Requires Duckwork v0.21.4 or later. Install: `duckwork plugins install TakeshiTGAL/duckwork-plugin-ja-writing-guard --enable` (once listed in the catalog, `duckwork plugins install ja-writing-guard --enable`; to try a local clone, `duckwork plugins install "file://$PWD" --enable` inside it), then optionally `duckwork config set plugins.entries.ja-writing-guard.settings.mode enforce`.

Caveats: in enforce mode, flagged answers arrive later by the rewrite time (up to the 25 s budget, kept under Duckwork' 30 s hook timeout); with CLI token streaming on, the original streams first and the rewrite prints after it (set `display.streaming: false` to replace before display); `transform_llm_output` is first-string-wins across plugins (handled as above for attachments; do not combine with cjk_sanitizer, which strips kanji). Disclosure: no network calls of its own; reads one Duckwork setting (`plugins.hook_callback_timeout`, read-only, via a non-public helper with a fallback); enforce mode sends flagged answers to the user's configured provider (one call per flagged answer; a second one only when the first rewrite fails the checks or is still over the threshold; `max_attempts` allows 1 to 3); on local surfaces only, the latest report is kept in process memory (nothing on disk besides one log line with the score).

Structure follows nanaism/yomiyasu and coji/natural-japanese (MIT); rules also come from textlint-ja presets, devswha/patina and others (MIT). See NOTICE and [docs/comparison.md](docs/comparison.md).
