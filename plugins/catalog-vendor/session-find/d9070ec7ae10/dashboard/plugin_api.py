"""Session Find dashboard API: the routes the search window calls.

The window talks to this file and never to a raw port, and two backends answer
the same contract behind it:

  - a session-find service on loopback (``SESSION_FIND_URL``, default
    ``http://127.0.0.1:8474``), which carries its own index and can rank by
    meaning as well as by keyword; and
  - this gateway's own ``state.db``, opened read only, through the FTS5 index the
    gateway already keeps over messages (``messages_fts``).

The service is preferred whenever it answers, and ``/status`` says which backend
is live, so the window can stop offering a vector toggle to a backend that has no
vectors. No ranking rule lives here that the service also owns: the native path
is a second backend, not a second copy of the service's scoring, and it exists so
the window is usable on a machine that has never run the service.

The native path answers ``/search``, ``/recent`` and ``/context``. It has no
vector half, so a query that asks for meaning alone is refused with a sentence
the window shows, rather than an empty list that reads as "no such session".
``/opened`` is counted by the service only; natively it is accepted and dropped,
because the gateway's database is opened read only here by design.

One shared ``httpx.AsyncClient`` per process, with keepalive. The first version
opened a fresh connection per request inside a threadpool and the hop measured
21.7 ms p50 on top of a service answer of a few milliseconds. The probe that
decides which backend to use is short and cached, so a machine without a service
pays it once per 30 s rather than once per keystroke.

`SESSION_FIND_URL` overrides the service address for a bench or a moved port. A
service that is down answers 503 with the address it tried, because "search
returned nothing" and "the indexer is not running" must not look the same in the
UI. `SESSION_FIND_STATE_DB` overrides the database the native path reads.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

# Ten seconds is well past the service's own budget (a warm search is a few
# milliseconds and the fused answer is tens), so a timeout here is a wedged
# process, not a slow query. The probe is far shorter: it runs in front of a
# keystroke, and a service that is not there must not be waited for.
TIMEOUT_SECONDS = 10.0
PROBE_SECONDS = 0.4
PROBE_TTL_SECONDS = 30.0
PROBE = {"at": 0.0, "kind": "", "vectors": False}

_client: httpx.AsyncClient | None = None


def _base() -> str:
    return os.environ.get("SESSION_FIND_URL", "http://127.0.0.1:8474").rstrip("/")


def _client_for() -> httpx.AsyncClient:
    """The one client for this process, created on first use.

    The limits are sized for one person typing into one search box: a few
    connections in flight, each kept alive long enough that the next keystroke
    reuses it instead of opening another socket.
    """
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(TIMEOUT_SECONDS),
            limits=httpx.Limits(
                max_connections=16,
                max_keepalive_connections=8,
                keepalive_expiry=60.0,
            ),
            headers={"user-agent": "duckwork-session-find-proxy/0.1"},
        )
    return _client


def _params(query: str) -> dict[str, str]:
    """The query string as a plain mapping. Decoding is left to the service."""
    pairs = (pair.split("=", 1) if "=" in pair else (pair, "") for pair in query.split("&"))
    return {key: value for key, value in pairs if key}


async def _request(
    path: str,
    query: str = "",
    body: bytes | None = None,
    method: str = "GET",
) -> tuple[int, Any]:
    url = _base() + path + (("?" + query) if query else "")
    headers = {"content-type": "application/json"} if body is not None else None
    try:
        response = await _client_for().request(
            method, url, content=body, headers=headers
        )
    except Exception as error:  # noqa: BLE001 - any transport fault is the same answer
        return 503, {
            "error": "session-find is not answering on %s: %s" % (_base(), error),
        }
    try:
        value = json.loads(response.content or b"null")
    except ValueError:
        return response.status_code, {
            "error": "session-find answered HTTP %d with a body that is not JSON"
            % response.status_code,
        }
    return response.status_code, value


async def _service() -> tuple[bool, bool]:
    """Is the service answering, and does it have a vector half? Cached.

    A service that is not running is the ordinary state on a machine that
    installed this plugin and nothing else, so this has to be cheap: one GET with
    a 0.4 s ceiling, remembered for 30 s. That window is also how a service
    started later gets picked up without restarting the gateway.
    """
    now = time.monotonic()
    if PROBE["kind"] and now - PROBE["at"] < PROBE_TTL_SECONDS:
        return PROBE["kind"] == "service", bool(PROBE["vectors"])

    kind, vectors = "native", False
    try:
        response = await _client_for().get(_base() + "/status", timeout=PROBE_SECONDS)
        if response.status_code == 200:
            payload = json.loads(response.content or b"null")
            if isinstance(payload, dict):
                kind = "service"
                vectors = bool(payload.get("embedder_ok")) and bool(
                    payload.get("vector_dim") or payload.get("dim")
                )
    except Exception:  # noqa: BLE001 - not answering means the native backend
        kind = "native"
    PROBE.update({"at": now, "kind": kind, "vectors": vectors})
    return kind == "service", vectors


# ---- the native backend: this machine's own database ------------------------------

FILTER = re.compile(r"^-?(?:in|after|before|me|repo|profile)\s*:", re.I)
QUOTED = re.compile(r'"([^"]+)"')
WORD = re.compile(r"[^\s]+")

SESSIONS_BY_ID = """
    SELECT id, source, profile_name, pinned, archived, display_name,
           last_activity_at, started_at,
           (SELECT trim(substr(replace(replace(m.content, char(10), ' '), char(13), ' '), 1, 90))
              FROM messages m
             WHERE m.session_id = sessions.id AND m.role = 'user'
               AND m.active = 1 AND m.content IS NOT NULL AND trim(m.content) != ''
             ORDER BY m.id LIMIT 1) AS first_user,
           (SELECT trim(substr(replace(replace(m.content, char(10), ' '), char(13), ' '), 1, 200))
              FROM messages m
             WHERE m.session_id = sessions.id AND m.active = 1
               AND m.content IS NOT NULL AND trim(m.content) != ''
             ORDER BY m.id DESC LIMIT 1) AS last_text,
           (SELECT m.id FROM messages m
             WHERE m.session_id = sessions.id AND m.active = 1
               AND m.content IS NOT NULL AND trim(m.content) != ''
             ORDER BY m.id DESC LIMIT 1) AS last_message_id
      FROM sessions
"""


def _state_db() -> Path:
    """The gateway's database, which is where DUCKWORK_HOME keeps it."""
    explicit = os.environ.get("SESSION_FIND_STATE_DB")
    if explicit:
        return Path(explicit)
    home = os.environ.get("DUCKWORK_HOME") or str(Path.home() / ".duckwork")
    return Path(home) / "state.db"


def _connect() -> sqlite3.Connection:
    """Read only, always: this file belongs to the gateway, and search never writes it."""
    connection = sqlite3.connect("file:%s?mode=ro" % _state_db(), uri=True, timeout=3.0)
    connection.row_factory = sqlite3.Row
    return connection


def _terms(text: str) -> list[str]:
    """The words to match, with the typed filters dropped and phrases kept.

    The box is the one source of truth and the filters live inside it, so the
    native path strips the same in:/after:/repo: tokens instead of matching a
    filter as a word nobody typed.
    """
    found: list[str] = []
    for phrase in QUOTED.findall(text):
        if phrase.strip():
            found.append(phrase.strip())
    for word in WORD.findall(QUOTED.sub(" ", text)):
        cleaned = word.strip()
        if len(cleaned) >= 2 and not FILTER.match(cleaned):
            found.append(cleaned)
    return found


def _match(terms: list[str]) -> str:
    """An FTS5 MATCH expression: every term quoted, the last one left open.

    Quoting is what makes a pasted identifier safe, because FTS5 reads bare words
    as its own query language and a stray OR or star from a search box would be
    an operator rather than a word. The last term stays open as a prefix so a
    half-typed word still answers.
    """
    if not terms:
        return ""
    quoted = ['"%s"' % term.replace('"', '""') for term in terms[:-1]]
    quoted.append('"%s"*' % terms[-1].replace('"', '""'))
    return " OR ".join(quoted)


def _row(
    session: sqlite3.Row,
    *,
    why: list[str],
    score: float,
    snippet: str | None,
    message_id: int | None,
) -> dict[str, Any]:
    """One session in the shape the window reads, whichever backend filled it."""
    title = (session["first_user"] or session["display_name"] or "").strip()
    return {
        "archived": bool(session["archived"]),
        "last_activity_at": session["last_activity_at"] or session["started_at"],
        "pinned": bool(session["pinned"]),
        "profile": session["profile_name"] or "",
        "score": score,
        "session_id": session["id"],
        "snippet": (snippet or session["last_text"] or "").strip(),
        "snippet_message_id": message_id
        if message_id is not None
        else session["last_message_id"],
        "source": session["source"] or "",
        "title": title,
        "why": why,
    }


def _native_search(query: str, limit: int) -> list[dict[str, Any]]:
    """Keyword search over the gateway's own FTS index, one row per session.

    FTS finds messages and the list is sessions, so each session is represented
    by its best matching message and the sessions are ordered by that hit's rank.
    ``bm25`` returns a negative number where lower is better, which is why the
    score is flipped and the sort looks reversed against a normal score.
    """
    expression = _match(_terms(query))
    if not expression:
        return []

    with _connect() as connection:
        hits = connection.execute(
            """
            SELECT m.session_id AS session_id, m.id AS message_id,
                   snippet(messages_fts, 0, '', '', ' ... ', 14) AS snippet,
                   bm25(messages_fts) AS rank
              FROM messages_fts
              JOIN messages m ON m.id = messages_fts.rowid
             WHERE messages_fts MATCH ?
               AND m.active = 1
               AND m.content IS NOT NULL
               AND trim(m.content) != ''
             ORDER BY rank
             LIMIT 300
            """,
            (expression,),
        ).fetchall()
        if not hits:
            return []

        best: dict[str, sqlite3.Row] = {}
        for hit in hits:
            held = best.get(hit["session_id"])
            if held is None or hit["rank"] < held["rank"]:
                best[hit["session_id"]] = hit
        ids = list(best)
        placeholders = ",".join("?" for _ in ids)
        sessions = connection.execute(
            SESSIONS_BY_ID + " WHERE id IN (%s)" % placeholders, ids
        ).fetchall()

    rows = []
    for session in sessions:
        hit = best[session["id"]]
        rows.append(
            _row(
                session,
                why=["keyword"],
                score=float(-hit["rank"]),
                snippet=hit["snippet"],
                message_id=hit["message_id"],
            )
        )
    rows.sort(key=lambda item: (item["score"], item["last_activity_at"] or 0), reverse=True)
    return rows[:limit]


def _native_recent(limit: int) -> list[dict[str, Any]]:
    """The empty box: pinned first, then whatever was used last.

    The service orders this list by frecency of opens, which it can do because it
    counts opens itself. Natively there is no such count, so the order is the
    session's own last activity and the reason says recent.
    """
    with _connect() as connection:
        sessions = connection.execute(
            SESSIONS_BY_ID
            + " WHERE COALESCE(hidden, 0) = 0"
            + " ORDER BY pinned DESC, COALESCE(last_activity_at, started_at) DESC LIMIT ?",
            (limit,),
        ).fetchall()

    return [
        _row(session, why=["recent"], score=0.0, snippet=None, message_id=None)
        for session in sessions
    ]


def _native_context(
    session_id: str, message_id: int | None, around: int
) -> list[dict[str, Any]]:
    """The messages around one hit, oldest first, for the preview pane."""
    window = max(0, min(around, 20))
    with _connect() as connection:
        if message_id is None:
            rows = connection.execute(
                """
                SELECT id, role, content, timestamp
                  FROM messages
                 WHERE session_id = ? AND active = 1 AND content IS NOT NULL
                 ORDER BY id DESC LIMIT ?
                """,
                (session_id, window * 2 + 1),
            ).fetchall()
            rows = list(reversed(rows))
        else:
            rows = connection.execute(
                """
                SELECT id, role, content, timestamp
                  FROM messages
                 WHERE session_id = ? AND active = 1 AND content IS NOT NULL
                   AND id >= ? - ? AND id <= ? + ?
                 ORDER BY id
                """,
                (session_id, message_id, window, message_id, window),
            ).fetchall()

    return [
        {
            "content": row["content"] or "",
            "id": row["id"],
            "role": row["role"] or "",
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]


async def _native(work: Callable[[], Any]) -> JSONResponse:
    """Run a blocking sqlite pass off the event loop and answer with its result."""
    try:
        payload = await asyncio.to_thread(work)
    except Exception as error:  # noqa: BLE001 - a broken database is one sentence
        return JSONResponse(
            status_code=503,
            content={
                "error": "Session Find could not read this machine's session database "
                "(%s): %s" % (_state_db(), error)
            },
        )
    return JSONResponse(status_code=200, content=payload)


async def _answered(
    path: str, query: str, native: Callable[[], Any] | None = None
) -> JSONResponse:
    """The service when it answers, this machine's own database when it does not."""
    alive, _vectors = await _service()
    if alive:
        status, payload = await _request(path, query)
        return JSONResponse(status_code=status, content=payload)
    if native is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": "Session Find has no service on %s and no local database to "
                "answer from" % _base()
            },
        )
    return await _native(native)


NO_VECTORS = {
    "error": "This Duckwork has no search service, so the window can match words "
    "only: turn Keywords on, or point SESSION_FIND_URL at a session-find service."
}


# ---- routes -----------------------------------------------------------------------


@router.get("/search")
async def search(request: Request) -> JSONResponse:
    """Forward the query string verbatim: q, limit, sort, scope, profile, vec, kw, fast.

    Verbatim matters: the typed filters (in:, -in:, after:, before:, me:, repo:
    and quoted phrases) live inside q, and re-encoding them here is how a filter
    silently stops working.
    """
    query = request.url.query
    params = _params(query)
    meaning = params.get("vec", "1") not in ("0", "false")
    keywords = params.get("kw", "1") not in ("0", "false")
    raw_limit = params.get("limit", "30")
    limit = max(1, int(raw_limit)) if raw_limit.isdigit() else 30
    text = params.get("q", "").replace("+", " ")

    alive, _vectors = await _service()
    if not alive and meaning and not keywords:
        return JSONResponse(status_code=503, content=NO_VECTORS)
    if alive:
        status, payload = await _request("/search", query)
        return JSONResponse(status_code=status, content=payload)
    return await _native(lambda: _native_search(text, limit))


@router.get("/recent")
async def recent(request: Request) -> JSONResponse:
    """The empty-box list: pinned first, then whatever was used last."""
    query = request.url.query
    raw_limit = _params(query).get("limit", "30")
    limit = max(1, int(raw_limit)) if raw_limit.isdigit() else 30
    return await _answered("/recent", query, lambda: _native_recent(limit))


@router.get("/context")
async def context(request: Request) -> JSONResponse:
    """The messages around one hit, for the preview pane.

    Forwards session_id, message_id and around verbatim; the service decides
    which rows count as context, and a session-level row answers with its last
    turn when no message is named.
    """
    query = request.url.query
    params = _params(query)
    session_id = params.get("session_id", "").replace("+", " ")
    raw_id = params.get("message_id", "")
    message_id = int(raw_id) if raw_id.isdigit() else None
    raw_around = params.get("around", "2")
    around = int(raw_around) if raw_around.isdigit() else 2
    return await _answered(
        "/context",
        query,
        lambda: _native_context(session_id, message_id, around),
    )


@router.post("/opened")
async def opened(request: Request) -> JSONResponse:
    """Count one open. The body is the service's own `{"session_id": ...}`.

    Natively this is accepted and dropped: the count belongs to the service's own
    index, and the gateway's database is opened read only here by design.
    """
    alive, _vectors = await _service()
    if alive:
        body = await request.body()
        status, payload = await _request("/opened", "", body, "POST")
        return JSONResponse(status_code=status, content=payload)
    return JSONResponse(status_code=200, content={"counted": False})


@router.get("/status")
async def status(request: Request) -> JSONResponse:
    """Which backend is live, and what it can do.

    ``vectors`` is what lets the window keep or drop the meaning toggle: a
    backend without a vector half must not offer one, or the first search a new
    user runs is an error about a service they have never heard of.
    """
    alive, vectors = await _service()
    if alive:
        status_code, payload = await _request("/status", "")
        if isinstance(payload, dict):
            payload = {**payload, "backend": "service", "vectors": vectors}
        return JSONResponse(status_code=status_code, content=payload)

    def counts() -> dict[str, Any]:
        with _connect() as connection:
            sessions = connection.execute(
                "SELECT count(*) FROM sessions WHERE COALESCE(hidden, 0) = 0"
            ).fetchone()[0]
            messages = connection.execute(
                "SELECT count(*) FROM messages WHERE active = 1"
            ).fetchone()[0]
        return {"indexed_sessions": sessions, "indexed_messages": messages}

    payload = {
        "backend": "native",
        "embedder": "none: this backend matches words, not meanings",
        "embedder_ok": False,
        "keyword": True,
        "service": _base(),
        "state_db": str(_state_db()),
        "vectors": False,
        "version": "1.0.0",
    }
    try:
        payload.update(await asyncio.to_thread(counts))
    except Exception:  # noqa: BLE001 - the counts are a nicety, not the answer
        pass
    return JSONResponse(status_code=200, content=payload)


@router.get("/health")
async def health() -> JSONResponse:
    """One line for a smoke test, whichever backend is behind it."""
    alive, _vectors = await _service()
    if alive:
        status_code, payload = await _request("/health", "")
        return JSONResponse(status_code=status_code, content=payload)
    return JSONResponse(status_code=200, content={"backend": "native", "ok": True})
