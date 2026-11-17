#!/usr/bin/env python3
"""Validate the portable Agent Plugins 1.0.0 manifests against the official schemas.

plugin.json and mcp.json at the repository root are what nine hosts read
(Codex, Kiro, Copilot, Grok Build, NanoClaw and others). The schemas are the
canonical ones from https://agent-plugins.org/schemas/1.0.0/, vendored under
schemas/agent-plugins/1.0.0/ so the check never depends on the network and a
schema change upstream is a reviewed diff here.

Exit 0 when both files validate, 1 with every error listed otherwise.
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas" / "agent-plugins" / "1.0.0"
PAIRS = [("plugin.json", "plugin.schema.json"), ("mcp.json", "mcp.schema.json")]


def main() -> int:
    failed = False
    for manifest, schema in PAIRS:
        data = json.loads((ROOT / manifest).read_text(encoding="utf-8"))
        validator = Draft202012Validator(
            json.loads((SCHEMAS / schema).read_text(encoding="utf-8")),
            format_checker=FormatChecker(),
        )
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
        if errors:
            failed = True
            for e in errors:
                where = "/".join(str(p) for p in e.absolute_path) or "(root)"
                print(f"FAIL {manifest} at {where}: {e.message}")
        else:
            print(f"ok   {manifest} matches Agent Plugins 1.0.0 {schema}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
