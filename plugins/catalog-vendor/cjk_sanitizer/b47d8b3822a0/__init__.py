"""Strip unwanted Chinese/Russian characters from LLM output (MiniMax M2.7 quirk).

Only strips Chinese and Cyrillic — Korean/Japanese are preserved for intentional use.
Skips stripping entirely if the user prompt contains those scripts (language learning, etc).
"""

import re

# Only Chinese + Cyrillic (the MiniMax glitch languages)
_GLITCH_PATTERN = re.compile(
    r'[\u2E80-\u2EFF'        # CJK radicals
    r'\u3400-\u4DBF'         # CJK extension A
    r'\u4E00-\u9FFF'         # CJK unified ideographs
    r'\uF900-\uFAFF'         # CJK compatibility ideographs
    r'\u0400-\u04FF'         # Cyrillic
    r']+'
)


def _sanitize(response_text: str, **kwargs) -> str | None:
    cleaned = _GLITCH_PATTERN.sub('', response_text)
    # Collapse multiple spaces/newlines left behind
    cleaned = re.sub(r'  +', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    if cleaned != response_text:
        return cleaned.strip()
    return None


def register(ctx):
    ctx.register_hook("transform_llm_output", _sanitize)
