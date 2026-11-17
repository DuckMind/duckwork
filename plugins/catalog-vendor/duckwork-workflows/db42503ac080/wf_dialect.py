#!/usr/bin/env python3
"""wf_dialect — the js-dialect interop seam (#33).

Two functions, one contract (`references/dialect.md` §1-§3, fixture corpus
`tests/fixtures/dialect/`):

  js_export(graph, name=None) -> str
      wf/1 graph dict -> a `.claude/workflows/<name>.js` script in Anthropic's
      documented shape (static `export const meta`, sequential top-level `await
      agent(...)`, `parallel([...])` for a static fan-out, `pipeline(items, stage…)`
      for an `items_from` fan-out and for a chain of fan-outs, `${args.KEY}` for
      `{run.KEY}`). Every wf/1 key with NO counterpart on their side (gates,
      requires, budgets, on_skip, profile, toolsets, repo, provider, …) is emitted
      as a `// LOSSY:` line at the node AND summarised in the header — never
      silently dropped. A graph whose SEMANTICS cannot be represented at all
      (fan-out `quorum` race, a human gate with no `default_option`, a `when`
      gate that prunes an arm, an `inputs` ref into a fan-out's `all_results`)
      is REFUSED with a named reason (DialectRefusal), mirroring the importer.
      Byte-stable for equal input.

  js_import(source, node_check=True) -> {"ok": True, "graph": <wf/1>, "warnings": [...]}
                                      | {"ok": False, "refuse": "<construct> at line N", ...}
      Their script -> a wf/1 graph, implementing ONLY the §3 constrained subset by
      conservative line-oriented extraction (a tiny string/comment/bracket scanner
      plus regexes; NO JavaScript parser). Everything outside the subset is refused
      with the construct and its 1-based line named. Refusals are not approximations:
      the importer never emulates JS glue.

Stdlib only. The only subprocess is the OPTIONAL `node --check <file>.js` syntax
gate (their shape — ESM export + top-level await + top-level return — only parses
as a `.js` PATH, never as a module string, so the gate writes a scratch file);
when `node` is absent the gate degrades to a documented skip-with-warning
(`node_check: skipped`), never a crash.

CLI (no door surface; see references/portable.md):
  python3 wf_dialect.py import <file.js> [--no-node-check]   -> JSON result on stdout, exit 0/1
  python3 wf_dialect.py export <graph.json> [--name N] [--out <path.js>]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

__all__ = ["js_export", "js_import", "export_report", "DialectRefusal", "node_check"]

# ---------------------------------------------------------------------------
# shared vocabulary
# ---------------------------------------------------------------------------

AGENT_OPTS = ("schema", "label", "model", "phase")   # dialect.md row 1 — the documented set
_JS_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_ID_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")   # wfcommon.ID_OK, duplicated to stay standalone
_RUN_KEY = re.compile(r"\{run\.([A-Za-z_][A-Za-z0-9_]*)\}")
_INPUTS_MARK = "## Inputs (wf/1 refs)"   # exporter-owned section; the importer strips it back to refs
_FORBIDDEN_CALLS = ("Date.now", "Math.random", "new Date", "Promise.resolve", "Promise.all", "import(")
_GLUE_METHODS = ("map", "filter", "reduce", "forEach", "join", "then", "catch", "flat", "flatMap",
                 "some", "every", "find", "slice", "splice", "concat", "sort", "keys", "values",
                 "entries", "split", "trim", "toLowerCase", "toUpperCase", "replace", "push", "pop")


def _forbidden_label(bad):
    if bad.endswith("("):
        return bad + ")"
    if bad.startswith("new"):
        return bad + "()"
    return bad + "()"


class DialectRefusal(Exception):
    """Raised by the exporter when a graph's semantics have no representable form.
    `.reason` is the named ground; `.node` the offending node id when there is one."""

    def __init__(self, reason, node=None):
        super().__init__(reason)
        self.reason = reason
        self.node = node


class _Refuse(Exception):
    def __init__(self, construct, line, detail=""):
        super().__init__(construct)
        self.construct, self.line, self.detail = construct, line, detail


# ---------------------------------------------------------------------------
# scanner: strings/comments masked, statements split, arguments split
# ---------------------------------------------------------------------------

def _mask(src):
    """Return a same-length copy of `src` where the INSIDE of every string literal and
    every comment is blanked (newlines kept so offsets and line numbers line up).
    Template-literal `${ … }` expression bodies stay visible (they are code); the
    `${`/`}` delimiters stay too. Quotes stay so callers can find literal spans."""
    out = list(src)
    i, n = 0, len(src)
    stack = []   # ("tpl", brace_depth) frames for nested template expressions
    while i < n:
        c = src[i]
        two = src[i:i + 2]
        if two == "//":
            j = src.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        if two == "/*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if src[k] != "\n":
                    out[k] = " "
            i = j
            continue
        if c in ("'", '"'):
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                if src[j] == "\\":
                    j += 1
                j += 1
            for k in range(i + 1, min(j, n)):
                out[k] = " "
            i = min(j, n) + 1
            continue
        if c == "`":
            i += 1
            while i < n:
                ch = src[i]
                if ch == "\\":
                    out[i] = " "
                    if i + 1 < n and src[i + 1] != "\n":
                        out[i + 1] = " "
                    i += 2
                    continue
                if ch == "`":
                    i += 1
                    break
                if src[i:i + 2] == "${":
                    # expression body: scan visibly until the matching close brace
                    i += 2
                    depth = 1
                    while i < n and depth:
                        ch = src[i]
                        if ch in ("'", '"'):
                            j = i + 1
                            while j < n and src[j] != ch and src[j] != "\n":
                                if src[j] == "\\":
                                    j += 1
                                j += 1
                            for k in range(i + 1, min(j, n)):
                                out[k] = " "
                            i = min(j, n) + 1
                            continue
                        if ch == "`":   # nested template inside an expression: blank it whole
                            j = i + 1
                            while j < n and src[j] != "`":
                                if src[j] == "\\":
                                    j += 1
                                j += 1
                            for k in range(i + 1, min(j, n)):
                                if src[k] != "\n":
                                    out[k] = " "
                            i = min(j, n) + 1
                            continue
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                        i += 1
                    continue
                if ch != "\n":
                    out[i] = " "
                i += 1
            continue
        i += 1
    return "".join(out)


def _line(src, off):
    return src.count("\n", 0, off) + 1


def _statements(src, masked):
    """Top-level statements as (start, end) offsets: split on `;` or newline at
    bracket depth 0. A `{`/`(`/`[` opened on one line keeps the statement open."""
    out = []
    depth = 0
    start = None
    i, n = 0, len(masked)
    while i < n:
        c = masked[i]
        if start is None:
            if not c.isspace() and c != ";":
                start = i
            i += 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == ";" and depth == 0:
            out.append((start, i))
            start = None
        elif c == "\n" and depth == 0:
            # a line ending in an operator / comma / dot continues (chained `.then(` on the next line)
            tail = masked[start:i].rstrip()
            nxt = masked[i + 1:].lstrip()
            if tail and tail[-1] in "=,.(+-*/&|?:" or nxt.startswith("."):
                i += 1
                continue
            out.append((start, i))
            start = None
        i += 1
    if start is not None:
        out.append((start, n))
    return [(s, e) for s, e in out if src[s:e].strip()]


def _split_top(masked, s, e, sep=","):
    """Split masked[s:e] on `sep` at bracket depth 0 -> list of (start, end)."""
    parts, depth, ps = [], 0, s
    for i in range(s, e):
        c = masked[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == sep and depth == 0:
            parts.append((ps, i))
            ps = i + 1
    parts.append((ps, e))
    return parts


def _match_close(masked, open_at):
    """Offset of the bracket closing the one at `open_at`."""
    pair = {"(": ")", "[": "]", "{": "}"}[masked[open_at]]
    depth = 0
    for i in range(open_at, len(masked)):
        c = masked[i]
        if c == masked[open_at]:
            depth += 1
        elif c == pair:
            depth -= 1
            if depth == 0:
                return i
    return -1


# ---------------------------------------------------------------------------
# literal parser (JSON-ish object/array/string/number/bool + template literals)
# ---------------------------------------------------------------------------

class _Tpl:
    """A template literal: parts are str (literal text) or _Ref (an `${expr}`)."""
    __slots__ = ("parts",)

    def __init__(self, parts):
        self.parts = parts


class _Ref:
    __slots__ = ("expr", "off")

    def __init__(self, expr, off):
        self.expr, self.off = expr, off


_ESC = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0",
        "\\": "\\", "'": "'", '"': '"', "`": "`", "$": "$", "\n": ""}


def _unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            d = s[i + 1]
            if d == "u" and i + 5 < len(s):
                try:
                    out.append(chr(int(s[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            out.append(_ESC.get(d, d))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


class _NonLiteral(Exception):
    def __init__(self, what, off):
        super().__init__(what)
        self.what, self.off = what, off


def _skip_ws(masked, i):
    n = len(masked)
    while i < n and masked[i].isspace():
        i += 1
    return i


def _parse_literal(src, masked, i, allow_tpl=True):
    """Parse one literal starting at offset i (whitespace allowed). Returns (value, next)."""
    i = _skip_ws(masked, i)
    if i >= len(src):
        raise _NonLiteral("unexpected end of input", i)
    c = src[i]
    if c in ("'", '"'):
        j = i + 1
        while j < len(src) and src[j] != c:
            if src[j] == "\\":
                j += 1
            j += 1
        return _unescape(src[i + 1:j]), j + 1
    if c == "`":
        if not allow_tpl:
            raise _NonLiteral("template literal", i)
        parts, buf, j = [], [], i + 1
        while j < len(src) and src[j] != "`":
            if src[j] == "\\":
                buf.append(src[j:j + 2])
                j += 2
                continue
            if src[j:j + 2] == "${":
                if buf:
                    parts.append(_unescape("".join(buf)))
                    buf = []
                close = _match_close(masked, j + 1)
                if close < 0:
                    raise _NonLiteral("unterminated template expression", j)
                parts.append(_Ref(src[j + 2:close].strip(), j + 2))
                j = close + 1
                continue
            buf.append(src[j])
            j += 1
        if buf:
            parts.append(_unescape("".join(buf)))
        return _Tpl(parts), j + 1
    if c == "{":
        obj, j = {}, i + 1
        while True:
            j = _skip_ws(masked, j)
            if j >= len(src):
                raise _NonLiteral("unterminated object", i)
            if src[j] == "}":
                return obj, j + 1
            if src[j:j + 3] == "...":
                raise _NonLiteral("spread", j)
            if src[j] in ("'", '"'):
                key, j = _parse_literal(src, masked, j, allow_tpl=False)
            else:
                m = _JS_IDENT.match(src, j)
                if not m:
                    raise _NonLiteral("object key", j)
                key, j = m.group(0), m.end()
            j = _skip_ws(masked, j)
            if j >= len(src) or src[j] != ":":
                raise _NonLiteral("shorthand/computed property", j)
            val, j = _parse_literal(src, masked, j + 1, allow_tpl)
            obj[key] = val
            j = _skip_ws(masked, j)
            if j < len(src) and src[j] == ",":
                j += 1
    if c == "[":
        arr, j = [], i + 1
        while True:
            j = _skip_ws(masked, j)
            if j >= len(src):
                raise _NonLiteral("unterminated array", i)
            if src[j] == "]":
                return arr, j + 1
            if src[j:j + 3] == "...":
                raise _NonLiteral("spread", j)
            val, j = _parse_literal(src, masked, j, allow_tpl)
            arr.append(val)
            j = _skip_ws(masked, j)
            if j < len(src) and src[j] == ",":
                j += 1
    m = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?").match(src, i)
    if m:
        t = m.group(0)
        return (float(t) if any(x in t for x in ".eE") else int(t)), m.end()
    for word, val in (("true", True), ("false", False), ("null", None)):
        if src.startswith(word, i) and not _JS_IDENT.match(src, i + len(word)):
            return val, i + len(word)
    m = _JS_IDENT.match(src, i)
    raise _NonLiteral(m.group(0) if m else src[i], i)


def _has_tpl(v):
    if isinstance(v, (_Tpl, _Ref)):
        return True
    if isinstance(v, dict):
        return any(_has_tpl(x) for x in v.values())
    if isinstance(v, list):
        return any(_has_tpl(x) for x in v)
    return False


# ---------------------------------------------------------------------------
# node --check gate (optional subprocess)
# ---------------------------------------------------------------------------

def node_check(source, timeout=20):
    """`node --check` on a scratch `.js` PATH (their shape needs the .js extension).
    Returns {"status": "ok"|"error"|"skipped", "detail": str}. Never raises."""
    node = shutil.which("node")
    if not node:
        return {"status": "skipped", "detail": "node not on PATH — syntax gate skipped; "
                                               "the importer's own scanner is the only check"}
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix="wf-dialect-", suffix=".js")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(source)
        p = subprocess.run([node, "--check", tmp], capture_output=True, text=True, timeout=timeout)
        if p.returncode == 0:
            return {"status": "ok", "detail": ""}
        err = (p.stderr or p.stdout or "").strip().replace(tmp, "<script>")
        return {"status": "error", "detail": err[-600:]}
    except Exception as e:   # a broken node is a skip, not a crash
        return {"status": "skipped", "detail": f"node --check unavailable: {type(e).__name__}: {e}"}
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# IMPORT
# ---------------------------------------------------------------------------

class _Importer:
    def __init__(self, src):
        self.src = src
        self.masked = _mask(src)
        self.consts = {}      # js const -> {"kind": "agent"|"fanout", "id", "schema", "source": "parallel"|"pipeline"}
        self.nodes = []
        self.ids = set()
        self.warnings = []
        self.dropped = []
        self.meta = None
        self.returned = None

    # -- helpers ------------------------------------------------------------
    def line(self, off):
        return _line(self.src, off)

    def refuse(self, construct, off, detail=""):
        raise _Refuse(construct, self.line(off), detail)

    def close_of(self, open_at, what, at=None):
        """_match_close or a named refusal (F2 #36): an unterminated construct is reported as
        itself — `unterminated <what> / unbalanced brackets at line N` — never as the glue
        message the `close < 0` branches used to fall into. `node --check` is lenient on
        ESM-detected .js (measured, Node 26), so this scanner message is what the user sees."""
        close = _match_close(self.masked, open_at)
        if close < 0:
            self.refuse(f"unterminated {what} / unbalanced brackets", open_at if at is None else at)
        return close

    def unbalanced(self, s, e):
        """True when masked[s:e] does not close every bracket it opens (an unterminated inner
        object/array keeps the statement open across lines, so the OUTER close still matches)."""
        depth = 0
        for c in self.masked[s:e]:
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
        return depth != 0

    def new_id(self, base, off):
        cand = re.sub(r"[^A-Za-z0-9_.-]", "_", str(base)) or "node"
        if not cand[0].isalnum():
            cand = "n" + cand
        cand = cand[:64]
        out, k = cand, 2
        while out in self.ids:
            out = f"{cand[:60]}_{k}"
            k += 1
        self.ids.add(out)
        return out

    def add_node(self, node):
        self.nodes.append(node)
        return node

    # -- statement walk -----------------------------------------------------
    def run(self):
        stmts = _statements(self.src, self.masked)
        if not stmts:
            raise _Refuse("empty script", 1)
        first_s, first_e = stmts[0]
        if not self.masked[first_s:first_e].lstrip().startswith("export const meta"):
            # meta absent or not first: name the first statement that stands in its way
            m = re.search(r"export\s+const\s+meta\b", self.masked)
            if m:
                self.refuse("non-literal meta (spread) / meta not first statement", m.start()
                            if "..." in self.masked[m.start():] else m.start())
            self.refuse("missing export const meta", first_s)
        self.parse_meta(first_s, first_e)
        # Pass 1 (dialect.md row 7): a top-level loop/branch is the LOUDEST construct — it is
        # named before any glue that merely feeds it (`let round = 0` above a `while`).
        for s, e in stmts[1:]:
            head = self.masked[s:e].lstrip()
            kw = _control_kw(head)
            if kw:
                self.refuse(kw, s + (e - s - len(head)))
        for s, e in stmts[1:]:
            if self.returned is not None:
                self.refuse("statement after return", s)
            self.statement(s, e)
        if not self.nodes:
            raise _Refuse("no agent() call (nothing to import)", self.line(stmts[-1][0]))
        return self.graph()

    def parse_meta(self, s, e):
        m = re.compile(r"export\s+const\s+meta\s*=\s*").match(self.masked, s)
        if not m:
            self.refuse("non-literal meta", s)
        try:
            val, j = _parse_literal(self.src, self.masked, m.end(), allow_tpl=False)
        except _NonLiteral as ex:
            self.refuse("non-literal meta (spread) / meta not first statement" if ex.what == "spread"
                        else f"non-literal meta ({ex.what})", ex.off)
        if not isinstance(val, dict) or not isinstance(val.get("name"), str) or not val["name"].strip():
            self.refuse("meta without a literal string name", s)
        if re.search(r"[\\/\s]", val["name"]) or val["name"] in (".", ".."):
            # portable.md: the graph is saved as <name>.workflow.json — a separator or whitespace
            # is a path, not a name (their side: `/<name>` command, same constraint)
            self.refuse("meta.name contains a path separator or whitespace", s)
        if self.masked[j:e].strip():
            self.refuse("non-literal meta (trailing expression)", j)
        for k in val:
            if k not in ("name", "description", "phases", "whenToUse"):
                self.refuse(f"unknown meta key: {k}", s)
        if "phases" in val:
            self.dropped.append("meta.phases (display-only; dialect.md row 4)")
        if "whenToUse" in val:
            self.dropped.append("meta.whenToUse (NOT DOCUMENTED; dropped)")
        self.meta = val

    def statement(self, s, e):
        text = self.src[s:e]
        mk = self.masked[s:e]
        head = mk.lstrip()
        off0 = s + (len(mk) - len(head))
        kw = _control_kw(head)
        if kw:
            self.refuse(kw, off0)
        m = re.match(r"(let|var)\s+", head)
        if m:
            self.refuse(f"{m.group(1)} declaration (mutable state)", off0)
        if re.match(r"(import|export)\b", head):
            self.refuse("import/export (only `export const meta` is allowed)", off0)
        if re.match(r"(function|class|async)\b", head):
            self.refuse("function/class declaration", off0)
        m = re.match(r"(phase|log)\s*\(", head)
        if m:
            return self.phase_or_log(m.group(1), off0, e)
        if re.match(r"return\b", head):
            return self.ret(off0, e)
        m = re.match(r"const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*", head)
        if m:
            name = m.group(1)
            rhs_off = off0 + m.end()
            rhs = self.masked[rhs_off:e].lstrip()
            rhs_off = e - len(rhs) if rhs else rhs_off
            rhs = rhs.rstrip()
            if name in self.consts:
                self.refuse(f"const {name} redeclared", off0)
            m2 = re.match(r"await\s+(agent|parallel|pipeline)\s*\(", rhs)
            if m2:
                kind = m2.group(1)
                open_at = rhs_off + m2.end() - 1
                close = self.close_of(open_at, f"{kind}(...)", at=off0)
                if self.masked[close + 1:e].strip():
                    if self.unbalanced(off0, e):
                        self.refuse(f"unterminated {kind}(...) / unbalanced brackets", off0)
                    self.refuse(f"expression after {kind}(...) (glue)", off0)
                return getattr(self, "c_" + kind)(name, open_at, close, off0)
            m3 = re.match(r"(agent|parallel|pipeline)\s*\(", rhs)
            if m3:
                self.refuse(f"un-awaited {m3.group(1)}() (a Promise held for later glue)", rhs_off)
            self.forbidden_in(rhs_off, e)
            self.refuse(self.glue_name(rhs) or "non-agent const expression (glue)", rhs_off)
        if re.match(r"await\s+(agent|parallel|pipeline)\s*\(", head):
            self.refuse("bare await without a const (result discarded — no node id)", off0)
        m = re.match(r"([A-Za-z_$][A-Za-z0-9_$.]*)\s*(=|\+=|-=)", head)
        if m and not head.startswith("const"):
            self.refuse("re-assignment of a result (mutable state)", off0)
        self.forbidden_in(off0, e)
        self.refuse(self.glue_name(head) or f"unrecognised statement `{text.strip()[:40]}`", off0)

    def glue_name(self, mk):
        """Best-effort name for a glue expression, from its visible method calls."""
        found = []
        if re.search(r"\bnew\s+Set\b", mk):
            found.append("Set")
        for meth in _GLUE_METHODS:
            if re.search(r"\." + meth + r"\s*\(", mk):
                found.append(meth)
        if "=>" in mk and not found:
            found.append("closure")
        if found:
            return "closure/glue between agents (" + "/".join(found) + ")"
        return ""

    def phase_or_log(self, which, off, e):
        open_at = self.masked.find("(", off)
        close = self.close_of(open_at, f"{which}(...)", at=off)
        try:
            val, j = _parse_literal(self.src, self.masked, open_at + 1, allow_tpl=True)
        except _NonLiteral as ex:
            self.refuse(f"{which}() with a non-literal argument", ex.off)
        if isinstance(val, _Tpl) and any(isinstance(p, _Ref) for p in val.parts):
            self.refuse(f"{which}() with a template over results (glue)", open_at)
        if not isinstance(val, (str, _Tpl)) or self.masked[j:close].strip():
            self.refuse(f"{which}() with a non-literal argument", open_at)
        self.dropped.append(f"{which}({json.dumps(val if isinstance(val, str) else ''.join(val.parts))}) "
                            f"at line {self.line(off)} (display-only)")

    def ret(self, off, e):
        expr = self.src[off + len("return"):e].strip()
        mexpr = self.masked[off + len("return"):e].strip()
        m = re.fullmatch(r"([A-Za-z_$][A-Za-z0-9_$]*)", mexpr)
        if m and m.group(1) in self.consts:
            self.returned = m.group(1)
            return
        m = re.fullmatch(r"([A-Za-z_$][A-Za-z0-9_$]*)\s*\.\s*filter\s*\(\s*Boolean\s*\)", mexpr)
        if m and m.group(1) in self.consts:
            if self.consts[m.group(1)]["kind"] != "fanout":
                self.refuse("computed return (.filter on a non-pipeline result)", off)
            self.returned = m.group(1)
            self.warnings.append(f"return {m.group(1)}.filter(Boolean) imported as the bare sink "
                                 f"(a no-op against fan-out output.items; dialect.md row 12)")
            return
        if mexpr.startswith("{") or mexpr.startswith("["):
            self.refuse("computed return (object/array construction)", off)
        self.forbidden_in(off, e)
        self.refuse(self.glue_name(mexpr).replace("closure/glue between agents", "computed return")
                    or f"computed return (`{expr[:40]}`)", off)

    # -- agent(...) argument parsing --------------------------------------
    def agent_args(self, open_at, close, params=()):
        """Parse `agent(<prompt>, {opts})` between the parens. Returns (prompt, opts, opt_offsets).
        `params` are the enclosing arrow-function parameter names (pipeline item/prev): a bare
        `label: file` is accepted as the per-item label (it is their documented idiom)."""
        parts = _split_top(self.masked, open_at + 1, close)
        parts = [p for p in parts if self.masked[p[0]:p[1]].strip()]
        if not parts or len(parts) > 2:
            self.refuse("agent() with an unexpected argument count", open_at)
        ps, pe = parts[0]
        self.forbidden_in(ps, pe)
        try:
            prompt, j = _parse_literal(self.src, self.masked, ps, allow_tpl=True)
        except _NonLiteral as ex:
            self.refuse(f"non-literal agent() prompt ({ex.what})", ex.off)
        if not isinstance(prompt, (str, _Tpl)) or self.masked[j:pe].strip():
            self.refuse("non-literal agent() prompt", ps)
        opts, offs = {}, {}
        if len(parts) == 2:
            os_, oe = parts[1]
            k = _skip_ws(self.masked, os_)
            if k >= oe or self.src[k] != "{":
                self.refuse("agent() options are not an object literal", k)
            ok_close = self.close_of(k, "agent() options object")
            if self.masked[ok_close + 1:oe].strip():
                self.refuse("agent() options followed by an expression", ok_close + 1)
            for bs, be in _split_top(self.masked, k + 1, ok_close):
                seg = self.masked[bs:be]
                if not seg.strip():
                    continue
                m = re.match(r"\s*([A-Za-z_$][A-Za-z0-9_$]*|'[^']*'|\"[^\"]*\")\s*:", seg)
                if not m:
                    if "..." in seg:
                        self.refuse("spread inside agent() options", bs)
                    self.refuse("agent() option is not a `key: value` pair", bs)
                key = m.group(1).strip("'\"")
                offs[key] = bs + m.start(1)
                if key not in AGENT_OPTS:
                    self.refuse(f"unknown agent() option: {key}", offs[key])
                vs = bs + m.end()
                self.forbidden_in(vs, be)
                try:
                    val, j = _parse_literal(self.src, self.masked, vs, allow_tpl=True)
                except _NonLiteral as ex:
                    if key == "label" and ex.what in params:
                        val, j = _Tpl([_Ref(ex.what, ex.off)]), ex.off + len(ex.what)
                    else:
                        self.refuse(f"non-literal agent() option {key} ({ex.what})", ex.off)
                if self.masked[j:be].strip():
                    self.refuse(f"agent() option {key} followed by an expression (glue)", j)
                opts[key] = val
            if "schema" in opts and (not isinstance(opts["schema"], dict) or _has_tpl(opts["schema"])):
                self.refuse("agent() schema is not a static object literal", offs.get("schema", k))
            if "model" in opts and not isinstance(opts["model"], str):
                self.refuse("agent() model is not a string literal", offs.get("model", k))
            if "label" in opts and not isinstance(opts["label"], (str, _Tpl)):
                # display-only on their side; a non-string can never seed an id -> warn, keep going
                self.warnings.append(f"agent() label at line {self.line(offs.get('label', k))} is not a string "
                                     f"({type(opts['label']).__name__}); ignored (label is display-only)")
            if "phase" in opts:
                self.dropped.append(f"agent option phase at line {self.line(offs.get('phase', k))} (display-only)")
        return prompt, opts, offs

    def forbidden_in(self, s, e):
        """dialect.md row 13: name Date.now()/Math.random()/new Date()/Promise.* by name."""
        seg = self.masked[s:e]
        for bad in _FORBIDDEN_CALLS:
            p = seg.find(bad)
            if p >= 0:
                self.refuse(_forbidden_label(bad), s + p)

    def label_text(self, label):
        """A literal label -> str; a template label -> its literal spine (for ids)."""
        if isinstance(label, str):
            return label
        if isinstance(label, _Tpl):
            return "".join(p for p in label.parts if isinstance(p, str)).strip("-_ ")
        return ""

    # -- template rendering -------------------------------------------------
    def ref_parts(self, ref):
        """`${expr}` -> ('args', key) | ('const', name, [fields]) | refuse. Accepts the
        exporter's JSON.stringify(<ref>) wrapper as a transparent serialization."""
        expr = ref.expr
        for bad in _FORBIDDEN_CALLS:
            if bad in expr:
                self.refuse(_forbidden_label(bad), ref.off)
        m = re.fullmatch(r"JSON\.stringify\(\s*([A-Za-z_$][A-Za-z0-9_$.]*)\s*\)", expr)
        if m:
            expr = m.group(1)
        if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*(\.[A-Za-z_$][A-Za-z0-9_$]*)*", expr):
            if re.search(r"\[[^\]]*\]", expr) and re.match(r"[A-Za-z_$][A-Za-z0-9_$]*", expr):
                head = re.match(r"[A-Za-z_$][A-Za-z0-9_$]*", expr).group(0)
                if head in self.consts and self.consts[head]["kind"] == "fanout":
                    self.refuse(f"template property access on a {self.consts[head]['source']} const (${{{expr}}})", ref.off)
            g = self.glue_name(expr)
            self.refuse(g.replace("closure/glue between agents", "template expression glue") if g
                        else f"template expression is not a plain reference (${{{expr}}})", ref.off)
        head, *fields = expr.split(".")
        if head == "args":
            if len(fields) != 1:
                self.refuse("args used as a whole value / nested path (only args.<key> in a template)", ref.off)
            return ("args", fields[0])
        return ("const", head, fields)

    def split_inputs_tail(self, parts):
        """The exporter's own `## Inputs (wf/1 refs)` tail is pure refs: fold it back to
        after/inputs with no prose. Returns (body parts, pure ref list). Shared by plain and
        fan-out item templates (a stage's node-level refs are emitted in the same section)."""
        tail_at = None
        for i, p in enumerate(parts):
            if isinstance(p, str) and _INPUTS_MARK in p:
                tail_at = i
                break
        if tail_at is None:
            return parts, []
        pre = parts[tail_at].split(_INPUTS_MARK, 1)[0].rstrip("\n")
        pure = [p for p in parts[tail_at + 1:] if isinstance(p, _Ref)]
        return parts[:tail_at] + ([pre] if pre else []), pure

    def render_plain(self, prompt, off, node):
        """A NON-fan-out goal: refs -> after/inputs (§3 data-flow rule), prose names the input."""
        if isinstance(prompt, str):
            return prompt
        parts, pure = self.split_inputs_tail(list(prompt.parts))
        out = []
        for p in parts:
            if isinstance(p, str):
                out.append(p)
                continue
            out.append(self.plain_ref(p, node, prose=True))
        for r in pure:
            self.plain_ref(r, node, prose=False)
        return "".join(out)

    def plain_ref(self, ref, node, prose):
        kind = self.ref_parts(ref)
        if kind[0] == "args":
            return "{run.%s}" % kind[1]
        _, name, fields = kind
        if name not in self.consts:
            self.refuse(f"template reference to an unknown/glue value (${{{ref.expr}}})", ref.off)
        c = self.consts[name]
        if c["kind"] == "fanout" and fields:
            self.refuse(f"template property access on a {c['source']} const (${{{ref.expr}}})", ref.off)
        if fields:
            props = (c.get("schema") or {}).get("properties") or {}
            if fields[0] not in props:
                self.refuse(f"template field ${{{ref.expr}}} is not declared by agent '{name}'s schema "
                            f"(use the bare const ${{{name}}} to inject it whole)", ref.off)
            refstr = ".".join([c["id"]] + fields)
            node.setdefault("inputs", [])
            if refstr not in node["inputs"]:
                node["inputs"].append(refstr)
            text = f"the input `{refstr}` (injected below)"
        else:
            text = f"the committed output of `{c['id']}` (injected below)"
        node.setdefault("after", [])
        if c["id"] not in node["after"]:
            node["after"].append(c["id"])
        return text if prose else ""

    def render_item(self, prompt, node, item_param, prev_param, prev_schema, stage_no, item_schema):
        """A fan-out ITEM goal: item/prev fields -> bare `{field}` (wf.py fmt_goal). An outer
        agent const ref imports as NODE-LEVEL inputs/after (§3: build_inputs renders one
        identical section for every item), the prose naming the ref like a plain goal."""
        if isinstance(prompt, str):
            return prompt
        parts, pure = self.split_inputs_tail(list(prompt.parts))
        out = []
        for p in parts:
            if isinstance(p, str):
                out.append(p)
                continue
            kind = self.ref_parts(p)
            if kind[0] == "args":
                out.append("{run.%s}" % kind[1])
                continue
            _, name, fields = kind
            if name == item_param or name == prev_param:
                if not fields:
                    out.append("{item}")
                    continue
                if len(fields) > 1:
                    self.refuse(f"nested item field ${{{p.expr}}} (fan-out templates interpolate one level)", p.off)
                if name == item_param and stage_no > 1:
                    carried = (prev_schema or {}).get("properties") or {}
                    if fields[0] not in carried:
                        self.refuse(f"stage {stage_no} references item.{fields[0]} not carried by stage {stage_no - 1}", p.off)
                    self.warnings.append(f"stage {stage_no} reads item.{fields[0]} — resolved from stage "
                                         f"{stage_no - 1}'s output field of the same name (per-node barrier)")
                if name == prev_param and prev_schema is not None:
                    carried = prev_schema.get("properties") or {}
                    if fields[0] not in carried:
                        self.refuse(f"stage {stage_no} references prev.{fields[0]} not declared by stage {stage_no - 1}'s schema", p.off)
                out.append("{%s}" % fields[0])
                continue
            out.append(self.plain_ref(p, node, prose=True))
        for r in pure:   # same order as render_plain: prose refs first, then the exporter's tail
            self.plain_ref(r, node, prose=False)
        return "".join(out)

    # -- const kinds ----------------------------------------------------------
    def c_agent(self, name, open_at, close, off):
        prompt, opts, offs = self.agent_args(open_at, close)
        nid = self.new_id(name, off)
        node = {"id": nid, "type": "agent"}
        node["goal"] = self.render_plain(prompt, open_at, node)
        if "model" in opts:
            node["model"] = opts["model"]
        if "schema" in opts:
            node["schema"] = opts["schema"]
        if "label" in opts and self.label_text(opts["label"]) not in ("", name):
            self.warnings.append(f"agent '{name}': label {json.dumps(self.label_text(opts['label']))} is display-only; "
                                 f"node id is the const name '{nid}'")
        self.consts[name] = {"kind": "agent", "id": nid, "schema": opts.get("schema"), "source": "agent"}
        self.add_node(_ordered(node))

    def c_parallel(self, name, open_at, close, off):
        k = _skip_ws(self.masked, open_at + 1)
        if k >= close or self.src[k] != "[":
            self.refuse("parallel() over a computed array (not a static [...] literal)", k)
        arr_close = self.close_of(k, "parallel([...])")
        if self.masked[arr_close + 1:close].strip():
            self.refuse("parallel() with extra arguments", arr_close + 1)
        node = {"id": None, "type": "agent"}
        items = []
        schemas = []
        for es, ee in _split_top(self.masked, k + 1, arr_close):
            seg = self.masked[es:ee]
            if not seg.strip():
                continue
            m = re.match(r"\s*(?:\(\s*\)\s*=>\s*|async\s*\(\s*\)\s*=>\s*)?agent\s*\(", seg)
            if not m:
                if "=>" in seg and "{" in seg.split("=>", 1)[1].lstrip()[:1]:
                    self.refuse("parallel element is a block-bodied thunk (glue)", es)
                self.refuse("parallel element is not an agent(...) call or a thunk returning one", es + len(seg) - len(seg.lstrip()))
            a_open = es + m.end() - 1
            a_close = self.close_of(a_open, "agent(...) inside parallel([...])")
            if self.masked[a_close + 1:ee].strip():
                self.refuse("parallel element chains an expression after agent(...) (glue)", a_close + 1)
            prompt, opts, offs = self.agent_args(a_open, a_close)
            it = {}
            lab = self.label_text(opts.get("label", ""))
            if lab:
                it["id"] = lab
            if "model" in opts:
                self.warnings.append(f"parallel '{name}': per-element model {opts['model']!r} has no per-item form; dropped")
            it["goal"] = self.render_plain(prompt, a_open, node)
            if "schema" in opts:
                schemas.append(opts["schema"])
            items.append(_ordered_item(it))
        if not items:
            self.refuse("parallel([]) with no elements", k)
        nid = self.new_id(name, off)
        node["id"] = nid
        node["fanout"] = {"items": items}
        if schemas:
            if all(s == schemas[0] for s in schemas) and len(schemas) == len(items):
                node["fanout"]["schema"] = schemas[0]
            else:
                self.warnings.append(f"parallel '{name}': elements carry differing/partial schemas; "
                                     f"fanout.schema is one object per node, so none was set")
        self.consts[name] = {"kind": "fanout", "id": nid, "schema": None, "source": "parallel"}
        self.add_node(_ordered(node))

    def c_pipeline(self, name, open_at, close, off):
        args = [(s, e) for s, e in _split_top(self.masked, open_at + 1, close) if self.masked[s:e].strip()]
        if len(args) < 2:
            self.refuse("pipeline() needs an item source and at least one stage", open_at)
        ss, se = args[0]
        src_txt = self.masked[ss:se].strip()
        src_off = ss + (len(self.masked[ss:se]) - len(self.masked[ss:se].lstrip()))
        items, items_from, first_after = None, None, None
        item_schema = None
        if src_txt.startswith("["):
            try:
                items, j = _parse_literal(self.src, self.masked, src_off, allow_tpl=False)
            except _NonLiteral as ex:
                self.refuse(f"pipeline item list is not a static literal ({ex.what})", ex.off)
            if self.masked[j:se].strip():
                self.refuse("pipeline item list followed by an expression", j)
            if not items:
                self.refuse("pipeline([]) with no items", src_off)
        else:
            m = re.fullmatch(r"([A-Za-z_$][A-Za-z0-9_$]*)((?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)", src_txt)
            if not m:
                if src_txt.startswith("args"):
                    self.refuse("args used as an iterable item source", src_off)
                self.refuse(self.glue_name(src_txt).replace("closure/glue between agents", "computed pipeline item source")
                            or "computed pipeline item source", src_off)
            head, path = m.group(1), m.group(2).lstrip(".")
            if head == "args":
                self.refuse("args used as an iterable item source", src_off)
            if head not in self.consts:
                self.refuse(f"pipeline over an unknown/glue value ({src_txt})", src_off)
            c = self.consts[head]
            if c["kind"] == "fanout":
                if path:
                    self.refuse(f"template property access on a {c['source']} const ({src_txt})", src_off)
                items_from = f"{c['id']}.items"
                self.warnings.append(f"pipeline '{name}' iterates the whole result of fan-out '{c['id']}' "
                                     f"-> items_from '{items_from}' (our output.items omits failed items; "
                                     f"theirs keeps nulls positionally)")
            else:
                if not path:
                    self.refuse(f"pipeline over a whole agent result ({head}) — name the array field", src_off)
                props = (c.get("schema") or {}).get("properties") or {}
                fld = path.split(".")[0]
                if fld not in props:
                    self.refuse(f"pipeline item source {src_txt} is not declared by agent '{head}'s schema", src_off)
                items_from = f"{c['id']}.{path}"
                item_schema = (props.get(fld) or {}).get("items") if "." not in path else None
            first_after = c["id"]
        prev_id, prev_schema, prev_label = None, None, None
        stage_ids = []
        for stage_no, (st_s, st_e) in enumerate(args[1:], 1):
            seg = self.masked[st_s:st_e]
            lead = st_s + (len(seg) - len(seg.lstrip()))
            m = re.match(r"\s*(?:async\s*)?(?:\(\s*([A-Za-z_$][A-Za-z0-9_$]*)?\s*(?:,\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*)?\)|([A-Za-z_$][A-Za-z0-9_$]*))\s*=>\s*", seg)
            if not m:
                self.refuse(f"pipeline stage {stage_no} is not an arrow function", lead)
            p1 = m.group(1) or m.group(3)
            p2 = m.group(2)
            body = seg[m.end():].lstrip()
            body_off = st_s + m.end() + (len(seg[m.end():]) - len(body))
            if body.startswith("{"):
                inner = body[1:]
                names = []
                if re.search(r"\bif\b", inner):
                    names.append("if")
                if "Promise.resolve" in inner:
                    names.append("Promise.resolve")
                if re.search(r"\.then\s*\(", inner):
                    names.append(".then")
                self.refuse("block-bodied pipeline stage with " + " / ".join(names) if names
                            else "block-bodied pipeline stage (glue)", lead)
            m2 = re.match(r"agent\s*\(", body)
            if not m2:
                self.refuse(self.glue_name(body).replace("closure/glue between agents", f"pipeline stage {stage_no} glue")
                            or f"pipeline stage {stage_no} is not a direct agent(...) call", body_off)
            a_open = body_off + m2.end() - 1
            a_close = self.close_of(a_open, f"agent(...) in pipeline stage {stage_no}")
            if self.masked[a_close + 1:st_e].strip():
                self.refuse(f"pipeline stage {stage_no} chains an expression after agent(...) (.then / glue)", a_close + 1)
            prompt, opts, offs = self.agent_args(a_open, a_close, params=tuple(x for x in (p1, p2) if x))
            if stage_no == 1:
                item_param, prev_param = p1, None
            else:
                prev_param, item_param = p1, p2
            node = {"id": None, "type": "agent"}
            lab = self.label_text(opts.get("label", ""))
            base = lab if (lab and len(args) > 2) else name
            if stage_no > 1 and not lab:
                base = f"{name}_stage{stage_no}"
            nid = self.new_id(base, off)
            node["id"] = nid
            goal = self.render_item(prompt, node, item_param, prev_param, prev_schema, stage_no, item_schema)
            fo = {}
            if stage_no == 1:
                if items is not None:
                    fo["items"] = items
                else:
                    fo["items_from"] = items_from
                    node.setdefault("after", [])
                    if first_after not in node["after"]:
                        node["after"].insert(0, first_after)
            else:
                fo["items_from"] = f"{prev_id}.items"
                node.setdefault("after", [])
                if prev_id not in node["after"]:
                    node["after"].insert(0, prev_id)
            fo["goal"] = goal
            if "schema" in opts:
                fo["schema"] = opts["schema"]
            if "model" in opts:
                node["model"] = opts["model"]
            node["fanout"] = fo
            self.add_node(_ordered(node))
            stage_ids.append(nid)
            prev_id, prev_schema = nid, opts.get("schema")
        self.consts[name] = {"kind": "fanout", "id": stage_ids[-1], "schema": None, "source": "pipeline",
                             "stages": stage_ids}

    def graph(self):
        g = {"grammar": "wf/1", "name": self.meta["name"]}
        if isinstance(self.meta.get("description"), str) and self.meta["description"].strip():
            g["description"] = self.meta["description"]
        g["nodes"] = self.nodes
        if self.returned is not None:
            sink = self.consts[self.returned]["id"]
            if self.nodes[-1]["id"] != sink:
                self.warnings.append(f"return names '{sink}' but the last node is '{self.nodes[-1]['id']}'; "
                                     f"the graph's sink is structural (no key added)")
        return g


_NODE_ORDER = ("id", "type", "after", "inputs", "goal", "model", "schema", "fanout")


def _control_kw(head):
    for kw in ("while", "for", "do", "if", "else", "switch", "try", "throw"):
        if re.match(kw + r"\b", head):
            return kw
    return ""


def _ordered(node):
    return {k: node[k] for k in _NODE_ORDER if k in node}


def _ordered_item(it):
    return {k: it[k] for k in ("id", "goal") if k in it}


def js_import(source, node_check=True):
    """See module docstring. `node_check=False` skips the optional subprocess gate."""
    if not isinstance(source, str):
        return {"ok": False, "refuse": "source is not a string at line 1", "construct": "input", "line": 1}
    gate = {"status": "not_run", "detail": ""}
    if node_check:
        gate = globals()["node_check"](source)
        if gate["status"] == "error":
            m = re.search(r":(\d+)\n", gate["detail"] + "\n")
            ln = int(m.group(1)) if m else 1
            return {"ok": False, "refuse": f"syntax error (node --check) at line {ln}",
                    "construct": "syntax error (node --check)", "line": ln, "node_check": gate}
    imp = _Importer(source)
    try:
        graph = imp.run()
    except _Refuse as r:
        out = {"ok": False, "refuse": f"{r.construct} at line {r.line}", "construct": r.construct,
               "line": r.line, "node_check": gate}
        if r.detail:
            out["detail"] = r.detail
        return out
    warnings = list(imp.warnings)
    if imp.dropped:
        warnings.append("dropped (display-only): " + "; ".join(imp.dropped))
    if gate["status"] == "skipped":
        warnings.append("node_check: skipped — " + gate["detail"])
    return {"ok": True, "graph": graph, "warnings": warnings, "node_check": gate}


# ---------------------------------------------------------------------------
# EXPORT
# ---------------------------------------------------------------------------

_AGENT_EXACT = {"id", "type", "after", "goal", "schema", "model", "inputs", "fanout", "context"}
_LOSSY_AGENT = ("provider", "toolsets", "max_turns", "timeout", "run_budget", "reasoning", "tier",
                "shape", "repo", "require_route", "route_verified", "profile", "requires")
_LOSSY_GATE = ("hold_timeout", "on_skip", "requires", "context", "wait", "when")
_LOSSY_FANOUT = ("schema",)   # only when per-item goals (parallel form carries schema per element anyway)


def _js_str(s):
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


def _tpl_escape(s):
    return str(s).replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def _js_literal(v, indent=0):
    """Deterministic JS literal (sorted object keys) — JSON is a JS subset."""
    return json.dumps(v, sort_keys=True, ensure_ascii=False, indent=None, separators=(", ", ": "))


def _const_name(nid, taken):
    base = re.sub(r"[^A-Za-z0-9_$]", "_", nid)
    if not re.match(r"[A-Za-z_$]", base):
        base = "n_" + base
    if base in ("args", "meta", "agent", "parallel", "pipeline", "phase", "log", "return", "await",
                "const", "let", "var", "item", "prev"):
        base = base + "_"
    out, k = base, 2
    while out in taken:
        out = f"{base}_{k}"
        k += 1
    taken.add(out)
    return out


def _run_args(text):
    return _RUN_KEY.sub(lambda m: "${args.%s}" % m.group(1), _tpl_escape(text))


def _string_typed(schema, field):
    props = (schema or {}).get("properties") or {}
    return (props.get(field) or {}).get("type") == "string"


class _Exporter:
    def __init__(self, graph, name):
        self.g = graph
        self.name = name or graph.get("name") or "workflow"
        self.lossy = []       # (node id, key, note)
        self.warnings = []
        self.pins = []
        self.taken = set()
        self.const = {}       # node id -> js const
        self.form = {}        # node id -> "agent"|"parallel"|"pipeline"|"gate"|"echo"|"stage"
        self.byid = {}
        self.defaults = graph.get("defaults") if isinstance(graph.get("defaults"), dict) else {}

    def refuse(self, reason, node=None):
        raise DialectRefusal(reason, node)

    def run(self):
        nodes = self.g.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            self.refuse("graph has no nodes")
        for n in nodes:
            if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not _ID_OK.match(n["id"]):
                self.refuse("node without a valid id")
            if n["id"] in self.byid:
                self.refuse(f"duplicate node id '{n['id']}'", n["id"])
            if n.get("type") not in ("agent", "gate", "echo"):
                self.refuse(f"node '{n['id']}' has unknown type {n.get('type')!r}", n["id"])
            self.byid[n["id"]] = n
        for n in nodes:
            for a in n.get("after") or []:
                if a not in self.byid:
                    self.refuse(f"node '{n['id']}' after unknown node '{a}'", n["id"])
        order = self.wave_order(nodes)
        self.check_semantics(nodes)
        for k in sorted(set(self.defaults) - {"model", "schema", "context"}):
            self.lossy.append(("defaults", k, _js_literal(self.defaults[k])))
        if self.g.get("model_policy"):
            self.lossy.append(("graph", "model_policy", _js_literal(self.g["model_policy"])))
        chain = self.chains(nodes, order)
        for n in order:
            self.const[n["id"]] = _const_name(n["id"], self.taken)
        lines = []
        depth = self.depths
        cur_wave = None
        emitted = set()
        for n in order:
            nid = n["id"]
            if nid in emitted:
                continue
            if depth[nid] != cur_wave:
                cur_wave = depth[nid]
                lines.append("")
                lines.append(f"phase({_js_str('Wave ' + str(cur_wave + 1))})")
            if n["type"] == "echo":
                lines.extend(self.emit_echo(n))
            elif n["type"] == "gate":
                lines.extend(self.emit_gate(n))
            elif n.get("fanout"):
                stages = chain.get(nid, [nid])
                lines.extend(self.emit_fanout(stages))
                emitted.update(stages)
            else:
                lines.extend(self.emit_agent(n))
            emitted.add(nid)
        last = order[-1]["id"]
        # the sink is the last node in wave order; a chained fan-out's sink is its last stage const
        sink_const = self.const[last]
        ret = f"return {sink_const}"
        if self.form.get(last) == "pipeline" or self.form.get(last) == "stage":
            ret += ".filter(Boolean)"
        body = "\n".join(lines).rstrip("\n") + "\n\n" + ret + "\n"
        return self.header() + self.meta(nodes) + body

    # -- ordering -----------------------------------------------------------
    def wave_order(self, nodes):
        depth = {}
        pending = list(nodes)
        guard = 0
        while pending:
            guard += 1
            if guard > len(nodes) + 2:
                self.refuse("cycle in graph (after edges)")
            rest = []
            for n in pending:
                ps = n.get("after") or []
                if all(p in depth for p in ps):
                    depth[n["id"]] = 0 if not ps else 1 + max(depth[p] for p in ps)
                else:
                    rest.append(n)
            if len(rest) == len(pending):
                self.refuse("cycle in graph (after edges)")
            pending = rest
        self.depths = depth
        idx = {n["id"]: i for i, n in enumerate(nodes)}
        return sorted(nodes, key=lambda n: (depth[n["id"]], idx[n["id"]]))

    def check_semantics(self, nodes):
        kids = {n["id"]: [] for n in nodes}
        for n in nodes:
            for a in n.get("after") or []:
                kids[a].append(n["id"])
        for n in nodes:
            nid = n["id"]
            fo = n.get("fanout")
            if isinstance(fo, dict) and fo.get("quorum") is not None:
                self.refuse(f"fanout.quorum on '{nid}': a first-N-wins race with straggler cancellation has "
                            f"no counterpart (parallel/pipeline are barriers) — remove quorum to export", nid)
            if n["type"] == "gate":
                if n.get("when") is not None and kids[nid] and n.get("on_skip", "prune") != "pass":
                    self.refuse(f"gate '{nid}' has a `when` predicate that prunes descendants "
                                f"({', '.join(kids[nid])}): their runtime has no bounded branch; "
                                f"export only a gate with on_skip:'pass' or no descendants", nid)
                if n.get("wait") is None and n.get("options") is not None and n.get("default_option") is None:
                    self.refuse(f"human gate '{nid}' has no default_option: their runtime cannot pause, and a "
                                f"silently auto-approved gate is worse than no export", nid)
                if n.get("wait") is None and n.get("options") is None and n.get("when") is None:
                    self.refuse(f"human gate '{nid}' has no options/default_option: their runtime cannot pause", nid)
            for ref in n.get("inputs") or []:
                head, _, path = str(ref).partition(".")
                src = self.byid.get(head)
                if src and src.get("fanout") and path not in ("", "items"):
                    self.refuse(f"node '{nid}' inputs ref '{ref}' reads inside a fan-out's committed object "
                                f"({{items, all_results}}): their result is a bare positional array, so only "
                                f"'{head}' or '{head}.items' can be represented", nid)
                if src and src["type"] == "gate" and path:
                    self.refuse(f"node '{nid}' inputs ref '{ref}' reads a field of gate '{head}': a gate's "
                                f"answer is a string on their side", nid)
            if n["type"] == "agent" and not n.get("fanout") and not n.get("goal"):
                self.refuse(f"agent '{nid}' has no goal", nid)

    def chains(self, nodes, order):
        """fan-out b directly after fan-out a with items_from a.items and no other reader of a
        -> one pipeline(items, s1, s2, …). Returns {head id: [stage ids]}."""
        consumers = {n["id"]: [] for n in nodes}
        for n in nodes:
            for a in n.get("after") or []:
                consumers[a].append(n["id"])
            for r in n.get("inputs") or []:
                consumers[str(r).split(".")[0]].append(n["id"])
            fo = n.get("fanout") or {}
            if fo.get("items_from"):
                consumers[str(fo["items_from"]).split(".")[0]].append(n["id"])
        nxt = {}
        for n in nodes:
            fo = n.get("fanout")
            if not fo or not fo.get("items_from"):
                continue
            head, _, path = str(fo["items_from"]).partition(".")
            a = self.byid.get(head)
            if not a or not a.get("fanout") or path != "items":
                continue
            if (n.get("after") or []) != [head] or n.get("inputs"):
                continue
            if set(consumers[head]) != {n["id"]}:
                continue
            if self.uniform_template(a) is None or self.uniform_template(n) is None:
                continue
            nxt[head] = n["id"]
        heads = [h for h in nxt if h not in nxt.values()]
        out = {}
        for h in heads:
            chain = [h]
            while chain[-1] in nxt:
                chain.append(nxt[chain[-1]])
            out[h] = chain
        return out

    def uniform_template(self, n):
        """A fan-out that is one template for every item (no per-item goals) -> template text."""
        fo = n["fanout"]
        items = fo.get("items")
        if items is not None and any(isinstance(it, dict) and it.get("goal") for it in items):
            return None
        return fo.get("goal") or n.get("goal") or None

    # -- emission -----------------------------------------------------------
    def lossy_lines(self, n, keys):
        out = []
        for k in keys:
            if n.get(k) is not None:
                v = n[k]
                note = _js_literal(v)
                if len(note) > 120:
                    note = note[:117] + "..."
                self.lossy.append((n["id"], k, note))
                out.append(f"// LOSSY: {k} = {note} — no counterpart in the js dialect; dropped")
        return out

    def agent_opts(self, n, label, extra_schema=None):
        opts = []
        opts.append(f"label: {_js_str(label)}")
        model = n.get("model") or self.defaults.get("model")
        if model:
            opts.append(f"model: {_js_str(model)}")
            if n.get("model") and n.get("require_route", True) is not False:
                self.pins.append(f"{n['id']}={model}")
        schema = extra_schema if extra_schema is not None else (n.get("schema") or self.defaults.get("schema"))
        if schema:
            opts.append(f"schema: {_js_literal(schema)}")
        return "{ " + ", ".join(opts) + " }"

    def node_context(self, n):
        """Effective `context` of an agent node = wfcommon.apply_graph_defaults semantics
        (wfcommon.apply_graph_defaults), folded AT EXPORT: defaults.context is prepended unless the node's
        own context already starts with it (a door-loaded graph arrives normalised; a raw
        fixture/CLI graph does not — both must export the same bytes). Applies to plain
        agents AND fan-outs: wf.py passes node.context to every fan-out child (wf.py `run_child` fan-out sites)."""
        ctx = str(n.get("context") or "")
        pre = str(self.defaults.get("context") or "")
        if pre and not ctx.startswith(pre):
            ctx = pre + ("\n\n" + ctx if ctx else "")
        return ctx

    def node_schema(self, n):
        """Plain-agent schema with the defaults.schema fill of wfcommon.py:411-413."""
        return n.get("schema") or self.defaults.get("schema")

    def fanout_schema(self, n):
        """Per-item schema as the runner resolves it: fanout.schema, else the node schema
        (which wfcommon fills from defaults.schema at load) — wf.py:1662."""
        return (n.get("fanout") or {}).get("schema") or self.node_schema(n)

    def prompt_text(self, n, goal):
        """goal (+context) + the exporter-owned refs section for after/inputs."""
        text = goal
        ctx = self.node_context(n)
        if ctx:   # context rides in the prompt, after the goal, as run_child composes it
            text = text + "\n\n" + ctx
        refs = []
        covered = set()
        for r in n.get("inputs") or []:
            head, _, path = str(r).partition(".")
            covered.add(head)
            refs.append(self.ref_expr(head, path))
        for p in n.get("after") or []:
            if p in covered:
                continue
            refs.append(self.ref_expr(p, ""))
        out = _run_args(text)
        if refs:
            out += "\n\n" + _INPUTS_MARK + "\n" + "\n".join(refs)
        return out

    def ref_expr(self, head, path):
        c = self.const[head]
        src = self.byid[head]
        if src["type"] == "echo":
            val = src.get("output")
            for part in [x for x in path.split(".") if x]:
                val = val.get(part) if isinstance(val, dict) else (val[int(part)] if isinstance(val, list) and part.isdigit() and int(part) < len(val) else None)
            tail = f".{path}" if path else ""
            expr = f"${{{c}{tail}}}" if isinstance(val, str) else f"${{JSON.stringify({c}{tail})}}"
        elif src["type"] == "gate":
            expr = f"${{{c}}}"
        elif src.get("fanout"):
            expr = f"${{JSON.stringify({c})}}"
        elif path:
            first = path.split(".")[0]
            if _string_typed(src.get("schema") or self.defaults.get("schema"), first) and "." not in path:
                expr = f"${{{c}.{path}}}"
            else:
                expr = f"${{JSON.stringify({c}.{path})}}"
        else:
            expr = f"${{{c}}}" if not (src.get("schema") or self.defaults.get("schema")) else f"${{JSON.stringify({c})}}"
        label = head if not path else f"{head}.{path}"
        return f"{label}: {expr}"

    def emit_agent(self, n):
        self.form[n["id"]] = "agent"
        out = self.lossy_lines(n, _LOSSY_AGENT)
        out.append(f"const {self.const[n['id']]} = await agent(`{self.prompt_text(n, n['goal'])}`, "
                   f"{self.agent_opts(n, n['id'])})")
        return out

    def emit_echo(self, n):
        self.form[n["id"]] = "echo"
        return [f"const {self.const[n['id']]} = {_js_literal(n.get('output'))}"]

    def emit_gate(self, n):
        self.form[n["id"]] = "gate"
        out = []
        c = self.const[n["id"]]
        if n.get("wait") is not None:
            out.append(f"// WAIT: {_js_literal(n['wait'])} — machine wait dropped (their runtime has no park); "
                       f"the script continues as if released")
            out.extend(self.lossy_lines(n, ("wait",) + tuple(k for k in _LOSSY_GATE if k != "wait")))
            out.append(f"const {c} = 'released'")
            return out
        q = n.get("question") or ""
        opts = n.get("options") or []
        d = n.get("default_option")
        out.append(f"// HOLD: {q} {_js_literal(opts)} — their runtime cannot pause; continuing with "
                   f"default_option {_js_literal(d)}")
        out.extend(self.lossy_lines(n, _LOSSY_GATE))
        out.append(f"const {c} = {_js_literal(d)}")
        return out

    def render_item_template(self, tmpl, param, item_schema, static_items, allow_prev=False):
        """`{field}` tokens -> `${param.field}` per wf.py fmt_goal, `{item}` -> `${param}`,
        `{run.K}` -> `${args.K}`; `{index}` has no per-item form (LOSSY, left literal)."""
        text = _tpl_escape(tmpl)
        known = None
        if item_schema and isinstance(item_schema, dict):
            if item_schema.get("type") == "string":
                known = set()
            elif item_schema.get("properties"):
                known = set(item_schema["properties"])
        if static_items is not None:
            known = set()
            for it in static_items:
                if isinstance(it, dict):
                    known |= set(it)
            if all(not isinstance(it, dict) for it in static_items):
                known = set()
        seen_index = []

        def sub(m):
            key = m.group(1)
            if key.startswith("run."):
                return "${args.%s}" % key[4:]
            if key == "item":
                return "${%s}" % param
            if key == "index":
                seen_index.append(1)
                return m.group(0)
            if not re.fullmatch(r"[A-Za-z0-9_]+", key):
                return m.group(0)
            if known is not None and key not in known:
                return m.group(0)
            return "${%s.%s}" % (param, key)
        text = re.sub(r"\{([^{}]+)\}", sub, text)
        if known is None:
            self.warnings.append("fan-out template item fields are undeclared (no item schema); every bare "
                                 "{field} token was mapped to ${%s.field}" % param)
        return text, bool(seen_index)

    def emit_fanout(self, stages):
        head = self.byid[stages[0]]
        fo = head["fanout"]
        out = []
        if len(stages) == 1 and fo.get("items") is not None and self.uniform_template(head) is None:
            return self.emit_parallel(head)
        # pipeline form
        for sid in stages:
            out.extend(self.lossy_lines(self.byid[sid], _LOSSY_AGENT))
        if fo.get("items") is not None:
            src_expr = _js_literal(fo["items"])
            item_schema = None
            static_items = fo["items"]
        else:
            h, _, path = str(fo["items_from"]).partition(".")
            srcn = self.byid[h]
            if srcn.get("fanout"):
                src_expr = self.const[h]
                item_schema = self.fanout_schema(srcn)
                self.warnings.append(f"fan-out '{head['id']}' iterates '{fo['items_from']}': their pipeline "
                                     f"result keeps nulls positionally; our output.items omits failed items")
            else:
                src_expr = f"{self.const[h]}.{path}"
                props = (srcn.get("schema") or self.defaults.get("schema") or {}).get("properties") or {}
                item_schema = (props.get(path.split(".")[0]) or {}).get("items") if "." not in path else None
            static_items = None
        stage_lines = []
        prev_schema = None
        for i, sid in enumerate(stages):
            n = self.byid[sid]
            tmpl = self.uniform_template(n)
            param = "item" if i == 0 else "prev"
            text, idx = self.render_item_template(tmpl, param, item_schema if i == 0 else prev_schema,
                                                  static_items if i == 0 else None)
            if idx:
                self.lossy.append((sid, "{index}", "fan-out template uses {index}; no per-item index in pipeline()"))
                stage_lines.append("  // LOSSY: {index} placeholder has no counterpart inside pipeline(); left literal")
            extra = self.prompt_text_refs(n, skip=[stages[i - 1]] if i else [h for h in [str(fo.get("items_from", "")).partition(".")[0]] if h])
            ctx = self.node_context(n)
            if ctx:   # F1 (#36): node/defaults context rides in every item prompt, raw (never item-formatted), as wf.py `run_child` passes it
                text += "\n\n" + _run_args(ctx)
            if extra:
                text += "\n\n" + _INPUTS_MARK + "\n" + extra
            schema = self.fanout_schema(n)
            opts = self.agent_opts(n, sid, extra_schema=schema or {})
            stage_lines.append(f"  ({param}) => agent(`{text}`, {opts}),")
            prev_schema = schema
            self.form[sid] = "pipeline" if i == 0 else "stage"
            self.const[sid] = self.const[stages[0]] if i == 0 else self.const[sid]
        c = self.const[stages[0]]
        for sid in stages[1:]:
            self.const[sid] = c   # every stage's committed output is the pipeline's result const
        out.append(f"const {c} = await pipeline(")
        out.append(f"  {src_expr},")
        out.extend(stage_lines)
        out.append(")")
        return out

    def prompt_text_refs(self, n, skip):
        refs, covered = [], set()
        for r in n.get("inputs") or []:
            head, _, path = str(r).partition(".")
            covered.add(head)
            refs.append(self.ref_expr(head, path))
        for p in n.get("after") or []:
            if p in covered or p in skip:
                continue
            refs.append(self.ref_expr(p, ""))
        return "\n".join(refs)

    def emit_parallel(self, n):
        self.form[n["id"]] = "parallel"
        out = self.lossy_lines(n, _LOSSY_AGENT)
        fo = n["fanout"]
        refs = self.prompt_text_refs(n, skip=[])
        schema = self.fanout_schema(n)
        ctx = self.node_context(n)   # F1 (#36): same fold as prompt_text; wf.py `run_child` gives it to every item
        elems = []
        for i, it in enumerate(fo["items"]):
            own = it.get("goal") if isinstance(it, dict) and isinstance(it.get("goal"), str) and it["goal"].strip() else None
            tmpl = own if own is not None else (fo.get("goal") or n.get("goal") or "")
            goal = _fmt_goal(tmpl, it, i)
            if own is not None and n.get("goal"):
                goal = n["goal"] + "\n\n" + goal
            text = _run_args(goal)
            if ctx:
                text += "\n\n" + _run_args(ctx)
            if refs:
                text += "\n\n" + _INPUTS_MARK + "\n" + refs
            label = it.get("id") if isinstance(it, dict) and isinstance(it.get("id"), str) else f"{n['id']}-{i}"
            elems.append(f"  () => agent(`{text}`, {self.agent_opts(n, label, extra_schema=schema or {})}),")
        out.append(f"const {self.const[n['id']]} = await parallel([")
        out.extend(elems)
        out.append("])")
        return out

    # -- header/meta ----------------------------------------------------------
    def header(self):
        h = [f"// {self.name}.js — exported from a duckwork-workflows wf/1 graph by wf_dialect (#33).",
             "// Their runtime awaits each statement in order; independent nodes of one wave run back-to-back.",
             "// Object-valued references are JSON.stringify'd into prompts; string fields are interpolated bare."]
        if self.lossy:
            h.append(f"// LOSSY SUMMARY: {len(self.lossy)} governance field(s) have no counterpart in the js dialect "
                     f"and were DROPPED (see the // LOSSY line at each node):")
            for nid, k, v in self.lossy:
                h.append(f"//   {nid}.{k}" + (f" = {v}" if nid in ("defaults", "graph") else ""))
        else:
            h.append("// LOSSY SUMMARY: none — every key of this graph has a counterpart.")
        if self.pins:
            h.append("// FAIL-CLOSED PINS (require_route): " + ", ".join(self.pins)
                     + " — their runtime SUBSTITUTES a blocked model with a warning; ours refuses the launch.")
        prov = self.g.get("provenance")
        if isinstance(prov, dict):
            h.append("// provenance: " + _js_literal(prov))
        return "\n".join(h) + "\n\n"

    def meta(self, nodes):
        ng = sum(1 for n in nodes if n["type"] == "gate")
        nf = sum(1 for n in nodes if n.get("fanout"))
        desc = self.g.get("description") or f"{len(nodes)} nodes, {ng} gates, {nf} fan-outs"
        return ("export const meta = {\n"
                f"  name: {_js_str(self.name)},\n"
                f"  description: {_js_str(desc)},\n"
                "}\n")


def _fmt_goal(text, item, idx):
    """wf.py fmt_goal, duplicated so the exporter stays standalone."""
    class D(dict):
        def __missing__(self, k):
            return "{" + k + "}"
    fields = D(item) if isinstance(item, dict) else D()
    if "item" not in fields:
        fields["item"] = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
    fields["index"] = idx
    return re.sub(r"\{([^{}]+)\}", lambda m: str(fields.get(m.group(1), m.group(0))), text) if text else ""


def export_report(graph, name=None):
    """{"ok": True, "js": str, "lossy": [{node, key, value}], "warnings": [...]} |
    {"ok": False, "refuse": reason, "node": id}. Never raises on a bad graph."""
    ex = _Exporter(graph, name)
    try:
        js = ex.run()
    except DialectRefusal as r:
        return {"ok": False, "refuse": r.reason, "node": r.node}
    return {"ok": True, "js": js, "lossy": [{"node": a, "key": b, "value": c} for a, b, c in ex.lossy],
            "warnings": ex.warnings}


def js_export(graph, name=None):
    """wf/1 graph dict -> js source (str). Raises DialectRefusal with a named reason."""
    return _Exporter(graph, name).run()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main(argv):
    if len(argv) >= 2 and argv[0] == "import":
        src = open(argv[1], encoding="utf-8").read()
        res = js_import(src, node_check="--no-node-check" not in argv)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res["ok"] else 1
    if len(argv) >= 2 and argv[0] == "export":
        graph = json.load(open(argv[1], encoding="utf-8"))
        name = argv[argv.index("--name") + 1] if "--name" in argv else None
        out = argv[argv.index("--out") + 1] if "--out" in argv else None
        if out and not os.path.isdir(os.path.dirname(os.path.abspath(out))):
            print(f"refusing: parent directory does not exist (never created): {out}", file=sys.stderr)
            return 1
        res = export_report(graph, name)
        if not res["ok"]:
            print(json.dumps({"ok": False, "refuse": res["refuse"], "node": res["node"]}), file=sys.stderr)
            return 1
        for w in res["warnings"]:
            print("warning: " + w, file=sys.stderr)
        for l in res["lossy"]:
            print(f"LOSSY: {l['node']}.{l['key']} dropped ({l['value']})", file=sys.stderr)
        if out:
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(res["js"])
            print(out)
        else:
            sys.stdout.write(res["js"])
        return 0
    print("usage:" + __doc__.split("CLI (no door surface; see references/portable.md):", 1)[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
