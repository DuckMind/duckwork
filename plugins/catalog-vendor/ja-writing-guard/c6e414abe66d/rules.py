"""Rule catalog for Japanese AI-writing tells.

Each rule is data, not code: a regular expression, a weight, a category, a
short label, a fix hint and the place the idea came from. The detector in
``detector.py`` runs them; ``surfaces.py`` scales the weights per surface.

Provenance keys (see NOTICE for the full attributions):

- ``yomiyasu``        nanaism/yomiyasu (MIT) — scripts/yomiyasu_lint.py, SKILL.md
- ``natural-japanese`` coji/natural-japanese (MIT) — scripts/lint.py,
                       references/forbidden-patterns.md, references/translationese.md
- ``textlint-ai``     textlint-ja/textlint-rule-preset-ai-writing (MIT)
- ``ja-technical``    textlint-ja/textlint-rule-preset-ja-technical-writing and its
                       bundled rules (MIT)
- ``jtf``             textlint-ja/textlint-rule-preset-JTF-style (MIT)
- ``patina``          devswha/patina (MIT) — Japanese lexicon and pattern packs
- ``geonwoo``         geonwoo-jeong/japanese-humanizer (MIT) — deterministic profiler
- ``gonta223``        gonta223/humanizer-ja (MIT)
- ``matsutouya``      matsutouya/humanizer-ja "Humanizer JP" (MIT)
- ``original``        written for this plugin

Patterns taken from these projects were rewritten as Python regular
expressions; the ``source`` field names the project each idea came from.

Weights and thresholds were set on ``eval/data/dev`` and ``eval/data/tune``; the
numbers reported in the README come from the separate ``eval/data/test`` split.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Categories, in the order the report lists them.
CATEGORIES = {
    "stock": "定型句・常套句",
    "inflated": "誇張・空虚な言葉",
    "translationese": "英語の直訳調",
    "template": "型どおりの構成",
    "format": "記号・書式",
    "rhythm": "文末の単調さ",
    "contrast": "対比の繰り返し",
    "sycophancy": "おもねり・決まり文句の応対",
    "register": "場面に合わない文体",
}


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    pattern: str
    weight: float
    label: str
    hint: str
    source: str = "original"
    # Count at most this many hits toward the score (all hits are still reported).
    max_count: int = 3
    # Regex flags (re.M is common for line-anchored rules).
    flags: int = 0
    # Skip hits inside 「」『』 quotes (dialogue, or a phrase being talked about).
    skip_in_quotes: bool = True
    # Only count when the text has at least this many hits of the rule.
    min_hits: int = 1
    # Match against the raw text (URLs and code not masked), for leaked tool markup.
    on_raw: bool = False
    # False: reported as a hint but never added to the score (common in human writing too).
    scored: bool = True
    # True: several hits in one sentence count once (min_hits then means "in that many sentences").
    per_sentence: bool = False
    compiled: re.Pattern = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        object.__setattr__(self, "compiled", re.compile(self.pattern, self.flags))


R = Rule  # short alias for the table below

RULES: list[Rule] = [
    # ------------------------------------------------------------------ stock
    R("stock.ieru_deshou", "stock", r"と(?:言|い)える(?:でしょう|だろう)", 3.0,
      "「〜と言えるでしょう」の結び",
      "推量の結びを外し、言い切るか、言い切れない理由を具体的に書く。",
      "natural-japanese"),
    R("stock.ieru", "stock", r"と(?:言|い)えます(?:[。ね]|$)", 1.5,
      "「〜と言えます」の結び",
      "「〜です」で言い切る。根拠があるなら根拠を先に書く。",
      "natural-japanese"),
    R("stock.nodewa", "stock", r"のではないでしょうか[。？?]", 1.5,
      "「〜のではないでしょうか」の問いかけ",
      "意見なら「〜と思います」、事実なら言い切る。",
      "natural-japanese", max_count=2),
    R("stock.ikaga", "stock", r"いかがでした(?:でしょう)?か", 4.0,
      "「いかがでしたか」の締め",
      "締めの問いかけを削り、本文の最後の事実や次の行動で終える。",
      "yomiyasu"),
    R("stock.zehi_close", "stock", r"ぜひ(?:一度)?(?:参考|試し|活用|お試し|ご活用|ご参考|チェック)(?:に)?(?:して|ください|になさって)|ぜひ(?:一度)?(?:[^。！!\n]{1,12})?試してみてください", 2.0,
      "「ぜひ〜してみてください」の締め",
      "勧める理由を1つ具体的に書くか、締めごと削る。",
      "yomiyasu", max_count=1),
    R("stock.matomeru_to", "stock", r"(?:^|[。\n])\s*(?:まとめると|総じて|要するに|結論として)、", 2.0,
      "「まとめると、」「総じて、」の前置き",
      "前置きを削り、まとめの中身から書く。",
      "natural-japanese", flags=re.M),
    R("stock.ketsuron", "stock", r"結論から(?:言うと|申し上げますと|いうと)", 2.0,
      "「結論から言うと」の前置き",
      "前置きを削り、結論そのものを1文目に置く。",
      "yomiyasu"),
    R("stock.juyou_nowa", "stock", r"(?:最も|もっとも|特に)?(?:重要|大切|大事)なのは", 1.5,
      "「重要なのは」の前置き",
      "評価を述語へ移す（「〜が大事です」）。前置きだけなら削る。",
      "natural-japanese"),
    R("stock.juuyou_desu", "stock", r"(?:する|しておく|おく)?ことが(?:非常に|とても|極めて)?(?:重要|大切|肝要|不可欠|鍵)(?:です|となります|になります|だ|である)", 1.5,
      "「〜することが重要です」の連発",
      "何がどう困るのかを書けば「重要」は要らない。1文書に1回までにする。",
      "natural-japanese", max_count=3, min_hits=2),
    R("stock.mitekimashou", "stock", r"(?:見て|解説して|紹介して|深掘りして|掘り下げて|整理して)いきましょう|(?:解説|紹介|深掘り)していきます", 2.0,
      "「〜していきましょう」の予告",
      "予告を削り、中身から始める。",
      "natural-japanese", max_count=2),
    R("stock.ni_tsuite_kaisetsu", "stock", r"(?:について|を)(?:詳しく)?(?:解説|ご紹介|紹介|ご説明|説明)(?:します|いたします|していきます)", 1.5,
      "「〜について解説します」の予告",
      "予告の文を削り、説明の1文目から書く。",
      "textlint-ai", max_count=1),
    R("stock.ichigai", "stock", r"一概には言え(?:ません|ない)|個人差がありますが|あくまで一例(?:です|ですが)", 1.0,
      "予防線の言い回し",
      "言い切れない条件を具体的に書くか削る。",
      "natural-japanese", max_count=2),
    R("stock.kagi", "stock", r"(?:が|は)(?:成功の)?鍵(?:となります|になります|を握ります|です)", 2.0,
      "「〜が鍵となります」",
      "何がどう効くのかを具体的に書く。",
      "original", max_count=2),
    R("stock.iu_made", "stock", r"言うまでも(?:なく|ありません)|改めて言うまでもなく", 1.0,
      "「言うまでもなく」",
      "言うまでもないなら削る。",
      "natural-japanese", max_count=1),
    R("stock.chuumoku", "stock", r"(?:ここで|特に)?注目(?:すべき|したい)(?:点|の)?は", 1.5,
      "「注目すべきは」の予告",
      "注目の重みを述語に残し、中身の文と1文にまとめる。",
      "yomiyasu", max_count=2),
    R("stock.ageraremasu", "stock", r"(?:が|として(?:は)?)挙げられ(?:ます|る)", 1.0,
      "「〜が挙げられます」",
      "「〜があります」「主な理由は〜です」と主語を立てて言う。",
      "textlint-ai", max_count=2, min_hits=2),

    # --------------------------------------------------------------- inflated
    R("inflated.buzz", "inflated",
      r"シームレス(?:に|な)|包括的(?:な|に)|多角的(?:な|に)|革新的(?:な|に)|画期的(?:な|に)|新たな価値|価値を(?:創出|提供)|可能性を(?:広げ|秘め)|架け橋|第一歩を|一歩先|次のステージ|未来を(?:切り拓|創|拓)|飛躍的(?:に|な)|圧倒的(?:な|に)|最大化(?:し|する|します)|シンプルかつ(?:堅牢|強力|柔軟)|幅広い(?:ユースケース|用途|ニーズ|シーン)に対応|強力に(?:後押し|サポート)|さらなる成長を加速",
      1.5, "宣伝調の大げさな言葉",
      "何がどれだけ変わるのかを数字や具体物で書く。",
      "natural-japanese", max_count=4),
    R("inflated.slop_nouns", "inflated",
      r"解像度を上げ|腹落ち|手触り感|温度感|熱量を|羅針盤|起爆剤|触媒となり|真髄|極致|深淵",
      1.5, "比喩の流行語",
      "ふだん使う言葉に置き換える。",
      "yomiyasu", max_count=3),
    R("inflated.yakuwari", "inflated", r"(?:重要な|大きな|中心的な|不可欠な|欠かせない)役割を(?:果たし|担っ|担い|果たす|担う)", 2.0,
      "「重要な役割を果たします」",
      "何をするのかを動詞で書く（「〜を受け付けます」）。",
      "original", max_count=2),
    R("inflated.samazama", "inflated", r"(?:様々|さまざま|多様|幅広い)な", 0.7,
      "「様々な」「多様な」の多用",
      "何が含まれるのかを2〜3個挙げる。",
      "natural-japanese", max_count=3, min_hits=3),
    R("inflated.hijou_ni", "inflated", r"(?:非常に|極めて|とても)(?:重要|大切|有効|効果的|便利|強力|魅力的)", 1.0,
      "強調語の重ね",
      "強調語を外して根拠で示す。",
      "natural-japanese", max_count=3, min_hits=2),
    R("inflated.kotoba_dake", "inflated", r"(?:言語化|深掘り|掘り下げ)(?:する|し|して|します)|正面から(?:扱|向き合)", 1.0,
      "作業したことだけを宣言する動詞",
      "何をどう書いたかを書く。",
      "natural-japanese", max_count=2),
    R("inflated.kakasenai", "inflated", r"欠かせない存在|なくてはならない存在|必要不可欠(?:な|です|となって)", 1.0,
      "「欠かせない存在」",
      "なぜ要るのかを具体的に書く。",
      "original", max_count=2),

    # ---------------------------------------------------------- translationese
    R("translationese.dekiru", "translationese", r"することが(?:でき(?:る|ます|た|ません)|可能(?:です|だ|となります|になります|になる|となる|となっています|になっています))", 1.0,
      "「〜することができます」",
      "可能形にする（「使えます」「確認できます」）。",
      "natural-japanese", max_count=3),
    R("translationese.dekiru_verb", "translationese", r"(?:(?<!す)る|[うくすつぬぶむぐ])ことが(?:でき(?:る|ます|た)|可能(?:です|だ|となります|になります))", 0.8,
      "「〜ことができます」（する以外の動詞）",
      "可能形にする（「使うことができます」→「使えます」）。",
      "ja-technical", max_count=3, min_hits=2),
    R("translationese.kanten", "translationese", r"という(?:観点|視点)(?:から|で)|という点(?:で|において)", 1.0,
      "「〜という観点から」",
      "「〜で見ると」「〜については」と短く言う。",
      "natural-japanese", max_count=2),
    R("translationese.ni_totte", "translationese", r"にとって(?:非常に)?(?:重要|不可欠|大切|欠かせない)", 1.0,
      "「〜にとって重要」",
      "「〜には〜が要る」と必要なものを書く。",
      "natural-japanese", max_count=2),
    R("translationese.motsu", "translationese", r"(?:意味|意義|価値|影響|可能性|特徴|強み)を持(?:つ|ち|っています|ちます)", 1.0,
      "「〜を持つ」（have の直訳）",
      "「〜がある」に直す。",
      "natural-japanese", max_count=2),
    R("translationese.niyotte", "translationese", r"することによって|することにより", 0.7,
      "「〜することによって」",
      "「〜して」「〜すれば」にする。",
      "natural-japanese", max_count=2),
    R("translationese.hokanaranai", "translationese", r"に他な(?:らない|りません)|であることは間違いな(?:い|いでしょう)|と言っても過言では(?:ない|ありません)", 2.0,
      "強い断定の決め文",
      "根拠を先に書き、決め文を外す。",
      "natural-japanese", max_count=2),
    R("translationese.mushoku_shugo", "translationese", r"(?:この|その)(?:結果|事実|データ|アプローチ|仕組み|機能)(?:は|が)[^。\n]{0,20}(?:を)?(?:示して|示唆して|物語って|可能にし|実現し)", 1.0,
      "無生物主語の他動詞",
      "人や状況を主語にする（「この結果から〜と分かります」）。",
      "natural-japanese", max_count=2),
    R("translationese.okonau", "translationese", r"を行(?:う|います|いました|って|い)(?:こと)?", 0.4,
      "「〜を行う」（do の直訳）",
      "「確認を行う」→「確認する」のように動詞にする。",
      "ja-technical", max_count=3, min_hits=3),

    # ---------------------------------------------------------------- template
    R("template.count_decl", "template", r"(?:[2-7２-７二三四五六七]つ|いくつか)の(?:重要な|主な|大切な)?(?:ポイント|理由|ステップ|方法|コツ|観点|要素|メリット|特徴|視点|柱|原則|軸)", 2.0,
      "「3つのポイント」型の数の宣言",
      "数を先に宣言せず、中身から書く。",
      "natural-japanese", max_count=1),
    R("template.ikutsuka", "template", r"いくつか(?:の)?(?:重要な|大切な|主な)?(?:コツ|ポイント|方法|理由|注意点|ステップ|選択肢|アプローチ)(?:が|を|に)", 1.5,
      "「いくつかのポイントがあります」の前置き",
      "前置きを削り、1つ目の中身から書く。",
      "original", max_count=1),
    R("template.ika_matome", "template", r"以下(?:に|の(?:とおり|通り|ように))[^。\n]{0,15}(?:まとめ|整理|紹介|解説|示し|挙げ)", 1.5,
      "「以下にまとめました」",
      "前置きを削り、そのまま本題に入る。",
      "original", max_count=1),
    R("template.rhetorical_q", "template", r"(?:なぜ|どうして)(?:でしょうか|なのでしょうか)[？?]\s*(?:それは|答えは|理由は)", 2.5,
      "自問自答の型",
      "問いを外して理由から書く。",
      "original", max_count=2),
    R("template.sorekoso", "template", r"これこそが|それこそが|これが[^。\n]{0,12}の(?:本質|真髄|核心)です", 1.5,
      "決め台詞の結び",
      "事実を淡々と書く。",
      "natural-japanese", max_count=1),
    R("template.closing_offer", "template", r"(?:何か|ほかに|他に)(?:ご不明な点|ご質問|気になる(?:点|こと))(?:や[^。\n]{0,10})?があれば(?:、)?(?:お気軽に|いつでも)", 1.0,
      "「何かあればお気軽に」の締め（チャット）",
      "締めを削るか、相手が次にすることを1つ書く。",
      "original", max_count=1),
    R("template.hope_helpful", "template", r"お役に立て(?:れば|たら)(?:幸いです|嬉しいです|うれしいです)|参考になれば(?:幸いです|嬉しいです)", 1.5,
      "「お役に立てれば幸いです」",
      "締めを削る。",
      "original", max_count=1),
    R("template.mazu_tsugini", "template", r"(?:^|[。\n])\s*まず(?:は)?、[\s\S]{0,600}?(?:^|[。\n])\s*(?:次に|続いて)、[\s\S]{0,600}?(?:^|[。\n])\s*(?:最後に|そして最後に)、", 1.5,
      "「まず・次に・最後に」の機械的な並べ方",
      "順序が要らない並びなら、まとめて1文で言う。",
      "original", max_count=1, flags=re.S),

    # ------------------------------------------------------------------ format
    R("format.em_dash", "format", r"[ぁ-んァ-ヶ一-龠々ー0-9A-Za-z）」』]\s*(?:——|—|―{2}|──)\s*(?:[ぁ-んァ-ヶ一-龠々ー0-9A-Za-z（「『。、]|$)", 2.0,
      "語と語の間のダッシュ（——）",
      "読点か括弧にするか、文を分ける。",
      "yomiyasu", max_count=3, skip_in_quotes=False),
    R("format.bold", "format", r"\*\*[^*\n]{1,40}\*\*", 1.0,
      "太字（**…**）",
      "太字を外す。強調したい文は短く言い切る。",
      "yomiyasu", max_count=4, skip_in_quotes=False, min_hits=2),
    R("format.bold_label", "format", r"^\s*(?:[-*・]|\d+[.)．])\s*\*\*[^*\n]{1,30}\*\*\s*[:：]?", 2.0,
      "「- **見出し語**：説明」の箇条書き",
      "箇条書きをやめて地の文で説明する。",
      "textlint-ai", max_count=3, flags=re.M, skip_in_quotes=False),
    R("format.bold_heading_line", "format", r"^\s*\*\*[^*\n]{2,40}\*\*\s*[:：]?\s*$", 1.5,
      "太字だけの行を見出し代わりにする",
      "短い返答なら段落で書く。文書なら見出しにする。",
      "textlint-ai", max_count=3, flags=re.M, skip_in_quotes=False),
    R("format.colon_lead", "format", r"[ぁ-んァ-ヶ一-龠々ー][：:]\s*$", 1.0,
      "文末のコロン（〜は以下のとおり：）",
      "句点で終えるか前置きを削る。",
      "yomiyasu", max_count=3, flags=re.M, skip_in_quotes=False, min_hits=2),
    R("format.heading_in_chat", "format", r"^#{2,4}\s+\S", 1.0,
      "Markdown の見出し",
      "短い返答なら見出しを使わず段落で書く。",
      "original", max_count=3, flags=re.M, skip_in_quotes=False),
    R("format.emoji_bullet", "format", r"^\s*(?:[-*・]\s*)?[✅✔❌⚠✨⭐\U0001F300-\U0001FAFF]\s*\S", 1.5,
      "絵文字を頭に付けた行",
      "絵文字を外し、普通の文で書く。",
      "yomiyasu", max_count=3, flags=re.M, skip_in_quotes=False),
    R("format.emoji", "format", r"[✅✨⭐\U0001F300-\U0001FAFF]", 0.5,
      "絵文字",
      "業務の文では絵文字を外す。",
      "yomiyasu", max_count=4, skip_in_quotes=False, min_hits=2),
    R("format.arrow_chain", "format", r"(?:→|⇒|➡)[^\n→⇒➡]{1,30}(?:→|⇒|➡)", 0.7,
      "矢印の連鎖",
      "矢印を文章にする（「〜すると〜になる」）。",
      "original", max_count=2, skip_in_quotes=False),
    R("format.exclaim", "format", r"[！!]", 0.4,
      "感嘆符の多用",
      "感嘆符を句点に戻す。",
      "original", max_count=4, skip_in_quotes=True, min_hits=3),
    R("format.paren_gloss", "format", r"[ァ-ヶー一-龠]{2,}[（(][A-Z][A-Za-z]+(?:[ -][A-Za-z]+){1,5}[）)]", 1.0,
      "英語の言い換えを添えたカッコ",
      "読み手に要らない英語の補足は削る。",
      "yomiyasu", max_count=2, skip_in_quotes=False, min_hits=2),

    # ---------------------------------------------------------------- contrast
    R("contrast.dewanaku", "contrast", r"ではなく、?|だけでなく、?[^。\n]{0,20}も|のではなく、?", 0.8,
      "「AではなくB」の繰り返し",
      "誤解を正す場面以外は、素直な肯定文にする。",
      "natural-japanese", max_count=4, min_hits=2),

    # -------------------------------------------------------------- sycophancy
    R("sycophancy.great_q", "sycophancy", r"(?:素晴らしい|すばらしい|いい|良い|鋭い|とても良い|非常に鋭い)(?:質問|ご質問|視点|着眼点|問い|ご指摘)(?:ですね|です)|(?:とても|非常に)?興味深いテーマですね", 4.0,
      "「素晴らしい質問ですね」",
      "前置きを削り、答えから書く。",
      "original", max_count=1),
    R("sycophancy.empathy", "sycophancy", r"(?:そのお気持ち|お気持ち|そう感じるのは)[^。\n]{0,10}(?:よく分かります|よくわかります|当然です|自然なことです)|(?:悩みますよね|迷いますよね|大変ですよね)", 2.0,
      "決まり文句の共感",
      "共感の前置きを削り、相手の状況に合う具体的な一言にする。",
      "original", max_count=1),
    R("sycophancy.kashikomari", "sycophancy", r"^(?:もちろんです|承知しました|かしこまりました)[！!。]", 1.0,
      "返答の頭の決まり文句",
      "決まり文句を削り、答えから書く。",
      "original", max_count=1, flags=re.M),
]

RULES += [
    # ------------------------------------------- from the wider product survey
    R("stock.chatbot_residue", "stock",
      r"ご紹介させていただきます|さらに詳しい情報が必要な場合は|他にご質問があれば|お気軽にお尋ねください",
      1.5, "チャットボットの決まり文句", "締めや前置きの決まり文句を削る。", "patina", max_count=2),
    R("stock.cutoff", "stock",
      r"知識のカットオフ|リアルタイム(?:の)?情報には?アクセスでき|最新の情報と異なる(?:場合|可能性)があります|最新の情報は公式[^。\n]{0,10}ご確認ください",
      3.0, "知識の時点についての断り書き", "断り書きを削り、日付や出典を具体的に書く。", "patina", max_count=1),
    R("stock.false_nuance", "stock", r"より正確には|公平に見れば|もう少し掘り下げると|実はもう少し(?:複雑|微妙)",
      1.0, "見せかけの補足の前置き", "前置きを削り、補足の中身だけを書く。", "patina", max_count=2),
    R("stock.filler", "stock", r"周知の(?:通り|とおり)|疑いなく|(?:指摘|強調)すべきは|注目に値(?:する|します)",
      1.0, "中身のない強調の前置き", "前置きを削る。", "patina", max_count=2),
    R("stock.empty_optimism", "stock",
      r"今後の(?:展開|発展|動向)に(?:注目|期待)|(?:さらなる|今後の)発展が期待され|大きな可能性を秘め|輝かしい未来|無限の可能性|新たな章の幕開け|ますます(?:重要|注目)(?:になって|を集めて|性を増して)|通過点に(?:すぎ|過ぎ)ません|これからも[^。\\n]{0,20}(?:成長し続け|挑戦し続け|進化し続け)",
      1.5, "中身のない明るい見通し", "見通しを書くなら、根拠と時期を書く。なければ削る。", "patina", max_count=2),
    R("stock.throat_clearing", "stock", r"(?:^|[。\n])\s*(?:正直に言うと|正直なところ|はっきり言って|本音を言えば|あえて言うと)、",
      0.8, "「正直に言うと」の前置き", "前置きを削る。", "patina", max_count=1, flags=re.M),
    R("stock.pseudo_insight", "stock", r"誰も教えてくれない|ほとんどの人が(?:間違え|知らない|見落と)|みんなが見落と|誰も言わない(?:真実|こと)",
      2.0, "煽りの前置き（SNS）", "煽りを削り、中身から書く。", "patina", max_count=1),
    R("stock.lexicon", "stock",
      r"現代社会において|デジタル時代において|テクノロジーの進化(?:により|によって)|新たな可能性を切り(?:開|拓)|急速に変化する(?:現代|社会|時代|ビジネス環境)|近年、[^。\n]{0,30}(?:急速に|ますます)|本記事では[^。\n]{0,40}(?:解説|紹介)",
      1.5, "AI の書き出しの決まり文句", "一般論の書き出しを削り、本題の事実から書く。", "patina", max_count=2),
    R("stock.mazu_saisho", "stock", r"まず最初に", 1.0, "「まず最初に」の重複", "「まず」か「最初に」の一方にする。", "textlint-ai", max_count=1),
    R("inflated.hype", "inflated",
      r"革命的な|ゲームチェンジャー|究極の|最先端の|魔法のように|奇跡的な|驚異的な|可能性を解き放|潜在能力を引き出|パラダイムシフト|業界を再定義|未来を変える|新たな基準を(?:打ち立て|設定)|根本的に変革",
      1.5, "誇大な宣伝語", "何がどれだけ変わるのかを事実で書く。", "textlint-ai", max_count=3),
    R("inflated.significance", "inflated",
      r"歴史的な転換点|新たな地平|礎を築|金字塔|の先駆けとなる|極めて重要な意義|時代を画する|新時代を切り(?:開|拓)",
      1.5, "意義を大きく言う言葉", "意義を言わず、起きたことを書く。", "patina", max_count=2),
    R("inflated.teki_chain", "inflated", r"(?:[一-龠]{2}的(?:な|に)?[^。！？\n]{0,25}){3}",
      1.0, "「〜的」の重ね", "「〜的」を外して具体的に言う。", "patina", max_count=2),
    R("translationese.ing_surface", "translationese",
      r"示しながら|強調しつつ|反映しており|象徴するとともに|体現しつつ|物語っており|浮き彫りにし(?:ており|ています|ました)",
      1.0, "付け足しの分詞構文", "文を分け、主語と動詞をはっきりさせる。", "gonta223", max_count=2),
    R("translationese.vague_source", "translationese", r"専門家(?:によると|によれば|は指摘)|一部の(?:見方|専門家)では|調査結果が示すように",
      0.8, "出典のない権威づけ", "誰の何という調査かを書くか削る。", "patina", max_count=2),
    R("translationese.stiff", "translationese", r"と言わざるを得(?:ない|ません)|の感が否め(?:ない|ません)|の一助となれば幸い",
      1.0, "硬すぎる決まり文句", "ふだんの言い方にする。", "patina", max_count=1),
    R("template.colon_reveal", "template", r"(?:結論|オチ|ネタバレ|一番すごいのは|実は|答え)[：:]\s*\S",
      1.5, "「結論：」の種明かし", "ラベルを外して文で言う。", "patina", max_count=2),
    R("format.info_prefix_bold", "format",
      r"\*\*(?:注意|重要|ポイント|メモ|参考|補足|確認|チェック|推奨|おすすめ|良い例|悪い例|結論|まとめ)(?:[：:][^*\n]*)?\*\*",
      1.5, "「**ポイント**」型の太字ラベル", "ラベルを外し、文で言う。", "textlint-ai", max_count=3, skip_in_quotes=False),
    R("format.ai_leakage", "format",
      r":contentReference|oaicite|oai_citation|\bturn\d+(?:search|view|news|fetch)\d*\b|\ufffc|utm_source=(?:chatgpt\.com|openai\.com|perplexity\.ai|claude\.ai|gemini\.google\.com)",
      5.0, "AI ツールの出力の痕跡", "痕跡（引用タグ・utm_source など）を消す。", "patina", max_count=1, skip_in_quotes=False,
      on_raw=True),
    R("format.halfwidth_mark", "format", r"[ぁ-んァ-ヶ一-龠][!?](?=[\sぁ-んァ-ヶ一-龠]|$)",
      0.5, "和文中の半角の！？", "全角にするか句点にする。", "jtf", max_count=3, flags=re.M, min_hits=2),
    R("contrast.nominarazu", "contrast", r"にとどまらず|単なる[^。\n]{1,15}(?:ではなく|ではありません|ではない)|を超えた何か",
      1.0, "「〜にとどまらず」の対比", "対比をやめ、言いたい方だけを書く。", "patina", max_count=2),
    R("stock.stacked_closing", "stock",
      r"よろしくお願い(?:いた)?します|よろしくお願い申し上げます|何卒よろしく|お気軽に(?:お問い合わせ|ご連絡|ご相談|お申し付け)|ご確認のほど[^。\n]{0,10}お願い",
      2.0, "締めのあいさつの重ね", "締めのあいさつは1つにする。", "original", max_count=1, min_hits=3),
    R("template.sns_question", "template",
      r"[^。？?\n]{0,40}(?:何ですか|どうですか|ありますか|どちらですか|何だと思いますか)[？?]\s*(?:よければ|よかったら|ぜひ)?[、,]?\s*コメント(?:で|欄で)?(?:教えて|聞かせて)",
      1.5, "問いかけ＋コメントのお願いの締め", "締めの型を外し、本当に聞きたいことを1つだけ具体的に聞く。問いかけだけなら残してよい。",
      "patina", max_count=1),
    R("template.sns_cta", "template", r"(?:ぜひ)?コメント(?:で|欄で)?(?:教えて|聞かせて)",
      1.5, "SNS で反応を求めるお願い", "お願いは依頼の文なので残してよい。書き直しでも消さない。", "patina", max_count=1,
      scored=False),
    R("inflated.marketing_cliche", "inflated",
      r"織りなす|至福のひととき|五感で(?:楽しむ|味わ|感じ)|こだわり抜い|ワンランク上の|シナジー|強みを掛け合わせ|唯一無二の|極上の",
      1.5, "宣伝文の決まり文句", "何がどう良いのかを、素材・数字・手順で書く。", "original", max_count=2),
    R("inflated.pr_cliche", "inflated",
      r"未来を(?:共に|ともに)?(?:創|つく|切り拓|切り開|拓)|ワンストップで(?:完結|提供|解決)|新しい価値(?:を|の)(?:創|つく|提供|生み)",
      1.5, "広報文の決まり文句", "理念の言い回しを削り、具体的に何をするのかを書く。", "original", max_count=2),
    R("inflated.pr_formula", "inflated",
      r"(?:お客様|皆様|地域)に寄り添|さらなる飛躍|より一層(?:努め|精進|邁進)|に貢献してまいります",
      1.0, "決意の定型句の重ね", "決意の言い回しは1つにし、具体的な予定を書く。", "original", max_count=2, min_hits=2,
      per_sentence=True),
    R("stock.both_sides", "stock",
      r"(?:いずれ|どちら|それぞれ)(?:の[^。\n]{0,10})?にも(?:メリットとデメリット|一長一短)|一長一短があり|目的(?:や状況)?に(?:応じて|合わせて)[^。\n]{0,15}(?:選択|使い分け)することが(?:重要|大切)",
      2.0, "どちらとも言える一般論の結び", "結論を言い切るか、判断の条件を具体的に書く。", "original", max_count=1),
    R("translationese.enable", "translationese", r"を可能に(?:します|する|しました|しています)|ことを期待(?:します|しています)",
      1.2, "「〜を可能にします」（enable の直訳）", "主語を立てて「〜できるようになります」と言う。", "natural-japanese", max_count=2),
    R("translationese.anata", "translationese", r"あなたの(?:チーム|会社|ビジネス|プロジェクト|貢献|ご意見|アイデア|成功|キャリア|ニーズ)",
      1.5, "「あなたの〜」（your の直訳）", "「あなたの」を外すか、「皆さんの」「ご自身の」にする。", "original", max_count=2),
    R("translationese.let_me_know", "translationese", r"遠慮なく(?:私に)?(?:お)?知らせて|私に(?:お)?知らせてください",
      1.5, "「遠慮なく知らせてください」（let me know の直訳）", "「ご連絡ください」と言う。", "original", max_count=1),
    R("stock.evaluative_cliche", "stock",
      r"大きな学び(?:に|と|の機会)|貴重な学び|有意義な(?:機会|時間)(?:となり|になり|でし)|肌で感じ(?:ることができ|られ)|"
      r"素晴らしい(?:ご縁|機会|経験|体験)(?:を|と|に|が)|かけがえのない(?:財産|経験|時間|存在|もの)|確かな(?:変化|一歩|成長)を|"
      r"奥が深いですね|奥深いですね|(?:何かの)?(?:ヒント|参考|きっかけ)になれば(?:嬉しい|うれしい|幸い)|"
      r"大きなメリットをもたらし|(?:両面|双方)において大きな|必ずや|と確信して(?:おります|います)|最優先(?:事項)?と考えて|"
      r"より良い[^。\n]{0,12}(?:づくり|の実現)に(?:取り組んで|努めて)まいります|この経験を糧に|想いを胸に|という想いから|"
      r"見違えるほど|複合的に絡み合|学びと気づき|気づきと学び|考えさせられる(?:一冊|一日|作品|時間|内容)|これ以上の喜びはありません|一助となって(?:いれば|いたのであれば)|心から歓迎|世代を超えて(?:愛され|受け継が)|持続可能な未来|心より楽しみにして",
      2.5, "感想・評価の決まり文句", "感想や評価の総括を削るか、起きた事実で言い直す。", "original", max_count=2),
    R("stock.era_opening", "stock",
      r"VUCA|不確実性の(?:高い|増す)時代|変化の激しい(?:時代|現代)|先行きの見えない時代|人生100年時代において",
      2.0, "時代を語る書き出し", "時代の話を削り、本題の事実から書く。", "patina", max_count=1),
    R("template.anata_e", "template", r"そんな(?:あなた|方)(?:へ|に)|と(?:お)?悩みの(?:方|あなた)|こんなお悩み(?:は)?ありませんか",
      1.5, "「そんなあなたへ」の呼びかけ", "呼びかけを削り、誰に何が役立つのかを書く。", "patina", max_count=1),
    R("template.before_after", "template", r"[「“『][^」”』\n]{1,10}[」”』]を[「“『][^」”』\n]{1,10}[」”』]に",
      1.5, "「“困った”を“できた”に」の型", "型を外し、何ができるようになるのかを普通に書く。", "original", max_count=1, skip_in_quotes=False),
    R("format.wave_heading", "format", r"＼[^／\n]{1,30}／",
      1.0, "＼見出し／の飾り", "飾りを外す。", "original", max_count=1, skip_in_quotes=False),
    R("stock.over_keigo", "stock", r"させていただ[きくけ]",
      0.8, "「させていただきます」の重ね", "「いたします」「します」を混ぜる。", "matsutouya", max_count=3, min_hits=3, scored=False),
    R("translationese.double_negative", "translationese",
      r"ないことはない|ないこともない|ないでもない|ないわけではない|なくもない|なくはない|ないとは(?:言い切れ|限ら)ない",
      0.6, "二重否定", "肯定文で言う。", "ja-technical", max_count=2, min_hits=2),
]

RULES_BY_ID = {r.id: r for r in RULES}

# Statistical / structural checks implemented in detector.py. Listed here so the
# report, the README table and the tests share one source of labels.
STRUCTURAL = {
    "rhythm.same_ending": ("rhythm", "同じ文末が続く", "文末の形を変えるか、2文を1文にまとめる。", "yomiyasu"),
    "rhythm.taigen_run": ("rhythm", "体言止めが続く", "動詞や「です」で終わる文を混ぜる。", "original"),
    "rhythm.mixed_register": ("rhythm", "敬体と常体が混ざる", "地の文を「です・ます」か「だ・である」のどちらかにそろえる。", "yomiyasu"),
    "register.plain_in_polite": ("register", "敬体が必要な場面での常体", "社外の文やメールは「です・ます」で書く。", "original"),
    "register.casual_in_formal": ("register", "改まった場面でのくだけた言葉", "「〜じゃない」「マジ」などを改まった言い方にする。", "original"),
    "format.list_heavy": ("format", "箇条書きの比率が高い", "考えのつながりは地の文で書く。", "yomiyasu"),
    "format.uniform_paragraphs": ("format", "段落の長さがそろいすぎている", "大事な段落を厚く、軽い段落は短くする。", "natural-japanese"),
}
