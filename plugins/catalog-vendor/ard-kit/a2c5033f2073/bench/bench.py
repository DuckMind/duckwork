#!/usr/bin/env python3
"""ard-kit retrieval benchmark: registry /search vs a ripgrep full-text baseline.

Both arms search the SAME corpus the registry indexes (CORPUS below must mirror
the --dir flags in scripts/systemd/ard-registry.service) and are scored against
hand-labeled gold tools (queries.json) with P@1 / P@5 / MRR, plus the candidate
pile each arm forces the agent to sift and the wall time each arm costs.

Queries are reported in two lanes. "tool" (the default) asks for a script or a
skill; "mcp" asks for a capability whose right answer is an MCP server card.
The lanes are scored separately because the card lane is structurally different:
every card shares one metadata.path (.mcp.json), so cards key by displayName,
and the ripgrep arm cannot surface a card at all -- .mcp.json holds no prose, so
grep of the corpus can only ever return a wrapper skill. Splitting the lanes
keeps the tool-lane headline comparable across runs instead of diluting it.

The question this answers: does querying ard-kit actually beat an agent's default
"just grep for it" discovery — and where does the lexical scorer fall down.

ponytail: the ripgrep arm is ranked by summed per-token match counts, which is
grep's *best* shot — real rg output is an unordered pile the agent eyeballs, so
this flatters the baseline. Upgrade path if the count-rank is ever disputed:
model an agent that greps only the single most-discriminative keyword.

Usage:
    python3 products/ard-kit/bench/bench.py             # run bench, print table
    python3 products/ard-kit/bench/bench.py --selfcheck # metric-math sanity
"""
from __future__ import annotations

import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent                      # repo root
QUERIES = HERE / "queries.json"
REG = os.environ.get("ARD_BENCH_REGISTRY", "http://127.0.0.1:8390")
TOKEN_ENV = Path("~/.config/secrets/ard-registry.env").expanduser()
# What the registry indexes: mirror of the --dir flags in the ard-registry unit
# plus the repo-root .mcp.json it always reads for server cards.
CORPUS = ["scripts", ".agents/skills",
          "tools/compound-engineering-plugin/skills",
          ".duckwork/profiles/redops/skills/redops",
          ".duckwork/skills/security/openspace-pentest",
          "products/web-check-mcp/skills/security/web-check-mcp",
          ".duckwork/profiles/producers/scripts",
          os.path.expanduser("~/projects/lyrics-kb"),
          ".mcp.json"]
PAGE = 20                                             # depth we rank / compute P@5 within
LANES = ("tool", "mcp")                               # reporting order
CARD_KEY = "mcp:"                                     # gold prefix for a server card

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset("a an and for of on the to with".split())   # mirrors registry.py


def _tool_key(path: str) -> str:
    """Collapse a file path to its tool identity.

    A skill dir is ONE tool: its SKILL.md and the scripts/references bundled
    beside it all key to the dir, so a gold label for the skill matches
    whichever of its files the registry surfaced. Detected by walking up to the
    nearest ancestor holding a SKILL.md rather than by hardcoding .agents/skills,
    because the registry now scans five skill roots.
    """
    p = Path(path.strip())
    for d in (p, *p.parents):
        if (ROOT / d / "SKILL.md").is_file():
            return d.as_posix()
    return p.as_posix()


def _entry_key(entry: dict) -> str:
    """Tool identity of a catalog entry.

    Cards all report metadata.path == .mcp.json, so keying them by path would
    collapse 19 servers into one tool; key by displayName instead.
    """
    if "mcp-server-card" in entry.get("type", ""):
        return CARD_KEY + entry.get("displayName", "")
    return _tool_key(entry.get("metadata", {}).get("path", ""))


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


def _bearer() -> str:
    for line in TOKEN_ENV.read_text().splitlines():
        if line.startswith("ARD_REGISTRY_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"no ARD_REGISTRY_TOKEN in {TOKEN_ENV}")


def arm_ardkit(query: str, tok: str) -> tuple[list[str], int]:
    """Ranked tool keys from the live registry /search, plus its totalResults."""
    body = json.dumps({"query": {"text": query}, "pageSize": PAGE}).encode()
    req = urllib.request.Request(
        REG + "/search", data=body,
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    keys: list[str] = []
    for e in data.get("results", []):
        k = _entry_key(e)
        if k and k not in keys:
            keys.append(k)
    return keys, int(data.get("totalResults", len(keys)))


def arm_ripgrep(query: str) -> tuple[list[str], int]:
    """Ranked tool keys from full-text grep: sum per-token match counts per file."""
    counts: dict[str, int] = {}
    for t in set(_tokens(query)):
        proc = subprocess.run(
            ["rg", "-F", "-c", "-i", "--no-messages", t, *CORPUS],
            cwd=ROOT, capture_output=True, text=True)
        for line in proc.stdout.splitlines():
            path, _, n = line.rpartition(":")
            if path and n.isdigit():
                k = _tool_key(path)
                counts[k] = counts.get(k, 0) + int(n)
    ranked = sorted(counts, key=lambda k: (-counts[k], k))
    return ranked, len(ranked)


def _rank_of(ranked: list[str], gold: set[str]) -> int:
    for i, k in enumerate(ranked, 1):
        if k in gold:
            return i
    return 0                                          # gold never surfaced


def _metrics(rank: int) -> tuple[int, int, float]:
    return (1 if rank == 1 else 0,
            1 if 1 <= rank <= 5 else 0,
            (1.0 / rank) if rank else 0.0)


def _blank() -> tuple[dict, dict, dict]:
    """Per-lane accumulators: metrics [p1, p5, rr, not-found], candidate piles, wall ms."""
    return ({lane: {"ard": [0, 0, 0.0, 0], "rg": [0, 0, 0.0, 0]} for lane in LANES},
            {lane: {"ard": [], "rg": []} for lane in LANES},
            {lane: {"ard": [], "rg": []} for lane in LANES})


def _report(agg: dict, cand: dict, ms: dict, lane: str, n: int) -> tuple[float, float]:
    """Print one lane's aggregate; return its (ard MRR, rg MRR)."""
    print(f"\n=== {lane} lane: aggregate over {n} labeled intent queries ===")
    for key, label in (("ard", "ard-kit /search"), ("rg", "ripgrep baseline")):
        p1, p5, rr, nf = agg[lane][key]
        med = statistics.median(cand[lane][key]) if cand[lane][key] else 0
        print(f"{label:<18} P@1={p1/n:.2f}  P@5={p5/n:.2f}  MRR={rr/n:.3f}  "
              f"not-found={nf}/{n}  median-candidates={med:.0f}")
    t = {k: statistics.median(ms[lane][k]) for k in ("ard", "rg") if ms[lane][k]}
    if len(t) == 2 and t["ard"] > 0:
        # The arms are timed interleaved per query, so this is a relative
        # comparison, not a clean latency profile: an ard-only loop over the same
        # queries measured p50 84.6ms (2026-09-05) against the 87-102ms here.
        print(f"{'wall time/query':<18} p50 ard={t['ard']:.0f}ms  rg={t['rg']:.0f}ms  "
              f"({t['rg'] / t['ard']:.1f}x)  "
              f"-> {'ard-kit is the faster arm too' if t['ard'] < t['rg'] else 'ripgrep is the faster arm'}")
    return agg[lane]["ard"][2] / n, agg[lane]["rg"][2] / n


def run() -> int:
    qs = json.loads(QUERIES.read_text())
    tok = _bearer()
    rows = []
    agg, cand, ms = _blank()
    counts = dict.fromkeys(LANES, 0)
    for item in qs:
        q = item["q"]
        lane = item.get("lane", "tool")
        if lane not in counts:
            raise SystemExit(f"{QUERIES.name}: unknown lane {lane!r}")
        gold = {_tool_key(g) for g in item["gold"]}
        t0 = time.perf_counter()
        a_keys, a_cand = arm_ardkit(q, tok)
        a_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        r_keys, r_cand = arm_ripgrep(q)
        r_ms = (time.perf_counter() - t0) * 1000
        a_rank, r_rank = _rank_of(a_keys, gold), _rank_of(r_keys, gold)
        a_m, r_m = _metrics(a_rank), _metrics(r_rank)
        for key, m, rk, c, t in (("ard", a_m, a_rank, a_cand, a_ms),
                                 ("rg", r_m, r_rank, r_cand, r_ms)):
            agg[lane][key][0] += m[0]; agg[lane][key][1] += m[1]
            agg[lane][key][2] += m[2]
            agg[lane][key][3] += 1 if rk == 0 else 0
            cand[lane][key].append(c)
            ms[lane][key].append(t)
        win = "ard" if a_m[2] > r_m[2] else "rg" if r_m[2] > a_m[2] else "="
        rows.append((lane, q, a_rank, a_cand, r_rank, r_cand, win))
        counts[lane] += 1

    W = min(max(len(r[1]) for r in rows) + 2, 54)
    print(f"{'lane':<5}{'query':<{W}} {'ard rk/cand':>13} {'rg rk/cand':>13}  win")
    print("-" * (W + 37))
    for lane, q, ar, ac, rr, rc, win in rows:
        a = f"{ar or '-'}/{ac}"
        g = f"{rr or '-'}/{rc}"
        print(f"{lane:<5}{q[:W-2]:<{W}} {a:>13} {g:>13}  {win}")

    mrrs = []
    for lane in LANES:
        if counts[lane]:
            mrrs.append((lane, *_report(agg, cand, ms, lane, counts[lane])))
    print()
    for lane, a_mrr, r_mrr in mrrs:
        verdict = ("ard-kit ranks the right tool higher" if a_mrr > r_mrr
                   else "ripgrep ranks the right tool higher" if r_mrr > a_mrr
                   else "dead heat on rank")
        print(f"{lane} lane MRR {a_mrr:.3f} (ard) vs {r_mrr:.3f} (rg): {verdict}.")
    return 0


def selfcheck() -> int:
    assert _tool_key(".agents/skills/jwt-attack/SKILL.md") == ".agents/skills/jwt-attack"
    assert _tool_key("scripts/ops/jwt_analyzer.py") == "scripts/ops/jwt_analyzer.py"
    # collapse is not .agents/skills-specific: the registry scans five skill roots
    assert _tool_key("tools/compound-engineering-plugin/skills/ce-debug/SKILL.md") == \
        "tools/compound-engineering-plugin/skills/ce-debug"
    # a script bundled inside a skill dir is the same tool as that skill
    assert _tool_key(".agents/skills/osint-autopilot/scripts/recon_pipeline.sh") == \
        ".agents/skills/osint-autopilot"
    # all 19 cards report metadata.path == .mcp.json; keying by path would merge them
    card = {"type": "application/mcp-server-card+json", "displayName": "web-check-mcp",
            "metadata": {"path": "/repo/.mcp.json"}}
    script = {"type": "application/vnd.ard-kit.script+json", "displayName": "x",
              "metadata": {"path": "scripts/x.py"}}
    assert _entry_key(card) == "mcp:web-check-mcp"
    assert _entry_key(script) == "scripts/x.py"
    assert _entry_key(card) != _entry_key({**card, "displayName": "openspace"})
    assert _rank_of(["a", "b", "c"], {"c"}) == 3
    assert _rank_of(["a", "b"], {"z"}) == 0
    assert _metrics(1) == (1, 1, 1.0)
    assert _metrics(2) == (0, 1, 0.5)
    assert _metrics(7) == (0, 0, 1 / 7)
    assert _metrics(0) == (0, 0, 0.0)
    assert _tokens("find a tool that Lists DNS records") == \
        ["find", "tool", "that", "lists", "dns", "records"]
    print("selfcheck OK")
    return 0


if __name__ == "__main__":
    sys.exit(selfcheck() if "--selfcheck" in sys.argv else run())
