#!/usr/bin/env python3
"""Minimal self-hosted ARD (Agentic Resource Discovery) registry.

Serves an ai-catalog.json produced by catalogize.py over the two surfaces
the ARD spec defines:

  - static manifest:  GET  /.well-known/ard.json
                      (also served at the predecessor paths
                      /.well-known/ai-catalog.json and /ai-catalog.json)
  - dynamic search:   POST /search   {"query": {"text": ..., "filter": {...}}}
                      -> one ranked page plus a pageToken cursor while more
                      local rows remain (spec 5.3.2, pageSize 1..100)
  - deterministic list: GET /agents?filter=&orderBy=&pageSize=&pageToken=
                      -> spec 5.3.4 browsing: stable order, no relevance,
                      never federated, answered as {items, total, pageToken}
  - explore:          POST /explore  {"resultType": {"facets": [{"field": ...}]}}
                      -> facet counts over the matched set (spec 5.3.3),
                      scoped to this registry; explore never federates

Extension (monid-style discover -> inspect -> run):

  - invoke schema:    GET  /inspect?identifier=<urn>  -> invoke + CLI arguments
    (served from the ai-catalog.inspect.json sidecar catalogize.py writes)
  - optional auth:    --token requires `Authorization: Bearer <token>` on
    every endpoint except /health
  - liveness:         GET  /health -> {status, version, auth, specVersion,
    entries, catalogGeneratedAt, catalog}; open by design, so --public-url
    narrows `catalog` to the file name instead of the local path

Search is a stdlib token-overlap scorer over displayName, description, tags,
aliases and representativeQueries. The catalog file is re-read on every
request, so re-running catalogize.py is picked up without a restart.

Federation (--upstreams): with `federation != "none"` in the request, the
query fans out to upstream ARD registries and merges their results
(fail-soft per upstream). totalResults counts each peer's own total for the
query rather than the rows its page returned, and a peer that still holds
rows past that page comes back as a referral, because a merged page carries
no cursor.
The manifest also advertises this registry itself
as an application/ai-registry+json entry so peers can discover its search URL.
Peer rows are screened by ard_kit.trust before they merge: a SUSPECT row is
dropped and logged to stderr rather than relayed into an agent's context.


ponytail: scorer is stem-folded token overlap, O(n) per query — fine up to
thousands of entries. The fold is not a real stemmer (certificates/certs,
enumerate/enum stay distinct), and that gap is measured, not worth closing:
an agentive/-ing fold moves bench P@1 by zero, and the field weights below
have no tuning band either — across a 25-point sweep every decisive margin is
≤0.056 of score between tools that both fit the query, and one baseline P@1
miss is an exact tie that the identifier string resolves, not a relevance
loss. Do not hand-tune either against a bench whose 37 queries mostly carry
one gold label. The live upgrade path is scale, not accuracy: an inverted
index or embeddings when the catalog outgrows the O(n) scan. Numbers in
docs/decisions.md.

Usage:
    python3 -m ard_kit.registry --catalog ai-catalog.json --host 127.0.0.1 \
        --port 8080 --domain scripts.local --upstreams https://peer.example.com
    ard-registry --catalog ai-catalog.json   # ard-registry.cmd on Windows
"""

from __future__ import annotations

import argparse
import base64
import bisect
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ard_kit import __version__, trust
from ard_kit.catalogize import guard_posix_paths

# ponytail: Unicode word chars minus '_'. Byte-identical to the old [a-z0-9]+ on
# pre-lowered ASCII, but a Cyrillic/Greek/CJK query or description now tokenizes
# instead of folding to set(). Ceiling: _STOPWORDS/_fold stay English-only, so
# non-ASCII function words pass through unfolded; upgrade path is a per-script
# stopword set, not embeddings (ULTRA_PLAN_V9 "Отложено").
_TOKEN = re.compile(r"[^\W_]+")
_STOPWORDS = frozenset("a an and for of on the to with".split())


def _fold(t: str) -> str:
    """Naive plural/verb-suffix fold so query and entry stems meet:
    subdomains->subdomain, cves->cve, prices->price, boxes->box,
    queries->query. Short acronyms (tls, dns, ips) and ss/us/is endings are
    left alone. ponytail: not a real stemmer — certificates/certs and
    enumerate/enum stay distinct. Adding agentive/-ing folding was measured at
    net zero P@1; see the module docstring before re-trying it."""
    if t.endswith("ies") and len(t) > 3:
        return t[:-3] + "y"
    if t.endswith(("ses", "xes", "zes", "ches", "shes")) and len(t) > 4:
        return t[:-2]
    if t.endswith("s") and not t.endswith(("ss", "us", "is")) and len(t) > 3:
        return t[:-1]
    return t


def _tokens(text: str) -> set[str]:
    return {
        _fold(t)
        for t in _TOKEN.findall(text.lower())
        if t not in _STOPWORDS
    }


def _field_text(value: Any) -> str:
    """Coerce one catalog field to searchable text without raising.

    A local catalog is operator-authored, but load_catalog does no shape
    validation, so a hand-edited or truncated entry can carry a non-str
    displayName or a list with non-str items. _tokens() calls text.lower() and
    " ".join() assumes an iterable of str; either raises straight out of
    score_entry, through search_catalog/explore_facets, and on the MCP lane out
    of serve() - killing the process. Fold the one bad field to "" so a
    malformed entry scores 0 instead of taking down the whole query.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(v for v in value if isinstance(v, str))
    return ""


def _dict_entries(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """The catalog's entry rows that are objects, in catalog order.

    _field_text folds a malformed FIELD to "" so one bad value scores 0
    instead of taking down the query; this is the sibling guard for a
    malformed ROW. load_catalog does no shape validation and the catalog is
    re-read every request, so a truncated write or a hand-edit can leave a
    null/str/number where an entry object belongs. Iterating that and calling
    entry.get()/entry.items() raises AttributeError out of search_catalog,
    explore_facets and list_agents (and a non-list `entries` raises TypeError
    out of the manifest route's list concat): one corrupt row then loses EVERY
    good row on /search, /explore, /agents and MCP ard_search, while
    ard_verify, trust.verdict_catalog and federated_search in the same process
    already skip it. Skip it here too, so every lane that reads the local
    catalog honours one degradation contract.

    A non-object CATALOG (top-level []/null/"x"/42) still raises at
    catalog.get() below and is contained to a clean 500 by the lane: that is a
    server misconfiguration, an honest 500, not a per-row defect (the 82488cb
    decision). Only content INSIDE an object catalog degrades - a non-list
    `entries` yields no rows, and non-dict rows are dropped, exactly as
    trust.verdict_catalog already does.
    """
    entries = catalog.get("entries", [])
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def score_entry(entry: dict[str, Any], query_tokens: set[str]) -> float:
    """Score an entry against query tokens; higher = better match.

    ponytail: these five weights are uncalibrated and not worth calibrating
    against bench/queries.json - reweighting does move P@1, but only by
    re-deciding ties and margins of ≤0.056. See the module docstring.
    """
    fields = [
        (_field_text(entry.get("displayName")), 3.0),
        (_field_text(entry.get("description")), 2.0),
        (_field_text(entry.get("aliases")), 2.0),
        (_field_text(entry.get("tags")), 2.0),
        (_field_text(entry.get("representativeQueries")), 1.5),
    ]
    score = 0.0
    for text, weight in fields:
        hit = query_tokens & _tokens(text)
        score += weight * len(hit) / max(len(query_tokens), 1)
    # Normalize by the total field weight. A full displayName hit used to
    # return 3.0, which the 0-100 band clamped to 100 along with every
    # other decent match. A constant divisor rescales without reordering.
    return round(score / sum(weight for _, weight in fields), 4)


def search_catalog(
    catalog: dict[str, Any],
    text: str,
    type_filter: list[str] | None,
    page_size: int,
    after: tuple[float, str] | None = None,
) -> tuple[int, list[dict[str, Any]], tuple[float, str] | None]:
    """Return (total matches, one page, key of the next page or None).

    Ranked by (score, identifier): a score tie used to fall back to catalog
    order, which moves when the catalog is regenerated, so a tie group cut by
    a page boundary handed the walking client one row twice and another never.
    `after` is a seek position, not an offset — rows added or removed mid-walk
    shift nothing that was already handed out.
    """
    qtokens = _tokens(text)
    results = []
    for entry in _dict_entries(catalog):
        if type_filter and entry.get("type") not in type_filter:
            continue
        s = score_entry(entry, qtokens) if qtokens else 0.0
        if qtokens and s <= 0:
            continue
        results.append(((s, str(entry.get("identifier", ""))), entry))
    results.sort(key=lambda pair: pair[0])
    keys = [pair[0] for pair in results]
    n = max(1, min(page_size, 100))
    # Highest rank first: the page ends at the cursor and grows backwards, so
    # deleting the cursor row itself still lands on the boundary it owned.
    hi = bisect.bisect_left(keys, after) if after is not None else len(keys)
    start = max(0, hi - n)
    page = [
        # score_entry returns a 0-1 value normalized by total field weight, so
        # the clamp is a guard against catalog-supplied scores, not calibration.
        # computed score last: a catalog-supplied "score" must not win.
        {**entry, "score": min(100, round(100 * s))}
        for (s, _), entry in results[start:hi][::-1]
    ]
    return len(results), page, (keys[start] if start > 0 else None)


def _as_int(value: Any, default: int) -> int:
    """Client-supplied number: fall back instead of raising out of a handler."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# Bumping this invalidates cursors already in flight instead of silently
# reading an old payload shape as a seek position.
_PAGE_TOKEN_VERSION = 2


def query_fingerprint(text: str, type_filter: list[str] | None) -> str:
    """Short digest of the query a cursor belongs to. Not a secret."""
    payload = json.dumps(
        [text, sorted(type_filter or [])], separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _page_token_encode(key: tuple, fingerprint: str) -> str:
    """Opaque cursor: a seek position plus the query it was minted for."""
    raw = json.dumps(
        {"v": _PAGE_TOKEN_VERSION, "k": list(key), "q": fingerprint},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    # Unpadded urlsafe base64: survives a query string or a JSON body.
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _page_token_decode(
    token: str, fingerprint: str, key_type: type
) -> tuple | None:
    """Seek position for this query, or None if the token is not usable here.

    A cursor replayed against a different text/filter would page through a
    different result set, so a fingerprint mismatch is refused rather than
    reinterpreted. Same for junk or a foreign version. The key shape is
    checked against the lane's own type because the fingerprint is not a
    secret: a hand-made token would reach bisect, and comparing a str against
    float scores raises straight out of the handler.
    """
    padded = token + "=" * (-len(token) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("v") != _PAGE_TOKEN_VERSION:
        return None
    if data.get("q") != fingerprint:
        return None
    key = data.get("k")
    if (
        not isinstance(key, list)
        or len(key) != 2
        or not isinstance(key[0], key_type)
        or not isinstance(key[1], str)
    ):
        return None
    return (key[0], key[1])


def _term_values(entry: dict[str, Any], path: str) -> list[str]:
    """Scalar values at a dotted term path, as facet bucket labels.

    Facet fields use the same syntax as filter keys (spec 5.3.1), so a path
    may cross a list of objects (trustManifest.attestations.type). That
    flattens rather than erroring; non-scalar leaves are skipped.
    """
    node: Any = entry
    for part in path.split("."):
        if isinstance(node, list):
            node = [item.get(part) for item in node if isinstance(item, dict)]
        elif isinstance(node, dict):
            node = node.get(part)
        else:
            return []
    values = node if isinstance(node, list) else [node]
    out: list[str] = []
    for value in values:
        if isinstance(value, list):
            out.extend(
                str(v) for v in value if isinstance(v, (str, int, float, bool))
            )
        elif isinstance(value, (str, int, float, bool)):
            out.append(str(value))
    return out


def explore_facets(
    catalog: dict[str, Any],
    text: str,
    type_filter: list[str] | None,
    facets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Facet counts over the matched set (spec 5.3.3), not over one page.

    The relevance cutoff is the same positive-overlap rule search uses; the
    spec requires one cutoff per registry governing both.
    """
    qtokens = _tokens(text)
    matched = [
        entry
        for entry in _dict_entries(catalog)
        if not (type_filter and entry.get("type") not in type_filter)
        and (not qtokens or score_entry(entry, qtokens) > 0)
    ]
    computed: dict[str, Any] = {}
    for facet in facets:
        field = facet.get("field")
        if not isinstance(field, str) or not field:
            continue
        limit = max(0, _as_int(facet.get("limit"), 20))
        min_count = _as_int(facet.get("minCount"), 0)
        counts: dict[str, int] = {}
        for entry in matched:
            # set(): a value repeated inside one entry counts that entry once
            for value in set(_term_values(entry, field)):
                counts[value] = counts.get(value, 0) + 1
        # count desc, then value: equal counts must not reshuffle per request
        ranked = sorted(
            ((v, c) for v, c in counts.items() if c >= min_count),
            key=lambda pair: (-pair[1], pair[0]),
        )
        head, tail = ranked[:limit], ranked[limit:]
        computed[field] = {"buckets": [{"value": v, "count": c} for v, c in head]}
        if tail:
            computed[field]["otherCount"] = sum(c for _, c in tail)
    return computed


def explore_response(
    catalog_path: Path, req: Any
) -> tuple[int, dict[str, Any]]:
    """POST /explore (spec 5.3.3). Returns (status, body) for the handler."""
    if not isinstance(req, dict):
        return 400, {"error": "invalid JSON body"}
    query = req.get("query") or {}
    if not isinstance(query, dict):
        return 400, {"error": "query must be an object"}
    # Spec: text and filter are both optional for explore - absent means
    # aggregate the whole registry.
    text = str(query.get("text", "")).strip()
    filt = query.get("filter") or {}
    if not isinstance(filt, dict):
        return 400, {"error": "query.filter must be an object"}
    unsupported = sorted(k for k in filt if k != "type")
    if unsupported:
        # Ignoring a filter we cannot honour would inflate every bucket and
        # the client could not tell. Refuse instead.
        return 400, {
            "error": "unsupported filter keys: " + ", ".join(unsupported)
        }
    type_filter = filt.get("type")
    if isinstance(type_filter, str):
        type_filter = [type_filter]
    elif not isinstance(type_filter, list):
        type_filter = None
    result_type = req.get("resultType")
    facets = result_type.get("facets") if isinstance(result_type, dict) else None
    if not isinstance(facets, list) or not facets:
        return 400, {"error": "resultType.facets is required"}
    try:
        catalog = load_catalog(catalog_path)
    except (OSError, ValueError) as exc:
        return 500, {"error": f"catalog unreadable: {exc}"}
    computed = explore_facets(
        catalog, text, type_filter, [f for f in facets if isinstance(f, dict)]
    )
    # Explore does not federate (spec 5.3.3): no upstream merge, no referrals.
    return 200, {"resultType": "facets", "facets": computed}


def federated_search(
    upstreams: list[str],
    text: str,
    type_filter: list[str] | None,
    page_size: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fan the query out to peer registries; fail-soft per upstream.

    Returns (rows, peers). A peer answers with at most pageSize rows plus its
    own totalResults for the whole query: the rows are a page, the total is a
    corpus count, and the two must not be added into one number. Each peers
    entry is {base, returned, total, rejected}, so the caller can report a
    union total and see which peers still hold rows this page never fetched.
    """
    merged: list[dict[str, Any]] = []
    peers: list[dict[str, Any]] = []
    query = {"text": text}
    if type_filter:
        query["filter"] = {"type": type_filter}
    body = json.dumps({"query": query, "pageSize": page_size}).encode("utf-8")
    for base in upstreams:
        url = base.rstrip("/") + "/search"
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )
        # Guard the whole per-upstream block: a peer answering with valid JSON
        # of the wrong shape must skip, not take down the local search.
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                raw = resp.read(trust.MAX_BODY + 1)
            if len(raw) > trust.MAX_BODY:
                raise ValueError(f"answered with more than {trust.MAX_BODY} bytes")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("answered with a non-object body")
            returned = 0
            rejected = 0
            rows = payload.get("results")
            # Absent results is a silent empty page; a present non-array is a
            # malformed peer - raise into the fail-soft handler below (logged +
            # skipped), not out of do_POST as a 500 that loses the local rows.
            if rows is None:
                rows = []
            if not isinstance(rows, list):
                raise ValueError("answered with a non-array results field")
            for result in rows:
                if not isinstance(result, dict):
                    continue
                returned += 1
                # A peer's row reaches an agent's context verbatim, so this is
                # a trust boundary (spec 4.5): screen it and drop what comes
                # back SUSPECT. Dropped, not annotated - the /search body is
                # conformance-validated and has no room for a verdict field.
                # Rows without a trustManifest stay UNVERIFIED and pass: an
                # honest peer is not punished for having nothing to prove.
                # Nor for having something we cannot check: UNSUPPORTED (a
                # did:key/SPIFFE/ANS identity, §4.5.1-legal but unresolvable
                # offline) is served, not dropped. Only SUSPECT is an
                # accusation, and worst-wins still makes an injected
                # did:key row SUSPECT, so the screen keeps its teeth.
                # ponytail: this is `== SUSPECT`, not `in trust._FLAGGED`, and
                # that is load-bearing rather than an oversight - dropping
                # UNSUPPORTED would silently reject every row from a peer that
                # identifies by SPIFFE. Upgrade path: revisit when a resolver
                # for SPIFFE/ANS lands and UNSUPPORTED stops meaning "spec
                # allows it, we cannot check it".
                verdict = trust.verdict_entry(result)
                if verdict["verdict"] == trust.SUSPECT:
                    rejected += 1
                    print(
                        f"trust: dropped {verdict['identifier']!r} from "
                        f"{base.rstrip('/')}: "
                        + "; ".join(verdict["findings"]),
                        file=sys.stderr,
                    )
                    continue
                # Never trust a peer's score: clamp into the documented band.
                try:
                    s = min(100, max(0, int(float(result.get("score", 0)))))
                except (TypeError, ValueError, OverflowError):
                    # OverflowError: a JSON 1e309 decodes to float('inf'), and
                    # int(inf) overflows - a non-finite score normalizes to 0
                    # like any other unusable one, keeping finite scores intact.
                    s = 0
                merged.append({**result, "score": s, "source": base.rstrip("/")})
            # Never trust a peer's total either. A bool (checked first - it is
            # an int subclass), a float, a string, a negative, or a count
            # below the rows it just sent is a broken peer, and the rows in
            # hand are the only number left to stand behind.
            raw = payload.get("totalResults")
            claimed = 0 if isinstance(raw, bool) else raw
            if not isinstance(claimed, int) or claimed < 0:
                claimed = 0
            peers.append({
                "base": base.rstrip("/"),
                "returned": returned,
                "total": max(claimed, returned),
                "rejected": rejected,
            })
        except (urllib.error.URLError, OSError, ValueError) as exc:
            # One line per dead upstream. Without it a peer that never answered
            # is indistinguishable from a peer that simply had no hits, and the
            # SUSPECT-drop path above already logs - silence here is a gap.
            print(
                f"trust: upstream {base.rstrip('/')} failed: {exc}",
                file=sys.stderr,
            )
            continue
    return merged, peers


def registry_entry(domain: str, public_url: str) -> dict[str, Any]:
    """Self-advert so peers can discover this registry's search base URL."""
    return {
        "@context": "https://agenticresourcediscovery.org/context/v1",
        "identifier": f"urn:air:{domain}:registry:ard-kit",
        "displayName": "ard-kit registry",
        "description": "Self-hosted ARD registry over locally catalogized scripts.",
        "type": "application/ai-registry+json",
        "url": public_url.rstrip("/") + "/search",
    }


def default_public_url(host: str, port: int) -> str:
    """Base URL peers see when --public-url is not given."""
    return "http://" + host + ":" + str(port)


def load_catalog(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_facts(path: Path, cache: dict[str, Any]) -> dict[str, Any]:
    """Catalog facts for /health, parsed only when the file changed.

    /health is the one endpoint the token does not cover, so a liveness probe
    must not cost a multi-megabyte JSON parse: stat decides, and the count is
    reused until mtime or size moves. Two racing probes can parse twice; both
    write the same values.
    """
    try:
        st = path.stat()
    except OSError as exc:
        return {"catalogError": str(exc)}
    key = (st.st_mtime_ns, st.st_size)
    if cache.get("key") != key:
        try:
            catalog = load_catalog(path)
        except (OSError, json.JSONDecodeError) as exc:
            return {"catalogError": str(exc)}
        if not isinstance(catalog, dict):
            return {"catalogError": "catalog is not a JSON object"}
        entries = catalog.get("entries")
        cache.clear()
        cache["key"] = key
        cache["specVersion"] = catalog.get("specVersion")
        cache["entries"] = len(entries) if isinstance(entries, list) else 0
    return {
        "specVersion": cache.get("specVersion"),
        "entries": cache.get("entries"),
        # The catalog schema allows only specVersion/host/entries, so the
        # generation time is the file's mtime, not a field inside it.
        "catalogGeneratedAt": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime)
        ),
    }


def health_payload(
    catalog_path: Path, token: str | None, public: bool, cache: dict[str, Any]
) -> dict[str, Any]:
    """The liveness body: what a caller needs before it blames the network.

    `auth` is here because a 401 on every endpoint reads as "registry broken"
    to a caller that never learned the gate is deliberate, and `entries`
    separates "catalog is empty" from "catalog path is wrong". The absolute
    path narrows to the file name once --public-url says other machines can
    reach this: a local filesystem layout is not public information. Status
    degrades rather than lying "ok" when the catalog cannot be read.
    """
    facts = catalog_facts(catalog_path, cache)
    payload: dict[str, Any] = {
        "status": "degraded" if "catalogError" in facts else "ok",
        "version": __version__,
        "auth": "required" if token else "none",
        "catalog": catalog_path.name if public else str(catalog_path),
    }
    payload.update(facts)
    return payload


# Spec 5.3.4 List, Appendix A: "field=value" clauses joined by AND, with OR
# inside one field via commas. The spec only sketches the grammar, so what
# this parser does not recognise is a 400 rather than a silent match-all.
_LIST_FILTER_FIELDS = ("displayName", "type")
# Appendix A names these as well, but a catalogized script has no publisher
# and no timestamps: "filtering" on them would just return everything.
_LIST_FILTER_ABSENT = ("publisherId", "createdAfter", "updatedAfter")
_LIST_ORDER_FIELDS = ("identifier", "displayName")


def parse_list_filter(expr: str) -> dict[str, list[str]]:
    """Parse a List filter expression, or raise ValueError with the reason."""
    # A dangling AND folds into the previous value and matches nothing; an
    # empty 200 for a malformed filter is the worst answer available.
    if re.match(r"(?i)^AND\b", expr) or re.search(r"(?i)\bAND$", expr):
        raise ValueError(f"dangling AND in filter: {expr!r}")
    parsed: dict[str, list[str]] = {}
    for clause in re.split(r"\s+AND\s+", expr.strip(), flags=re.IGNORECASE):
        field, sep, value = clause.partition("=")
        if not sep:
            raise ValueError(f"filter clause is not field=value: {clause!r}")
        field = field.strip()
        value = value.strip()
        # Only a matching outer quote pair is a delimiter. Values may legally
        # contain quotes (type=text/markdown; profile="urn:air:...") - tearing
        # off lone quote chars turned that filter into a plausible empty page.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if field in _LIST_FILTER_ABSENT:
            raise ValueError(
                f"filter field carries no data in this registry: {field}"
            )
        if field not in _LIST_FILTER_FIELDS:
            raise ValueError(f"unknown filter field: {field}")
        values = [v.strip() for v in value.split(",") if v.strip()]
        if not values:
            raise ValueError(f"empty value for filter field: {field}")
        parsed[field] = values
    return parsed


def parse_order_by(order_by: str) -> tuple[str, bool]:
    """Return (field, reverse) for an orderBy clause, or raise ValueError."""
    parts = order_by.split()
    if len(parts) > 2:
        raise ValueError(f"malformed orderBy: {order_by!r}")
    field = parts[0]
    if field not in _LIST_ORDER_FIELDS:
        raise ValueError(f"unknown orderBy field: {field}")
    direction = parts[1].upper() if len(parts) == 2 else "ASC"
    if direction not in ("ASC", "DESC"):
        raise ValueError(f"orderBy direction must be ASC or DESC: {parts[1]!r}")
    return field, direction == "DESC"


def _list_key(entry: dict[str, Any], field: str) -> tuple[str, str]:
    """Total order for GET /agents: the ordered field, then the identifier."""
    return (str(entry.get(field, "")), str(entry.get("identifier", "")))


def list_agents(
    catalog: dict[str, Any],
    filters: dict[str, list[str]],
    order_by: str,
    page_size: int,
    after: tuple[str, str] | None = None,
) -> tuple[int, list[dict[str, Any]], tuple[str, str] | None]:
    """Deterministic listing: filtered, totally ordered, seek window.

    Returns (row count, one page, key of the next page or None).
    """
    field, reverse = parse_order_by(order_by)
    rows = []
    for entry in _dict_entries(catalog):
        types = filters.get("type")
        if types and entry.get("type") not in types:
            continue
        names = filters.get("displayName")
        if names:
            # Appendix A calls this a case-insensitive name filter.
            name = str(entry.get("displayName", "")).lower()
            if not any(n.lower() in name for n in names):
                continue
        rows.append(entry)
    # Ordered by (field, identifier) rather than catalog order. displayName
    # repeats across directories, and a tie left to catalog order moves when
    # the catalog is regenerated: a tie group cut by a page boundary then
    # hands the walking client one row twice and another never. Identifiers
    # are unique per catalog (catalogize dedupes on them), so this is a total
    # order. Rows are sorted ascending and a DESC page is read backwards off
    # the same keys: one order, one bisect, and the cursor names a row rather
    # than a position, so entries added or removed mid-walk cannot shift what
    # was already handed out.
    rows.sort(key=lambda e: _list_key(e, field))
    keys = [_list_key(e, field) for e in rows]
    n = max(1, min(page_size, 100))
    if reverse:
        # The page ends at the cursor and grows backwards, so deleting the
        # cursor row itself still lands on the boundary it used to own.
        hi = (
            bisect.bisect_left(keys, after) if after is not None else len(keys)
        )
        start = max(0, hi - n)
        window = rows[start:hi][::-1]
        next_key = keys[start] if start > 0 else None
    else:
        lo = bisect.bisect_right(keys, after) if after is not None else 0
        window = rows[lo : lo + n]
        end = lo + len(window)
        next_key = keys[end - 1] if window and end < len(rows) else None
    page = [
        # representativeQueries index an entry, they do not present it.
        {k: v for k, v in entry.items() if k != "representativeQueries"}
        for entry in window
    ]
    return len(rows), page, next_key


def list_response(
    catalog_path: Path, params: dict[str, list[str]]
) -> tuple[int, dict[str, Any]]:
    """Answer GET /agents: (status, payload). Never federates (spec 5.3.4)."""
    page_size = _as_int(params.get("pageSize", ["20"])[0], 0)
    if not 1 <= page_size <= 100:
        return 400, {"error": "pageSize must be an integer in 1..100"}
    filter_expr = params.get("filter", [""])[0].strip()
    order_by = params.get("orderBy", ["identifier"])[0].strip() or "identifier"
    try:
        filters = parse_list_filter(filter_expr) if filter_expr else {}
        parse_order_by(order_by)
    except ValueError as exc:
        return 400, {"error": str(exc)}
    # The cursor belongs to this listing: filter and orderBy decide the row
    # order, so replaying it elsewhere would skip or repeat entries.
    fingerprint = query_fingerprint(
        "agents\x00" + filter_expr + "\x00" + order_by, None
    )
    after: tuple[str, str] | None = None
    token = params.get("pageToken", [None])[0]
    if token is not None:
        decoded = _page_token_decode(token, fingerprint, str)
        if decoded is None:
            return 400, {
                "error": "pageToken is invalid or was minted for "
                "another listing"
            }
        after = decoded
    try:
        catalog = load_catalog(catalog_path)
    except (OSError, json.JSONDecodeError) as exc:
        return 500, {"error": f"catalog unreadable: {exc}"}
    total, page, next_key = list_agents(
        catalog, filters, order_by, page_size, after
    )
    # The listing envelope is the OpenAPI ListResponse: items + total. A
    # search page carries results + totalResults instead — the two endpoints
    # do not share one envelope, and the official conformance suite rejects
    # /agents for the search one.
    payload: dict[str, Any] = {"items": page, "total": total}
    if next_key is not None:
        payload["pageToken"] = _page_token_encode(next_key, fingerprint)
    return 200, payload


def make_handler(
    catalog_path: Path,
    domain: str,
    public_url: str,
    upstreams: list[str],
    token: str | None = None,
    public: bool = False,
) -> type[BaseHTTPRequestHandler]:
    inspect_path = catalog_path.with_suffix(".inspect.json")
    health_cache: dict[str, Any] = {}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            # /health stays open so watchdogs/systemd can liveness-check
            # without carrying the token.
            if token is None or self.path.split("?", 1)[0] in ("/", "/health"):
                return True
            auth = self.headers.get("Authorization", "")
            # Constant-time: a plain == leaks the token byte by byte.
            if hmac.compare_digest(auth, f"Bearer {token}"):
                return True
            self._send(
                401,
                {
                    "error": "invalid or missing bearer token",
                    # Without a next step a 401 sends the operator to restart
                    # a registry that is working exactly as configured.
                    "hint": "set ARD_REGISTRY_TOKEN; the value comes from "
                    "whoever started this registry (GET /health reports "
                    "whether auth is on, and stays open)",
                },
            )
            return False

        def _fail_internal(self, exc: BaseException) -> None:
            # Last-resort boundary for the HTTP lane, mirroring the MCP
            # lane's -32603 guard (0.19.2): an unexpected error must degrade
            # to a clean 500, not a dropped connection the client cannot tell
            # from a network fault. A catalog that is valid JSON but not an
            # object - a hand-written [], null, or a bare array of entries -
            # raises AttributeError/TypeError out of catalog.get("entries")
            # on every lane; ThreadingHTTPServer contains it to one thread
            # but the client still sees an empty reply instead of a status.
            # Every trigger in _route_get/_route_post raises upstream of the
            # first _send, so no response bytes are on the wire yet and this
            # is the only status line written. Cause to stderr, body generic.
            print(
                f"ard-registry: internal error on {self.path}: {exc!r}",
                file=sys.stderr,
            )
            self._send(500, {"error": "internal error"})

        def do_GET(self) -> None:  # noqa: N802 — http.server API
            try:
                self._route_get()
            except Exception as exc:
                self._fail_internal(exc)

        def _route_get(self) -> None:
            if not self._authorized():
                return
            if self.path in (
                # Spec 5.1: consumers MUST fetch /.well-known/ard.json.
                # The other two are the predecessor paths, kept for old clients.
                "/.well-known/ard.json",
                "/.well-known/ai-catalog.json",
                "/ai-catalog.json",
            ):
                try:
                    catalog = load_catalog(catalog_path)
                except (OSError, json.JSONDecodeError) as exc:
                    self._send(500, {"error": f"catalog unreadable: {exc}"})
                    return
                catalog = {
                    **catalog,
                    "entries": [registry_entry(domain, public_url)]
                    + _dict_entries(catalog),
                }
                self._send(200, catalog)
            elif self.path == "/inspect" or self.path.startswith("/inspect?"):
                parsed = urllib.parse.urlparse(self.path)
                ident = urllib.parse.parse_qs(parsed.query).get("identifier", [""])[0]
                if not ident:
                    self._send(400, {"error": "identifier query param is required"})
                    return
                try:
                    schemas = json.loads(inspect_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    # Sidecar is an ard-kit extension; without it inspect is
                    # not implemented rather than broken.
                    self._send(501, {"error": "no inspect sidecar next to catalog"})
                    return
                schema = schemas.get(ident) if isinstance(schemas, dict) else None
                if schema is None:
                    self._send(404, {"error": f"unknown identifier: {ident}"})
                    return
                self._send(200, {"identifier": ident, **schema})
            elif self.path == "/agents" or self.path.startswith("/agents?"):
                parsed = urllib.parse.urlparse(self.path)
                code, payload = list_response(
                    catalog_path, urllib.parse.parse_qs(parsed.query)
                )
                self._send(code, payload)
            elif self.path in ("/", "/health"):
                self._send(
                    200, health_payload(catalog_path, token, public, health_cache)
                )
            else:
                self._send(404, {"error": "not found"})

        def _read_request(self) -> dict[str, Any] | None:
            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                return None
            # The same ceiling as every other untrusted read; also rejects
            # negative/absurd lengths.
            if not 0 <= length <= trust.MAX_BODY:
                return None
            try:
                return json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                return None

        def do_POST(self) -> None:  # noqa: N802 — http.server API
            try:
                self._route_post()
            except Exception as exc:
                self._fail_internal(exc)

        def _route_post(self) -> None:
            if not self._authorized():
                return
            if self.path == "/explore":
                code, payload = explore_response(
                    catalog_path, self._read_request()
                )
                self._send(code, payload)
                return
            if self.path != "/search":
                self._send(404, {"error": "not found"})
                return
            req = self._read_request()
            if not isinstance(req, dict):
                self._send(400, {"error": "invalid JSON body"})
                return
            query = req.get("query") or {}
            if not isinstance(query, dict):
                self._send(400, {"error": "query must be an object"})
                return
            text = str(query.get("text", "")).strip()
            if not text:
                self._send(400, {"error": "query.text is required"})
                return
            raw_page_size = req.get("pageSize")
            page_size = 10 if raw_page_size is None else _as_int(raw_page_size, 0)
            if not 1 <= page_size <= 100:
                # Spec 5.3.2 bounds this at 1..100. Clamping silently let
                # pageSize:-5 answer with one row as if that was the ask.
                self._send(
                    400, {"error": "pageSize must be an integer in 1..100"}
                )
                return
            filt = query.get("filter") or {}
            type_filter = filt.get("type") if isinstance(filt, dict) else None
            # Client-supplied: a bare string would substring-match, anything
            # else raises straight out of the handler.
            if isinstance(type_filter, str):
                type_filter = [type_filter]
            elif not isinstance(type_filter, list):
                type_filter = None
            mode = req.get("federation", "auto")
            if mode not in ("auto", "referrals", "none"):
                # A typo used to fall through to the auto branch and fan out
                # to every upstream; an unknown mode is a client bug.
                self._send(
                    400,
                    {"error": "federation must be auto, referrals or none"},
                )
                return
            fingerprint = query_fingerprint(text, type_filter)
            after: tuple[float, str] | None = None
            token = req.get("pageToken")
            if token is not None:
                decoded = (
                    _page_token_decode(token, fingerprint, float)
                    if isinstance(token, str)
                    else None
                )
                if decoded is None:
                    self._send(
                        400,
                        {
                            "error": "pageToken is invalid or was minted "
                            "for another query"
                        },
                    )
                    return
                if upstreams and mode != "none":
                    # Peer ordering is not stable between requests, so a
                    # merged page 2 could repeat or drop rows.
                    self._send(
                        400,
                        {
                            "error": "pageToken requires federation:none; "
                            "merged peer results are not pageable"
                        },
                    )
                    return
                after = decoded
            try:
                catalog = load_catalog(catalog_path)
            except (OSError, json.JSONDecodeError) as exc:
                self._send(500, {"error": f"catalog unreadable: {exc}"})
                return
            total, results, next_key = search_catalog(
                catalog, text, type_filter, page_size, after
            )
            # Spec 5.3.2: a result names the registry it came from. Local hits
            # are ours; peer hits get their source in federated_search().
            for result in results:
                result["source"] = public_url.rstrip("/")
            referrals: list[dict[str, Any]] = []
            remote: list[dict[str, Any]] = []
            peer_total = 0
            if upstreams and mode != "none":
                if mode == "referrals":
                    # Spec mode: hand the client the peers instead of merging.
                    # Each referral carries the peer's own host, not ours.
                    referrals = [
                        registry_entry(
                            urllib.parse.urlparse(u).hostname or domain, u
                        )
                        for u in upstreams
                    ]
                else:
                    remote, peers = federated_search(
                        upstreams, text, type_filter, page_size
                    )
                    results.extend(remote)
                    # A peer page is capped at pageSize; the peer's own total
                    # is the corpus behind it. Adding the rows we fetched
                    # made the union total collapse to the truth only when
                    # every peer happened to be shallower than one page.
                    peer_total = sum(p["total"] for p in peers)
                    # Whatever a peer holds past this page is unreachable
                    # here - a merged page carries no cursor - so hand back
                    # the peers that still have rows and let the client walk
                    # them at the source. An unreachable count with no
                    # address would be a bigger lie than the undercount.
                    referrals = [
                        registry_entry(
                            urllib.parse.urlparse(p["base"]).hostname
                            or domain,
                            p["base"],
                        )
                        for p in peers
                        if p["total"] > p["returned"]
                    ]
            results.sort(key=lambda r: r.get("score", 0), reverse=True)
            response: dict[str, Any] = {
                "query": {"text": text},
                "results": results[:page_size],
                "totalResults": total + peer_total,
            }
            if type_filter is not None:
                # Echo the filter the page was computed under: a client that
                # only gets its text back cannot tell the filter was dropped.
                response["query"]["filter"] = {"type": type_filter}
            if referrals:
                response["referrals"] = referrals
            if not remote and next_key is not None:
                # Spec 5.3.2 names the response cursor pageToken as well.
                # Only local pages are pageable, hence no cursor once peer
                # results merged into this page.
                response["pageToken"] = _page_token_encode(
                    next_key, fingerprint
                )
            self._send(200, response)

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"{self.address_string()} {fmt % args}", file=sys.stderr)

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Minimal self-hosted ARD registry over an ai-catalog.json.",
    )
    parser.add_argument(
        "--catalog",
        default="ai-catalog.json",
        help="Catalog file produced by catalogize.py (default: ./ai-catalog.json).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address.")
    parser.add_argument("--port", type=int, default=8390, help="Bind port.")
    parser.add_argument(
        "--domain",
        default="localhost",
        help="Publisher domain embedded in the self-advert identifier.",
    )
    parser.add_argument(
        "--public-url",
        default=None,
        help="Externally reachable base URL (default: http://<host>:<port>).",
    )
    parser.add_argument(
        "--upstreams",
        default="",
        help="Comma-separated peer ARD registry base URLs to federate with.",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer token required on all endpoints except /health. "
        "Falls back to the ARD_REGISTRY_TOKEN environment variable (preferred "
        "for service deployments: keeps the secret out of the process list).",
    )
    args = parser.parse_args()

    # A POSIX --catalog resolves under the system drive on Windows instead of
    # failing, so the operator gets "catalog not found" naming a path they
    # never typed. Refuse at the door.
    path_error = guard_posix_paths({"catalog": args.catalog})
    if path_error:
        print(f"ERROR: {path_error}", file=sys.stderr)
        return 2

    token = args.token if args.token is not None else os.environ.get(
        "ARD_REGISTRY_TOKEN"
    )
    if token is not None and not token:
        # An empty token would silently serve everything unauthenticated;
        # callers who set the flag/env expect auth to be on.
        print(
            "ERROR: token is set but empty; refusing to serve unauthenticated",
            file=sys.stderr,
        )
        return 2

    public_url = args.public_url or default_public_url(args.host, args.port)
    upstreams = [u for u in (u.strip() for u in args.upstreams.split(",")) if u]
    bad = [u for u in upstreams if not u.startswith(("http://", "https://"))]
    if bad:
        print(f"WARNING: skipping non-http upstreams: {bad}", file=sys.stderr)
        upstreams = [u for u in upstreams if u not in bad]
    if upstreams and args.public_url is None:
        print(
            "WARNING: --upstreams set but --public-url not given; peers will "
            "see a loopback self-advert URL",
            file=sys.stderr,
        )
    if args.domain == "localhost":
        print(
            "WARNING: --domain defaults to localhost; use your real FQDN for "
            "catalogs meant to federate",
            file=sys.stderr,
        )

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        print(
            f"WARNING: catalog not found: {catalog_path} "
            "(requests will 500 until catalogize.py runs)",
            file=sys.stderr,
        )

    server = ThreadingHTTPServer(
        (args.host, args.port),
        make_handler(
            catalog_path,
            args.domain,
            public_url,
            upstreams,
            token,
            # --public-url is the operator saying other machines reach this,
            # which is when /health stops naming the local catalog path. The
            # loopback default keeps it: there is nobody else to read it.
            public=args.public_url is not None,
        ),
    )
    print(
        "ARD registry on " + default_public_url(args.host, args.port)
        + f" (catalog: {catalog_path})"
    )
    print("  manifest: GET  /.well-known/ard.json")
    print("  inspect:  GET  /inspect?identifier=<urn>")
    print("  list:     GET  /agents?filter=&orderBy=&pageSize=&pageToken=")
    print(f"  search:   POST /search   (upstreams: {upstreams or 'none'})")
    print("  explore:  POST /explore  (facet counts over the matched set)")
    print(f"  verify:   ard-verify --catalog {catalog_path}   (trust verdicts)")
    print(f"  health:   GET  /health   (open; auth: {'required' if token else 'none'})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
