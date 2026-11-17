"""Opt-in bounded prompt warming for OpenAI-compatible chat endpoints."""
import contextvars

from .warmer import Warmer


def register(ctx):
    # Background threads must retain the registration profile, not the ambient one.
    scope = contextvars.copy_context()
    warmer = Warmer(lambda: scope.run(ctx.get_config, "warming", {}))
    ctx.on_unload(lambda: warmer.command("stop"))
    ctx.register_middleware("llm_request", warmer.capture)
    ctx.register_hook("pre_llm_call", warmer.busy)
    ctx.register_hook("post_llm_call", warmer.idle)
    ctx.register_hook("on_session_end", warmer.remove)
    ctx.register_command("warming", warmer.command,
                         "Show session warmer status or stop it for this process",
                         args_hint="[status|stop]")
    # No threads or network until enabled configuration and a supported request.
