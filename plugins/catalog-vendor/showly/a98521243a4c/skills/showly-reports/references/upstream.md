# Renderer provenance and updates

`scripts/vendor/am.mjs` is bundled from
[Answer me with HTML](https://github.com/QingYunA/answer-me-with-html), version
0.4.14, commit `e729b248816c0c420531ee61be0d1aac6b197220`, with one recorded
modification (below). `scripts/vendor/upstream.json` records both digests —
`upstreamSha256` for the bundle as upstream published it, `shippedSha256` for the
bytes actually shipped here — and the bundled dependency versions.
`THIRD_PARTY_LICENSES.txt` retains the upstream MIT notice and licenses for marked,
dagre and graphlib. Showly's Skill instructions and wrapper adapt this renderer
for local reports and Showly hosting.

## The one modification

Upstream's `src/update.js` polled its own published package metadata on a weekly
timer and told the user to run an update command. A vendored copy must not carry
a second update path beside Showly's, and an installed skill must not reach out
to GitHub on its own, so that module is replaced by an inert stub: the update
helpers still exist and still satisfy their call sites in `src/cli.js`, but they
report no version, fetch nothing and spawn nothing. Its `update_check` config key
is gone with it.

This is also a hard requirement of Duckwork's catalog build, whose
`pinned-source-validate` gate rejects any file that both names a GitHub fetch URL
and writes plugin files — catalog rule 3 allows no update path but the pinned
commit. `pnpm check:agent-plugin` asserts here that those URL patterns stay out
of the bundle, so a byte-for-byte re-vendor reddens this repository instead of
someone else's CI.

The upstream bundle includes additional commands, but Showly's `scripts/report.mjs`
entrypoint exposes only static rendering, patching, linting and syntax help. It
requires Node.js 20+, uses temporary upstream configuration, suppresses browser
opening, and leaves an existing upstream installation alone. No per-user npm
install is needed. This is local code execution, not a remote MCP rendering tool.

To update, maintainers should check out an explicit upstream commit, copy that
commit's generated bundle, review its dependency lockfile, re-apply the
`src/update.js` stub against that release's own module, and refresh the
third-party notices and both digests in `upstream.json`. Review upstream changes
to file access, networking, embedded source and output behavior. Run the
package's tests, including installed-skill rendering and patching, then check a
packed npm artifact includes both skills, the wrapper, the renderer and licenses.
Release through Showly's existing package release process; never self-update the
vendor file in a user's installed skill directory.
