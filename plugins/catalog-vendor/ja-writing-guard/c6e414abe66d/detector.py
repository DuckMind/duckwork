"""Deterministic detector for Japanese AI-writing tells.

``check(text, surface)`` returns a ``Report``: a 0–100 score (higher = reads
more like unedited AI output), the surface threshold, and every finding with
its character offsets, line, column, the matched excerpt and a fix hint.

Standard library only. Same input, same output; no model calls. Code blocks,
inline code, URLs and quoted lines (``>``) are masked before scanning, and most
phrase rules ignore hits inside 「」『』 so dialogue and quoted examples do not
count against the writer.
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import asdict, dataclass, field

from .rules import CATEGORIES, RULES, STRUCTURAL
from .surfaces import Surface, get_surface

# ----------------------------------------------------------------- masking

_FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.M | re.S)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_URL = re.compile(r"https?://[^\s)）>\]」]+")
_QUOTE_LINE = re.compile(r"^\s*>.*$", re.M)
_HTML_TAG = re.compile(r"<[^>\n]{1,200}>")

_KANA = re.compile(r"[ぁ-んァ-ヶ]")
_JA = re.compile(r"[ぁ-んァ-ヶ一-龠々〆ヵヶ]")
_LETTER = re.compile(r"[A-Za-zぁ-んァ-ヶ一-龠々]")


def _mask(text: str) -> str:
    """Replace ignored spans with spaces, keeping offsets and newlines."""
    chars = list(text)

    def blank(m: re.Match):
        for i in range(m.start(), m.end()):
            if chars[i] != "\n":
                chars[i] = " "

    for pat in (_FENCE, _INLINE_CODE, _URL, _QUOTE_LINE, _HTML_TAG):
        for m in pat.finditer(text):
            blank(m)
    return "".join(chars)


def _quote_spans(text: str) -> list[tuple[int, int]]:
    """Ranges inside 「」 or 『』 (outermost pair), for rules that skip quotes."""
    spans, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch in "「『":
            if depth == 0:
                start = i
            depth += 1
        elif ch in "」』" and depth:
            depth -= 1
            if depth == 0:
                spans.append((start, i + 1))
        elif ch == "\n" and depth and i - start > 400:
            depth = 0  # unbalanced quote; stop treating the rest as quoted
    return spans


def _inside(pos: int, spans: list[tuple[int, int]]) -> bool:
    lo, hi = 0, len(spans)
    while lo < hi:
        mid = (lo + hi) // 2
        s, e = spans[mid]
        if pos < s:
            hi = mid
        elif pos >= e:
            lo = mid + 1
        else:
            return True
    return False


def is_japanese(text: str, min_kana: int = 10) -> bool:
    """True when the text is mainly Japanese prose (enough kana, mostly JA letters)."""
    kana = len(_KANA.findall(text))
    if kana < min_kana:
        return False
    letters = len(_LETTER.findall(text)) or 1
    return len(_JA.findall(text)) / letters >= 0.4


# --------------------------------------------------------------- sentences

_LIST_LINE = re.compile(r"^\s*(?:[-*+]\s|\d+[.)．]\s|[・●■◆▶]\s?)")
_MD_LIST_LINE = re.compile(r"^\s*(?:[-*+]\s|\d+[.)．]\s)")
_HEADING = re.compile(r"^\s*(?:#{1,6}\s|【[^】]{1,30}】\s*$|■)")
_TABLE = re.compile(r"^\s*\|")
_SENT_SPLIT = re.compile(r"(?<=[。！？!?])")
_SENTENCE_END = re.compile(r"[。！？!?\n]")

_POLITE_END = re.compile(
    r"(?:です|ます|ました|でした|ません|ませんでした|でしょう|ましょう|ください|下さい|ございます|"
    r"いたします|致します|願います|存じます|申し上げます)(?:ね|よ|か|よね|が|けれど|けど)?$")
_PLAIN_END = re.compile(
    r"(?:だ|である|であった|だった|だろう|ではない|じゃない|ない|なかった|た|だ|る|う|く|す|つ|ぬ|む|ぶ|ぐ|い|よう|まい|ず|ぬ|"
    r"のだ|のである|かもしれない|と思う|と考える)(?:ね|よ|な|か|よね|わ|ぞ|さ)?$")
_NOMINAL_END = re.compile(r"(?:[一-龠々ァ-ヶーA-Za-z0-9０-９％%]|こと|もの|ため|とおり|通り)$")


@dataclass
class Sentence:
    text: str
    start: int
    end: int
    kind: str  # prose | list | heading
    ending: str  # polite | plain | nominal | other
    key: str  # fine-grained ending for the monotony check
    terminated: bool = False  # ended with 。！？ (not a bare line such as a signature)


def _ending(core: str) -> tuple[str, str]:
    core = core.rstrip("。！？!?…・ 　)）")
    if not core:
        return "other", ""
    if core.endswith(("」", "』", "\"")):
        return "other", ""
    if _POLITE_END.search(core):
        m = re.search(r"(?:て|で)?(?:い|おり|あり|し|でき|なり|られ|され)?(?:ます|ました|ません|です|でした|でしょう|ましょう|ください|ございます|いたします)(?:ね|よ|か)?$", core)
        return "polite", (m.group(0) if m else core[-2:])
    if _NOMINAL_END.search(core):
        return "nominal", "N"
    if _PLAIN_END.search(core):
        return "plain", core[-2:]
    return "other", core[-1:]


def _split_outside_parens(line: str) -> list[str]:
    """Split after 。！？ unless inside （）() or 「」『』, e.g. （以下「法」という。）."""
    pieces, depth, start = [], 0, 0
    for i, ch in enumerate(line):
        if ch in "（(「『":
            depth += 1
        elif ch in "）)」』" and depth:
            depth -= 1
        elif ch in "。！？!?" and depth == 0:
            pieces.append(line[start:i + 1])
            start = i + 1
    if start < len(line):
        pieces.append(line[start:])
    return pieces


def split_sentences(scan: str) -> list[Sentence]:
    out: list[Sentence] = []
    pos = 0
    for raw_line in scan.split("\n"):
        line_start = pos
        pos += len(raw_line) + 1
        stripped = raw_line.strip()
        if not stripped or _TABLE.match(raw_line):
            continue
        if _HEADING.match(raw_line):
            out.append(Sentence(stripped, line_start, line_start + len(raw_line), "heading", "other", ""))
            continue
        kind = "list" if _LIST_LINE.match(raw_line) else "prose"
        offset = 0
        for piece in _split_outside_parens(raw_line):
            if not piece:
                continue
            s = line_start + offset
            offset += len(piece)
            core = piece.strip()
            if len(core) < 4 or not _JA.search(core):
                continue
            ending, key = _ending(core)
            terminated = core[-1] in "。！？!?"
            out.append(Sentence(core, s, s + len(piece), kind, ending, key, terminated))
    return out


# ------------------------------------------------------------------ report


@dataclass
class Finding:
    rule: str
    category: str
    label: str
    hint: str
    start: int
    end: int
    line: int
    col: int
    excerpt: str
    weight: float
    counted: bool
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    surface: str
    score: int
    threshold: int
    over_threshold: bool
    japanese: bool
    chars: int
    findings: list[Finding] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    # Surface policy (です・ます required, no slang in formal text) is reported
    # apart from the AI-likeness score: a human notice written in である調 is not
    # AI-like, but it still does not fit an outside-facing surface.
    register_issues: int = 0

    @property
    def register_violation(self) -> bool:
        return self.register_issues > 0

    @property
    def needs_rewrite(self) -> bool:
        return self.japanese and (self.over_threshold or self.register_violation)

    @property
    def reasons(self) -> list[str]:
        out = []
        if self.over_threshold:
            out.append("ai_like")
        if self.register_violation:
            out.append("register")
        return out

    @property
    def verdict(self) -> str:
        if not self.japanese:
            return "not_japanese"
        return "rewrite" if self.needs_rewrite else "ok"

    def by_category(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for f in self.findings:
            if f.counted:
                totals[f.category] = round(totals.get(f.category, 0.0) + f.weight, 2)
        return dict(sorted(totals.items(), key=lambda kv: -kv[1]))

    def summary_ja(self) -> str:
        if not self.japanese:
            return "日本語の文ではないため検査していません。"
        head = f"AI的な言い回し {self.score}/100（{self.surface} の基準 {self.threshold}）"
        if not self.findings:
            return head + "。指摘なし。"
        cats = "・".join(CATEGORIES.get(c, c) for c in list(self.by_category())[:3])
        n = len(self.findings)
        if self.over_threshold and self.register_violation:
            tail = "AI的な言い回しが基準を超え、場面の文体にも合いません。書き直しの対象です。"
        elif self.over_threshold:
            tail = "書き直しの対象です。"
        elif self.register_violation:
            tail = "AI的な言い回しは基準内ですが、場面の文体（敬体など）に合わないため書き直しの対象です。"
        else:
            tail = "基準内です。"
        return f"{head}。指摘 {n} 件（多い順: {cats}）。{tail}"

    def to_dict(self, max_findings: int | None = None) -> dict:
        items = self.findings if max_findings is None else self.findings[:max_findings]
        return {
            "surface": self.surface,
            "score": self.score,
            "threshold": self.threshold,
            "verdict": self.verdict,
            "reasons": self.reasons,
            "register_violation": self.register_violation,
            "summary": self.summary_ja(),
            "chars": self.chars,
            "by_category": self.by_category(),
            "findings": [f.to_dict() for f in items],
            "findings_total": len(self.findings),
            "stats": self.stats,
        }


def _line_col(text: str, pos: int) -> tuple[int, int]:
    line = text.count("\n", 0, pos) + 1
    col = pos - (text.rfind("\n", 0, pos) + 1) + 1
    return line, col


def _excerpt(text: str, start: int, end: int, pad: int = 12) -> str:
    s = max(0, start - pad)
    e = min(len(text), end + pad)
    snippet = text[s:e].replace("\n", "⏎")
    return ("…" if s > 0 else "") + snippet + ("…" if e < len(text) else "")


# Scale: how many weighted points saturate the score for a text of this length.
SCORE_K = 4.0
LENGTH_UNIT = 500


def _score(points: float, ja_chars: int) -> int:
    norm = math.sqrt(max(1.0, ja_chars / LENGTH_UNIT))
    return int(round(100 * (1 - math.exp(-points / (SCORE_K * norm)))))


_CASUAL = re.compile(r"じゃん|マジ|めっちゃ|ヤバ|やば[いく]|っす(?:[。！!ね]|$)|ちゃう|だよね|でしょ[。！!]|笑[)）]|（笑）|w{2,}", re.M)


def check(text: str, surface: str | Surface | None = None, threshold: int | None = None) -> Report:
    """Score ``text`` for Japanese AI-writing tells on the given surface."""
    prof = surface if isinstance(surface, Surface) else get_surface(surface)
    thr = int(threshold) if threshold else prof.threshold
    text = text or ""
    scan = _mask(text)
    ja_chars = len(_JA.findall(scan))
    japanese = is_japanese(scan)
    report = Report(surface=prof.name, score=0, threshold=thr, over_threshold=False,
                    japanese=japanese, chars=ja_chars)
    if not japanese:
        return report

    quotes = _quote_spans(scan)
    findings: list[Finding] = []

    def add(rule_id, category, label, hint, start, end, base, counted, source):
        w = prof.weight(rule_id, category, base)
        line, col = _line_col(text, start)
        findings.append(Finding(rule_id, category, label, hint, start, end, line, col,
                                _excerpt(text, start, end), round(w, 2), counted and w > 0, source))

    # Phrase and pattern rules.
    for rule in RULES:
        hits = [m for m in rule.compiled.finditer(text if rule.on_raw else scan)
                if m.end() > m.start() and not (rule.skip_in_quotes and _inside(m.start(), quotes))]
        if rule.per_sentence:
            seen, unique = set(), []
            for m in hits:
                key = len(_SENTENCE_END.findall(scan, 0, m.start()))
                if key not in seen:
                    seen.add(key)
                    unique.append(m)
            hits = unique
        if len(hits) < rule.min_hits:
            continue
        for i, m in enumerate(hits):
            add(rule.id, rule.category, rule.label, rule.hint, m.start(), m.end(),
                rule.weight, rule.scored and i < rule.max_count, rule.source)

    # Structural checks over sentences.
    sents = split_sentences(scan)
    prose = [s for s in sents if s.kind == "prose" and s.terminated and not _inside(s.start, quotes)]

    def structural(rule_id, start, end, base, counted=True):
        cat, label, hint, source = STRUCTURAL[rule_id]
        add(rule_id, cat, label, hint, start, end, base, counted, source)

    # Same fine-grained ending three or more times in a row.
    runs = 0
    i = 0
    while i < len(prose):
        j = i
        while j + 1 < len(prose) and prose[j + 1].key and prose[j + 1].key == prose[i].key:
            j += 1
        if j - i + 1 >= 4 and prose[i].key not in ("", "N"):
            structural("rhythm.same_ending", prose[i].start, prose[j].end, 1.0, runs < 3)
            runs += 1
        i = j + 1

    # Three or more nominal-ending prose sentences in a row.
    runs = 0
    i = 0
    while i < len(prose):
        j = i
        while j < len(prose) and prose[j].ending == "nominal":
            j += 1
        if j - i >= 3:
            structural("rhythm.taigen_run", prose[i].start, prose[j - 1].end, 1.5, runs < 2)
            runs += 1
        i = max(j, i + 1)

    polite = [s for s in prose if s.ending == "polite"]
    plain = [s for s in prose if s.ending == "plain"]
    if prof.polite_required:
        for k, s in enumerate(plain):
            structural("register.plain_in_polite", s.start, s.end, 2.5, k < 3)
    elif len(prose) >= 4 and len(polite) >= 2 and len(plain) >= 2:
        minority = min(len(polite), len(plain)) / (len(polite) + len(plain))
        if minority >= 0.2:
            first = (plain if len(plain) <= len(polite) else polite)[0]
            structural("rhythm.mixed_register", first.start, first.end, 2.0)

    if prof.formal:
        for k, m in enumerate(m for m in _CASUAL.finditer(scan) if not _inside(m.start(), quotes)):
            structural("register.casual_in_formal", m.start(), m.end(), 2.0, k < 2)

    lines = [ln for ln in scan.split("\n") if ln.strip()]
    md_list = [ln for ln in lines if _MD_LIST_LINE.match(ln)]
    list_ratio = len(md_list) / len(lines) if lines else 0.0
    if len(md_list) >= 4 and list_ratio >= 0.5:
        first = scan.find(md_list[0])
        structural("format.list_heavy", first, first + len(md_list[0]), 2.0)

    paragraphs = [p for p in re.split(r"\n\s*\n", scan) if p.strip()
                  and not _MD_LIST_LINE.match(p) and not _HEADING.match(p)]
    plens = [len(_JA.findall(p)) for p in paragraphs]
    if len(plens) >= 4 and min(plens) >= 30:
        cv = statistics.pstdev(plens) / (statistics.mean(plens) or 1)
        if cv < 0.2:
            first = scan.find(paragraphs[0])
            structural("format.uniform_paragraphs", first, first + min(40, len(paragraphs[0])), 1.0)

    findings.sort(key=lambda f: (f.start, f.rule))
    points = sum(f.weight for f in findings if f.counted and f.category != "register")
    report.register_issues = sum(1 for f in findings if f.counted and f.category == "register")
    report.findings = findings
    report.score = _score(points, ja_chars)
    report.over_threshold = report.score >= thr
    endings: dict[str, int] = {}
    for s in prose:
        endings[s.ending] = endings.get(s.ending, 0) + 1
    lens = [len(_JA.findall(s.text)) for s in prose]
    burst = None
    if len(lens) >= 2:
        mu, sd = statistics.mean(lens), statistics.pstdev(lens)
        burst = round((sd - mu) / (sd + mu), 3) if (sd + mu) else None
    report.stats = {
        "points": round(points, 2),
        "sentences": len(prose),
        "endings": endings,
        "list_ratio": round(list_ratio, 2),
        "burstiness": burst,
    }
    return report
