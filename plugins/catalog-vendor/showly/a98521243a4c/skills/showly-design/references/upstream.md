# Sources and maintenance

- [pbakaus/impeccable](https://github.com/pbakaus/impeccable/tree/c63b8dd7dd5a5f3c32eaabe1af76d0694f863ed2) — `c63b8dd7dd5a5f3c32eaabe1af76d0694f863ed2`.

Showly rewrites selected design principles into a short entrypoint and two task-specific references. The derived design guidance is distributed under Apache-2.0. It omits upstream engines, hooks, detectors, persistence, mandatory delegation, platform references and command menus. User brand constraints take precedence over general aesthetic preferences.

Taste Skill was reviewed at commit `d237dd399d57524945c0c81327da5da19f7a468d` ([source](https://github.com/Leonxlnx/taste-skill/tree/d237dd399d57524945c0c81327da5da19f7a468d)). It is deferred: its default motion/variance presets and framework-selection instructions add stronger preferences and overlap with this first release. No Taste Skill content is bundled.

[upstream.json](upstream.json) records immutable commits and source-file SHA-256 hashes. [Third-party notices](../THIRD_PARTY_LICENSES.txt) retain upstream license text. These are locally modified adaptations, not unmodified upstream releases or endorsements.

To update, fetch an explicit commit, review changed guidance and license terms, adapt only relevant rules, refresh the source hashes and notices, then rerun installation, packaging and behavior checks. Updates ship through Showly releases; installed skills never fetch new instructions at runtime.
