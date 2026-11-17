<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Examples

No Duckwork process and no API key. Start here:

```bash
pip install duckwork-tenuo
duckwork-tenuo demo
# or, from this directory: python demo.py
```

That is one story: a nightly job leaves its slip, then the same check on a
child grant and on two gateway users. The longer scripts below are the
same `DuckworkGuard.pre_tool_call` path, one file per scene.
`subagent_scope.py` is the grant; `gateway_multiuser.py` is one
independently minted warrant per session.

```bash
python cron_warrant.py
python subagent_scope.py
python gateway_multiuser.py
```

A recorded Duckwork session with a planted prompt injection is
[`docs/walkthrough.md`](../docs/walkthrough.md) (`examples/walkthrough/setup.sh`).

Requires `tenuo>=0.3.2`.
