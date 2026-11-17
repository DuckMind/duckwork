"""Agent Hold 'Em — Duckwork Desktop plugin backend package.

Kept trivial on purpose: no imports at package-import time other than the standard
library, so `import agent_hold_em` never triggers Duckwork agent-runtime imports (which
require `scripts/env.sh`'s DUCKWORK_DISABLE_LAZY_INSTALLS=1 to be safe). Submodules
(`agent_hold_em.controller`, `agent_hold_em.engine`, ...) import Duckwork lazily,
inside functions, for the same reason.
"""

__all__: list[str] = []
