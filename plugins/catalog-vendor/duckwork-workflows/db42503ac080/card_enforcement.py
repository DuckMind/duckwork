"""#157 MACHINERY (backend half): card enforcement — the ::workflow card ships unasked.

core fires the ``transform_llm_output`` lifecycle hook once per turn BEFORE the
final assistant row is persisted (core: duckwork_cli/plugins.py VALID_HOOKS;
agent/turn_finalizer.py apply_llm_output_transform — the first hook returning a
non-empty string wins and that string becomes the persisted+streamed text). This
module is the last-resort shipper: when a turn's text carries NO parseable
``::workflow{id="<run_id>"}`` directive, the cards for runs THIS session launched
inside the recency window are appended as bare lines, so the desktop directive
renderer (desktop/plugin.js DirectiveCard) renders even when the model never
pastes. The model's paste stays the primary path — this hook only fills silence.

Design notes:
* ONE-SHOT LEDGER (zero new files): a run's card counts as shipped when its
  events.jsonl carries a ``card.echoed`` marker (appended on CONFIRMATION,
  below; a failed write costs only a re-ship next turn, never a lost turn).
  run.json stays byte-identical.
* SHIPPED MEANS SELECTED (#168 P1): core's dispatch (plugins_dispatch.invoke_hook)
  fires EVERY transform_llm_output callback and apply_llm_output_transform keeps
  the FIRST non-empty string — so a return value is a HOPE, not a shipment.
  A proposal is therefore recorded in-memory (_PENDING) and the card.echoed
  marker is written only on CONFIRMATION that the text was selected:
  (1) the returned text is touched — core truth-tests each result at selection
      time (isinstance + bool) and str-manipulates the winner, so any attribute
      access or bool coercion of our return proves delivery;
  (2) at the session's next hook call, a still-referenced proposal text is
      treated as the persisted winner (a discarded text dies with the dispatch
      results list);
  (3) an optional module-level ``_witness`` callable (test seam / durable-row
      probe) vouches for the committed row directly and suppresses (1).
  An unconfirmed proposal is simply dropped — the card replays next turn
  instead of being silently lost. A second proposal for the SAME (session,
  turn) can never win (first non-empty already holds) and returns None.
* PASTE RETIREMENT (#168 P2): a bare directive seen in this session's turn text
  retires that run's owed card PER RUN (a sibling run's card is untouched),
  even when the directive arrived through a different route (model paste);
  a fenced/inline-code directive is dead text and retires nothing.
* FENCE TRAP (#168 P3): appending into a text that ends INSIDE an open ```
  fence buries the card renderer-dead while the ledger says shipped — the
  append closes the open fence first so the card always lands outside every
  fence, as the final lines of the text.
* RECOGNITION parity with the directive renderer: the exact form
  ``::workflow{id="<run_id>"}`` with run_id matching [A-Za-z0-9._-]+, OUTSIDE any
  ``` fence or `inline code` span — a code-blocked directive is dead text to the
  renderer, so it does NOT count as shipped (the paste hint says the same).
* FAIL-OPEN: every path is guarded; any exception means "ship nothing, change
  nothing". A broken ledger must never eat the user's reply.
* The unknown surface (falsy platform) is never guessed: no surface, no append.

Path resolution is NOT reimplemented: the door injects its bound wfcommon
instance via bind() and every root comes from the existing resolvers
(runs_root / profiles_root+profile_home / launch_runs_root legacy).
"""
import json
import logging
import re
import weakref
from datetime import datetime, timezone
from typing import Any, Callable, Optional

_LOG = logging.getLogger(__name__)

# Cards appended per turn. ponytail: the launch turn carries one fan-out burst
# (1-3 launches is the measured shape); 3 keeps a runaway loop honest. Upgrade
# path: raise the constant (or move it to owner settings) once bursts > 3 are
# measured — the ledger makes every later card ship on a later turn anyway.
MAX_CARDS_PER_TURN = 3

DEFAULT_WINDOW_MINUTES = 30          # launched this recently = the launch turn's window
WINDOW_SETTING = "card_window_minutes"  # plugins.entries.duckwork-workflows.settings.<k>
TERMINAL_STALE_MINUTES = 10          # done-and-stale runs are past the ship moment: never spam

_DIRECTIVE = re.compile(r'::workflow\{id="([A-Za-z0-9._-]+)"\}')
_FENCE_MARK = ("```", "~~~")
_INLINE_CODE = re.compile(r"`[^`\n]*`")

_COMMON: Any = None   # the door's bound wfcommon (bind())
_CARD: Optional[Callable[[str], str]] = None   # the door's _card helper (bind()) — one card grammar, no fork
# In-memory proposal ledger (#168 P1): (session_id, run_id) ->
# {"dir": run dir, "turn_id": str, "ref": weakref to the proposed text}.
# Nothing reaches events.jsonl until a proposal is CONFIRMED selected; a
# proposal whose text died unconfirmed is dropped so the card replays.
_PENDING: dict = {}
# Paste retirement (#168 P2): (session_id, run_id) whose bare directive was
# seen in this session's turn text — delivered through the paste route, so
# the owed card retires WITHOUT a card.echoed marker.
_RETIRED = set()
# (session_id, turn_id) -> True once this hook proposed text for that turn:
# a second proposal in the same turn (duplicate registration / in-turn retry)
# can never be selected (first non-empty wins), so it ships nothing.
_PROPOSED = {}
_witness: Optional[Callable[..., bool]] = None   # durable-row probe (test seam)


def bind(common, card_fn):
    """Wire the door's shared read model and card grammar into this module."""
    global _COMMON, _CARD
    _COMMON, _CARD = common, card_fn


def _strip_code(text):
    """Blank out ```/~~~ fenced blocks and `inline code` spans (line-wise), so a
    directive that only lives inside code never reads as shipped."""
    out, fence = [], None
    for line in text.splitlines():
        stripped = line.lstrip()
        if fence is None:
            if stripped.startswith(_FENCE_MARK):
                fence = stripped[:3]
                out.append("")
            else:
                out.append(_INLINE_CODE.sub("", line))
        else:
            out.append("")
            if stripped.startswith(fence):
                fence = None
    return "\n".join(out)


def _bare_directive_ids(text):
    """Run ids whose directive appears LIVE (outside any fence / inline-code
    span) in this turn's text — the renderer will see them; fenced examples
    are dead text and never qualify."""
    return _DIRECTIVE.findall(_strip_code(text))


def _open_fence(text):
    """The fence marker (``` or ~~~) the text ENDS inside, or None. Line-wise
    toggle parity, same walk the recognition path uses."""
    open_mark = None
    for line in text.splitlines():
        stripped = line.lstrip()
        if open_mark is None:
            if stripped.startswith(_FENCE_MARK):
                open_mark = stripped[:3]
        elif stripped.startswith(open_mark):
            open_mark = None
    return open_mark


def _age_minutes(ts, now):
    """Minutes before `now` of an ISO ts; None when unparseable (unreadable clock
    = not discoverable, fail-open)."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 60.0


def _events(r):
    """events.jsonl lines as dicts; torn/unreadable lines are skipped, never fatal."""
    try:
        lines = (r / "events.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict):
            out.append(e)
    return out


def _roots():
    """Every runs root this session's launches could have landed in — the resolved
    root, EVERY profile root (a profile-scoped gateway lands runs under its own
    home), and the legacy launch root. Existing resolvers only; deduped."""
    roots = [_COMMON.runs_root(), _COMMON.launch_runs_root()]
    try:
        pr = _COMMON.profiles_root()
        if pr.is_dir():
            for child in sorted(pr.iterdir()):
                if child.is_dir():
                    # A profile-scoped gateway resolves duckwork_home() to its own
                    # home, so its runs land under <profile_home>/workflows —
                    # answered by the SAME resolver, not a re-typed path law.
                    roots.append(_COMMON.effective_runs_root(
                        {"WF_RUNS_ROOT": "", "DUCKWORK_HOME": str(child)}))
    except OSError:
        pass
    seen, out = set(), []
    for p in roots:
        key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _terminal_stale(r, now):
    """A run whose completion (run.done) happened more than TERMINAL_STALE_MINUTES
    ago is past the ship moment — the card belongs to the launch turn, and old
    runs must never be spammed. Completion is read from events.jsonl (the
    runner's record) or the run.done marker file's mtime."""
    done_ages = [a for e in _events(r) if e.get("event") == "run.done"
                 and (a := _age_minutes(e.get("ts"), now)) is not None]
    if done_ages:
        return min(done_ages) > TERMINAL_STALE_MINUTES
    try:
        marker = (r / "run.done")
        if marker.exists():
            age = (now.timestamp() - marker.stat().st_mtime) / 60.0
            return age > TERMINAL_STALE_MINUTES
    except OSError:
        pass
    return False


def _outstanding(session_id, now):
    """Run ids launched by this session, inside the window, card still unshipped —
    newest first (started desc)."""
    window = DEFAULT_WINDOW_MINUTES
    try:
        cfg = _COMMON.owner_setting(WINDOW_SETTING)
        if type(cfg) is int and 0 < cfg <= 24 * 60:
            window = cfg
    except Exception:
        pass
    hits = []
    # est-2ek.1.762 census hygiene: one pass through wfcommon.iter_run_dirs —
    # unique by run-dir NAME across every root this session could have hit
    # (symlinked profile roots multiply hits; the same launch must not be
    # proposed three times).
    for r in _COMMON.iter_run_dirs(_roots()):
        try:
            meta = _COMMON.jload(r / "run.json")
            if not isinstance(meta, dict):
                continue
            owner = meta.get("owner") or {}
            if not isinstance(owner, dict) or owner.get("session_id") != session_id:
                continue
            age = _age_minutes(meta.get("started") or meta.get("started_at"), now)
            if age is None or age < 0 or age > window:
                continue
            if any(e.get("event") == "card.echoed" for e in _events(r)):
                continue
            if (session_id, r.name) in _RETIRED or (session_id, r.name) in _PENDING:
                continue          # pasted (retired) or a live proposal covers it
            if _terminal_stale(r, now):
                continue
            hits.append((age, r.name, r))
        except Exception:
            continue        # a torn run dir is invisible, never an exception upward
    hits.sort(key=lambda t: (t[0], t[1]))   # ascending age = newest launch first
    return [(rid, r) for _, rid, r in hits]


def _mark(r, session_id, turn_id):
    """Append the card.echoed marker. Best-effort: a failed write means the card
    ships once more next turn — never raise, never lose the text."""
    try:
        with (r / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "event": "card.echoed",
                 "session_id": session_id, "turn_id": turn_id},
                ensure_ascii=False) + "\n")
    except Exception as exc:
        _LOG.debug("card.echoed marker failed for %s: %s", r, exc)


def _confirm(session_id, run_id, entry):
    """Write the card.echoed marker for a proposal proven SELECTED and clear the
    pending entry. Marker-write failure still clears: the fail-open law says a
    dead ledger must not suppress forever — the card re-ships next turn."""
    _PENDING.pop((session_id, run_id), None)
    _mark(entry["dir"], session_id, entry["turn_id"])


def _reconcile(session_id, turn_id):
    """Decide the fate of PROPOSALS FROM EARLIER TURNS at this session's next
    call. Confirmed (delivered) -> stamp card.echoed; denied -> drop the entry
    so the card replays. A discarded text dies with the dispatch results list;
    a still-referenced one is the persisted winner. With ``_witness`` bound the
    probe answers instead (durable-row truth, same shape as the reconcile probe
    for #161's notice belt)."""
    for key in [k for k in _PENDING if k[0] == session_id]:
        entry = _PENDING[key]
        if entry.get("turn_id") == turn_id:
            continue                        # this turn proposed it; selection hasn't run
        rid = key[1]
        try:
            if _witness is not None:
                ok = bool(_witness(session_id=session_id,
                                   turn_id=entry.get("turn_id", ""), run_id=rid))
            else:
                ref = entry.get("ref")
                ok = bool(ref) and ref() is not None
            if ok:
                _confirm(session_id, rid, entry)
            else:
                _PENDING.pop(key, None)     # never selected: replayable, not lost
        except Exception as exc:
            _LOG.debug("card pending reconcile skipped for %s (fail-open): %s", rid, exc)
            _PENDING.pop(key, None)


class _CardText(str):
    """The augmented reply. A str in every respect, plus the #168 P1 witness:
    core selection (``isinstance(r, str) and r``) truth-tests and str-methods
    the WINNER and only the winner, so the first attribute access or bool
    coercion of this object proves it was selected -> stamp the ledger then.
    A loser is never touched again after being appended to the results list."""

    def __new__(cls, text, entries, session_id, turn_id):
        self = str.__new__(cls, text)
        self._ce_entries = entries          # [(run_id, run dir)]
        self._ce_session = session_id
        self._ce_turn = turn_id
        self._ce_done = False
        return self

    def _ce_confirm(self):
        if object.__getattribute__(self, "_ce_done"):
            return
        if _witness is not None:
            return                          # the probe alone vouches (witness mode)
        entries = object.__getattribute__(self, "_ce_entries")
        sid = object.__getattribute__(self, "_ce_session")
        turn = object.__getattribute__(self, "_ce_turn")
        object.__setattr__(self, "_ce_done", True)
        for rid, r in entries:
            entry = _PENDING.get((sid, rid))
            if entry is not None and entry.get("dir") == r:
                _confirm(sid, rid, entry)

    def __bool__(self):
        try:
            self._ce_confirm()
        except Exception as exc:            # fail-open: never break selection
            _LOG.debug("card confirm skipped (fail-open): %s", exc)
        return True                         # non-empty by construction

    def __getattribute__(self, name):
        if not name.startswith("_ce_"):
            try:
                object.__getattribute__(self, "_ce_confirm")()
            except Exception as exc:
                _LOG.debug("card confirm skipped (fail-open): %s", exc)
        return object.__getattribute__(self, name)


def _propose(response_text, take, session_id, turn_id):
    """Build the augmented text as a _CardText and register the proposals. The
    weakref callback (not a __del__ hook) drops an unconfirmed proposal the
    moment core discards the text, keeping the card replayable."""
    text = response_text.rstrip() + "\n\n" + "\n\n".join(_CARD(rid) for rid, _ in take)
    open_mark = _open_fence(response_text)
    if open_mark:                           # fence trap (#168 P3): never ship buried
        text = response_text.rstrip() + "\n\n" + open_mark + "\n\n" + \
            "\n\n".join(_CARD(rid) for rid, _ in take)
    obj = _CardText(text, [(rid, r) for rid, r in take], session_id, turn_id)
    keys = []
    for rid, r in take:
        key = (session_id, rid)
        _PENDING[key] = {"dir": r, "turn_id": turn_id,
                         "ref": weakref.ref(obj,
                                            lambda _r, k=key: _PENDING.pop(k, None))}
        keys.append(key)
    _PROPOSED[(session_id, turn_id)] = True
    if len(_PROPOSED) > 4096:
        _PROPOSED.clear()                   # a turn key is turn-scoped; a full table just re-arms
    if len(_RETIRED) > 4096:
        _RETIRED.clear()
    return obj


def _card_hook(response_text, session_id, turn_id="", model="", platform="", **_):
    """transform_llm_output callback: append outstanding cards, or return None.

    Fail-open law: any exception returns None — the user's reply is never eaten
    or blocked by this module. Nothing under .github is ever touched."""
    try:
        if _CARD is None or _COMMON is None:
            return None                 # unbound module = door never registered: no-op
        if not isinstance(response_text, str) or not response_text:
            return None                 # no final text: nothing to attach to
        if not platform:
            return None                 # unknown surface — never guess where this renders
        if not session_id:
            return None
        # Turn ledger bookkeeping first: last turn's hopes are settled against
        # this call (#168 P1 — shipped means SELECTED, not returned).
        _reconcile(session_id, turn_id)
        ids = _bare_directive_ids(response_text)
        if ids:
            for rid in ids:             # paste route delivered: retire THAT run
                _RETIRED.add((session_id, rid))
                _PENDING.pop((session_id, rid), None)
            return None                 # the model pasted (unfenced): hands off
        if _PROPOSED.get((session_id, turn_id)):
            return None                 # this turn already proposed; a duplicate
                                        # registration can never win selection
        now = datetime.now(timezone.utc)
        pending, seen_rid = [], set()
        for rid, r in _outstanding(session_id, now):
            if rid in seen_rid:
                continue                # same run visible under two roots: ship once
            seen_rid.add(rid)
            pending.append((rid, r))
        if not pending:
            return None
        take = pending[:MAX_CARDS_PER_TURN]
        if not take:
            return None                 # no proposal may carry the empty string:
                                        # core keeps non-None results and an
                                        # empty winner would hijack the reply
        return _propose(response_text, take, session_id, turn_id)
    except Exception as exc:
        _LOG.debug("card enforcement skipped (fail-open): %s", exc)
        return None
