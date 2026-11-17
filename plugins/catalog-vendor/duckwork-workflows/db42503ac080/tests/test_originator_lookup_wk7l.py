#!/usr/bin/env python3
"""est-wk7l — the originating-agent lookup must be root-normalized, root-scoped,
and never substitute another root's answer (independent-review findings at PR #156
head 992416a; runtime-proven by the committee's probe_originator.py).

Findings pinned here, one check each:
  B1  a NAMED-profile home (…/profiles/<name>) must resolve through the repo's own
      profiles_root()/duckwork_root() normalizers — the raw `home/"profiles"` join
      looked INSIDE the profile and found nothing (probe: profile_scoped_scan={}).
  B2  the ROOT default profile's state.db (root/state.db) participates; a session
      owned by the root/default profile resolves instead of falling through.
  B3  the TTL cache is keyed by the NORMALIZED root: sweeping root B within root
      A's TTL returns B's map, never A's (probe: same-session stayed 'alpha' after
      switching home to estate-b).
  B4  a different root whose sweep yields NOTHING contributes nothing — the old
      map of a DIFFERENT root is never retained across it (probe: empty_home kept
      the old labels after TTL expiry).
  B5  absent/empty/foreign-schema dbs contribute no rows and never raise.

Red-proof (pre-fix head 992416a): B1-B4 all FAIL (B1 {} vs {'beta-session':'beta'},
B2 default-session absent, B3 wrong_home_attribution='alpha', B4 keeps old labels);
B5 passes pre-fix and must stay green.
"""
import json, shutil, sqlite3, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import wfcommon

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

FIX = HERE / ".tmp-wk7l"
shutil.rmtree(FIX, ignore_errors=True)
A = FIX / "estate-a"; B = FIX / "estate-b"; EMPTY = FIX / "empty-estate"

def db(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, profile_name TEXT)")
        c.execute("DELETE FROM sessions")
        c.executemany("INSERT INTO sessions VALUES (?, ?)", rows)

# estate layout mirroring the field: root db owns the default profile's sessions;
# each named profile owns its own db under <root>/profiles/<name>/state.db.
db(A / "state.db", [("default-session", "default")])
db(A / "profiles/alpha/state.db", [("alpha-session", "alpha"), ("same-session", "alpha")])
db(B / "profiles/beta/state.db", [("beta-session", "beta"), ("same-session", "beta")])
EMPTY.mkdir(parents=True)

def reset():
    # force TTL expiry however the cache is structured
    c = wfcommon._profile_by_session_cache
    if isinstance(c, dict) and "at" in c:
        c["at"] = 0.0
        c["map"] = {}
    else:
        for v in c.values():
            if isinstance(v, dict):
                v["at"] = 0.0
                v["map"] = {}

# B2 — root default state.db participates
reset()
m = dict(wfcommon.profiles_by_session(A))
check("B2 root default profile db participates",
      m.get("default-session") == "default" and m.get("alpha-session") == "alpha",
      f"map={m}")

# B1 — named-profile home resolves via the normalizers: scanning from
# <root>/profiles/<name> must reach the ROOT's profiles census (sibling profiles),
# not a profiles dir inside the profile (the raw join found nothing — probe {}).
reset()
m_root = dict(wfcommon.profiles_by_session(A))
reset()
m_named = dict(wfcommon.profiles_by_session(A / "profiles" / "alpha"))
check("B1 named-profile home scans the normalized profiles root",
      m_named.get("alpha-session") == "alpha" and "beta-session" not in m_named,
      f"named={m_named} (root census for comparison: {m_root})")

# B3 — cache keyed by normalized root: a home switch within the TTL re-sweeps
reset()
wfcommon.profiles_by_session(A)
mB = dict(wfcommon.profiles_by_session(B))
check("B3 within-TTL home switch returns the NEW root's map (no substitution)",
      mB.get("same-session") == "beta" and "alpha-session" not in mB,
      f"map={mB}")

# B4 — a different empty root contributes nothing; no stale labels across roots
mB2 = dict(wfcommon.profiles_by_session(EMPTY))
check("B4 empty root yields nothing, old map of ANOTHER root never retained",
      mB2 == {}, f"map={mB2}")

# B5 — absent/empty/foreign-schema dbs: no rows, no raise
strange = FIX / "strange"
(strange / "profiles" / "gamma").mkdir(parents=True)
(strange / "profiles" / "gamma" / "state.db").write_bytes(b"not a sqlite file at all")
reset()
try:
    m = dict(wfcommon.profiles_by_session(strange))
    check("B5 foreign-schema db contributes nothing and never raises", m == {}, f"map={m}")
except Exception as e:
    check("B5 foreign-schema db contributes nothing and never raises", False, f"raised {e!r}")

shutil.rmtree(FIX, ignore_errors=True)
print("RESULT", "ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
