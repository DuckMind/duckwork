"""Lane C (read model) acceptance, 1.1 team sprint — wfcommon profile/requires
validation + precondition facts + profile-aware child_metrics home.

RATIFY F2 (validation + facts) and F4 (validation + facts rendering). Everything
here is read-model only: no runner, no door. Stdlib-only.
"""
import json, os, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfcommon

ok = 0
def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1; print("PASS", msg)

# ---------- fixture: a fake profiles root with one consenting teammate ----------
BASE = Path(tempfile.mkdtemp(prefix="c11-home-", dir=str(ROOT / "tests")))
PROOT = BASE / "root" / "profiles"
def mkprofile(name, config=True, consent=None):
    ph = PROOT / name
    ph.mkdir(parents=True)
    if config:
        (ph / "config.yaml").write_text("model:\n  default: fake\n")
    if consent is not None:
        (ph / "workflow_team.json").write_text(json.dumps(consent))
    return ph

mkprofile("teammate", consent={"accept_from": ["repo-bot", "default"]})
mkprofile("noconsent", consent=None)
mkprofile("wronglist", consent={"accept_from": ["someone-else"]})
mkprofile("badjson")
(PROOT / "badjson" / "workflow_team.json").write_text("{not json")
mkprofile("nolist", consent={"accept_from": "repo-bot"})
mkprofile("noconfig", config=False, consent={"accept_from": ["repo-bot"]})

def nodes(**over):
    base = {"id": "review", "type": "agent", "goal": "g", "after": ["fix"]}
    base.update(over)
    return [dict(base), {"id": "fix", "type": "agent", "goal": "g"}]

PE = lambda ns, launcher="repo-bot": wfcommon.profile_errors(ns, launcher=launcher,
                                                                 profiles_dir=PROOT)

# ---------- F2 validation ----------
check(PE(nodes(profile="teammate")) == [], "consented teammate + listed launcher = clean")
e = PE(nodes(profile="ghost"))
check(len(e) == 1 and e[0]["node"] == "review" and e[0]["field"] == "profile"
      and "ghost" in e[0]["msg"], "bogus profile -> one {node,field:'profile',msg} error")
e = PE(nodes(profile="default"))
check(len(e) == 1 and "default" in e[0]["msg"], "profile 'default' rejected (never a target)")
e = PE(nodes(profile="")) + PE(nodes(profile="   ")) + PE(nodes(profile=None)) + PE(nodes(profile=7))
check(len(e) == 4 and all(x["field"] == "profile" for x in e),
      "empty/whitespace/non-string profile rejected 4/4")
e = PE(nodes(profile="noconsent"), launcher="repo-bot")
check(len(e) == 1 and "workflow_team.json" in e[0]["msg"] and "delegation" in e[0]["msg"],
      "missing consent file rejected; msg documents delegation-not-isolation + the file to write")
e = PE(nodes(profile="wronglist"))
check(len(e) == 1 and "repo-bot" in e[0]["msg"] and "someone-else" in e[0]["msg"],
      "launcher not in accept_from rejected, naming both launcher and the list")
e = PE(nodes(profile="noconsent"), launcher="default")
check(len(e) == 1, "'default' IS a legal launcher name (still needs consent)")
e = PE(nodes(profile="noconfig"))
check(len(e) == 1 and "config.yaml" in e[0]["msg"], "profile without config.yaml rejected")
e = PE(nodes(profile="badjson"))
check(len(e) == 1 and "accept_from" in e[0]["msg"], "malformed consent json fails closed")
e = PE(nodes(profile="nolist"))
check(len(e) == 1 and "accept_from" in e[0]["msg"], "accept_from non-list rejected")
for bad in ("../evil", "a/b", ".hidden", ""):
    if not bad: continue
    e = PE(nodes(profile=bad))
    check(len(e) == 1 and "safe" in e[0]["msg"], f"profile {bad!r} rejected as unsafe path")
check(not any(".." in str(x.get("profile")) for x in []), "no traversal reaches the fs")
check(PE([{"id": "g", "type": "gate", "after": [], "requires": {}}]) == [],
      "gate without 'profile' key: profile_errors silent")
check(PE([{"id": "n", "type": "echo", "output": {}, "profile": "ghost"}]) == [],
      "profile on a NON-agent node is left to the closed-key grammar, not double-reported")

# launcher resolution: from DUCKWORK_HOME only, never a graph arg
ph2 = PROOT / "launcher"
ph2.mkdir(parents=True)
os.environ["DUCKWORK_HOME"] = str(PROOT / "repo-bot")
check(wfcommon.launcher_profile() == "repo-bot", "launcher from DUCKWORK_HOME under profiles/")
os.environ["DUCKWORK_HOME"] = str(BASE / "root")
check(wfcommon.launcher_profile() == "default", "non-profile DUCKWORK_HOME -> launcher 'default'")
check(str(wfcommon.profiles_root(BASE / "root" / "profiles" / "x")) == str(PROOT),
      "profiles_root = root/profiles via DUCKWORK_HOME.parent.parent")
check(str(wfcommon.profiles_root(BASE / "root")) == str(BASE / "root" / "profiles"),
      "profiles_root = DUCKWORK_HOME/profiles when DUCKWORK_HOME is the root itself")
check(str(wfcommon.profile_home("teammate", BASE / "root" / "profiles" / "x"))
      == str(PROOT / "teammate"), "profile_home = <profiles_root>/<name>")

# ---------- F4 validation ----------
def rerr(nodes_):
    return wfcommon.validate_graph_errors(nodes_)
errs = rerr([{"id": "fix", "type": "agent", "goal": "g"},
             {"id": "mid", "type": "agent", "goal": "g", "after": ["fix"]},
             {"id": "rev", "type": "agent", "goal": "g", "after": ["mid"],
              "requires": {"fix": ["pr_url"]}}])
check(not any(e["field"].startswith("requires") for e in errs),
      "transitive ancestor (grandparent) in the after closure is legal")
errs = rerr([{"id": "fix", "type": "agent", "goal": "g"},
             {"id": "via", "type": "echo", "output": {}, "after": ["fix"]},
             {"id": "rev", "type": "agent", "goal": "g", "after": ["via"],
              "requires": {"fix": ["pr_url"]}}])
check(not any(e["field"].startswith("requires") for e in errs),
      "transitive requires closure crosses echo nodes as ancestors")
errs = rerr([{"id": "fix", "type": "agent", "goal": "g"},
             {"id": "other", "type": "agent", "goal": "g"},
             {"id": "rev", "type": "agent", "goal": "g", "after": ["fix"],
              "requires": {"other": ["pr_url"]}}])
check(len(errs) == 1 and errs[0]["node"] == "rev" and errs[0]["field"] == "requires",
      "requires key NOT in the after closure -> one error 1/1")
errs = rerr([{"id": "fix", "type": "agent", "goal": "g"},
             {"id": "rev", "type": "agent", "goal": "g", "after": ["fix"],
              "requires": {"fix": ["pr_url", ""]}}])
check(len(errs) == 1 and errs[0]["field"] == "requires.fix", "empty path string rejected")
errs = rerr([{"id": "fix", "type": "agent", "goal": "g"},
             {"id": "rev", "type": "agent", "goal": "g", "after": ["fix"],
              "requires": {"fix": []}}])
check(len(errs) == 1, "empty path list rejected")
errs = rerr([{"id": "fix", "type": "agent", "goal": "g"},
             {"id": "rev", "type": "agent", "goal": "g", "after": ["fix"],
              "requires": {"fix": "pr_url"}}])
check(len(errs) == 1, "non-list paths rejected")
errs = rerr([{"id": "rev", "type": "agent", "goal": "g", "requires": {}}])
check(len(errs) == 1, "empty requires object rejected")
errs = rerr([{"id": "fix", "type": "agent", "goal": "g"},
             {"id": "g8", "type": "gate", "after": ["fix"], "question": "q",
              "requires": {"fix": ["pr_url"]}}])
check(not any(e["field"].startswith("requires") for e in errs),
      "gates take requires too (GATE_KEYS + F4)")
errs = rerr([{"id": "fix", "type": "agent", "goal": "g"},
             {"id": "e1", "type": "echo", "after": ["fix"], "output": {},
              "requires": {"fix": ["pr_url"]}}])
check(any(e["field"] == "requires" for e in errs),
      "requires on an echo node rejected by the closed grammar")
errs = rerr([{"id": "fix", "type": "agent", "goal": "g"},
             {"id": "rev", "type": "agent", "goal": "g", "after": ["fix"],
              "requires": {"fix": ["a.b.c"]}}])
check(not errs, "dotted path strings accepted verbatim")
errs = rerr([{"id": "fix", "type": "agent", "goal": "g", "profile": "x"}])
check(not errs, "'profile' is a legal OPTIONAL agent key (grammar accepts it)")

# ---------- F4 facts: render 'failed (precondition: fix.pr_url)' ----------
rec = {"status": "failed", "error_class": "precondition",
       "error": "precondition unmet: fix.pr_url", "output": {"missing": ["fix.pr_url"]}}
check(wfcommon.precondition_facts(rec) == "failed (precondition: fix.pr_url)",
      "precondition fact renders 'failed (precondition: fix.pr_url)'")
rec2 = dict(rec, error="precondition unmet: fix.pr_url", output=None)
check(wfcommon.precondition_facts(rec2) == "failed (precondition: fix.pr_url)",
      "no output.missing -> parsed from the error text (same render)")
check(wfcommon.precondition_facts({"status": "failed", "error_class": "timeout"}) is None,
      "non-precondition failures render no precondition fact")
rr = Path(tempfile.mkdtemp(prefix="c11-run-", dir=str(ROOT / "tests")))
(rr / "nodes").mkdir(parents=True)
(rr / "nodes" / "review.json").write_text(json.dumps(rec))
nf = wfcommon.node_facts(rr, "review")
check(nf["fact"] == "failed (precondition: fix.pr_url)",
      "node_facts carries the rendered precondition fact")
check(nf["status"] == "failed" and nf["error_class"] == "precondition",
      "node_facts keeps verbatim record fields beside the fact")
(rr / "nodes" / "plain.json").write_text(json.dumps({"status": "done", "output": {}}))
check("fact" not in wfcommon.node_facts(rr, "plain"), "done node has no precondition fact")
check("profile" not in nf and "profile_home" not in nf,
      "no-profile node_facts stays byte-identical (no new keys)")
(rr / "nodes" / "routed.json").write_text(json.dumps(
    {"status": "done", "profile": "teammate", "profile_home": str(PROOT / "teammate")}))
routed_nf = wfcommon.node_facts(rr, "routed")
check(routed_nf is not None and routed_nf["profile"] == "teammate" and
      routed_nf["profile_home"] == str(PROOT / "teammate"),
      "profile/profile_home exposed as facts ONLY for routed nodes")

# ---------- profile-aware child_metrics home ----------
home_t = PROOT / "teammate"
home_t.mkdir(parents=True, exist_ok=True)
run = Path(tempfile.mkdtemp(prefix="c11-run2-", dir=str(ROOT / "tests"))) / "c-run"
run.mkdir(parents=True)
(run / "nodes").mkdir(parents=True)
(run / "nodes" / "solo.json").write_text(json.dumps({"status": "done"}))
check(wfcommon.node_child_home(run, "solo") is None,
      "no-profile record -> home None == today's duckwork_home() default (no-team identical)")
# profile-only record (no profile_home) derives <profiles_root>/<name>
os.environ["DUCKWORK_HOME"] = str(PROOT / "repo-bot")
(run / "nodes" / "derived.json").write_text(json.dumps({"status": "done", "profile": "teammate"}))
check(wfcommon.node_child_home(run, "derived") == home_t,
      "profile-only record derives profile_home = <profiles_root>/<profile>")

shutil.rmtree(BASE, ignore_errors=True)
shutil.rmtree(rr, ignore_errors=True)
shutil.rmtree(run, ignore_errors=True)
print(f"OK {ok} checks")
