# Notices and provenance

## License conclusion

This standalone package is intended to be distributed under the MIT License in
[`LICENSE`](LICENSE).

The SidePulse source repository's inspected `LICENSE` is MIT and names Peter
Kuhar as copyright holder.[1] The original Hermes integration was added to the
SidePulse repository by Cesar J. Garcia in commit `48659331e9e8e58120a9dd5c1781bf84ed009287`.[2]
The standalone extraction and Desktop companion preserve that upstream MIT
notice and identify Cesar J. Garcia for the standalone changes.

This is an attribution and provenance record, not legal advice. A publisher
should re-check the exact source tree and dependency bundle at release time.

## Source provenance

The inspected SidePulse working copy reported these public remotes:

- origin: `https://github.com/d31tcjg/sidepulse.git`
- upstream: `https://github.com/inteliwear/sidepulse.git`

The Hermes integration history was traced with `git log --follow` and targeted
`git blame` on the integration README and manifest. The relevant history is:

| Commit | Finding |
| --- | --- |
| `48659331e9e8e58120a9dd5c1781bf84ed009287` | Added `integrations/hermes/` including the Python plugin, manifest, diagnostics, README, and tests.[2] |
| `4bfbb74825c9b1876aac04062a045049d287d435` | Added session-activation handling. |
| `5f3d9a62d6b6692c0e0a7d132af7941511a32851` | Required profile provenance and failed closed without it. |
| `27b0776bb8a1400bfa20a9f3c1692055fb0ceeb8` | Documented Hermes-to-LED mode mapping. |
| `35b73acd23ccae0f3e0d225f51cb6552d94f8388` | Added the post-upgrade compatibility check. |
| `b692921928e5965afc5e3fd013d4635d7a08eae1` | Documented the compatibility check. |
| `4c92c74802047e20061e1128db812705eafb9181` | Synchronized completed-chat status. |
| `25c834514c1e7fedb8ae816da89328050ea9decf` | Added finalization cleanup. |
| `a8d8067eba6046833935be15c7d589f2ff6fde7d` | Ignored Hermes background review activity.[3] |

The local standalone candidate is not byte-identical to the source integration.
The bounded comparison found these intentional deltas:

- The runtime Python plugin now lives under `python/`; its `plugin.yaml`
  reports `0.2.0-beta.1` instead of the source manifest's `0.1.0`.
- `on_session_activate` was removed from the standalone manifest and Python
  registration list because the tested Hermes baseline does not expose that
  hook.
- `python/bridge.py` recognizes `desktop_session_activate`, accepts
  `hermes-desktop-plugin` records during bounded recovery, and emits that
  integration label for Desktop activation.
- `python/dashboard/` adds the authenticated local activation backend.
- `desktop/` adds the Hermes Desktop SDK companion and its tests.
- `python/scripts/check_hermes_compat.py` ships with the Python runtime so the
  installed `hermes sidepulse compat` command works.

The source `diagnostics.py` was unchanged in the bounded comparison. No claim
is made here that unrelated SidePulse files were audited.

## Hermes SDK and host-runtime licensing

The tested Hermes Agent checkout is MIT-licensed by Nous Research.[4] The
Desktop companion imports the host-provided `@hermes/plugin-sdk` and
`react/jsx-runtime`; it does not copy the Hermes SDK source or vendor React.
The Python dashboard module imports Hermes host APIs plus runtime-provided
FastAPI, Pydantic, and PyYAML. Those packages are not bundled by this
standalone directory and retain their own notices in the host Hermes/runtime
distribution.

The plugin manifest does not declare Python dependencies. The package therefore
assumes a supported Hermes runtime supplies the dashboard dependencies. It is
not documented as a free-standing FastAPI application.

The plugin registers no model-facing tool and makes no Hermes core edit. The
Desktop activation path is authenticated by Hermes' existing REST token gate;
the local-only focus decision is made in the Desktop companion before the
request is sent.

## Publication caveats

- Runtime version declarations are aligned at `0.2.0-beta.1`.
- macOS automated tests passed for this exact candidate; its predecessor was
  live-tested. Hosted Linux has not run, and Windows is unsupported.
- The verification used a local Unix-socket harness and Hermes' stock runtime;
  it does not claim that a physical SidePulse device was connected during this
  documentation pass.
- Do not ship runtime `hermes.jsonl`, SidePulse state snapshots, sockets,
  compatibility baselines, Hermes sessions, or device history in an archive.
- No publication, repository creation, commit, or push was performed.

## Sources

[1] https://github.com/d31tcjg/sidepulse/blob/5194136c10843e138b9dbdf6d2298b6ebb76c00e/LICENSE — SidePulse LICENSE at inspected origin commit

[2] https://github.com/d31tcjg/sidepulse/commit/48659331e9e8e58120a9dd5c1781bf84ed009287 — Original Hermes integration commit

[3] https://github.com/d31tcjg/sidepulse/commit/a8d8067eba6046833935be15c7d589f2ff6fde7d — Latest inspected Hermes integration commit

[4] https://github.com/NousResearch/hermes-agent/blob/cf7895c1bd9ebbee3c9fc355c552d4d73338a9b4/LICENSE — Hermes Agent LICENSE at tested upstream commit

[5] https://github.com/NousResearch/hermes-agent/blob/cf7895c1bd9ebbee3c9fc355c552d4d73338a9b4/website/docs/reference/cli-commands.md — Hermes plugin CLI reference at tested upstream commit
