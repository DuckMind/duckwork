"""Surface profiles: the same sentence is judged differently by where it goes.

A profile scales rule weights by category or by rule id, sets the score at
which a text counts as "AI-like" (``threshold``), and decides register checks:
``polite_required`` turns plain-form sentence endings (〜だ。〜する。) into a
finding, as an outside reader expects です・ます.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SURFACE_LABELS = {
    "chat": "チャット",
    "business_email": "業務メール",
    "external": "社外文（お知らせ・リリース・案内）",
    "sns": "SNS 投稿",
    "tech_doc": "技術文書",
}

DEFAULT_SURFACE = "chat"


@dataclass(frozen=True)
class Surface:
    name: str
    threshold: int
    polite_required: bool = False
    formal: bool = False
    category_scale: dict = field(default_factory=dict)
    rule_scale: dict = field(default_factory=dict)

    def weight(self, rule_id: str, category: str, base: float) -> float:
        if rule_id in self.rule_scale:
            return base * self.rule_scale[rule_id]
        return base * self.category_scale.get(category, 1.0)


SURFACES: dict[str, Surface] = {
    # Chat: plain form is fine, a heading or two is fine; sycophancy and
    # canned closings are what make a chat reply read as generated.
    "chat": Surface(
        name="chat",
        threshold=40,
        category_scale={"format": 0.7, "register": 0.0},
        rule_scale={"format.heading_in_chat": 1.2, "format.bold": 0.6, "format.exclaim": 0.5,
                    "template.closing_offer": 1.5, "template.hope_helpful": 1.5,
                    "stock.over_keigo": 0.5},
    ),
    # Business email: です・ます required; Markdown has no place in an email.
    "business_email": Surface(
        name="business_email",
        threshold=35,
        polite_required=True,
        formal=True,
        category_scale={"format": 1.3},
        rule_scale={"template.closing_offer": 0.3, "stock.ni_tsuite_kaisetsu": 0.7,
                    "format.emoji": 3.0, "format.exclaim": 1.5},
    ),
    # External text (announcements, releases, service pages): strictest.
    "external": Surface(
        name="external",
        threshold=40,
        polite_required=True,
        formal=True,
        category_scale={"inflated": 1.4, "format": 1.2},
        rule_scale={"template.closing_offer": 0.5, "format.emoji": 3.0},
    ),
    # SNS: emoji and exclamation marks are normal; templates and hype are not.
    "sns": Surface(
        name="sns",
        threshold=35,
        category_scale={"register": 0.0, "template": 1.3, "inflated": 1.2},
        rule_scale={"format.emoji": 0.0, "format.exclaim": 0.0, "format.emoji_bullet": 1.0,
                    "rhythm.taigen_run": 0.3},
    ),
    # Tech docs: headings, lists, bold and 「〜を行う」 are part of the genre.
    "tech_doc": Surface(
        name="tech_doc",
        threshold=45,
        category_scale={"format": 0.4, "register": 0.0},
        rule_scale={"format.list_heavy": 0.0, "format.heading_in_chat": 0.0,
                    "translationese.okonau": 0.3, "format.paren_gloss": 0.5},
    ),
}


def get_surface(name: str | None) -> Surface:
    key = (name or DEFAULT_SURFACE).strip().lower().replace("-", "_")
    aliases = {"email": "business_email", "mail": "business_email", "press": "external",
               "public": "external", "x": "sns", "twitter": "sns", "tech": "tech_doc",
               "docs": "tech_doc", "doc": "tech_doc"}
    key = aliases.get(key, key)
    if key not in SURFACES:
        raise ValueError(f"unknown surface {name!r}; choose one of {', '.join(SURFACES)}")
    return SURFACES[key]
