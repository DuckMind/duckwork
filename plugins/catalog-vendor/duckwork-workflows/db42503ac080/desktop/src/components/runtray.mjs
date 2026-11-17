/**
 * runtray.mjs — SKELETON for the collapsible live-run tray (#22, design
 * contract on issue #22).
 *
 * Target shape (accepted design, supersedes the #28 sticky-rail shape for
 * live runs): a collapsible situational tray stacked as a sibling of the
 * native task-list / subagents / queued-messages family directly above the
 * chat window, keyed on owner.session_id INCLUDING dispatch/cron-shaped
 * launches whose owner.session_id matches the focused chat.
 *
 *   - collapsed: ONE thicker tray row — pulse glyph ⌬, aggregate label
 *     `N runs · X building · Y held` (held amber, failed red), micro
 *     node-transition sparkline, ▾. Hidden at zero live runs; the last
 *     completion lingers 60 s as `last run done · n/n nodes`, then retracts.
 *   - expanded: one row per owned run — status chip, name + lane_key, node
 *     dots + x/y, current node, elapsed, token chip. Order held → building →
 *     queued → finished (held pinned top). Finished rows ack-away (cap 10).
 *     Row click accordion-expands the shared MiniGraph; `open ↗` escalates to
 *     the pane; click-away collapses; Esc collapses to the collapsed row.
 *
 * SKELETON LAWS (this file):
 *  - Bodies are TODO shells: importing this module must never throw and must
 *    never touch the network or persistent state (R6: no behaviour by
 *    source-text; atoms in-memory only, never localStorage).
 *  - The REAL integration today lives in desktop/plugin.js: SessionStrip is
 *    the mount owner and the tray models (trayScoping, trayModel,
 *    trayAggregateLabel, trayRecap, ackFinished, toggleTray, $trayOpen) are
 *    exported from there and exercised by tests/test_run_tray.mjs (RED-first
 *    — the scaffold PR ships them failing on purpose). This module is the
 *    component family the build lane grows those bodies into; plugin.js must
 *    stay import-clean on its own regardless (tests/test_11_ui_imports.mjs
 *    freezes plugin.js imports to exactly three sources, so plugin.js may
 *    NEVER import-reexport from this file).
 *  - Imports ride the frozen baseline only: @duckwork/plugin-sdk, react,
 *    react/jsx-runtime — zero new sources. The shells below import NOTHING so
 *    the file also parses/loads clean under plain node until the build lane
 *    grows real bodies (the moment jsx is needed it comes from
 *    react/jsx-runtime, the repo's baseline).
 *
 * STATUS (build lane, #22): the REAL implementation landed IN PLACE in
 * desktop/plugin.js — trayScoping/trayModel/trayAggregateLabel/trayRecap/
 * trayShouldShow/ackFinished/toggleTray + RunTrayRow/RunTrayRunRow/RunTray
 * are exported there (test_11_ui_imports freezes plugin.js imports at the
 * three SDK sources, so plugin.js may never import-reexport from this file).
 * The shells below are kept as DESIGN DOCUMENTATION only: the contract
 * tests/test_run_tray.mjs asserts, in shell shape. They throw on call so any
 * accidental live use is loud, never silently divergent.
 */

/**
 * Pure model shells. Mirrors the contract tests/test_run_tray.mjs asserts —
 * the build lane ports these to desktop/plugin.js (or re-exports the real
 * implementations from there); until then they throw to make any accidental
 * live use loud instead of silently wrong.
 */
export function trayScoping(runs, sid, uiSid, pairKey) {
  // TODO(build-lane): keep every run whose owner.session_id === sid —
  // dispatch/cron-shaped launches included; other sessions and blank-owner
  // runs never appear (pane-only, ownedRuns law).
  throw new Error('runtray scaffold: trayScoping not implemented')
}

export function trayModel(runs, acked) {
  // TODO(build-lane): rows with bands held → building → queued → finished
  // (held pinned top; within band: live by started desc, finished by updated
  // desc); un-acked finished rows stay in the ledger; acked rows drop out.
  throw new Error('runtray scaffold: trayModel not implemented')
}

export function trayAggregateLabel(runs, acked) {
  // TODO(build-lane): { total, building, held, failed, line, segments } with
  // line `N runs · X building · Y held`; segment colours read NODE_TONE
  // entries — the ONE tone table, never a forked palette.
  throw new Error('runtray scaffold: trayAggregateLabel not implemented')
}

export function trayRecap(model, now) {
  // TODO(build-lane): `last run done · n/n nodes` for 60 s after the last
  // live row leaves, then null (queued-messages parity); absent counts read
  // '?', never fabricated 0/0; null while anything is live.
  throw new Error('runtray scaffold: trayRecap not implemented')
}

export function ackFinished(acked, runId) {
  // TODO(build-lane): newest-first ack ledger capped at 10.
  throw new Error('runtray scaffold: ackFinished not implemented')
}

export function toggleTray(state, runId) {
  // TODO(build-lane): collapsed → { expanded: true, openRun: null };
  // open tray: row click accordion-toggles that row only.
  throw new Error('runtray scaffold: toggleTray not implemented')
}

/** Collapsed affordance: one thicker tray row (native tray-row height) —
 *  ⌬ pulse glyph tied to node transitions, aggregate label with amber held /
 *  red failed segments, micro sparkline, ▾. Click anywhere expands. */
export function RunTrayRow({ runs, acked, onExpand }) {
  // TODO(build-lane): render via trayAggregateLabel; zero runs + no recap
  // window => the owner (RunTray) renders nothing.
  return null
}

/** One expanded row for a single owned run: status chip, name + lane_key,
 *  per-node dots + x/y, current node label, elapsed, token chip; accordion
 *  MiniGraph when open; GateActions for held; `open ↗` to the pane. */
export function RunTrayRunRow({ run, open, onOpenPane }) {
  // TODO(build-lane)
  return null
}

/** The tray family root: collapsed row + drop-down run rows (max ~40%
 *  viewport, internal scroll), ordering held → building → queued → finished,
 *  ack-away × per finished row (cap 10), click-away + Esc collapse. Mounts
 *  beside PillRail inside the SessionStrip composer registration. */
export function RunTray({ runs, sid }) {
  // TODO(build-lane)
  return null
}
