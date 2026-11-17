#!/usr/bin/env python3
"""Test-only crash injector: kill the claiming process at an actual filesystem seam.
No monkeypatch or hook in production code. Usage: 11-claim-wrapper.py PHASE GRAPH_JSON.
PHASE: post-run-json | mid-entry | post-entry. EXIT 93 marks the precise seam.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys

phase, graph_path = sys.argv[1:3]
if phase not in ('post-run-json', 'mid-entry', 'post-entry'):
    sys.exit('invalid phase')
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
orig_write = Path.write_text
orig_replace = os.replace


def die():
    # os._exit bypasses finally, mimicking SIGKILL while the per-key kernel flock
    # remains held; parent detects the 93 sentinel instead of relying on timing.
    os._exit(93)


def write(path, text, *args, **kwargs):
    p = Path(path)
    if phase == 'post-run-json' and p.name == 'run.json' and p.parent.parent == Path(os.environ['WF_RUNS_ROOT']):
        result = orig_write(p, text, *args, **kwargs)
        die()
        return result
    if phase == 'mid-entry' and p.parent.name == 'lanes' and p.suffix == '.tmp':
        # Write only half of a temporary entry; atomically published JSON must
        # never be malformed. Kill before os.replace.
        orig_write(p, text[:max(1, len(text) // 2)], *args, **kwargs)
        die()
    return orig_write(p, text, *args, **kwargs)


def replace(src, dst, *args, **kwargs):
    result = orig_replace(src, dst, *args, **kwargs)
    if phase == 'post-entry' and Path(dst).parent.name == 'lanes' and Path(dst).suffix == '.json':
        die()
    return result


Path.write_text = write
os.replace = replace
spec = importlib.util.spec_from_file_location('lane_e_claim_wrapper_door', root / '__init__.py')
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
result = door.act_run({'graph': json.loads(Path(graph_path).read_text()), 'lane_key': 'claim/fixture'})
print(json.dumps(result))
