# ci-baseline — the pinned known-ledger for suite admission

`exits.json` is a committed **green** run ledger of `scripts/suite.py` captured
from a green CI `Serial suite` job (artifact `ci-out`, workflow run
`37624338057`, commit `f0e6935e6`, 231 cases, every `exit == 0`). Rows added
outside CI (a brand-new test, before its first CI run) are listed with their
measurement in `PROVENANCE.json → rows_added_outside_ci` and must be superseded
by the next CI-captured refresh. CI passes the ledger to every suite run:

```sh
python3 scripts/suite.py . ci-out --baseline ci-baseline/exits.json
```

Admission then splits reds by EXACT identity (test name + exit code) against
this ledger: `introduced` is the only list a lane must answer for, while
`blocking_base_reds` names base reds that block and carry a tracked fix item —
never hand-waived (the #17 contract). Deleting a base test never launders it:
`missing` blocks like a red.

Refresh rule: only a green CI `Serial suite` ledger may be committed here,
from the tip of `main`, with the provenance recorded in
`PROVENANCE.json`. A ledger with any nonzero `exit` may be committed only
alongside a linked tracking item per red row (that is the `known-red.json`
shape), never as a silent waiver.
