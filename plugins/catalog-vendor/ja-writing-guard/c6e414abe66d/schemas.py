"""Tool schema the model reads to decide when to call the checker."""

from .surfaces import SURFACES

JA_WRITING_CHECK = {
    "name": "ja_writing_check",
    "description": (
        "Proofread Japanese text for AI-style phrasing that is common in Japanese business "
        "writing (stock phrases like 〜と言えるでしょう, inflated words, English-calque grammar "
        "such as 〜することができます, em dashes and Markdown in emails, monotonous sentence "
        "endings, register that does not fit the surface). It checks wording, not authorship. "
        "Deterministic and offline: returns a 0-100 score (higher = more of these patterns), "
        "the surface threshold, and each finding with line, column, excerpt and a fix hint in "
        "Japanese. Use it before sending Japanese emails, announcements, posts or docs, and "
        "again after rewriting to confirm the score went down."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The Japanese text to check."},
            "surface": {
                "type": "string",
                "enum": sorted(SURFACES),
                "description": (
                    "Where the text goes. business_email and external require です・ます and "
                    "are strictest; chat is lenient; sns allows emoji; tech_doc allows "
                    "headings, lists and code. Default: chat."
                ),
            },
            "max_findings": {
                "type": "integer",
                "description": "Cap on findings returned (default 30).",
            },
        },
        "required": ["text"],
    },
}
