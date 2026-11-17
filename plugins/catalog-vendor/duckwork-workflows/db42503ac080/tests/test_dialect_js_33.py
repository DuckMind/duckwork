#!/usr/bin/env python3
"""#33 js-dialect interop: the 13-fixture corpus is the spec.

(1) every `verdict: importable` fixture js_imports to a graph that validates under the
    shared validator, is def-equal to the sidecar's graph_sketch on every key the sketch
    pins EXCEPT plain-goal prose (the sketch's goals are hand-paraphrased; the contract
    pins the mechanism — inputs/after refs and NO brace tokens on plain goals — and the
    fan-out goals byte-for-byte);
(2) every `verdict: refuse` fixture js_imports to ok:false naming the sidecar's
    refuse_construct (name-equal, or the sidecar's headword for the two glue rows whose
    sidecar text lists every method) at refuse_line;
(3) export(import(fixture)) round-trips: the emitted .js passes `node --check` (when node
    exists), re-imports, and the re-imported nodes are def-equal to the first import;
(4) the exporter's golden (`tests/fixtures/dialect/golden-export.workflow.json`, every
    lossy family + a decorative gate + an echo + a run_context binding + a fan-out of each
    form carrying `context`, with `defaults.context`/`defaults.schema` set) exports to
    byte-pinned output (sha256 below), every dropped key appears as a `// LOSSY:` line AT
    the node AND in the header summary, fan-out `context` rides in every item prompt (#36
    F1 — the runtime gives it to every child; a raw graph and a wfcommon-normalised one
    export the same bytes), and the semantic refusals (quorum, gate without
    default_option, pruning `when`, all_results ref) name their node;
(5) node --check degrades to skip-with-warning when node is absent (PATH emptied).
Standalone, stdlib only: `python3 tests/test_dialect_js_33.py` -> exit 0 + ALL PASS.
"""
import copy, hashlib, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = HERE / "fixtures" / "dialect"
sys.path.insert(0, str(ROOT))
import wf_dialect as d   # noqa: E402
import wfcommon           # noqa: E402

GOLDEN_SHA256 = "8e3a5ad05f247010be8567779e52e4659ed72982494f75e6a10a44e95018591c"

ok = 0
def check(cond, msg, detail=""):
    global ok
    assert cond, msg + (f"  << {detail}" if detail else "")
    ok += 1
    print("PASS", msg)


# --- courtesy-gate feature detection (#227) -------------------------------------------
# `node --check` is a COURTESY gate (see section (5) below and the docstring of the
# node-absent test): the python-side scanner verdict is the authoritative one and the
# node gate must never flip it. Measured node families on this corpus (issue #227
# matrix, official nodejs.org linux-x64 builds):
#   PASS --check on every fixture: 22.11, 22.21, 23.11, 24.0-24.20, 25.2, 26.7
#   FAIL --check on the refuse fixtures: 24.21.0+ (tightened ESM top-level-return
#     detection: a file containing `export` parses as ESM and the dialect's top-level
#     `return` became a hard SyntaxError)
# Rather than hard-coding versions, feature-detect: `node --check` a canonical
# dialect-valid script (export meta + one agent + bare return — the exact shape the
# exporter emits). If this node build rejects even THAT, its verdict cannot be the
# gate for dialect-shaped files, and refuse-fixture assertions defer to the scanner
# (node_check=False) with a WARN. On builds whose --check accepts the canonical script,
# the original assertion stands unchanged — a TRUE syntax error in a refuse fixture
# (one node sees but the canonical script passes) stays RED.
_CANON_VALID = "export const meta = { name: 'probe' }\nconst a = await agent('p')\nreturn a\n"
NODE_COURTESY_TRUSTED = d.node_check(_CANON_VALID)["status"] != "error"

fixtures = sorted(FIX.glob("*.js"))
check(len(fixtures) == 13, "corpus has 13 .js fixtures", str(len(fixtures)))
imported = {}
if not NODE_COURTESY_TRUSTED:
    print("WARN node --check rejects the canonical dialect-valid script — courtesy gate "
          "distrusted for the corpus loop; the python scanner is the verdict (#227)")
for js in fixtures:
    exp = json.loads(js.with_suffix(".expected.json").read_text(encoding="utf-8"))
    src = js.read_text(encoding="utf-8")
    r = d.js_import(src, node_check=NODE_COURTESY_TRUSTED)
    name = js.stem
    if exp["verdict"] == "importable":
        check(r["ok"], f"{name}: importable fixture imports", json.dumps(r)[:300])
        g = r["graph"]
        check(g.get("grammar") == "wf/1" and g.get("name") == exp["graph_sketch"]["name"],
              f"{name}: graph is wf/1 and keeps meta.name")
        errs = wfcommon.validate_graph_errors(g)
        check(errs == [], f"{name}: imported graph passes the shared validator", json.dumps(errs))
        sk = exp["graph_sketch"]["nodes"]
        got = g["nodes"]
        check([n["id"] for n in got] == [n["id"] for n in sk], f"{name}: node ids/order == sketch",
              str([n["id"] for n in got]))
        for sn, gn in zip(sk, got):
            for k, v in sn.items():
                if k == "goal" and "fanout" not in sn:
                    # mechanism, not prose: no brace token other than {run.K}; input names appear
                    # (the source's own prose braces like "Return {findings}." are theirs and stay)
                    tokens = [t for t in re.findall(r"\{([^{}]+)\}", gn["goal"]) if not t.startswith("run.")]
                    bad = [t for t in tokens if any(t in (ref, ref.split(".")[0], ref.split(".", 1)[-1])
                                                    for ref in sn.get("inputs", []) + sn.get("after", []))]
                    check(not bad, f"{name}/{sn['id']}: plain goal carries no brace token for a ref", str(bad))
                    for ref in sn.get("inputs", []):
                        check(ref in gn["goal"], f"{name}/{sn['id']}: goal names input {ref} in prose", gn["goal"])
                    for key in re.findall(r"\{run\.([a-z]+)\}", v):
                        check("{run.%s}" % key in gn["goal"], f"{name}/{sn['id']}: goal keeps {{run.{key}}}")
                    continue
                if k == "fanout":
                    fv = {kk: vv for kk, vv in gn["fanout"].items() if kk in v}
                    check(fv == v, f"{name}/{sn['id']}: fanout == sketch (items/items_from/goal)",
                          json.dumps(gn["fanout"]))
                    continue
                check(gn.get(k) == v, f"{name}/{sn['id']}: {k} == sketch", json.dumps(gn.get(k)))
        for gn in got:
            if gn.get("schema") is not None:
                check("schema" in gn, f"{name}/{gn['id']}: schema carried")
        imported[name] = g
        # sidecar rows cite the node kinds present
        if 3 in exp["rows"]:
            check(any("items_from" in (n.get("fanout") or {}) for n in got), f"{name}: row 3 -> items_from fan-out present")
        if 2 in exp["rows"]:
            check(any("items" in (n.get("fanout") or {}) for n in got), f"{name}: row 2 -> static-items fan-out present")
        if 4 in exp["rows"]:
            check(any("display-only" in w for w in r["warnings"]), f"{name}: row 4 -> phase drop reported", str(r["warnings"]))
        if 5 in exp["rows"]:
            check(any("{run." in json.dumps(n) for n in got), f"{name}: row 5 -> {{run.KEY}} binding present")
    else:
        check(not r["ok"], f"{name}: refuse fixture is refused", json.dumps(r)[:300])
        want_c, want_l = exp["refuse_construct"], exp["refuse_line"]
        got_c = r["construct"]
        head = want_c.split(" (")[0]
        check(got_c == want_c or got_c.startswith(head), f"{name}: refuse names {want_c!r}", got_c)
        check(r["line"] == want_l, f"{name}: refuse cites line {want_l}", str(r["line"]))
        check(r["refuse"] == f"{got_c} at line {r['line']}", f"{name}: refuse string is '<construct> at line N'", r["refuse"])
        check("graph" not in r, f"{name}: a refusal carries no graph (never an approximation)")

check(len(imported) == 5, "five importable fixtures (sidecar verdicts)", str(sorted(imported)))

# --- (3) round trip ------------------------------------------------------------------
node_present = d.node_check("export const meta = { name: 'x' }\nreturn 1\n")["status"] == "ok"
for name, g in sorted(imported.items()):
    rep = d.export_report(g)
    check(rep["ok"], f"{name}: export of the imported graph succeeds", json.dumps(rep)[:300])
    check(rep["lossy"] == [], f"{name}: export is exact (no LOSSY lines)", json.dumps(rep["lossy"]))
    js = rep["js"]
    check("export const meta = {" in js and f"name: '{name}'" in js, f"{name}: export starts with a static literal meta")
    check("// LOSSY SUMMARY: none" in js, f"{name}: header states no loss")
    check(d.js_export(g) == js == d.js_export(copy.deepcopy(g)), f"{name}: export is byte-stable")
    if node_present:
        nc = d.node_check(js)
        check(nc["status"] == "ok", f"{name}: exported script passes node --check", nc["detail"])
    r2 = d.js_import(js, node_check=False)
    check(r2["ok"], f"{name}: exported script re-imports", json.dumps(r2)[:300])
    check(r2["graph"]["nodes"] == g["nodes"], f"{name}: re-imported nodes are def-equal to the first import",
          json.dumps(r2["graph"]["nodes"])[:400])
    check(wfcommon.validate_graph_errors(r2["graph"]) == [], f"{name}: re-imported graph validates")
    # pipelines end with the documented idiom; plain sinks are bare returns
    last = g["nodes"][-1]
    if (last.get("fanout") or {}).get("items_from"):
        check(re.search(r"^return \w+\.filter\(Boolean\)$", js, re.M), f"{name}: pipeline sink returns .filter(Boolean)")
    else:
        check(re.search(r"^return \w+$", js, re.M), f"{name}: sink is a bare `return <const>`")

# --- (4) golden export of our own graph ---------------------------------------------
golden = json.loads((FIX / "golden-export.workflow.json").read_text(encoding="utf-8"))
check(wfcommon.validate_graph_errors(golden) == [], "golden graph validates", json.dumps(wfcommon.validate_graph_errors(golden)))
rep = d.export_report(golden)
check(rep["ok"], "golden exports", json.dumps(rep)[:300])
js = rep["js"]
check(js == d.js_export(golden) == d.js_export(json.loads(json.dumps(golden))), "golden export byte-stable")
sha = hashlib.sha256(js.encode("utf-8")).hexdigest()
check(sha == GOLDEN_SHA256, "golden export bytes are pinned (re-pin GOLDEN_SHA256 deliberately when the exporter changes)", sha)
if node_present:
    nc = d.node_check(js)
    check(nc["status"] == "ok", "golden export passes node --check", nc["detail"])
lossy_expected = {("recon", "toolsets"), ("recon", "shape"), ("review", "max_turns"), ("review", "timeout"),
                  ("review", "repo"), ("review", "profile"), ("review", "requires"), ("publish", "hold_timeout"),
                  ("publish", "requires"), ("digest", "run_budget"), ("digest", "reasoning"), ("digest", "require_route")}
got_lossy = {(l["node"], l["key"]) for l in rep["lossy"]}
check(got_lossy == lossy_expected, "every governance key without a counterpart is reported lossy", str(sorted(got_lossy)))
header, _, body = js.partition("export const meta")
for nid, key in sorted(lossy_expected):
    check(f"//   {nid}.{key}" in header, f"header LOSSY SUMMARY lists {nid}.{key}")
    check(re.search(rf"^// LOSSY: {key} = .* — no counterpart", body, re.M), f"node-level // LOSSY line for {nid}.{key}")
check(f"// LOSSY SUMMARY: {len(lossy_expected)} governance field(s)" in header, "summary count matches")
check("// HOLD: Publish the review digest? [\"yes\", \"no\"]" in body and "const publish = \"no\"" in body,
      "human gate exports as a // HOLD stub continuing with default_option")
check("${args.area}" in body, "{run.KEY} -> ${args.KEY}")
check("const params = {\"depth\": 2, \"target\": \"src/\"}" in body, "echo exports as a literal const")
check("${params.target}" in body and "${JSON.stringify(review)}" in body, "inputs refs: string field bare, fan-out result stringified")
check("(item) => agent(`Review module ${item} for dead code" in body, "items_from fan-out exports as pipeline over <const>.<field>")
check("recon.modules," in body, "pipeline iterates the declared array field")
check("Reply with ONLY a fenced json block." in body and "Keep it under one page." in body,
      "defaults.context and node context ride in the prompt")
# #36 F1: fan-out context is emitted in every item prompt, for all three fan-out forms
check("PIPE-CTX: cite file:line for every finding." in body, "items_from fan-out (pipeline form) context rides in the stage prompt")
check(body.count("PAR-CTX: one probe per item.") == 2, "per-item-goal fan-out (parallel form) context rides in EVERY element prompt")
check("UNI-CTX: never write files." in body, "uniform static-items fan-out (pipeline form) context rides in the stage prompt")
check(body.count("Reply with ONLY a fenced json block.") == 6, "defaults.context reaches every agent prompt incl. every fan-out item (recon + 2 probes + smoke + review + digest)", str(body.count("Reply with ONLY a fenced json block.")))
for ctx_line in ("PIPE-CTX", "PAR-CTX", "UNI-CTX"):
    check(re.search(rf"Return \{{[^}}]*\}}\.\n\nReply with ONLY a fenced json block\.\n\n{ctx_line}", body),
          f"{ctx_line}: goal, then defaults.context, then node context (run_child order)")
check(not any(l["key"] == "context" for l in rep["lossy"]), "fan-out context is emitted, never LOSSY")
# #36 F1b: defaults.schema fills an unset fan-out schema (wfcommon.py:411-413 semantics) for both forms
check(body.count("{ label: 'lint', model: 'worker-tier', schema: {\"properties\": {\"note\"") == 1
      and "label: 'types', model: 'worker-tier', schema: {\"properties\": {\"note\"" in body
      and "label: 'smoke', model: 'worker-tier', schema: {\"properties\": {\"note\"" in body,
      "defaults.schema fills unset fan-out item schemas (parallel + pipeline forms)")
check("label: 'review', model: 'worker-tier', schema: {\"properties\": {\"findings\"" in body, "explicit fanout.schema wins over defaults.schema")
# fold-at-export == normalise-via-wfcommon: a door-loaded (apply_graph_defaults) graph exports the same bytes
normalised = wfcommon.apply_graph_defaults(copy.deepcopy(golden))
check(any(n.get("context", "").startswith("Reply with ONLY") for n in normalised["nodes"] if n.get("fanout")),
      "wfcommon.apply_graph_defaults prepends defaults.context to fan-out nodes too")
code = lambda src: [l for l in src.splitlines() if not l.startswith("//")]
check(code(d.js_export(normalised)) == code(js),
      "raw graph and wfcommon-normalised graph export identical code lines (context/schema folded once; only "
      "the LOSSY comments differ, because apply_graph_defaults also bakes shape max_turns/timeout)")
# the adversary's F1 repro (review comment 5898859366): context now in js, still no LOSSY line
G = {"name": "ctx", "nodes": [{"id": "a", "type": "agent", "goal": "List. Return {xs}.", "schema": {"type": "object", "properties": {"xs": {"type": "array", "items": {"type": "string"}}}}},
     {"id": "p", "type": "agent", "after": ["a"], "context": "PIPE-CTX", "fanout": {"items_from": "a.xs", "goal": "Do {item}"}},
     {"id": "q", "type": "agent", "after": ["a"], "context": "PAR-CTX", "fanout": {"items": [{"id": "i1", "goal": "g1"}, {"id": "i2", "goal": "g2"}]}}]}
r = d.export_report(G)
check(r["ok"] and r["lossy"] == [] and "PIPE-CTX" in r["js"] and r["js"].count("PAR-CTX") == 2, "F1 repro: fan-out context emitted for items_from and per-item forms", json.dumps(r)[:300])
r2 = d.js_import(r["js"], node_check=False)
check(r2["ok"] and "PIPE-CTX" in r2["graph"]["nodes"][1]["fanout"]["goal"] and "PAR-CTX" in r2["graph"]["nodes"][2]["fanout"]["items"][0]["goal"],
      "exported fan-out context re-imports (as item goal text, like plain-agent context)", json.dumps(r2)[:300])
check("model: 'worker-tier'" in body and "model: 'sonnet'" in body, "defaults.model fills unset nodes; explicit pin kept verbatim")
# semantic refusals name their node
def gnode(g, nid):
    return next(n for n in g["nodes"] if n["id"] == nid)
q = copy.deepcopy(golden); gnode(q, "review")["fanout"]["quorum"] = 2
r = d.export_report(q)
check(not r["ok"] and r["node"] == "review" and "quorum" in r["refuse"], "quorum fan-out refuses export by name", json.dumps(r))
q = copy.deepcopy(golden); del gnode(q, "publish")["default_option"]
r = d.export_report(q)
check(not r["ok"] and r["node"] == "publish" and "default_option" in r["refuse"], "human gate without default_option refuses export")
q = copy.deepcopy(golden); gnode(q, "publish")["when"] = "out.recon.modules != 'x'"
r = d.export_report(q)
check(not r["ok"] and r["node"] == "publish" and "when" in r["refuse"], "pruning when-gate refuses export")
q = copy.deepcopy(golden); gnode(q, "digest")["inputs"] = ["review.all_results"]
r = d.export_report(q)
check(not r["ok"] and r["node"] == "digest" and "all_results" in r["refuse"], "inputs into a fan-out's all_results refuses export")
try:
    d.js_export(q); raised = False
except d.DialectRefusal as e:
    raised = e.node == "digest"
check(raised, "js_export raises DialectRefusal with the node named")
r = d.export_report({"name": "empty", "nodes": []})
check(not r["ok"], "empty graph refuses export")
# LOSSY lines never break their own syntax: a value with a newline stays on one line
q = copy.deepcopy(golden); gnode(q, "recon")["toolsets"] = ["a\nb"]
js2 = d.js_export(q)
check(all(l.startswith("//") or "LOSSY" not in l for l in js2.splitlines()) and (not node_present or d.node_check(js2)["status"] == "ok"),
      "LOSSY comment values are single-line and keep the script parseable")

# --- (5) node gate degrades, never crashes ----------------------------------------
saved = os.environ.get("PATH")
os.environ["PATH"] = str(HERE / "no-such-dir")
try:
    nc = d.node_check("export const meta = { name: 'x' }\n")
    check(nc["status"] == "skipped" and "node" in nc["detail"], "node absent -> status skipped with a reason", json.dumps(nc))
    r = d.js_import((FIX / "audit-routes.js").read_text(encoding="utf-8"))
    check(r["ok"] and any(w.startswith("node_check: skipped") for w in r["warnings"]),
          "import without node still succeeds and warns once", json.dumps(r.get("warnings")))
    r = d.js_import((FIX / "while-loop.js").read_text(encoding="utf-8"))
    check(not r["ok"] and r["line"] == 12, "refusals do not depend on node")
finally:
    os.environ["PATH"] = saved or ""
if node_present:
    # measured on Node 26: `node --check <file>.js` is LENIENT once the file contains `export`
    # (ESM syntax detection); a file it parses as CJS still gets a real verdict. The scanner
    # is the gate that matters; node's is a courtesy and is documented as such.
    r = d.js_import(")))) not javascript\nexport const meta = { name: 'x' }\n")
    check(not r["ok"] and r["construct"].startswith("syntax error (node --check)") and r["line"] == 1,
          "syntax error node CAN see is a named refusal with its line", json.dumps(r))
    r = d.js_import("export const meta = { name: 'x' }\nconst a = await agent('hi', {\n")
    check(not r["ok"] and r["line"] == 2, "syntax error node cannot see (ESM-detected .js) is still refused by the scanner", json.dumps(r))

# --- extra refusals the prose names but no fixture pins --------------------------------
def refuses(src, construct_prefix, line):
    r = d.js_import(src, node_check=False)
    check(not r["ok"] and r["construct"].startswith(construct_prefix) and r["line"] == line,
          f"refuses {construct_prefix!r} at line {line}", json.dumps(r)[:200])

M = "export const meta = { name: 'x', description: 'y' }\n"
refuses(M + "const a = await agent('p')\nconst b = a.then(x => x)\nreturn b\n", "closure/glue between agents (then)", 3)
refuses(M + "const a = await agent('p')\nconst b = await agent('q', { schema: a.schema })\n", "non-literal agent() option schema", 3)
refuses(M + "const a = await parallel([1, 2])\n", "parallel element is not an agent(...) call or a thunk", 2)
refuses(M + "const a = await parallel([() => { return agent('p') }])\n", "parallel element is a block-bodied thunk", 2)
refuses(M + "const a = await agent('p')\nconst b = await pipeline(a.items.length, i => agent(`${i}`))\n",
        "pipeline item source a.items.length is not declared", 3)
refuses(M + "const a = await parallel([() => agent('p')])\nconst b = await agent(`${a.items}`)\n",
        "template property access on a parallel const (${a.items})", 3)
refuses(M + "const a = await parallel([() => agent('p')])\nconst b = await agent(`${a[0]}`)\n",
        "template property access on a parallel const (${a[0]})", 3)
refuses(M + "const a = await agent('p')\nreturn { a }\n", "computed return (object/array construction)", 3)
refuses(M + "const a = await agent('p')\nreturn a.map(x => x)\n", "computed return", 3)
refuses(M + "const a = await agent('p')\nlog(`got ${a}`)\nreturn a\n", "log() with a template over results", 3)
refuses(M + "const a = await agent('p')\nconst r = Math.random()\n", "Math.random()", 3)
refuses(M + "const a = await agent('p')\nconst r = new Date()\n", "new Date()", 3)
refuses(M + "const a = await agent('p')\nfor (const x of [1]) { await agent('q') }\n", "for", 3)
refuses(M + "const a = await agent('p')\nif (a) { await agent('q') }\n", "if", 3)
refuses(M + "import x from 'y'\n", "import/export", 2)
refuses(M + "const a = await agent('p', { schema: { type: 'object' }, phase: 'z', extra: 1 })\n", "unknown agent() option: extra", 2)
refuses(M + "const a = await agent('p')\nconst b = await agent(`${a.nope}`)\n", "template field ${a.nope} is not declared", 3)
refuses(M + "const a = await agent('p')\nconst b = await pipeline(args.files, f => agent(`${f}`))\n", "args used as an iterable item source", 3)
refuses("const meta = { name: 'x' }\nconst a = await agent('p')\n", "missing export const meta", 1)
refuses(M + "const a = await agent('p')\nreturn a\nconst b = await agent('q')\n", "statement after return", 4)
# #36 F2: an unterminated construct is named as itself, never as "expression after ... (glue)"
refuses(M + "const a = await agent(`p\nreturn a\n", "unterminated agent(...) / unbalanced brackets", 2)          # unterminated template
refuses(M + "const a = await agent('p', { schema: { type: 'object' }\nreturn a\n", "unterminated agent(...) / unbalanced brackets", 2)   # unterminated options object
refuses(M + "const a = await parallel([() => agent('p')\nreturn a\n", "unterminated parallel(...) / unbalanced brackets", 2)
refuses(M + "const a = await parallel([agent('p') )\nreturn a\n", "unterminated parallel(...) / unbalanced brackets", 2)   # inner [ never closed
refuses(M + "const a = await pipeline(['x'], f => agent(`${f}`)\nreturn a\n", "unterminated pipeline(...) / unbalanced brackets", 2)
refuses(M + "const a = await pipeline(['x'], f => agent(`${f}` )\nreturn a\n", "unterminated pipeline(...) / unbalanced brackets", 2)
refuses(M + "phase('x'\nconst a = await agent('p')\n", "unterminated phase(...) / unbalanced brackets", 2)
# ...and a genuinely balanced trailing expression still names glue (the message F2 used to leak)
refuses(M + "const a = await agent('p').then(x => x)\nreturn a\n", "expression after agent(...) (glue)", 2)
# minors (#36): non-string label warns and is ignored; meta.name that is a path refuses
r = d.js_import(M + "const a = await agent('p', { label: 5 })\nreturn a\n", node_check=False)
check(r["ok"] and any("label at line 2 is not a string (int)" in w for w in r["warnings"]), "non-string label -> warning, import proceeds", json.dumps(r)[:200])
refuses("export const meta = { name: '../x y' }\nconst a = await agent('p')\n", "meta.name contains a path separator or whitespace", 1)
refuses("export const meta = { name: 'a b' }\nconst a = await agent('p')\n", "meta.name contains a path separator or whitespace", 1)
# accepted edge: bare whole-const reference to a parallel result imports (auto-injected whole)
r = d.js_import(M + "const a = await parallel([() => agent('p'), agent('q')])\nconst b = await agent(`Summarise ${a}`)\nreturn b\n", node_check=False)
check(r["ok"] and r["graph"]["nodes"][1]["after"] == ["a"] and "inputs" not in r["graph"]["nodes"][1]
      and len(r["graph"]["nodes"][0]["fanout"]["items"]) == 2, "bare ${parallelConst} imports as after (whole inject); thunk + bare call mixed", json.dumps(r)[:300])
# accepted (#36 F3, dialect.md §3 data-flow rule): an outer agent const referenced inside a pipeline
# stage template imports as NODE-LEVEL inputs + after — build_inputs renders one identical section
# for every item, so the import is runtime-sound and the stage prose names the ref (no brace token)
r = d.js_import(M + "const plan = await agent('Propose. Return {target}.', { schema: {type:'object', properties:{target:{type:'string'}}} })\n"
                "const items = await pipeline(['a','b'], (item) => agent(`Refactor ${item} toward ${plan.target}.`))\nreturn items.filter(Boolean)\n", node_check=False)
check(r["ok"] and r["graph"]["nodes"][1]["after"] == ["plan"] and r["graph"]["nodes"][1]["inputs"] == ["plan.target"]
      and r["graph"]["nodes"][1]["fanout"]["items"] == ["a", "b"] and "plan.target" in r["graph"]["nodes"][1]["fanout"]["goal"]
      and "{plan" not in r["graph"]["nodes"][1]["fanout"]["goal"] and "{item}" in r["graph"]["nodes"][1]["fanout"]["goal"],
      "outer-const ref inside a pipeline stage imports as node-level inputs+after (identical per item)", json.dumps(r)[:400])
check(wfcommon.validate_graph_errors(r["graph"]) == [], "stage-captures-outer-const graph validates")
rep = d.export_report(r["graph"])
check(rep["ok"] and rep["lossy"] == [] and "${plan.target}" in rep["js"] and d.js_import(rep["js"], node_check=False)["graph"]["nodes"] == r["graph"]["nodes"],
      "…and round-trips through the exporter as the same nodes", json.dumps(rep)[:300])
# accepted: static pipeline list
r = d.js_import(M + "const a = await pipeline(['x', 'y'], f => agent(`Do ${f}`))\nreturn a.filter(Boolean)\n", node_check=False)
check(r["ok"] and r["graph"]["nodes"][0]["fanout"] == {"items": ["x", "y"], "goal": "Do {item}"}, "pipeline over a literal list -> fanout.items", json.dumps(r)[:300])
check(wfcommon.validate_graph_errors(r["graph"]) == [], "literal-list pipeline validates")
# duplicate labels never collide as ids (id = const name)
r = d.js_import(M + "const a = await agent('p', { label: 'same' })\nconst b = await agent('q', { label: 'same' })\nreturn b\n", node_check=False)
check(r["ok"] and [n["id"] for n in r["graph"]["nodes"]] == ["a", "b"], "ids come from const names; repeated labels are fine")

print(f"\nALL PASS ({ok})")
