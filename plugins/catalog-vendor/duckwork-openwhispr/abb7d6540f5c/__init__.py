"""duckwork-openwhispr: agent-side entry point.

Skill-carrier by design: registers the bundled OpenWhispr skill, and all
OpenWhispr work goes through the external `@openwhispr/cli` via the
`terminal` tool. Local desktop bridge by default; cloud only on explicit
opt-in. No tools, hooks, or middleware registered here.
"""

from pathlib import Path


def register(ctx):
    """Register the bundled skill; nothing else."""
    skill_md = Path(__file__).parent / "skills" / "openwhispr" / "SKILL.md"
    if skill_md.is_file():
        try:
            ctx.register_skill("openwhispr", skill_md)
        except TypeError:
            # Older runtimes take the path as str.
            ctx.register_skill("openwhispr", str(skill_md))
    return None
