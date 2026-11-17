# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""The plugin's three settings, read only through Duckwork's secret scope.

Design 24, "Settings through Duckwork's secret scope (0.21.5)". Duckwork's
catalogue rule 11: a plugin's declared secrets are read with
``agent.secret_scope.get_secret(NAME)``, which returns the active profile's
value. One Duckwork may serve several profiles, each with its own ``.env``;
the process environment holds at most one of them. So:

- every read goes through :func:`get`, at the time of use (a turn runs inside
  its profile's scope), never at import or registration only;
- nothing here, or anywhere in the plugin, reads the process environment
  for a setting. With no scope bound and multiplexing off, ``get_secret`` itself
  reads the process environment, which is the single-profile case;
- a Duckwork without ``agent.secret_scope`` (older than 0.21.5, which
  ``requires_duckwork`` already excludes) gets no settings at all, and
  :data:`TOO_OLD` says why.
"""

from __future__ import annotations

URL = "VORNIK_URL"
BROKER_TOKEN = "VORNIK_BROKER_TOKEN"
MEMORY_TOKEN = "VORNIK_MEMORY_TOKEN"
NAMES = (URL, BROKER_TOKEN, MEMORY_TOKEN)

MIN_DUCKWORK = "0.21.5"
TOO_OLD = ("vornik-companion needs Duckwork %s or later: this Duckwork has no agent.secret_scope, "
           "the route a plugin reads its settings through, so the plugin reads none." % MIN_DUCKWORK)
HOW_TO_SET = ("Set it for this Duckwork profile with `duckwork config set NAME <value>` "
              "(`duckwork -p <profile> config set` for another profile), or in the Desktop under "
              "Settings > Plugins > vornik-companion.")
HOW_TO_SET_EACH = HOW_TO_SET.replace("Set it", "Set each").replace("NAME", "<NAME>")


def _get_secret():
    try:
        from agent.secret_scope import get_secret
    except ImportError:
        return None
    return get_secret


def supported() -> bool:
    """True when this Duckwork has the secret scope."""
    return _get_secret() is not None


def get(name: str) -> str:
    """The active profile's value of one setting, '' when unset.

    Raises what ``get_secret`` raises (``UnscopedSecretError`` when a
    multiplexing Duckwork calls with no profile scope bound): reading another
    profile's value is not a fallback."""
    get_secret = _get_secret()
    if get_secret is None:
        return ""
    return str(get_secret(name, "") or "").strip()


def getter(name: str):
    """A zero-argument callable reading ``name`` at each call."""
    return lambda: get(name)


def missing(*names: str) -> list:
    return [n for n in names if not get(n)]


def not_configured(*names: str) -> str:
    """The answer for a use that needs ``names``: which are not set, and how
    to set them. '' when all are set."""
    if not supported():
        return TOO_OLD
    gone = missing(*names)
    if not gone:
        return ""
    verb = "is" if len(gone) == 1 else "are"
    return "Vornik is not configured in this Duckwork profile: %s %s not set. %s" % (
        " and ".join(gone), verb, HOW_TO_SET.replace("NAME", gone[0]) if len(gone) == 1 else HOW_TO_SET_EACH)
