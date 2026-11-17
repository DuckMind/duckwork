#!/usr/bin/env python3
"""Jev cron wake gate: skip an agent cron run when Jev says it would do nothing useful.

Duckwork cron runs a job's pre-run script and skips the LLM run entirely when the
script's last stdout line is {"wakeAgent": false}. This runner builds a small state
snapshot from the gate's config, asks TypeSafe Jev one yes/no question ("would a run
now do useful work?"), and prints that line.

Standalone and stdlib-only: Duckwork copies it into <DUCKWORK_HOME>/scripts/ and a tiny
per-job wrapper calls it with the gate name. Fail-open everywhere: missing config,
missing key, network error, or low confidence all wake the agent as before.

Config: <DUCKWORK_HOME>/jev-cron-gates/<name>.json
  {
    "question": "Running the agent now would ...",   # the noul statement Jev scores
    "sources": [                                      # what Jev sees (the "state")
      {"file": "~/proj/APPROVALS.md"},
      {"file": "~/proj/log.jsonl", "tail": 900},
      {"changed": ["~/proj/src", "~/proj/notes.md"]}, # changed since the last wake?
      {"url": "http://127.0.0.1:8888/..."},           # localhost only
      {"text": "Static context for Jev."}
    ],
    "skip_below": 0.2,          # skip when P(useful) < this
    "max_consecutive_skips": 4  # then force a wake so a job can't stall silently
  }
Log: <DUCKWORK_HOME>/jev-cron-gates/log.jsonl, one line per decision.
"""
import glob
import json
import os
import sys
import time
import urllib.parse
import urllib.request

DEFAULT_URL = "https://api.typesafe.ai/v1/systemone"
MAX_STATE = 6000


def duckwork_home():
    return os.path.expanduser(os.environ.get("DUCKWORK_HOME") or "~/.duckwork")


def gates_dir():
    return os.path.join(duckwork_home(), "jev-cron-gates")


def _api_key():
    for var in ("TYPESAFE_API_KEY", "JEV_API_KEY"):
        if os.environ.get(var, "").strip():
            return os.environ[var].strip()
    # Cron scripts don't always inherit the profile .env; read it directly.
    env = os.path.join(duckwork_home(), ".env")
    try:
        for line in open(env):
            k, _, v = line.strip().partition("=")
            if k in ("TYPESAFE_API_KEY", "JEV_API_KEY") and v.strip():
                return v.strip().strip("'\"")
    except OSError:
        pass
    return ""


def _mtime(path):
    newest = 0.0
    for p in glob.glob(os.path.expanduser(path)):
        try:
            newest = max(newest, os.path.getmtime(p))
            if os.path.isdir(p):
                for root, dirs, files in os.walk(p):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
                    for f in files[:500]:
                        try:
                            newest = max(newest, os.path.getmtime(os.path.join(root, f)))
                        except OSError:
                            pass
        except OSError:
            pass
    return newest


def build_state(cfg, last_wake):
    parts = []
    for s in cfg.get("sources", []):
        try:
            if "file" in s:
                txt = open(os.path.expanduser(s["file"])).read()
                if s.get("tail"):
                    txt = txt[-int(s["tail"]):]
                parts.append(f"## {s['file']}\n{txt}")
            elif "changed" in s:
                ch = {p: _mtime(p) > last_wake for p in s["changed"]}
                parts.append(f"## Changed since last agent run\n{json.dumps(ch)}")
            elif "url" in s:
                host = urllib.parse.urlparse(s["url"]).hostname or ""
                if host not in ("127.0.0.1", "localhost", "::1"):
                    parts.append(f"## {s['url']}\n(skipped: only localhost URLs are allowed)")
                    continue
                with urllib.request.urlopen(s["url"], timeout=10) as r:
                    parts.append(f"## {s['url']}\n{r.read(int(s.get('tail', 4000))).decode('utf-8', 'replace')}")
            elif "text" in s:
                parts.append(s["text"])
        except Exception as e:  # a broken source shouldn't kill the gate
            parts.append(f"## source error: {type(e).__name__}")
    hrs = round((time.time() - last_wake) / 3600, 1) if last_wake else "never"
    parts.append(f"## Hours since the agent last ran\n{hrs}")
    return "\n\n".join(parts)[-MAX_STATE:]


def ask_jev(state, question, timeout=15):
    key = _api_key()
    if not key:
        return None, "no TYPESAFE_API_KEY"
    body = json.dumps({"model": os.environ.get("TYPESAFE_MODEL", "jev-latest"), "state": state,
                       "questions": {"useful": {"type": "noul", "instructions": question}}}).encode()
    req = urllib.request.Request(os.environ.get("TYPESAFE_BASE_URL", DEFAULT_URL), data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return float(json.load(r)["answers"]["useful"]["noul"]), None
    except Exception as e:
        return None, f"jev error: {type(e).__name__}"


def decide(name):
    d = gates_dir()
    state_path = os.path.join(d, f"{name}.state.json")
    try:
        cfg = json.load(open(os.path.join(d, f"{name}.json")))
    except (OSError, ValueError):
        return True, {"note": "no config; waking"}
    st = {}
    try:
        st = json.load(open(state_path))
    except (OSError, ValueError):
        pass
    t0 = time.time()
    score, err = ask_jev(build_state(cfg, st.get("last_wake", 0)), cfg["question"])
    wake = True if score is None else score >= float(cfg.get("skip_below", 0.2))
    skips = 0 if wake else st.get("skips", 0) + 1
    note = err or f"useful={score:.2f}"
    if skips > int(cfg.get("max_consecutive_skips", 4)):
        wake, skips, note = True, 0, note + " (skip cap; waking)"
    st["skips"] = skips
    if wake:
        st["last_wake"] = time.time()
    os.makedirs(d, exist_ok=True)
    json.dump(st, open(state_path, "w"))
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "gate": name, "wake": wake, "score": score,
           "note": note, "ms": int((time.time() - t0) * 1000)}
    with open(os.path.join(d, "log.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return wake, rec


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    name = argv[0] if argv else ""
    wake, rec = decide(name) if name else (True, {"note": "no gate name; waking"})
    print(f"[jev-cron-gate:{name}] {rec.get('note')} -> {'wake' if wake else 'skip'}")
    print(json.dumps({"wakeAgent": wake}))


if __name__ == "__main__":
    main()
