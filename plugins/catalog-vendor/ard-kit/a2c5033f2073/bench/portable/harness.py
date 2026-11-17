#!/usr/bin/env python3
"""Portable, deterministic ard-kit retrieval benchmark.

The sibling bench/bench.py measures the LIVE station registry (127.0.0.1:8390 +
a bearer token from ~/.config/secrets) against a ripgrep baseline over the whole
workstation. That is useful but not portable: it needs station directories and a
secrets file, and it compares retrieval against grep rather than pinning it.

This harness answers a narrower, reproducible question: given a SMALL harmless
fixture corpus (scripts, package bin commands, Skills, MCP cards) and a frozen
set of gold labels (refs.json), does the production scorer return the right
capability -- and how big is the answer? It runs from a clean checkout with no
station paths and no secrets:

  1. catalogize the fixture corpus in-process (subprocess, --host bench.local);
  2. normalize the corpus absolute root to <CORPUS> so served bytes are identical
     wherever the checkout lives (only url/metadata.path/metadata.workspace carry
     it -- never a scored field, so ranking is untouched);
  3. serve the normalized catalog through the REAL ard_kit.registry.make_handler
     on an ephemeral 127.0.0.1 port with token=None (no secrets), and POST each
     query to /search -- true wire bytes, no re-implementation drift.

It reports three things HONESTLY and by their real names: SEARCH QUALITY
(P@1/P@5/MRR), RESPONSE SIZE (HTTP body bytes) and LATENCY (wall ms/query).
Response bytes are NOT tokens spent, and latency is in-process, so it is excluded
from the frozen digest. This is retrieval quality, NOT agent task success -- the
agent A/B is a separate experiment.

Gold labels allow SEVERAL correct tools (multi-gold): a tie between two fitting
capabilities is a pass, not an arbitrary pick. The ru group documents a measured
cross-lingual limitation: the [a-z0-9]+ tokenizer reduces pure Cyrillic to an
empty token set, so the scorer returns the WHOLE catalog at score 0 and the
intended tool is not ranked. That gap is reported, NOT fixed here.

ponytail: refs.json labels were authored against the real search_catalog output,
not predicted, and are frozen. Do NOT re-freeze expected.json to make a regression
look like a pass -- the drift diagnostic separates "behavior changed" from
"corpus changed" from "scorer code changed" precisely so a real change is visible.

Usage:
    python3 bench/portable/harness.py               # run, report, compare to expected.json
    python3 bench/portable/harness.py --freeze      # pin this run into expected.json
    python3 bench/portable/harness.py --selfcheck   # pure-helper asserts; no server/network
    python3 bench/portable/harness.py --json out.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent              # bench/portable
PKG = HERE.parent.parent                            # products/ard-kit (holds ard_kit/)
CORPUS = HERE / "corpus"
REFS = HERE / "refs.json"
EXPECTED = HERE / "expected.json"
DOMAIN = "bench.local"
PAGE = 20
DIRS = ("scripts", "skills")                        # cli (package.json) + mcp (.mcp.json) are auto
PLACEHOLDER = "<CORPUS>"

if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))


# --- pure helpers (selfcheck covers these; no I/O, no server) ---

def _ident_key(urn: str) -> str:
    """Domain-independent gold key: the identifier tail after 'urn:air:<domain>:'."""
    return ":".join(urn.split(":")[3:])


def _rank_of(ranked: list[str], gold: set[str]) -> int:
    """1-based rank of the first gold key surfaced, or 0 if none was (mirrors bench.py)."""
    for i, k in enumerate(ranked, 1):
        if k in gold:
            return i
    return 0


def _metrics(rank: int) -> tuple[int, int, float]:
    return (1 if rank == 1 else 0,
            1 if 1 <= rank <= 5 else 0,
            (1.0 / rank) if rank else 0.0)


def _normalize(obj: Any, root: str, placeholder: str = PLACEHOLDER) -> Any:
    """Recursively replace the corpus absolute root in every string.

    Makes served bytes identical across environments (station vs a fresh clone at
    a different path). Touches only url / metadata.path / metadata.workspace --
    never displayName/description/aliases/tags/representativeQueries -- so ranking
    is unaffected.
    """
    if isinstance(obj, str):
        return obj.replace(root, placeholder)
    if isinstance(obj, dict):
        return {k: _normalize(v, root, placeholder) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize(v, root, placeholder) for v in obj]
    return obj


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _code_sha() -> str:
    """Pin the scorer code version: sha256 over the sorted ard_kit/*.py contents."""
    h = hashlib.sha256()
    for py in sorted((PKG / "ard_kit").glob("*.py")):
        h.update(py.name.encode("utf-8"))
        h.update(py.read_bytes())
    return h.hexdigest()


def _digest(corpus_version: str, domain: str, page_size: int, frozen: list[dict]) -> str:
    """Reproducibility artifact: everything except latency (non-deterministic)."""
    return _sha(_canonical({"corpusVersion": corpus_version, "domain": domain,
                            "pageSize": page_size, "outcomes": frozen}))


# --- catalog build + in-process registry ---

def build_catalog(tmp: Path, corpus: Path, domain: str,
                  dirs: tuple[str, ...]) -> tuple[Path, str]:
    """Catalogize the fixture corpus, normalize it, return (path, catalog_sha)."""
    raw = tmp / "catalog.raw.json"
    cmd = [sys.executable, "-m", "ard_kit.catalogize", "--workspace", str(corpus),
           "--host", domain, "--output", str(raw), "--quiet"]
    for d in dirs:
        cmd += ["--dir", d]
    proc = subprocess.run(cmd, cwd=str(PKG), capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"catalogize failed (rc={proc.returncode}):\n{proc.stderr}")
    cat = json.loads(raw.read_text(encoding="utf-8"))
    norm = _normalize(cat, str(corpus.resolve()))
    norm_path = tmp / "catalog.json"
    norm_path.write_text(json.dumps(norm, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    return norm_path, _sha(_canonical(norm))


@contextmanager
def serve(catalog_path: Path, domain: str, public_url: str):
    """Serve the normalized catalog through the REAL handler; yield the port."""
    from ard_kit.registry import make_handler        # deferred: --selfcheck stays hermetic
    base = make_handler(catalog_path, domain, public_url, [], None)

    class _Quiet(base):                               # silence per-request stderr spam
        def log_message(self, *a: Any) -> None:
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Quiet)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def search(port: int, query: str, page_size: int) -> tuple[int, dict, float]:
    body = json.dumps({"query": {"text": query}, "pageSize": page_size}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{port}/search", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    return len(raw), json.loads(raw), (time.perf_counter() - t0) * 1000


def _run_query(port: int, item: dict, group: str, page_size: int) -> dict:
    query = item["q"]
    gold = set(item.get("gold", []))
    nbytes, data, ms = search(port, query, page_size)
    results = data.get("results", [])
    ranked = [_ident_key(r.get("identifier", "")) for r in results
              if r.get("score", 0) > 0]
    return {
        "group": group, "q": query, "kind": item.get("kind"),
        "gold": sorted(gold), "rank": _rank_of(ranked, gold),
        "matched": len(ranked), "total": int(data.get("totalResults", 0)),
        "bytes": nbytes, "top": ranked[0] if ranked else None, "ms": round(ms, 3),
    }


# --- reporting ---

def _print_group(name: str, rows: list[dict]) -> None:
    n = len(rows)
    med_bytes = statistics.median([r["bytes"] for r in rows])
    print(f"\n=== {name} ({n} queries) ===")
    if all(not r["gold"] for r in rows):              # negative group
        empty_ok = sum(1 for r in rows if r["total"] == 0)
        print(f"correctly-empty={empty_ok}/{n}  (totalResults==0 -> can say 'no such capability')"
              f"  median-bytes={med_bytes:.0f}")
        for r in rows:
            flag = "ok" if r["total"] == 0 else f"FALSE-POSITIVE total={r['total']}"
            print(f"  [{flag}] {r['q']!r}")
        return
    p1 = sum(_metrics(r["rank"])[0] for r in rows) / n
    p5 = sum(_metrics(r["rank"])[1] for r in rows) / n
    mrr = sum(_metrics(r["rank"])[2] for r in rows) / n
    nf = sum(1 for r in rows if r["rank"] == 0)
    print(f"P@1={p1:.2f}  P@5={p5:.2f}  MRR={mrr:.3f}  not-found={nf}/{n}"
          f"  median-bytes={med_bytes:.0f}")
    for kind in sorted({r["kind"] for r in rows if r.get("kind")}):
        krows = [r for r in rows if r.get("kind") == kind]
        ranked_ok = sum(1 for r in krows if r["rank"] >= 1)
        tail = (" -- tokenizer-blind: pure Cyrillic -> empty token set -> "
                "whole catalog at score 0" if kind == "cyrillic-blind" else "")
        print(f"  {kind} ({len(krows)}): ranked {ranked_ok}/{len(krows)}{tail}")
    for r in rows:
        rk = r["rank"] or "-"
        print(f"  rank={rk:>2} matched={r['matched']:>2} total={r['total']:>2}"
              f" bytes={r['bytes']:>5} top={r['top']}  {r['q']!r}")


def run(args: argparse.Namespace) -> int:
    refs = json.loads(Path(args.refs).read_text(encoding="utf-8"))
    corpus_version = str(refs.get("corpusVersion", "1"))
    domain = args.domain or refs.get("domain", DOMAIN)
    page_size = args.page_size or int(refs.get("pageSize", PAGE))
    public_url = f"https://{domain}"
    corpus = Path(args.corpus)

    tmp = Path(tempfile.mkdtemp(prefix="ardbench-"))
    try:
        norm_path, catalog_sha = build_catalog(tmp, corpus, domain, DIRS)
        code_sha = _code_sha()
        with serve(norm_path, domain, public_url) as port:
            outcomes = [_run_query(port, item, g["name"], page_size)
                        for g in refs["groups"] for item in g["queries"]]
    finally:
        if args.keep_tmp:
            print(f"[kept tmp] {tmp}", file=sys.stderr)
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    frozen = [{k: v for k, v in o.items() if k != "ms"} for o in outcomes]
    digest = _digest(corpus_version, domain, page_size, frozen)

    print(f"ard-kit portable benchmark -- corpus v{corpus_version}, domain {domain}, "
          f"pageSize {page_size}")
    print("measures SEARCH QUALITY (P@1/P@5/MRR), RESPONSE SIZE (bytes), LATENCY (ms).")
    print("bytes = HTTP response bytes, NOT tokens spent; latency in-process, excluded from digest.")
    order: list[str] = []
    for o in outcomes:
        if o["group"] not in order:
            order.append(o["group"])
    for name in order:
        _print_group(name, [o for o in outcomes if o["group"] == name])
    all_ms = [o["ms"] for o in outcomes]
    print(f"\nlatency p50={statistics.median(all_ms):.1f}ms/query (in-process, excluded from digest)")
    print(f"corpusVersion={corpus_version}  catalogSha={catalog_sha[:12]}  "
          f"codeSha={code_sha[:12]}  digest={digest[:12]}")

    exp_path = Path(args.expected)
    expected = json.loads(exp_path.read_text(encoding="utf-8")) if exp_path.exists() else None

    if args.json:
        Path(args.json).write_text(json.dumps({
            "corpusVersion": corpus_version, "domain": domain, "pageSize": page_size,
            "catalogSha": catalog_sha, "codeSha": code_sha, "digest": digest,
            "expected": expected, "outcomes": outcomes,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")

    if args.freeze:
        exp_path.write_text(json.dumps({
            "corpusVersion": corpus_version, "domain": domain, "pageSize": page_size,
            "catalogSha": catalog_sha, "codeSha": code_sha, "digest": digest,
            "outcomes": frozen,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nfroze {exp_path.name}: digest={digest[:12]} "
              f"catalog={catalog_sha[:12]} code={code_sha[:12]}")
        return 0

    if expected is None:
        print(f"\nno frozen reference ({exp_path.name} missing) -- run --freeze to pin this result")
        return 0

    diffs = []
    if expected.get("digest") != digest:
        diffs.append(("digest", "retrieval behavior changed (rank/bytes/total differ)"))
    if expected.get("catalogSha") != catalog_sha:
        diffs.append(("catalogSha", "corpus or catalogize output changed"))
    if expected.get("codeSha") != code_sha:
        diffs.append(("codeSha", "ard_kit scorer code changed"))
    if not diffs:
        print(f"\n{exp_path.name} MATCH -- reproducible (digest {digest[:12]})")
        return 0
    print(f"\nDRIFT vs {exp_path.name}:")
    for name, why in diffs:
        print(f"  {name}: {why}")
    print("  investigate; re-freeze ONLY if the change is intended "
          "(do not rewrite refs to flatter numbers)")
    return 1


def selfcheck() -> int:
    """Pure-helper asserts only: no catalogize, no server, no network, no LLM."""
    assert _ident_key("urn:air:bench.local:script:scripts:word_count") == "script:scripts:word_count"
    assert _ident_key("urn:air:other.example:skill:skills:pdf-extract") == "skill:skills:pdf-extract"
    assert _ident_key("urn:air:bench.local:cli:archive-pack") == "cli:archive-pack"
    assert _ident_key("urn:air:bench.local:script:scripts:git_summary.sh") == "script:scripts:git_summary.sh"

    assert _rank_of(["a", "b", "c"], {"c"}) == 3
    assert _rank_of(["a", "b"], {"z"}) == 0
    assert _rank_of(["x", "a"], {"a", "x"}) == 1          # multi-gold: first surfaced wins
    assert _rank_of([], {"a"}) == 0
    assert _metrics(1) == (1, 1, 1.0)
    assert _metrics(2) == (0, 1, 0.5)
    assert _metrics(7) == (0, 0, 1 / 7)
    assert _metrics(0) == (0, 0, 0.0)

    sample = {"url": "file:///abs/corpus/scripts/x.py",
              "metadata": {"path": "/abs/corpus/.mcp.json", "workspace": "/abs/corpus"},
              "description": "no path here", "tags": ["a", "b"]}
    norm = _normalize(sample, "/abs/corpus")
    assert norm["url"] == "file://<CORPUS>/scripts/x.py"
    assert norm["metadata"] == {"path": "<CORPUS>/.mcp.json", "workspace": "<CORPUS>"}
    assert norm["description"] == "no path here"          # scored prose untouched
    assert norm["tags"] == ["a", "b"]

    assert _sha(_canonical({"b": 1, "a": 2})) == _sha(_canonical({"a": 2, "b": 1}))
    assert len(_sha(b"x")) == 64
    assert _digest("1", "d", 20, [{"q": "x", "rank": 1}]) == \
        _digest("1", "d", 20, [{"q": "x", "rank": 1}])
    assert _digest("1", "d", 20, [{"q": "x", "rank": 1}]) != \
        _digest("1", "d", 20, [{"q": "x", "rank": 2}])
    print("selfcheck OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="portable deterministic ard-kit retrieval benchmark")
    ap.add_argument("--corpus", default=str(CORPUS), help="fixture corpus dir")
    ap.add_argument("--refs", default=str(REFS), help="gold-label refs json")
    ap.add_argument("--expected", default=str(EXPECTED), help="frozen reference json")
    ap.add_argument("--domain", default=None, help="override refs.domain")
    ap.add_argument("--page-size", type=int, default=None, help="override refs.pageSize")
    ap.add_argument("--json", default=None, metavar="OUT", help="write full machine-readable report")
    ap.add_argument("--freeze", action="store_true", help="write expected.json from this run")
    ap.add_argument("--selfcheck", action="store_true", help="pure-helper asserts; no server/network")
    ap.add_argument("--keep-tmp", action="store_true", help="do not delete the temp catalog dir")
    args = ap.parse_args(argv)
    if args.selfcheck:
        return selfcheck()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
