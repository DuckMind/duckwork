# examples/diagrams/ — derived diagram table

Every template below ships with a diagram that is **derived from its
graph bytes**, never drawn by hand (DIAGRAM LAW v1). The layout rule
(lane/col/stack, compared bytes) is the **LAYOUT RULE paragraph in
`scripts/graph_diagram.py`'s docstring** — one-source law: that
paragraph is the spec, this README cites it, a contradiction between
diagram and graph is a bug in that file (named defendant).
Regenerate everything after editing any example:

```sh
python3 scripts/graph_diagram.py --all        # candidates (stdlib, deterministic)
# render + shoot with the VENDORED archify (scripts/vendor/archify/, version in
# ARCHIFY_VERSION — the only oven the repo owns; any machine with node >= 18:
#   node scripts/vendor/archify/renderers/workflow/render-workflow.mjs \
#     examples/diagrams/<name>.candidate.json examples/diagrams/<name>.html
#   # then screenshot examples/diagrams/<name>.html with any headless chromium
#   # (chrome-headless-shell --headless --no-sandbox --screenshot=... works;
#   #  strip the viewer chrome before saving the records png)
#   # and record a QA lap per diagram at examples/diagrams/qa/<name>.qa.json:
#   #  {browser, expected_nodes (= candidate nodes length), clipped, legible,
#   #   chrome_free} — this table DERIVES the gates column from those receipts,
python3 scripts/diagram_readme.py             # rebuild this table (derived)
python3 scripts/graph_diagram.py --check --all # CI freshness gate: exit 1 on drift
```

| example | diagram | candidate sha256 | png sha256 | profile | gates |
|---|---|---|---|---|---|
| examples/basics/approve-publish.json | [approve-publish.png](approve-publish.png) | `a6e17c2be85d1fb1` | `64a6ae89c2d2c8bf` | standard | derived + rendered via vendored archify; browser-check done (local chromium (snap) headless --screenshot at 1512px width; archify viewer toolbars (.toolbar, .diagram-nav) hidden by injected style before capture, no PATH/MAP/LENS/zoom visible in any shot; vision-QA lap per png (clip, legibility, counts vs legend), no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/basics/branch-on-verdict.json | [branch-on-verdict.png](branch-on-verdict.png) | `77280e59eaacd37d` | `0b7e44fa842cdc6e` | standard | derived + rendered via vendored archify; browser-check done (cloud-chromium via CDP Page.captureScreenshot (captureBeyondViewport); authoring box has no local chromium — recorded honestly as cloud, not local, no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/basics/exchange-run.workflow.json | [exchange-run.workflow.png](exchange-run.workflow.png) | `e09d40d68e42c83f` | `c36f6301551df1bf` | standard | derived + rendered via vendored archify; browser-check done (local chromium (snap) headless --screenshot at 1512px width; archify viewer toolbars (.toolbar, .diagram-nav) hidden by injected style before capture, no PATH/MAP/LENS/zoom visible in any shot; vision-QA lap per png (clip, legibility, counts vs legend), no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/basics/smoke.json | [smoke.png](smoke.png) | `55eeebdc657b4750` | `ba070f54366d7e27` | standard | derived + rendered via vendored archify; browser-check done (cloud-chromium via CDP Page.captureScreenshot (captureBeyondViewport); authoring box has no local chromium — recorded honestly as cloud, not local, no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/build/bulk-transform.workflow.json | [bulk-transform.workflow.png](bulk-transform.workflow.png) | `c8bdef15d7c2ab3e` | `2fd80c9af2b4173d` | standard | derived + rendered via vendored archify; browser-check done (local chromium (snap) headless --screenshot at 1512px width; archify viewer toolbars (.toolbar, .diagram-nav) hidden by injected style before capture, no PATH/MAP/LENS/zoom visible in any shot; vision-QA lap per png (clip, legibility, counts vs legend), no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/build/census-fanout.workflow.json | [census-fanout.workflow.png](census-fanout.workflow.png) | `484b0733752dc923` | `877f81acd8de3de7` | standard | derived + rendered via vendored archify; browser-check done (cloud-chromium via CDP Page.captureScreenshot (captureBeyondViewport); authoring box has no local chromium — recorded honestly as cloud, not local, no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/build/quorum-probe.workflow.json | [quorum-probe.workflow.png](quorum-probe.workflow.png) | `dae0138a65df9fa9` | `20748709a9d73684` | standard | derived + rendered via vendored archify; browser-check done (cloud-chromium via CDP Page.captureScreenshot (captureBeyondViewport); authoring box has no local chromium — recorded honestly as cloud, not local, no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/build/triage-route.workflow.json | [triage-route.workflow.png](triage-route.workflow.png) | `2d98dfd53c8f0110` | `ff7b53ecc9e8948b` | standard | derived + rendered via vendored archify; browser-check done (local chromium (snap) headless --screenshot at 1512px width; archify viewer toolbars (.toolbar, .diagram-nav) hidden by injected style before capture, no PATH/MAP/LENS/zoom visible in any shot; vision-QA lap per png (clip, legibility, counts vs legend), no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/ops/incident-response.json | [incident-response.png](incident-response.png) | `e460883d28d85a2b` | `67a2d81174071f72` | standard | derived + rendered via vendored archify; browser-check done (cloud-chromium via CDP Page.captureScreenshot (captureBeyondViewport); authoring box has no local chromium — recorded honestly as cloud, not local, no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/release/gated-publish.workflow.json | [gated-publish.workflow.png](gated-publish.workflow.png) | `812b57a89a149406` | `2317e3971a1b1421` | standard | derived + rendered via vendored archify; browser-check done (local chromium (snap) headless --screenshot at 1512px width; archify viewer toolbars (.toolbar, .diagram-nav) hidden by injected style before capture, no PATH/MAP/LENS/zoom visible in any shot; vision-QA lap per png (clip, legibility, counts vs legend), no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/release/issue-to-pr.workflow.json | [issue-to-pr.workflow.png](issue-to-pr.workflow.png) | `9c9b14283d83ce3a` | `91f3d09b532379cd` | standard | derived + rendered via vendored archify; browser-check done (cloud-chromium via CDP Page.captureScreenshot (captureBeyondViewport); authoring box has no local chromium — recorded honestly as cloud, not local, no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/release/machine-watch.workflow.json | [machine-watch.workflow.png](machine-watch.workflow.png) | `19591bb7539b6ade` | `4bd7e1b66431749d` | standard | derived + rendered via vendored archify; browser-check done (local chromium (snap) headless --screenshot at 1512px width; archify viewer toolbars (.toolbar, .diagram-nav) hidden by injected style before capture, no PATH/MAP/LENS/zoom visible in any shot; vision-QA lap per png (clip, legibility, counts vs legend), no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/release/release-lifecycle.workflow.json | [release-lifecycle.workflow.png](release-lifecycle.workflow.png) | `7bbe81a8144a4251` | `c19a0c0ace8feb16` | standard | derived + rendered via vendored archify; browser-check done (local chromium (snap) headless --screenshot at 1512px width; archify viewer toolbars (.toolbar, .diagram-nav) hidden by injected style before capture, no PATH/MAP/LENS/zoom visible in any shot; vision-QA lap per png (clip, legibility, counts vs legend), no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/release/submit-pr.workflow.json | [submit-pr.workflow.png](submit-pr.workflow.png) | `f093c5ab135b7848` | `ed27a91e1e21df34` | standard | derived + rendered via vendored archify; browser-check done (cloud-chromium via CDP Page.captureScreenshot (captureBeyondViewport); authoring box has no local chromium — recorded honestly as cloud, not local, no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/review/blind-council.workflow.json | [blind-council.workflow.png](blind-council.workflow.png) | `163891d0085e7e7e` | `7b077bb36cdb2711` | standard | derived + rendered via vendored archify; browser-check done (local chromium (snap) headless --screenshot at 1512px width; archify viewer toolbars (.toolbar, .diagram-nav) hidden by injected style before capture, no PATH/MAP/LENS/zoom visible in any shot; vision-QA lap per png (clip, legibility, counts vs legend), no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/review/escalation-ladder.workflow.json | [escalation-ladder.workflow.png](escalation-ladder.workflow.png) | `76202d9ff88b96de` | `6b66951ce91ce7cb` | standard | derived + rendered via vendored archify; browser-check done (local chromium (snap) headless --screenshot at 1512px width; archify viewer toolbars (.toolbar, .diagram-nav) hidden by injected style before capture, no PATH/MAP/LENS/zoom visible in any shot; vision-QA lap per png (clip, legibility, counts vs legend), no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |
| examples/review/portable-review.workflow.json | [portable-review.workflow.png](portable-review.workflow.png) | `eca24a58063b50cd` | `9c5a940488c4676d` | standard | derived + rendered via vendored archify; browser-check done (cloud-chromium via CDP Page.captureScreenshot (captureBeyondViewport); authoring box has no local chromium — recorded honestly as cloud, not local, no-clip, legible, chrome-free); receipts in qa/ (generator + renderer version-stamped) |

Cards (the two panels inside each diagram) are the ONLY hand-authored
diagram input; they live in `<name>.cards.json` beside the graph. Every
number in a card must be recomputable from the graph bytes it describes.

Scope: every graph under `examples/` carries a conforming diagram.
Test fixtures (`tests/fixtures/`) are engine inputs consumed by test
code, not docs — no diagram (rung zero). Census command for the scope:
`git ls-tree -r --name-only HEAD | grep '\.json$' | grep -v '^graphify-out/'
 | grep -v '^examples/diagrams/' | grep -v '\.cards\.json$'` —
every file whose parsed JSON has a non-empty `nodes` array must have a
table row or queue row in this table (receipt at build: examples/ 17
= 17 table + 0 queue).

