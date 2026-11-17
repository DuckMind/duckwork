# Decisions

What this project decided, and why, once the merge request that decided it is
gone from the top of `git log`. Plans live in issues; this file is only for
choices that are already made and that the code is expected to keep.

Every entry names the mechanism, not the intention: if a claim here cannot be
checked against `ard_kit/` or `selfcheck.py`, it does not belong in this file.

## Identifiers

**A command name never carries an npm scope.** `bin` in string form means "the
name of the package", so `{"name": "@org/tool", "bin": "./cli.js"}` publishes
one command. The scope is stripped before the name reaches the identifier
builder (`_declared_segment(dist)`), because `Path` would split `@org/tool`
into two path parts and `_SLUG_SAFE` would silently rewrite `@org` into
`_org`, leaking the scope into the URN as an extra segment:
`urn:air:<host>:cli:_org:tool`. npm's own docs do not spell the strip out, so
it was verified against the live CLI (npm 11.11.0 / node 24.14.1): a scoped
string `bin` links `.bin/tool`, and an object `bin` key is linked by its last
path part too - `{"@org/tool": ...}` as `tool`, `{"deep/sub/dir": ...}` as
`dir`, `{"trail//": ...}` as `trail` - except `{"@org/": ...}`, which keeps
`@org`, with a later key winning a basename collision.

**Conformance cannot guard this.** The spec's URN pattern allows `_` and `:`
in the middle segment, so `urn:air:host:cli:_org:tool` passes both the regex
and the schema while lying about the publisher. That failure mode is
silent-publish, not silent-fail, which is why the whole-string asserts in
`selfcheck.py` section 8 are the only identifier tripwire in the system.

**Flattening stays at the declared-name doors, not in `_make_identifier`.**
Minting looked like the chokepoint and is not: `_make_identifier` takes a
`Path` and cannot tell a publisher-declared name from a real one, and the flat
value is load-bearing beyond the URN - for a `bin` entry it is also the
`displayName`, `aliases` and `metadata.invoke`. So each door that holds a
declared name calls `_declared_segment` where the name is resolved (string
`bin`, object `bin` keys, `mcpServers` keys), and `_make_identifier`'s
docstring carries the rule for a fourth door.

**Scoped identifier asserts compare whole strings.** A substring check is dead
on arrival here: the mangled URN still contains `tool`. Section 8 asserts
`== "urn:air:localhost:cli:tool"`.

**Object-form `bin` keys are flattened like the string form.** Every key goes
through `_declared_segment`, so a scoped key no longer reproduces the mangled
URN through a second door; section 8 asserts the whole identifier list against
the commands npm really links for scoped, slashed, degenerate and colliding
keys.

**A leading underscore in a segment is not malformed.** npm links the key
`"@org/"` as the command `@org`, and `_SLUG_SAFE` writes that as `_org`, so
`urn:air:<host>:cli:_org` is faithful to an installed command. Rejecting
segments that start with `_` would reject a correct URN: the lie to catch is
segment *count*, not segment spelling.

**The sidecar and the catalog agree on every identifier, checked once over the
whole output.** `main()` writes the catalog from `deduped` (first-wins) but the
`.inspect.json` sidecar from `all_schemas`, so a twice-minted URN - "my tool.py"
and "my_tool.py" both slug to `scripts:my_tool` - used to pair the winner's entry
with the loser's schema and ship two different `invoke` strings for one id. Every
schema write site is now `setdefault` and both cross-lane merges are first-wins,
so the same winner survives on both sides. The acceptance is one assert over the
whole output, not a per-lane convention: after the dedupe and before either file
is written, every catalog id must have a sidecar schema whose `invoke` equals the
entry's `metadata.invoke`, and no id may carry a bare `""`/`.`/`..` `:`-section.
It fails closed - a divergence publishes neither file - and it covers lanes that
do not exist yet: a new lane that mints a taken URN with a different invoke
reddens the assert without anyone remembering the rule.

**A `[project.scripts]` name is not slug-safe on charset alone.** `_TOML_KEY`
admits `.`, so a bare `..` key parsed cleanly and minted `urn:air:<host>:cli:..`
- an Escape claiming a location outside the scan root. The pyproject door now
runs `_declared_segment(command)` and skips the entry when it flattens to
empty/`.`/`..`, the guard the `mcpServers` and object-`bin` doors already had;
the bare-section contract in the whole-output assert is its backstop. `_TOML_KEY`
never admits `/`, so for an honest key the flatten is identity and nothing
changes (`hybtool` still mints `cli:hybtool`). A comment that justified the
missing check by claiming `_TOML_KEY` "happens to constrain to exactly the
slug-safe set" was false and is gone in the same change - a wrong comment
defending an absent guard outlives the guard's absence.

**`_declared_segment` splits on `/` only - `[F1] → skipped: platform-conditional,
add when a Windows-separator gate exists`.** On POSIX a backslash in a declared
name is an ordinary character, so `a\b` is one faithful segment minting `cli:a_b`.
Splitting on `\` too - the proposed platform-divergence fix - would mint `cli:b`:
a shorter, wrong tail, one lie traded for another. The divergence is real only
where `Path` treats `\` as a separator (Windows), and this tree runs on POSIX;
the docstring carries the rule so a fourth door or a Windows port re-reads it
instead of "fixing" the split. Revisit only beside a real Windows-separator gate,
never as a standalone edit to the split.

## Extraction boundary

The JavaScript lane declares, it does not analyse:

- `invoke` is the command name, `arguments` is empty. There is no argparse to
  mine, and reading commander or yargs would be the same scope creep as
  writing our own JSON parser.
- `description`, `version` and `distribution` come from the `description`,
  `version` and `name` fields, nothing is inferred.
- A `bin` target that does not exist on disk is declared, not validated. A
  missing file is the publisher's problem, and the section 8 fixture ships no
  `cli.js` on purpose.
- Manifests are read with `json.loads` from the standard library only.
- `pyproject.toml` wins when a workspace ships both manifests, and that
  precedence is documented in the README rather than resolved by merging the
  two. It still owes one line on stderr when a non-empty `bin` is dropped.

The MCP client-config lane also declares rather than analyses, and one of the
things it declares reads as a lie if it is dropped:

**A root `.mcp.json` is read by `main()`, because `catalog_directory` cannot
reach it.** The rglob door walks under a `--dir`, and a client config sits
above every scan dir by definition, so the servers a workspace declared stayed
invisible to the catalog an agent asks "which of these can do X". `main()`
reads it before the "no scan directories found" check and appends its entries
to the tail, which is what keeps re-catalogizing an existing catalog a pure
append: the station one went 1438 -> 1457 with the prefix identical, nothing
removed, nothing pre-existing changed, and the `.inspect.json` sidecar
unchanged. A workspace holding nothing but a client config is catalogable on
its own (`mcponly`, section 2d).

**`env` is never copied.** Client configs keep their secrets there and the
catalog is served over HTTP. Section 2d writes `s3cret-not-cataloged` into a
fixture `env` and asserts it is absent from the whole catalog; the station
audit counted 18 `env` pairs of 8+ characters, and no value and no key name of
them reached the catalog.

**An http-only server's `invoke` is its `url`, not `''`.** `shlex.quote("")` is
the two-character string `"''"`, it survives `.strip()`, and `cmd or server_url`
then prefers the garbage over the url. That shipped in 0.15.9 through both
doors. Fixed once, in the shared `_catalog_mcp_file` - the empty command is
skipped instead of quoted - and asserted from both doors on purpose, 2a at the
rglob one (`mcp:scripts:web-check`) and 2d at the root one (`memory-gw`),
because the fix lives in a helper neither caller owns.

**`disabled` is carried in metadata, not dropped and not written into the
description.** 8 of the station's 19 declared servers are `"disabled": true`,
and the host's live mount set is exactly the 11 that are not. Skipping them was
the rejected alternative: under JIT mounting a server the host has not mounted
is the case discovery exists for. It lands in `metadata.disabled` because
`registry.py` indexes `displayName`, `description`, `aliases`, `tags` and
`representativeQueries` only - metadata is not search text - so the flag rides
the result without letting a capability query be answered by the word
"disabled". Section 2d asserts both values and that absence reads as `False`.

**A card's capability prose is declared in a sibling `<manifest>.ard.json`,
because there is nothing to extract it from.** The generated description is
still the fallback - `MCP server <name> (<stdio|http>).` - and a card with no
prose is still found by its own name at score 100. What prose adds is the other
direction: a capability query with the name withheld. This reverses the earlier
stance that hand-written card prose is the metadata-file posture the project
exists to avoid, and the reason is that the posture argument assumes there is a
source to extract from. For scripts and skills there is (argparse, docstrings,
frontmatter); for a client config there is not - the station's per-server keys
are only `args`, `command`, `disabled` and `env`, and honoring a
publisher-declared `description` key inside `.mcp.json` stays rejected as
speculative. The one place the tool names do live is the host's post-connect
description cache, which is host-specific, written after connect, and still out
of bounds (see Not doing). So the choice is no capability text on a card ever,
or a file the workspace declares.

The sidecar is that file: `<manifest>.ard.json` beside the manifest
(`.mcp.json` -> `.mcp.ard.json`), keyed by the exact `mcpServers` key, each
value `{description?, tags?, aliases?}`, every field optional. Written into
`.mcp.json` itself it would be wrong twice over - the host owns that file and
rewrites it (the station's copy carries 8 `disabled` flags another agent added,
and `env` secrets that must never be copied), and a description key there is
not a thing any client reads. A sibling costs no CLI flag and no unit change:
both `_catalog_mcp_file` callers glob exactly `.mcp.json`, so `with_suffix`
cannot raise and no lane can re-ingest the sidecar as a manifest. Prose feeds
`description` (weight 2.0), `tags` (2.0), `aliases` (2.0) and through them
`representativeQueries` (1.5) and `metadata.keywords` - keywords are carried,
not scored. It is capped at 500 characters like a docstring rather than run
through `_shorten`, which caps at 120 and cuts at the first sentence: on a card
the description is the only capability text there is. Wrongly-typed fields are
dropped, not coerced - a list in `description` would otherwise be serialized
into the one field the scorer reads hardest. A missing, unreadable, misshapen or
orphan-keyed sidecar costs at most one stderr line each and never the scan,
because prose is optional by definition and must not be able to abort the thing
carrying it. Prose also has to be in a language the tokenizer reads:
`_TOKEN` is `[a-z0-9]+`, so a Cyrillic description is invisible to search
however accurate it is.

**A docstring section header counts at a line start or after a sentence end,
and its capture drops path words.** `_extract_keywords` mines `Usage:`,
`Notes:`, `Design goals:` and `Summary:` for tags. The match was unanchored and
case-insensitive, so the first `release notes: ...` anywhere in the prose
hijacked the `Notes:` capture and tagged that sentence's tail instead of the
header's list. Anchoring to `^` alone is the rejected fix: `_join_block` folds
a `>` block with `" "`, so a header written on its own frontmatter line lands
mid-line after folding, and line-anchoring would have dropped the genuine one
along with the impostor. The rule is `(?:^|[.;]\s+)`, which keeps both. Words
holding a slash or an interior dot are then dropped whole rather than stripped
first, because `Usage:` lines are examples: `scripts/gate.py` and `draft.md`
otherwise spend the 15-keyword cap - and so the seven usable tag slots, the
first three being the path's own stem words - on `scripts` and `draft`. The dot
test has to be interior, not "any dot": the header's last word carries the
period that ended its sentence, and dropping it lost the one keyword the tail
was worth. Stripping first is also wrong, it would have turned `./scripts` into
a clean-looking keyword. `check_keywords()` in selfcheck.py holds these cases.

**`invoke` names the interpreter of the machine that built the catalog, and its
paths use forward slashes.** `metadata.invoke` hardcoded `python3`, which does
not exist on a stock Windows install - there is `python.exe`, `py.exe`, and a
Microsoft Store stub that opens the store instead of running anything - so 1399
of the station's 1740 rows, 80.4%, proposed a command that could not run there.
`interpreter()` resolves the name once per scan, `python` on win32 and `python3`
everywhere else: a catalog built on Windows is runnable on Windows and one built
on Linux is byte-identical to before. Rejected alternatives: `$(PYTHON)
script.py` puts a shell substitution into the one field `trust.py` screens for
shell chaining, which would mark every honest row SUSPECT; `invoke.windows`
beside `invoke` adds a second command field that the chain screen, the
entry/sidecar invoke invariant and every pin would have to learn about, plus
~70 KB to the station catalog, to say what one resolved name already says;
`sys.executable` is precise and leaks the building machine's filesystem,
including a venv name that does not exist on the reader's box. Paths inside the
command go through `as_posix()`, because an agent whose shell is Git Bash reads
`scripts\ops\foo.py` as `scriptsopsfoo.py` while cmd.exe accepts forward
slashes - it costs nothing on Windows and stops lying everywhere else.
`metadata.path` keeps the native spelling: it is a location, not a command.

**The inspect sidecar carries the workspace beside the invoke.** Every invoke
in it is relative, so an agent whose cwd is not the scan root ran the command in
the wrong directory and got a missing-file error naming a path that exists.
`/inspect` is this package's extension rather than spec, so its schema is free
to grow a key, and `main()` sets it in one pass over every lane
(`schema.setdefault("workspace", ...)`) instead of per lane, which is also what
covers lanes that do not exist yet. It lands in the sidecar and not in
`metadata` because the manifest requires metadata values to be scalars, and the
sidecar is already where the non-scalar invoke schema lives. Absolute paths in
`invoke` were the other option and were rejected: they pin the catalog to one
machine's filesystem, which the federation merge then serves to another.

**One option, one row in the argument schema.** `_extract_argparse_args` walks
the whole AST, so a script that configures a subparser re-declaring `--config`
minted one row per declaration - 50 of the station's 1740 inspect rows carried a
duplicate argument name (`waydroid_device_profile` had three `--config`, two of
them with empty `help`), and an agent building a command line from the schema
passed the flag twice. Rows are collected into a dict keyed by `(name, kind)`
and returned in insertion order, first non-empty `help` winning; the empty one
is the common case (2444 arguments had no help at all), so merging is what keeps
the row useful rather than merely unique. selfcheck asserts the count and the
merged help and not the row order, because `ast.walk` order is not part of the
contract.

**A POSIX path in a flag is refused on Windows instead of resolved.** On win32
`Path("/home/x/ai-catalog.json").is_absolute()` is False - one leading slash is
not a root without a drive - so the `if not path.is_absolute()` branch joined it
onto the cwd and `--output` then `mkdir(parents=True)`'d
`C:\home\ameobius\projects\...`, a tree the operator's own contract forbids and
nobody asked for. `guard_posix_paths()` runs right after `parse_args()` in all
four CLIs (catalogize exits 1; registry, mcp_server and trust exit 2, matching
what "cannot load" already returns there), and the complaint names the path
Windows would have resolved to, a Windows-path example, and the
`\\wsl.localhost\<distro>\...` UNC form - reading a catalog that lives inside
WSL is the actual Windows use case, so the error has to carry the way through.
`//` stays legal: that is UNC, not a POSIX root. The helper lives in
`catalogize.py` rather than a new `paths.py` because catalogize is stdlib-only
*and* selfcheck runs it as a bare file in 14 places with no PYTHONPATH, so
anything it imported from the package would ImportError; the other three modules
already import from it, and none of them is run bare. Both helpers take a
platform seam (`windows=`, `nt=`) and selfcheck pins them through it, because CI
has no Windows runner and `os.name` on a Linux runner would prove nothing.

## Cursors and paging

**A page cursor names the row it last delivered, not a position.**
`_page_token_encode` carries that row's sort key, and both windows are a bisect
over one ascending key list: `bisect_right` forwards, `bisect_left` backwards
for DESC, where the page ends at the cursor and grows behind it. A key cursor
cannot shift, because it does not count - and the catalog is regenerated on
every `ard-registry` start, so rows added or removed ahead of a walking client
used to move everything behind its cursor.

**A walk that spans a regeneration survives it.** Exact-once over the rows that
existed when the walk started: rows added mid-walk belong to the next walk, a
delivered row that disappears is neither re-served nor leaves a hole, a row not
yet reached is simply absent from it. `walk_moving` in `selfcheck.py` writes a
mutated catalog under a live cursor for each of those four cases and compares
the finished walk against the mutated truth.

**Rejected alternative: a fingerprint over the catalog file.** Binding the
cursor to a digest of the catalog bytes and retiring it with 400 when the digest
moves fails *closed* instead of surviving: every restart kills every in-flight
cursor, and the digest costs a second full read of the catalog per request -
1.75 MB twice on the live station one - with `_atomic_write_json` still able to
land between the two reads, so the fingerprint is stamped over version A while
the rows come from version B. It also needs an "unreadable" sentinel, a third
state the window has to mean something in. That was !25, closed as superseded
rather than merged. If a client ever needs to *know* the corpus moved rather
than merely survive it, the honest shape is an advisory field on the response,
not a fingerprint that retires cursors and not a second read.

**The live cursor binding is the query, not the catalog bytes.** What is
rejected above is a fingerprint over the *catalog file*; the cursor that ships is
bound to the *query* that minted it. `query_fingerprint(text, type_filter)` is a
16-hex sha256 of the query, stamped into the token as `q` (`_page_token_encode`),
and `_page_token_decode` returns `None` - the existing 400 - when a token's `q`
does not match the query it is presented to, because a cursor replayed against a
different text or filter would page through a different result set. That binding
is to the query's identity, so it survives catalog regeneration exactly like the
seek key; it is not a claim that the corpus is unchanged. There is no
`catalog_fingerprint` in the tree - the epitaph is "the catalog-byte binding was
replaced by the seek cursor, and the query binding is live", not "the cursor is
unbound" and not "one fingerprint covers every surface".

**`_PAGE_TOKEN_VERSION` tracks the token layout, not its contents.** The layout
went from an offset to a two-part key, so the version is 2 and a v1 token still
in flight gets the 400 that already exists for a foreign cursor instead of
being reinterpreted as a position. Changing what goes *into* the fingerprint
does not bump it.

**Decode checks the key type before a bisect sees it.** The fingerprint is
documented as not a secret, so a hand-made token is reachable.
`_page_token_decode` takes the lane's own key type (`str` for `/agents`,
`float` for `/search`) and returns `None` - the existing 400 - rather than
letting a `str` meet a `float` inside `bisect` and raise out of the HTTP
handler.

**Both lanes order totally, and the tiebreak is inside the cursor key.**
`/agents` orders by the requested field, `/search` by score, with `identifier`
second in each (`_list_key`, and the pair `search_catalog` sorts on).
Identifiers are unique per catalog because catalogize dedupes on them, so the
order is total. A tie left to catalog order moves the next time the catalog is
regenerated, and a tie group cut by a page boundary then hands the walking
client one row twice and another never. The tiebreak has to be part of the key
the cursor carries and not only part of the sort, or the window bisects on less
than the order the rows arrived in.

**Every surface that mints a cursor has a tripwire on the plumbing.** The codec
has three consumers - `do_POST /search`, `list_response` and
`mcp_server.ard_search` - and dropping the decoded cursor argument at any one
of them stops a walk from terminating, so each is walked to exhaustion under a
page ceiling (`cursor walk did not terminate`, `agents cursor walk did not
terminate`, `mcp cursor walk did not terminate`). A test on the paging function
alone stays green through that regression: the function is still correct, it is
the call site that stopped passing the argument.

## Response envelopes

**The two lanes answer in different envelopes, and neither shape is ours to
choose.** `POST /search` returns `results` (+`referrals`, +`pageToken`);
`GET /agents` returns `items` (+`total`, +`pageToken`). Both come from
`spec/schemas/ard.openapi.yaml` - `SearchResponse` and `ListResponse` - and the
prose in `spec/ard.md` names neither key, so the OpenAPI file is the only
authority on them and guessing from the conformance CLI's assertion is how the
second key gets left behind. `/agents` shipped the search envelope
(`results`/`totalResults`) up to and including 0.17.0, and the official
registry leg rejected it as a critical error - `Missing 'items' array`. The
local gate stayed green the whole time because `selfcheck.py` asserted ard-kit's
own keys rather than the spec's; the leg that would have caught it lived only in
a GitHub workflow that never ran (Actions are disabled account-wide). Three
tripwires cover it now, and only the third one is new. A missing key dies on the
plain reads - `listed_all["total"]` raises `KeyError` before any comparison, so
that is what a flip of the envelope actually produces, measured, not an
`AssertionError`. The whole-envelope equality on an empty filter result,
`== {"items": [], "total": 0}`, is the one that also fails on an *extra* key,
which the reads cannot see: it is what pins the listing to `ListResponse` rather
than merely to two of its field names.

**`totalResults` on `/search` is an ard-kit extension, kept knowingly.**
`SearchResponse` is `additionalProperties: false` and defines `results`,
`referrals` and `pageToken` only, so the field is off-spec. It stays: the
conformance CLI does not flag unknown keys on that endpoint, and it is
load-bearing in `selfcheck.py`, `bench/bench.py`, the federation merge in
`registry.py` and the README. Removing it is a breaking change for readers of
`/search` and belongs in a release with a migration note, not folded into a
conformance fix.

**The `entries`/`results` confusion is fixed in the prose, not with an alias
key.** `skills/ard-registry/SKILL.md` said `/search` "returns entries" - the
catalog file's own key, and the name `/health` reports a row *count* under - and
a Windows onboarding agent reading that sentence literally parsed an empty list
out of a working registry and reported the catalog as empty. Serving both keys
would add a second off-spec field to a `SearchResponse` that is
`additionalProperties: false`, in the same category as `totalResults` above but
with nothing load-bearing reading it, to cover one stale sentence. The skill
names `results`/`totalResults`/`pageToken` instead, and states the `/agents`
(`items`/`total`) and `/explore` (`resultType`/`facets`) envelopes beside it:
documenting one shape is what invited the guess that the others share it.
Verified against the live station registry (1739 entries) - `/search` top-level
keys `['pageToken', 'query', 'results', 'totalResults']`, `/agents`
`['items', 'pageToken', 'total']`, `/explore` `['facets', 'resultType']`.

## Federation

- `source` on a result is the address the fan-out actually reached, not the
  address a peer advertises for itself.
- Under federation, `totalResults` is the local total plus the rows a peer
  returned: a lower bound on the union, not its size. Anything else would
  require asking every peer for a count they do not have to give.
- Peer rows are screened by `ard_kit.trust` before they merge (spec 4.5). A
  row that verdicts SUSPECT is dropped, not annotated: a peer's `displayName`
  and `description` reach the caller's context verbatim, so an annotated row
  would still be an injection path. Rows with no `trustManifest` stay
  UNVERIFIED and pass - a catalog is its own only witness. So does a row that
  verdicts UNSUPPORTED: the gate compares against SUSPECT alone rather than
  the `_FLAGGED` pair the CLI exits on, and that is load-bearing, not an
  omission - §4.5.1 permits a did:key, SPIFFE or ANS identity, and dropping
  UNSUPPORTED would reject every row from a peer that identifies by anything
  but did:web. Worst-wins still makes an injected did:key row SUSPECT, so the
  screen keeps its teeth. Each peer reports `{base, returned, total,
  rejected}`, so what was withheld is visible.
- A merged page carries no `pageToken`, and a cursor sent with
  `federation != none` is a 400. Merged peer ordering is not stable between
  requests, so a cursor over it would be a promise the server cannot keep.
- A dead peer degrades to the local answer. Federation is best-effort by
  design; a 500 would make one unreachable neighbour everyone's outage.

## How changes are accepted

A green pipeline is not the gate for most work - the pipeline adds exactly one
check the landing environment cannot reproduce, the pinned conformance step
(both its legs now: manifest and registry, the second one ported out of the
dead GitHub workflow, which has since been deleted - `.github/workflows/`
held two YAMLs that never ran once, Actions being disabled account-wide, and
the conformance one cloned ard-spec unpinned: a supply-chain read with no
execution behind it); the rest of it is the local gate run again, and CI has
run out of minutes before, failing jobs without a trace. It is narrowed, not
waived: that step
lives inside the single `selfcheck` job, and its network download is forbidden
in the landing environment, so a gate-branch does not run a different job - it
reads the same `selfcheck` result before `main` has moved. Everything else
lands on the local gate below and never waits for CI. The gate is:

1. `selfcheck.py` green.
2. A **targeted** flip: revert the single most fragile expression the change
   relies on, name the assert and the exception type expected, watch it go
   red, restore. Flipping a master switch proves only that the suite runs.
3. A wheel build for anything that ships.
4. For extraction changes, a recatalogize of a real corpus with the field diff
   printed, and `0` changed on the rerun - of the catalog **and** the
   `.inspect.json` sidecar: two files, not one.

Step 4 has a known blind spot: a station whose root ships `pyproject.toml`
never exercises the `package.json` lane, so `0/0/0` there proves absence of
regression and nothing about the new code. When the corpus cannot reach the
new branch, the gate must add a workspace that does.

The version lives in three carriers - `ard_kit/__init__.py` (the truth),
`pyproject.toml` and `.qoder-plugin/plugin.json` - and `check_versions()`
refuses to run when they disagree. Release commits are pure bumps of those
three files; features never ride along in them.

**The trust suite runs twice in CI, once per dependency arm.** The plain
`python3 selfcheck.py` run is stdlib-only, so `check_trust()` takes the
designed-degradation branch there and every real JWS assertion - including
the attached-payload binding that was 0.19.0's CRIT - skips. A second leg
installs `cryptography`, asserts `trust.Ed25519PublicKey is not None` (so the
leg cannot silently skip) and re-runs `check_trust()` alone. The
`pip install jsonschema` that used to sit between them was dead: nothing in
the suite consumes it since the schema checks moved out, and an install line
whose comment lies is worse than no line. Both facts came out of the 0.19.1
review; the MR that carried the first fix (!32) was superseded by the
0.19.1 commit on `main` - same R1 finding, and main's version additionally
returns UNSUPPORTED rather than False when the attached payload does not
decode, because a malformed inner body is a check we could not complete, not
proof of tampering.

**Changes land fast-forward-only - linear, no merge commit.** Re-established
by the 0.15.7 release, whose bump, docs and fix commits landed with no merge
commit between them, so the rule is asserted here rather than remembered.
Landed by `git merge --ff-only` and a push, never the platform merge button:
`merge_method` is `merge`, so the button would write a two-parent commit; the
rule is a lander convention, not platform-enforced. An MR and its gate-branch
are for changes that must wait on the pinned conformance check - logic and
extraction. A pure bump or a docs-only edit cannot fail it, so it lands by a
direct ff-push to `main` (both remotes, single-parent), the MR trail optional.

**A pure bump does not wait for the pipeline.** It rides no gate-branch: a
logic-free carrier bump cannot fail the pinned conformance step, and the
three-carrier agreement is checked in a versioned place - `check_versions()`
inside `selfcheck.py`, which the `selfcheck` CI job runs on every push
(`.gitlab-ci.yml` has no `rules:`); the pre-push hook is the same check
faster and locally, per-clone and not in the repo. Logic and extraction
changes are the opposite - they ride a gate-branch and wait for conformance.
Not waiting is not skipping: the bump's pipeline still runs, so a red one on
`main` is read at the next landing, not never - the CI file records the
precedent, a relative `catalogize.py` path that died with Errno 2 and was
"masked until now by the missing runner quota". The fate is fixed here on
purpose; letting it drift between "gate-branched" and "does not wait" is
worse than either.

## Release routine

Publishing and its verification are run, not recalled - each step below has
burned a release by being remembered instead of executed.

**Publish explicit filenames; check `dist/` against the two expected names
before `twine`.** Never a `dist/*` glob: `DeleteFile` has reported success on
a stale prior-version sdist+wheel while the files persisted, and a glob would
have shipped them. PyPI is append-only, so a wrong upload is retracted only by
yank - the guard belongs before the upload, `dist/` holding exactly this
version's sdist and wheel. Reproduced again on 0.16.0: the delete of a stale
wheel reported success and the file was still on disk at the next `ls`. The
cleanup that works is `mv` out of `dist/` into an untracked place outside the
repo, then `ls` - a delete that reports success proves nothing, and a
`dist-archive/` inside the repo is untracked noise on a pure-bump commit.

**Install-verify: poll, then `uv tool upgrade <name> --reinstall`, then read
the version from the tool venv's own python at a neutral cwd.** The index can
serve the new version on the first poll while uv's resolver still reports "no
version" (a stale CDN edge); `UV_NO_CACHE=1` alone does not clear it, a refresh
does - and on uv 0.9.28 `--reinstall` *is* that refresh, its help reading
"Reinstall all packages ... Implies `--refresh`". Neither `--refresh` nor
`--force` is a flag `uv tool upgrade` accepts there: either one prints a usage
error and changes nothing, leaving the venv on the old version while the
metadata read below looks like a clean pass (reproduced on 0.18.0). `--reinstall`
also forces past the false "Nothing to upgrade". Measured: `- agentic-ard-kit==0.17.0
/ + agentic-ard-kit==0.18.0`. Read the version with
`importlib.metadata` from the venv's own interpreter run outside the repo - a
cwd holding a stale `*.egg-info` reports that instead - and grep the shipped
fix markers in the installed tree, because metadata alone does not prove the
code moved. For an extraction change the markers are not enough on their own:
run the *installed* CLI over a workspace that only the new lane can reach (a
root `.mcp.json` and nothing else, for 0.16.0) and read the entries it emits.

**A bump with no tracked payload is not a release - not tagged, not
published.** Precedent 0.15.8: the version moved in all three carriers, but
the only functional change - the Duckwork-compatible `command` form - sat in the
gitignored root `mcp.json`, so no tracked payload rode the bump. `v0.15.8` was
never tagged and 0.15.8 never reached PyPI. Bump the carriers only when a
tracked payload rides with them; a version spent as a signal to a local tool is
a spent public contract, not a release. A spent number is never reused - the
next release takes the next number, so `v0.15.8` is not tagged and 0.15.8 not
published even if a real payload lands later.

## Install preflight (`ard-doctor`)

Added by the 2026-09-19 Windows onboarding report, whose last finding was that
no step of the form "installed the plugin -> proved it is ready" existed
anywhere: the six things a newcomer had to get right (interpreter name, wrapper
resolution, `.mcp.json` shape, registry auth, catalog path, harness) were six
separate surprises spread over an afternoon, each discovered by a tool failing
somewhere other than at the point of the mistake. One preflight command closes
all six at once, so `ard-doctor` is that command - seven checks in chain order,
printed as they complete, exit status as the verdict.

- **Chain order, cheap-and-blocking first:** interpreter -> `bin/ard-*` on PATH
  -> one wrapper actually runnable -> catalog path -> registry `/health` ->
  search probe -> harness. A check is placed before another only when the second
  cannot mean anything if the first fails: no interpreter makes the wrapper probe
  decoration, no catalog makes `/health` and the probe decoration. The harness is
  last because it is the slow one (7.2 s here) and a preflight that hides its own
  progress behind a minute of silence reads as a hang.
- **Every failure carries a `hint:` and a `next:`** - why it matters to the
  caller, and a command that can be pasted. A verdict without a way out sends the
  reader back to the report that motivated this section. The pairing of `/health`
  and the search probe is what makes the hint specific: the probe reads the
  health body's `auth` field, so a 401 with `auth: required` says "export the
  token" and a 401 with `auth: none` says something is wrong with the server.
- **Warnings pass, failures do not.** Exit 1 is reserved for `FAIL`; `WARN` and
  `SKIP` are reported and counted in the verdict line but leave the status at 0.
  A developer working from a checkout has every wrapper under `bin/` and none on
  PATH, and that install is not broken - it is just not a shell-away install. A
  preflight that fails on its own maintainer's normal setup gets run once and
  then not run.
- **"Found on PATH" and "found in this checkout" are counted apart.** `wrapper()`
  resolves PATH first and falls back to `bin/`, which is right for *running*
  something and wrong for *reporting* it: the union printed
  `bin/ard-* on PATH ..... 5 of 5 found` on a machine where `command -v
  ard-doctor` answered nothing at all. That is a green light over a broken
  install - the exact failure mode this command exists to prevent - so the row
  now says `WARN: 5 of 5 found (ard-doctor only in <checkout>/bin, not on PATH)`.
- **The search probe queries a term taken from the catalog itself**
  (`entries[0].displayName`, falling back to a fixed phrase only when the
  catalog yields none). A fixed probe phrase returns `totalResults 0` on any
  small or freshly built catalog and would WARN on a healthy install - noise
  trains the reader to ignore the row that is actually load-bearing. On the
  station catalog: `1 returned, totalResults 9 for 'HIVE_SUPERVISOR'`.
- **`ARD_DOCTOR` guards the harness against nesting.** The harness pins the
  doctor and the doctor runs the harness, so without the marker
  doctor -> selfcheck -> doctor -> ... is a fork bomb with a progress bar. The
  guard answers `SKIP: already inside an ard-doctor run` and the pin inherits the
  marker on purpose, which makes the pin prove the guard rather than merely
  tolerate it. `SKIP` also covers a missing `selfcheck.py`: the harness ships in
  the checkout and not in the wheel, so an installed copy cannot prove itself and
  must say so instead of failing on a file that was never meant to be there.
- **The token is named, never printed** - `ARD_REGISTRY_TOKEN set (32 chars)`.
  A preflight is run in front of an operator, pasted into a report and executed
  in CI logs; one that echoes the bearer token turns a diagnostic into a leak.
- **`guard_posix_paths` is deliberately not called in `main()`.** The guard
  exists to stop a *writer* minting `C:\home\...` from a POSIX `--output`, and
  the doctor writes nothing: its `--catalog` is read-only, and refusing a
  POSIX-shaped path there would close off the one legitimate way to read a WSL
  catalog from Windows Python (a `//wsl.localhost/...` UNC path, which the guard
  already passes through).

The pin lives in the harness's stage 5c and holds **both ends of the exit
status**: green against the live token-authenticated registry started two
sections earlier (exit 0, no `FAIL:` in the output, all eight row labels present,
the SKIP marker, `passed` in the last line) and red with the token removed (exit
1, `401`, `hint:`, `next:`), plus a unit pin on `check_wrappers` with
`shutil.which` patched to answer nothing. Both ends, because a preflight whose
verdict is always "passed" is decoration and only the red leg can tell the two
apart. Two targeted flips confirmed the pin bites: forcing `off_path = []` failed
on `AssertionError: Check(label='bin/ard-* on PATH', status='ok', detail='5 of 5
found')`, and neutering the failure branch failed on `returncode 0` where 1 was
expected.

## Known trade-offs

- The scorer is token intersection, linear in the catalog per query. Fine for
  thousands of entries, wrong for millions. Measured on the station
  (2026-09-05, 1707 entries, 2.18 MB catalog): `/search` p50 84.6 ms over 111
  requests - `load_catalog` (a full `json.loads` per request, no cache) 32 ms,
  scoring 48 ms, HTTP handler ~4 ms. `/health`, which reads no catalog, is
  p50 1.0 ms, so the server frame is not where the time goes. The catalog-
  dependent part works out at ~47 us per entry, which puts "starts to hurt"
  near 20k entries (~1 s per query). Add a cached parse invalidated on catalog
  mtime when the count approaches that, not before: at 85 ms the lookup is
  noise next to the LLM call that consumes its result, and the ripgrep
  fallback an agent would use instead is slower anyway (p50 347-399 ms per
  query on the same intents, `bench/bench.py`).
- Scores are clamped to 0-100 rather than normalised per field.
- Request bodies are capped at 1 MiB.
- Skill frontmatter is parsed as a subset of YAML and `pyproject.toml` as a
  subset of TOML by regex, because `tomllib` is 3.11+ and the floor here is
  3.10.
- `specVersion` is hardcoded `"1.0"` while the spec document reads v0.91.
  These are different numbers: the schema declares `specVersion` as
  `enum: ["1.0"]`. The hardcode is correct. Re-verified 2026-09-17 against
  `spec/schemas/ai-catalog.schema.json`, byte-identical at `c21ac6a`, at the
  current pin and at main (sha256
  `c55238483a4738e08b250bdd6af1f4dc05a91afe882c649d224d09c19cd8fe09`; the
  digest `.gitlab-ci.yml` pins is the conformance-test binary's, not this
  schema's - the earlier text conflated the two): top-level
  `required: ["specVersion", "entries"]` and `specVersion.enum: ["1.0"]`. The
  document version (v0.91, in the spec's Status line) is NOT the manifest
  `specVersion` value. A deep-research pass that read the version prose
  returned "emit 0.91 / specVersion optional" - a false positive that would
  fail the schema enum. Trust the pinned schema artifact, not the prose.
- Card prose is hand-maintained, so it drifts: a server gains a tool and the
  sidecar does not. Nothing detects that - the package will not spawn a server
  to compare. Measured on the station (1537 entries, all 19 cards declared):
  the mcp lane of the bench went from `P@1=0.00 P@5=0.00 MRR=0.012
  not-found=10/12` to `P@1=0.92 P@5=1.00 MRR=0.958 not-found=0/12`, and the
  tool lane paid for it, `P@1=0.76 -> 0.64`, `MRR=0.863 -> 0.793`, `P@5`
  unchanged at 1.00. Five tool-lane queries were displaced by exactly one rank
  and in four of the five the displacing card is a legitimate answer to the
  intent ("solve a captcha using a vision llm" -> `captcha-solver` over the
  skill that documents that very server; likewise telegram, volatility,
  web-check for a DNS query). The gold labels were deliberately left alone:
  they were written when a card could never win, and editing them in the same
  commit that changes retrieval makes the measurement unfalsifiable. The cost
  stays visible instead. One genuine over-match is in the pile - "run full osint
  recon on a domain" now ranks `web-check-mcp` first, which is one check, not a
  pipeline. Re-measured at 1707 entries the same five queries are still the
  card-topped misses, now at ranks 2, 2, 2, 3 and 4: the catalog grew around
  two of them, which is the drift this bullet describes, not a new effect.
- The catalog indexes every copy the station has, including the copies the
  station has not resolved. Measured 2026-09-05 at 1707 entries: 30 names sit
  at more than one path, 66 entries (3.9% of the catalog), 36 extra copies.
  Half are byte-identical - 9 `scripts/legacy/X` twins of a live `scripts/X`,
  9 copies of vendored compound-engineering scripts across 5 names
  (`peer-job-runner.py` alone ships in six skill dirs), 1 script in two
  profiles. Half have drifted: `find_clean_proxy.py` differs from its legacy
  twin by two cosmetic lines, `kwork_birja_scanner.py` exists at three paths
  (3471/3471/5526 B), `redops_issue_manifest.py` at two (12355 B vs 43994 B).
  None of it costs P@1. All nine tool-lane misses are attributed: five have an
  MCP card on top (in four the card is the server the gold skill documents, the
  fifth is `web-check-mcp` over the script `ops/dns_dig_probe.py`), four are a
  lexical near-miss between two different tools. A copy does hold the top slot
  in two of the nine - `legacy/find_working_proxy.sh`, identical to the live
  script that would top that list anyway, and `ops/subdomain_takeover.py`, one
  of two drifted forks - but dropping every extra copy leaves the gold at rank
  2 in both, so the metric does not move. What copies cost is depth. On "find a
  clean working proxy" the three slots above the gold are
  `legacy/find_working_proxy.sh`, `legacy/find_clean_proxy.py` and
  `find_working_proxy.sh`, so `find_clean_proxy.py` lands at rank 4 instead of
  2, and an agent that stops at the first plausible hit can run the stale fork.
  So `catalogize` does not dedupe: it would drop 19 entries, change no P@1, and
  ard-kit cannot say which drifted fork is canonical - a station-hygiene call,
  of which the 9 byte-identical `scripts/legacy/` twins are the part deletable
  with no information loss. Reproduce with a sha256 group-by over
  `metadata.path` in `data/ard/station-catalog.json`, skipping the 125
  `SKILL.md` entries (the bench collapses a skill dir to one tool) and the 19
  cards (all share one path): neither is pollution.
- The scorer's advertised upgrade path is measured and closed. `registry.py`
  named Porter/Snowball as the fix for a fold that leaves `drafter`/`draft`
  and `enumerate`/`enum` distinct; it is not the fix. Measured 2026-09-05
  offline against the same frozen gold, scoring the live 1707-entry catalog
  in-process - the harness reproduces the server exactly (tool
  0.64/1.00/0.793, mcp 0.92/1.00/0.958), so these are the server's numbers
  and not a model of them. An agentive/-ing fold with doubled-consonant
  collapse moves tool P@1 by zero: it fixes "draft a bug bounty report from
  findings" and breaks "graphql introspection scan", where `scanner`->`scan`
  pulls `recon/graphql_scanner.py` into a 67-67 tie with the gold
  `ops/graphql_introspection_probe.py` and the (score, identifier) tie-break
  hands rank 1 to the lexicographically later path. A scanner is a legitimate
  answer to that query, so the label lost there, not the retrieval. Combined
  with a weight change the fold is strictly worse (0.68). The field weights
  are not a lever either: a 25-point displayName-vs-description sweep has a
  9-point band reading tool 0.72 / mcp 1.00, and all nine points agree on the
  same three fixes and the same one break. That agreement is not a plateau; the
  margins say what it is. Across the three weightings and the five queries that
  move, every decisive margin - what has to shift to change the gold's rank -
  is 0.0000-0.0555 of score, and two of the five are not relevance losses at
  all. At the shipped weights "draft a bug bounty report from findings" is an
  exact 0.4444 tie between the gold `bounty_drafter.py` and `ops/report_draft.py`
  that the (score, identifier) tie-break hands to the non-gold, and "solve a
  captcha using a vision llm" goes to the `captcha-solver` card at 0.54-0.62
  over the gold skill at 0.34-0.36 in every weighting - there the card is the
  right answer and the label points at the skill. The wins are as thin as the
  losses: `dnsrecon_lite.py` takes "enumerate subdomains for a domain" by
  0.0196 at name/desc 1.0/2.0 and by 0.0416 at 3.0/3.5, `sms_verify.py` takes
  the phone/otp query by 0.0098 and 0.0139. The one "regression" is
  `jwt_none_attack.py` over `jwt_alg_confusion.py` by 0.0147-0.0312, and the
  none-alg attack is an alg-confusion attack. What moves is the ruler, not the
  ranking: 30 of the 37 queries carry a single gold label (7 carry two, and two
  of those seven are movers above), over a catalog where several tools
  legitimately fit each query. Tuning to it would ship a coin-flip on ties and
  report +0.08 P@1. So: no stemmer, no reweighting, no version bump, and the
  bench's gold set is not worth growing to enable tuning that would only fit
  it. P@5 is 1.00 on both lanes and not-found is 0/37; the registry never
  loses the tool. The only reason left to touch the scorer is scale, which is
  the latency bullet's problem.
- Declaring prose also deduped `tags`, and that touched cards with no sidecar
  prose at all: `dict.fromkeys` around the tag list drops the duplicate `mcp`
  token a name like `red-tools-mcp` used to produce (`['mcp','red','tools',
  'mcp']` -> `['mcp','red','tools']`), 6 of the station's 19 cards, 10 fields
  in the gate diff. Kept because dedupe is load-bearing once prose can collide
  with `mcp` or with a name word, and because scoring is a set intersection, so
  the second `mcp` was inert noise rather than signal.
- The `type` filter is not a way around scoring: `application/mcp-server-card
  +json` returns all 19 cards when the text matches them and correctly returns
  none when it does not, the filter being an exact string match applied on top
  of scoring rather than instead of it.
- The MCP front reads the catalog and its inspect sidecar from disk on every
  call, inside `call_tool`, instead of holding the parsed catalog in the server
  process. A recatalogize therefore reaches an already-mounted server with no
  host restart - verified live, a server started before the catalog was
  rewritten serving the rewritten entries on the next call. The cost is one
  read per call of a ~1.8 MB file against a scorer already linear in the same
  entries. It also moves the failure: a corrupt or half-written catalog
  surfaces as `catalog unreadable` on the next call rather than at startup,
  which is the right place for it, since the file belongs to whatever
  regenerates it and not to the server serving it.

## Not doing

Issuing signatures: no key generation, no attestation of our own cards, no
did:web document to publish. Verifying someone else's is in the package -
`ard_kit/trust.py` binds a `trustManifest.identity` to the domain its URN
claims, verifies a detached Ed25519 JWS against a JWKS, and reports VERIFIED /
UNVERIFIED / SUSPECT / UNSUPPORTED with the worst finding winning. The
asymmetry is deliberate: a consumer needs a verdict, an issuer needs a key
custody story, and a station catalog that signs its own rows would only be
proving that it can read its own file. Also out: vector search, Postgres,
access policies, and a public hosted registry. Those are the territory of the
large registries and of OpenARD; the value here is turning a folder that
already works into a valid catalog. Also out: parsing JS argument
libraries, npm `scripts` and workspaces, a hand-rolled parser for any format
that the standard library already reads, merging two manifests in one
workspace, and reading a host's post-connect description cache to put tool
names into a server card.

Also out of the doctor: a `--json` mode (add one when a machine reader exists -
today the only consumer is a human or an agent reading the same stdout), an
`ARD_CATALOG` environment variable (a second source of truth for the catalog
path is a second thing the preflight would have to explain; `--catalog` with its
`ai-catalog.json` default is the only one), and a `--no-selfcheck` flag (the two
legitimate reasons not to run the harness - no file, already inside one - are
already `SKIP`, and a flag would add a third reason that is just impatience).
