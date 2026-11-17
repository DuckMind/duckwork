"""Rewrite a flagged text with one bounded LLM call, then check the result.

The detector decides *whether* and *where*; the model only rewrites the spans
it was shown. A rewrite is accepted only when it passes every guard:

- code blocks, inline code, URLs, @mentions and #hashtags survive verbatim;
- every number in the original survives (full-width digits and commas are
  normalised first), so dates, amounts and counts cannot drift;
- ASCII words outside the flagged spans survive (product names, identifiers);
- Japanese names survive: the word before 様・さん・殿・氏・御中, the name in
  「〜の中川です」, company names
  with 株式会社 and the like, and short names in 「」『』;
- a name is matched whole: 「ミナトリンク」 does not pass as 「ミナトリンクス」;
- weekdays such as （水）, 午前 and 午後 keep their counts outside flagged spans;
- lines without sentence punctuation (subject, addressee, department and
  signature lines, section labels) that hold no finding survive verbatim;
- negation keeps its direction: the words negated outside the flagged spans
  stay negated and no new word becomes negated (ご提案したく must not turn
  into ご提案できず; 参加できます must not swap with 必要ありません);
- the length stays between 50% and 130% of the original;
- the detector score goes down.

Otherwise the original text is kept. The model call is injected (``llm``) so
this module has no Duckwork dependency and can be tested offline.

The rewriting rules in ``SYSTEM_PROMPT`` follow the meaning-preservation
principles of nanaism/yomiyasu (主張・比重・言い切りの強さ・文の働きを変えない、
足さない) and the revision guidance of coji/natural-japanese (MIT, see NOTICE).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable

from .detector import Report, check
from .surfaces import SURFACE_LABELS, get_surface

SYSTEM_PROMPT = """あなたは日本語の編集者です。AIが書いた日本語のうち、指摘された箇所だけを、人が書いたような自然な文に直します。

守ること（この順に優先）:
1. 意味を変えない。主張、何を一番大事としているか、言い切りの強さ（断定・推量・可能性）、文の働き（説明・依頼・予定・評価）を元のまま保つ。
2. 足さない。元の文にない事実・数字・例・理由・条件・人名・社名を書かない。分からないことは書かない。
3. 数字・日付・金額・固有名詞・URL・コード（`…` と ``` で囲んだ部分）は一字も変えずに残す。
4. 直すのは指摘された箇所と、その文を自然にするのに要る範囲だけ。指摘のない文はそのまま残す。
5. 箇条書きや見出しは、場面に合わないと指摘されたときだけ地の文にする。手順や並列の情報は箇条書きのまま残してよい。
6. 前置き・締めの決まり文句（「いかがでしたか」「お役に立てれば幸いです」など）は削る。評価を担っている言葉（「〜が大事です」）は述語に移して残す。
7. 「AではなくB」は、誤解を正している場合はそのまま残す。
8. 依頼・呼びかけ・約束・予定の文（「ご連絡ください」「コメントで教えてください」「これからも〜します」）は消さない。言い回しだけを直す。
9. 宛名・署名・会社名・人名・製品名は一字も変えない。
10. 説明や前置きを付けずに、直した本文だけを <rewritten> と </rewritten> の間に書く。"""

_SURFACE_NOTES = {
    "business_email": "場面は業務メール。地の文は「です・ます」にそろえる。Markdown（見出し・太字・箇条書きの記号）と絵文字は使わない。宛名・挨拶・署名はそのまま残す。",
    "external": "場面は社外向けの文（お知らせ・リリース・案内）。地の文は「です・ます」にそろえる。宣伝調の大げさな言葉は、元の文にある事実だけで言い直す。絵文字は使わない。",
    "sns": "場面は SNS の投稿。くだけた口調・絵文字・感嘆符はそのままでよい。型どおりの前置きと締めだけを直す。",
    "tech_doc": "場面は技術文書。見出し・箇条書き・コードはそのまま残す。直訳調と空疎な言葉だけを直す。",
    "chat": "場面はチャットの返答。短い返答なら見出しや太字を外して段落で書く。返答の頭と締めの決まり文句は削る。",
}

_FENCE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
_INLINE = re.compile(r"`[^`\n]+`")
_URL = re.compile(r"https?://[^\s)）>\]」]+")
_HANDLE = re.compile(r"(?<![\w@])[@#][\w぀-ヿ一-鿿]+")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_ASCII_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_.+-]{1,}")
_TAGGED = re.compile(r"<rewritten>\s*(.*?)\s*</rewritten>", re.S)
_HONORIFIC_NAME = re.compile(r"([一-龠々ァ-ヶーA-Za-z]{1,10})\s?(?:様|さん|殿|氏|御中|先生)")
_COMPANY = re.compile(r"(?:株式会社|有限会社|合同会社|一般社団法人|公益財団法人)\s?[一-龠々ァ-ヶーA-Za-z0-9]{1,15}|"
                      r"[一-龠々ァ-ヶーA-Za-z0-9]{1,15}(?:株式会社|有限会社|合同会社)")
_JA_CHAR = re.compile(r"[ぁ-んァ-ヶ一-龠]")
_SELF_INTRO = re.compile(r"(?:の|、)([一-龠々]{2,4})(?:です|でございます|と申します)[。、]")
_QUOTED_NAME = re.compile(r"[「『]([^」』\n]{1,20})[」』]")
_NAME_CONT = r"(?![ァ-ヶー一-龠々A-Za-z0-9])"
_WEEKDAY = re.compile(r"[（(][月火水木金土日](?:曜日?)?[）)]|午前|午後")
_NEG_STEM = re.compile(r"([一-龠々ぁ-んァ-ヶー]{2})(?=(?:ませ|な(?:い|く|かっ)|(?<!ま)(?<!必)(?<!かなら)ず[にて、。]))")
# Adverbs that only look negative: 無理なく, 間もなく, もれなく, 途切れず ...
_NEG_ADVERB = re.compile(r"(?:無理|間も|まも|もれ|漏れ|ほど|くま|途切れ|絶え間|容赦|惜しみ|例外|余すところ|残ら|心置き|思わ|知らず知ら)(?:なく|ず)")


def _strip_neg_adverbs(text: str) -> str:
    return _NEG_ADVERB.sub("", text)


_BARE_LINE = re.compile(r"^(?!\s*(?:[-*+#|>]|\d+[.)]\s))[^\n。！？!?]{1,40}$", re.M)
_NEGATION = re.compile(r"(?:な(?:い|く|かった)|ません|(?<!ま)(?<!必)(?<!かなら)ず(?:に|、|。)|できず|ぬ(?:。|、))")
# Generic forms of address are not names: お客様, 皆様, ご担当者様 ...
_GENERIC_ADDRESS = {"客", "皆", "皆さま", "各位", "担当者", "ご担当者", "担当", "利用者", "関係者", "参加者", "会員",
                    "生徒", "保護者", "社員", "先方", "患者", "お客", "みな", "皆々", "業者", "相手"}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"(?<=\d),(?=\d{3})", "", text)


def _numbers(text: str) -> list[str]:
    return sorted(_NUMBER.findall(_norm(text)))


def _flagged_spans(report: Report) -> list[tuple[int, int]]:
    return [(f.start, f.end) for f in report.findings]


def _outside(spans, start, end) -> bool:
    return not any(s <= start < e or s < end <= e for s, e in spans)


def guard_problems(original: str, candidate: str, report: Report) -> list[str]:
    """Reasons a candidate must be refused; an empty list means it may be used."""
    problems = []
    if not candidate.strip():
        return ["empty rewrite"]
    for pat, what in ((_FENCE, "code block"), (_INLINE, "inline code"), (_URL, "URL"), (_HANDLE, "@/# handle")):
        for m in pat.finditer(original):
            if m.group(0) not in candidate:
                problems.append(f"{what} changed or dropped: {m.group(0)[:40]}")
    spans = _flagged_spans(report)
    cand_norm_all = _norm(candidate)
    for pat, what in ((_HONORIFIC_NAME, "name"), (_SELF_INTRO, "name"), (_COMPANY, "company name"),
                      (_QUOTED_NAME, "quoted name")):
        for m in pat.finditer(original):
            token = m.group(1) if pat is not _COMPANY else m.group(0)
            if pat in (_HONORIFIC_NAME, _SELF_INTRO) and (token in _GENERIC_ADDRESS or original[max(0, m.start() - 1):m.start()] in ("お", "ご")):
                continue
            whole = re.escape(_norm(token).replace(" ", "")) + (_NAME_CONT if pat is _COMPANY else "")
            if _outside(spans, m.start(), m.end()) and not re.search(whole, cand_norm_all.replace(" ", "")):
                problems.append(f"{what} changed or dropped: {token}")
                break
    unflagged_text = "".join(" " if not _outside(spans, i, i + 1) else ch for i, ch in enumerate(original))
    if sorted(_WEEKDAY.findall(_norm(unflagged_text))) != sorted(
            w for w in _WEEKDAY.findall(_norm(candidate)) if w in set(_WEEKDAY.findall(_norm(original)))) \
            or len(_WEEKDAY.findall(_norm(candidate))) > len(_WEEKDAY.findall(_norm(original))):
        problems.append("weekday or 午前/午後 changed")
    cand_lines = {ln.strip() for ln in candidate.splitlines()}
    for m in _BARE_LINE.finditer(original):
        line = m.group(0).strip()
        if line and _outside(spans, m.start(), m.end()) and _JA_CHAR.search(line) and line not in cand_lines:
            problems.append(f"line changed: {line[:30]}")
            break
    orig_neg = _NEG_STEM.findall(_strip_neg_adverbs(unflagged_text))
    all_neg = set(_NEG_STEM.findall(_strip_neg_adverbs(original)))
    cand_neg = _NEG_STEM.findall(_strip_neg_adverbs(candidate))
    missing_neg = [w for w in orig_neg if w not in cand_neg]
    new_neg = [w for w in cand_neg if w not in all_neg]
    if missing_neg or new_neg:
        problems.append("negation changed: " + ", ".join(sorted(set(missing_neg + new_neg))[:6]))
    neg_all = len(_NEGATION.findall(_strip_neg_adverbs(original)))
    neg_cand = len(_NEGATION.findall(_strip_neg_adverbs(candidate)))
    if neg_cand > neg_all and not any(p.startswith("negation") for p in problems):
        problems.append(f"negation added ({neg_all} -> {neg_cand})")
    # Numbers inside a flagged span (「3つのポイント」, a numbered heading) may go;
    # every other number must survive, and no new number may appear.
    unflagged = "".join(" " if not _outside(spans, i, i + 1) else ch for i, ch in enumerate(original))
    orig_nums, cand_nums = _numbers(unflagged), _numbers(candidate)
    missing = list(orig_nums)
    for n in cand_nums:
        if n in missing:
            missing.remove(n)
    if missing:
        problems.append("numbers dropped or changed: " + ", ".join(sorted(set(missing))[:8]))
    all_orig = set(_numbers(original))
    extra = [n for n in set(cand_nums) if n not in all_orig]
    if extra:
        problems.append("numbers added: " + ", ".join(sorted(extra)[:8]))
    cand_norm = _norm(candidate)
    for m in _ASCII_WORD.finditer(original):
        if _outside(spans, m.start(), m.end()) and _norm(m.group(0)) not in cand_norm:
            problems.append(f"word dropped: {m.group(0)}")
            break
    # Sentences without findings carry the content; dropping a flagged greeting or
    # closing is the point of the rewrite, so only the clean sentences set the floor.
    clean_len = sum(e - s for s, e in _sentences(original) if _outside(spans, s, e) and
                    not any(s <= fs and fe <= e for fs, fe in spans))
    floor = max(0.3 * len(original), 0.8 * clean_len)
    if len(candidate) < floor or len(candidate) > 1.3 * len(original):
        ratio = len(candidate) / max(1, len(original))
        problems.append(f"length changed too much ({ratio:.0%} of the original)")
    return problems


def _sentences(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in re.finditer(r"[。！？!?\n]", text):
        if m.end() - start > 1:
            spans.append((start, m.end()))
        start = m.end()
    if len(text) - start > 1:
        spans.append((start, len(text)))
    return spans


def build_messages(text: str, report: Report, feedback: list[str] | None = None) -> list[dict]:
    surface = report.surface
    lines = []
    for f in report.findings[:20]:
        lines.append(f"- {f.line}行目「{f.excerpt}」: {f.label}。{f.hint}")
    user = [
        _SURFACE_NOTES.get(surface, ""),
        f"場面: {SURFACE_LABELS.get(surface, surface)}",
        "",
        "指摘（検出器の結果。直す候補であり、意味を担っているものは残してよい）:",
        *lines,
    ]
    if feedback:
        user += ["", "前回の書き直しは次の理由で使えませんでした。直してください:", *[f"- {p}" for p in feedback]]
    user += ["", "元の文:", "<original>", text, "</original>"]
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "\n".join(user)}]


def extract(reply: str) -> str:
    m = _TAGGED.search(reply or "")
    return m.group(1).strip() if m else ""


@dataclass
class Outcome:
    text: str
    changed: bool
    before: Report
    after: Report | None
    attempts: int
    reason: str
    rejected: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "changed": self.changed,
            "reason": self.reason,
            "attempts": self.attempts,
            "score_before": self.before.score,
            "score_after": self.after.score if self.after else None,
            "threshold": self.before.threshold,
            "rejected": self.rejected,
        }


LlmCall = Callable[[list[dict]], str]


def _rank(r: Report) -> tuple[int, int]:
    return (r.register_issues, r.score)


def _improved(before: Report, after: Report) -> bool:
    """Better on one axis and no worse on the other."""
    if after.score > before.score or after.register_issues > before.register_issues:
        return False
    return after.score < before.score or after.register_issues < before.register_issues


def rewrite(text: str, llm: LlmCall, surface: str | None = None, threshold: int | None = None,
            max_attempts: int = 2, report: Report | None = None) -> Outcome:
    """Rewrite ``text`` when it is over the threshold; keep the original otherwise."""
    prof = get_surface(surface)
    before = report or check(text, prof, threshold)
    if not before.needs_rewrite:
        return Outcome(text, False, before, None, 0, "under threshold")
    best: tuple[str, Report] | None = None
    feedback: list[str] | None = None
    rejected: list[list[str]] = []
    attempts = 0
    for attempts in range(1, max(1, max_attempts) + 1):
        try:
            reply = llm(build_messages(text, before, feedback))
        except Exception as exc:  # the model call is best effort; keep the original
            rejected.append([f"model call failed: {type(exc).__name__}"])
            break
        candidate = extract(reply)
        problems = guard_problems(text, candidate, before) if candidate else ["no <rewritten> block in the reply"]
        after = check(candidate, prof, threshold) if candidate else None
        if after is not None and not _improved(before, after):
            problems.append(f"score did not go down ({before.score} -> {after.score}, "
                            f"register issues {before.register_issues} -> {after.register_issues})")
        if problems:
            rejected.append(problems)
            feedback = problems
            continue
        if best is None or _rank(after) < _rank(best[1]):
            best = (candidate, after)
        if not after.needs_rewrite:
            break
        feedback = [f"まだ基準を超えています（{after.score}/{after.threshold}）。残った指摘: "
                    + "、".join(sorted({f.label for f in after.findings if f.counted}))]
    if best is None:
        return Outcome(text, False, before, None, attempts, "kept original: no rewrite passed the guards", rejected)
    reason = "rewritten" if not best[1].needs_rewrite else "rewritten (still over threshold, best attempt)"
    return Outcome(best[0], True, before, best[1], attempts, reason, rejected)
