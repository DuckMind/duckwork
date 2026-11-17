#!/usr/bin/env python3
"""MCP front for the local ARD catalog: discovery over stdio, no HTTP.

The registry only speaks HTTP, which means an agent host has to be told a
URL before it can find anything. Editors that speak MCP (Claude Desktop,
Cursor, Qoder) mount a command instead, so this exposes the same three
operations — search the catalog, inspect one entry, verdict its trust —
as MCP tools.

Wire format is the MCP stdio transport: newline-delimited JSON-RPC 2.0,
one request object per line in, one response object per line out.

    {"mcpServers": {"ard-kit": {"command": "./bin/ard-mcp",
                                "args": ["--catalog", "ai-catalog.json"],
                                "cwd": "./"}}}

"cwd" is "./" rather than ".": the same directory to every path resolver, but
Agent Plugins hosts prefix-match the value and drop the whole server on a bare
dot.

The wrapper resolves its own interpreter; a literal "python3" here is a trap
on Windows, where Python ships as python or py and never as python3.

ponytail: no HTTP client, no SDK, no session state — search_catalog() and
the inspect sidecar already are the implementation; this file is only the
wire adapter over them.

Usage:
    python3 -m ard_kit.mcp_server --catalog ai-catalog.json
    ard-mcp --catalog ai-catalog.json   # ard-mcp.cmd on Windows
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from ard_kit import __version__, trust
from ard_kit.catalogize import guard_posix_paths
from ard_kit.registry import (
    _page_token_decode,
    _page_token_encode,
    load_catalog,
    query_fingerprint,
    search_catalog,
)

PROTOCOL_VERSION = "2025-06-18"

# Tool names stay [a-z_]: several hosts reject a dot in a tool name.
TOOLS: list[dict[str, Any]] = [
    {
        "name": "ard_search",
        "description": (
            "Search the local ARD catalog by intent and return ranked "
            "capabilities (scripts, agent skills, MCP servers). Returns "
            "summaries only; call ard_inspect before running one. When the "
            "result carries a pageToken, pass it back with the same text to "
            "read the next page."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "What the task needs, in plain words.",
                },
                "type": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional media types to filter by.",
                },
                "pageSize": {
                    "type": "integer",
                    "description": "Results per page (default 5, from 1 to 100).",
                },
                "pageToken": {
                    "type": "string",
                    "description": (
                        "Cursor from a previous ard_search result; only "
                        "valid with the same text and type."
                    ),
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "ard_inspect",
        "description": (
            "Return the invoke command and CLI arguments for one catalog "
            "entry, addressed by the urn:air identifier ard_search returned."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "urn:air:... identifier from ard_search.",
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "ard_verify",
        "description": (
            "Trust verdict for one catalog entry before you run it. VERIFIED "
            "means evidence beyond the entry's own text; UNVERIFIED means "
            "nothing wrong but nothing proven, which is normal for a local "
            "catalog; SUSPECT means a concrete reason not to believe it "
            "(prompt-injection markers, invisible characters, an identity "
            "that does not match its URN) and the findings say which; "
            "UNSUPPORTED means a check this install cannot perform. A score "
            "from ard_search is relevance, never trust."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "urn:air:... identifier from ard_search.",
                },
            },
            "required": ["identifier"],
        },
    },
]


def _result(payload: Any, is_error: bool = False) -> dict[str, Any]:
    """Wrap a payload as an MCP tool result.

    Tool errors travel inside the result, not as JSON-RPC errors: the model
    is meant to read them and try something else.
    """
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _catalog_hint(catalog_path: Path) -> str:
    """Name the path actually looked at, plus the command that fixes it.

    A relative --catalog resolves against whatever cwd the host forked us
    from - on Windows that is the editor's directory, not the plugin's - so
    a bare "catalog unreadable" sends the operator hunting through the wrong
    tree. The WSL line covers the supported split setup (registry in Linux,
    editor on Windows), where a POSIX path does not fail loudly: Windows
    resolves it against the current drive and finds nothing there.
    """
    resolved = Path(catalog_path).absolute()
    hint = (
        f"looked for {resolved} from cwd {Path.cwd()}; build one with "
        f"python -m ard_kit.catalogize --dir <dir> --output {resolved}"
    )
    if sys.platform == "win32" and str(catalog_path).startswith("/"):
        hint += (
            "; that is a WSL path - from Windows pass "
            "\\\\wsl.localhost\\<distro>"
            + str(catalog_path).replace("/", "\\")
            + " (wsl -l -q lists distros)"
        )
    return hint


def call_tool(
    name: str, arguments: dict[str, Any], catalog_path: Path
) -> dict[str, Any]:
    """Run one tool call against the catalog on disk."""
    if name == "ard_search":
        text = str(arguments.get("text", "")).strip()
        if not text:
            return _result({"error": "text is required"}, True)
        type_filter = arguments.get("type")
        # Model-supplied: a bare string would substring-match, anything else
        # has no business reaching the scorer.
        if isinstance(type_filter, str):
            type_filter = [type_filter]
        elif not isinstance(type_filter, list):
            type_filter = None
        raw_page_size = arguments.get("pageSize")
        try:
            page_size = 5 if raw_page_size is None else int(raw_page_size)
        except (TypeError, ValueError):
            page_size = 0
        if not 1 <= page_size <= 100:
            # A model that asked for 200 rows should be told so, not handed
            # five and left to conclude the catalog is that small.
            return _result(
                {"error": "pageSize must be an integer in 1..100"}, True
            )
        fingerprint = query_fingerprint(text, type_filter)
        after: tuple[float, str] | None = None
        token = arguments.get("pageToken")
        if token is not None:
            decoded = (
                _page_token_decode(token, fingerprint, float)
                if isinstance(token, str)
                else None
            )
            if decoded is None:
                return _result(
                    {
                        "error": "pageToken is invalid or was minted for "
                        "another query"
                    },
                    True,
                )
            after = decoded
        try:
            catalog = load_catalog(catalog_path)
        except (OSError, json.JSONDecodeError) as exc:
            return _result(
                {
                    "error": f"catalog unreadable: {exc}",
                    "hint": _catalog_hint(catalog_path),
                },
                True,
            )
        total, hits, next_key = search_catalog(
            catalog, text, type_filter, page_size, after
        )
        # Summaries only: a whole entry costs the model context for fields it
        # cannot act on. The invoke schema comes from ard_inspect, once.
        results = [
            {
                "identifier": hit.get("identifier"),
                "displayName": hit.get("displayName"),
                "description": hit.get("description"),
                "type": hit.get("type"),
                "score": hit.get("score"),
            }
            for hit in hits
        ]
        payload: dict[str, Any] = {"totalResults": total, "results": results}
        if next_key is not None:
            # Without a cursor, totalResults named rows the model could see
            # and never reach - the same lie the HTTP surface used to tell.
            payload["pageToken"] = _page_token_encode(next_key, fingerprint)
        return _result(payload)

    if name == "ard_inspect":
        identifier = str(arguments.get("identifier", "")).strip()
        if not identifier:
            return _result({"error": "identifier is required"}, True)
        try:
            schemas = json.loads(
                catalog_path.with_suffix(".inspect.json").read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, json.JSONDecodeError):
            # Sidecar is an ard-kit extension; without it inspect is absent,
            # not broken.
            return _result(
                {
                    "error": "no inspect sidecar next to catalog",
                    "hint": "expected "
                    f"{catalog_path.with_suffix('.inspect.json').absolute()}",
                },
                True,
            )
        schema = schemas.get(identifier) if isinstance(schemas, dict) else None
        # Not `is None`: a sidecar value that is present but not an object (a
        # str/list from a hand-edited or corrupt .inspect.json) would reach
        # {**schema} and raise TypeError out of serve(). Treat it as unknown.
        if not isinstance(schema, dict):
            return _result({"error": f"unknown identifier: {identifier}"}, True)
        return _result({"identifier": identifier, **schema})

    if name == "ard_verify":
        identifier = str(arguments.get("identifier", "")).strip()
        if not identifier:
            return _result({"error": "identifier is required"}, True)
        try:
            catalog = load_catalog(catalog_path)
        except (OSError, json.JSONDecodeError) as exc:
            return _result(
                {
                    "error": f"catalog unreadable: {exc}",
                    "hint": _catalog_hint(catalog_path),
                },
                True,
            )
        entries = catalog.get("entries") if isinstance(catalog, dict) else None
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            if entry.get("identifier") != identifier:
                continue
            # Catalog-local, so no hosted_from: an identity asserted by the
            # entry's own text stays UNVERIFIED rather than being promoted.
            # Fetching a model-supplied URL from here would be an SSRF
            # surface - the operator CLI does that with `ard-verify --url`.
            return _result(trust.verdict_entry(entry))
        return _result({"error": f"unknown identifier: {identifier}"}, True)

    return _result({"error": f"unknown tool: {name}"}, True)


def handle_request(
    request: dict[str, Any], catalog_path: Path
) -> dict[str, Any] | None:
    """Map one JSON-RPC request to its response; None for a notification."""
    request_id = request.get("id")
    method = str(request.get("method", ""))
    if request_id is None:
        # Notification (notifications/initialized and friends): the spec says
        # answer nothing at all, not even an empty result.
        return None
    params = request.get("params")
    params = params if isinstance(params, dict) else {}

    if method == "initialize":
        asked = params.get("protocolVersion")
        result: dict[str, Any] = {
            # Echo the version the client named: it knows its own transport,
            # and both sides only use the subset below anyway.
            "protocolVersion": asked if isinstance(asked, str) else PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "ard-kit", "version": __version__},
        }
        if not catalog_path.exists():
            # Fail loud, not fail empty: tools/list keeps advertising the three
            # tools, because a host handed zero tools shows the operator
            # nothing to debug and the model never learns the names.
            # `instructions` is the one initialize field hosts surface, so the
            # missing catalog is reported where it gets read instead of dying
            # in a stderr line the host swallows.
            result["instructions"] = (
                "ARD catalog is missing: " + _catalog_hint(catalog_path)
            )
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        arguments = params.get("arguments")
        result = call_tool(
            str(params.get("name", "")),
            arguments if isinstance(arguments, dict) else {},
            catalog_path,
        )
    elif method == "ping":
        result = {}
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"method not found: {method}"},
        }
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _write(stream: TextIO, payload: dict[str, Any]) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    stream.flush()


def serve(stream_in: TextIO, stream_out: TextIO, catalog_path: Path) -> int:
    """Read requests until stdin closes; the host owns our lifetime."""
    for line in stream_in:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError:
            # No id to answer against, so JSON-RPC says report it against null
            # rather than dying on one bad line.
            _write(stream_out, {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "parse error"},
            })
            continue
        if not isinstance(request, dict):
            _write(stream_out, {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "invalid request"},
            })
            continue
        try:
            response = handle_request(request, catalog_path)
        except Exception as exc:  # one bad request must not kill the lane
            # A handler exception (e.g. a malformed catalog field reaching
            # score_entry before it was coerced, or any future tool bug) used
            # to walk straight out of this read loop and kill the ard-mcp
            # process, dropping every other tool call with it. JSON-RPC 2.0
            # -32603: contain it to the one request, log on stderr (stdout is
            # the protocol channel), and stay up for the next line.
            print(
                f"ard-mcp: internal error on request: {exc!r}", file=sys.stderr
            )
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32603, "message": "internal error"},
            }
        if response is not None:
            _write(stream_out, response)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MCP stdio front over an ard-kit catalog.",
    )
    parser.add_argument(
        "--catalog",
        default="ai-catalog.json",
        help="Catalog file produced by catalogize.py (default: ./ai-catalog.json).",
    )
    args = parser.parse_args()
    # stderr only, same as every other complaint here: stdout is the protocol
    # channel, so a refused --catalog must not be written as a JSON line.
    path_error = guard_posix_paths({"catalog": args.catalog})
    if path_error:
        print(f"ERROR: {path_error}", file=sys.stderr)
        return 2
    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        # stderr only: stdout is the protocol channel and must stay JSON.
        print(
            "WARNING: catalog not found - " + _catalog_hint(catalog_path),
            file=sys.stderr,
        )
    return serve(sys.stdin, sys.stdout, catalog_path)


if __name__ == "__main__":
    sys.exit(main())
