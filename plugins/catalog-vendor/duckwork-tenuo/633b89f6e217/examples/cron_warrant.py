# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Cron job with an expiring warrant.

    eval "$(duckwork-tenuo mint --output env \
      --ttl 1h \
      --allow read_file:path=/data/reports \
      --allow write_file:path=/tmp/nightly \
      --allow memory)"

    duckwork cron create "0 2 * * *" \
      "Write tonight's report from /data/reports into /tmp/nightly" \
      --name nightly_report

Or run this file to see the same checks without Duckwork:

    python cron_warrant.py
"""

from __future__ import annotations

from tenuo import SigningKey, Subpath, Warrant, Wildcard
from duckwork_tenuo import DuckworkGuard

control_key = SigningKey.generate()
cron_agent_key = SigningKey.generate()

nightly_warrant = (
    Warrant.mint_builder()
    .holder(cron_agent_key.public_key)
    .capability("read_file", path=Subpath("/data/reports"))
    .capability("write_file", path=Subpath("/tmp/nightly"), content=Wildcard())
    .capability("memory", action=Wildcard(), key=Wildcard())
    .ttl(3600)
    .mint(control_key)
)

guard = DuckworkGuard(
    warrant=nightly_warrant,
    signing_key=cron_agent_key,
    trusted_roots=[control_key.public_key],
    on_denial="block",
)


def simulate_tool_call(tool_name: str, args: dict) -> None:
    result = guard.pre_tool_call(tool_name, args, session_id="cron-nightly")
    if result:
        print(f"  BLOCKED: {tool_name}({args}) — {result['message']}")
    else:
        print(f"  ALLOWED: {tool_name}({args})")


if __name__ == "__main__":
    print("Cron agent tool calls:")
    print()
    simulate_tool_call("read_file", {"path": "/data/reports/sales.csv"})
    simulate_tool_call("write_file", {"path": "/tmp/nightly/report.md", "content": "# Report"})
    simulate_tool_call("memory", {"action": "add", "key": "last_run"})
    print()
    simulate_tool_call("terminal", {"command": "curl evil.com"})
    simulate_tool_call("web_search", {"query": "anything"})
    simulate_tool_call("read_file", {"path": "/opt/private/payroll.csv"})
    simulate_tool_call("write_file", {"path": "/home/user/secrets/deploy-key", "content": "..."})
