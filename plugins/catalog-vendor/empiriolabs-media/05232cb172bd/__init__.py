"""EmpirioLabs AI image, video and text-to-speech backends for Duckwork Agent.

``register(ctx)`` adds three backends named ``empiriolabs``: one for ``image_generate``
(``image_gen.provider``), one for ``video_generate`` (``video_gen.provider``) and one for
``text_to_speech`` (``tts.provider``). It registers no tools, hooks, commands or threads.
Requests go to the EmpirioLabs AI API with ``EMPIRIOLABS_API_KEY`` only when one of those
backends is selected and the agent calls its tool.
"""

from __future__ import annotations

from ._api import __version__
from .image import EmpirioLabsImageGenProvider
from .speech import EmpirioLabsTTSProvider
from .video import EmpirioLabsVideoGenProvider

__all__ = [
    "EmpirioLabsImageGenProvider",
    "EmpirioLabsTTSProvider",
    "EmpirioLabsVideoGenProvider",
    "__version__",
    "register",
]


def register(ctx) -> None:
    """Duckwork plugin entry point."""
    ctx.register_image_gen_provider(EmpirioLabsImageGenProvider())
    ctx.register_video_gen_provider(EmpirioLabsVideoGenProvider())
    ctx.register_tts_provider(EmpirioLabsTTSProvider())
