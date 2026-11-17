// Feedback #10 regression: wide graphs WRAP into new row-bands fitted to the
// measured canvas width — never a horizontal scrollbar, never a clipped box.
// Same React-stub harness as test_edge_routing.mjs: pure layout funcs + Edges
// are extracted from plugin.js and driven with simulated geometry that
// mirrors what the wrapped DOM renders (canvas = column of bands; each band a
// left-anchored flex row; column x = the pack's own left offset + padding).
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const src = readFileSync(new URL('../desktop/plugin.js', import.meta.url), 'utf8')
const grab = name => {
  const i = src.indexOf(`function ${name}(`)
  if (i < 0) throw new Error(`no ${name}`)
  let depth = 0, j = src.indexOf(') {', i) + 2
  for (; j < src.length; j++) if (src[j] === '{') depth++; else if (src[j] === '}' && --depth === 0) break
  return src.slice(i, j + 1)
}
const constGrab = name => {
  const i = src.indexOf(`const ${name} =`)
  if (i < 0) throw new Error(`no ${name}`)
  let depth = 0, j = src.indexOf('=', i)
  for (; j < src.length; j++) { const c = src[j]; if (c === '{' || c === '[') depth++; else if (c === '}' || c === ']') --depth; else if (c === '\n' && depth === 0) break }
  return src.slice(i, j + 1)
}
let instance = 0
const jsx = (type, props, key) => ({ type, props, key })
const { depthMap, columnGroups, bandRows, Edges, CARD_W, MINI } = new Function(
  'jsx', 'jsxs', 'useId',
  [constGrab('EDGE_TONE'),
    `const NODE_TONE = Object.fromEntries(Object.entries(EDGE_TONE).map(([k,v]) => [k, { color:v, borderColor:v, shadow:null, shadowHover:null, pulseMs:null, calm:true, ui:'muted', gate:null, breathe:null }]));\nNODE_TONE.waiting = NODE_TONE.pending;`,
    constGrab('CARD_W'), constGrab('MINI'),
    grab('edgeFlowPolicy'), grab('depthMap'), grab('columnGroups'), grab('bandRows'),
    grab('edgeTone'), grab('nodeState'), grab('routeEdge'), grab('Edges')].join('\n')
  + '; return { depthMap, columnGroups, bandRows, Edges, CARD_W, MINI }'
)(jsx, jsx, () => `t-${++instance}`)

const PAGE = { w: CARD_W, h: 74, colGap: 112, rowGap: 28, pad: 48 }

// Rendered geometry of the wrapped layout: bands stack vertically, each band
// is a flex row starting at x=pad, columns keep the pack's left offsets.
function layout(defs, canvasW, mini = false) {
  const g = mini ? { w: MINI.pillW, h: MINI.pillH, colGap: MINI.colGap, rowGap: MINI.rowGap, pad: MINI.pad } : PAGE
  const cols = columnGroups(defs, depthMap(defs))
  const bands = bandRows(cols, canvasW ? Math.max(1, canvasW - g.pad * 2) : Infinity, () => g.w, g.colGap)
  const boxes = {}
  let y = g.pad
  for (const row of bands) {
    let bandH = 0
    for (const [, col, x] of row) {
      let cy = y
      for (const n of col) {
        boxes[n.id] = { x: g.pad + x, y: cy, w: g.w, h: g.h }
        cy += g.h + g.rowGap
      }
      bandH = Math.max(bandH, cy - g.rowGap - y)
    }
    y += bandH + g.colGap
  }
  return { bands, boxes }
}
function points(d) {
  const t = d.match(/[A-Za-z]|-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/g), out = []
  let i = 0, x = 0, y = 0
  while (i < t.length) {
    const op = t[i++], ax = x, ay = y
    if (op === 'M') { x = +t[i++]; y = +t[i++]; out.push([x, y]); continue }
    if (op === 'C') {
      const bx = +t[i++], by = +t[i++], cx = +t[i++], cy = +t[i++]; x = +t[i++]; y = +t[i++]
      for (let j = 1; j <= 200; j++) { const s = j / 200, u = 1 - s; out.push([u * u * u * ax + 3 * u * u * s * bx + 3 * u * s * s * cx + s * s * s * x, u * u * u * ay + 3 * u * u * s * by + 3 * u * s * s * cy + s * s * s * y]) }
    } else {
      if (op === 'H') x = +t[i++]; else if (op === 'V') y = +t[i++]; else if (op === 'L') { x = +t[i++]; y = +t[i++] } else throw new Error('unknown path ' + op)
      for (let j = 1; j <= 200; j++) out.push([ax + (x - ax) * j / 200, ay + (y - ay) * j / 200])
    }
  }
  return out
}
let checkedEdges = 0
// The full contract on WRAPPED coordinates: ports on card edges, curve inside
// the canvas width, no pass-through of unrelated cards, no arrowhead pile.
function checkWrap(defs, canvasW, mini, label) {
  const { bands, boxes } = layout(defs, canvasW, mini)
  const states = Object.fromEntries(defs.map(n => [n.id, { status: 'done' }]))
  const svg = Edges({ nodes: defs, rects: boxes, states })
  const paths = (svg?.props.children || []).filter(x => x && x.type === 'path')
  assert.equal(paths.length, defs.reduce((n, d) => n + (d.after?.length || 0), 0), `${label}: every dependency routed`)
  const ports = {}
  for (const path of paths) {
    const [a, b] = path.key.split('->'), p = points(path.props.d), from = boxes[a], to = boxes[b]
    assert.equal(p[0][0], from.x + from.w); assert.equal(p.at(-1)[0], to.x)
    assert.ok(p.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y) && x >= 0 && y >= 0), `${label}: finite path`)
    // No-crossing invariant on WRAPPED coords: the blocker set is exactly the
    // one routeEdge enforces (same in-span predicate as test_edge_routing),
    // and the sampled curve must never pierce one of those boxes — verified
    // for band-to-band skip edges and within-band sibling chains alike.
    const xa = Math.min(p[0][0], p.at(-1)[0]), xb = Math.max(p[0][0], p.at(-1)[0])
    for (const [id, r] of Object.entries(boxes)) {
      if (id === a || id === b) continue
      if (!(r.x + r.w > xa + 2 && r.x < xb - 2)) continue
      assert.ok(!p.some(([x, y]) => x > r.x && x < r.x + r.w && y > r.y && y < r.y + r.h), `${label}: ${path.key} avoids unrelated ${id}`)
    }
    ;(ports[b] ||= []).push(p.at(-1)[1])
  }
  for (const ys of Object.values(ports)) assert.equal(new Set(ys).size, ys.length, `${label}: arrowheads do not pile`)
  // WRAP LAW core assertions for this layout:
  const right = Math.max(...Object.values(boxes).map(r => r.x + r.w))
  assert.ok(right <= (canvasW ? canvasW : Infinity) + 0.01, `${label}: no box beyond canvas width (${right} > ${canvasW})`)
  assert.ok(bands.length >= 1, `${label}: at least one band`)
  const ids = Object.keys(boxes)
  assert.equal(new Set(ids).size, ids.length, `${label}: no box overlap possible with unique ids`)
  const all = Object.values(boxes)
  for (let i = 0; i < all.length; i++) for (let j = i + 1; j < all.length; j++) {
    const a = all[i], b = all[j]
    assert.ok(a.x + a.w <= b.x + 0.01 || b.x + b.w <= a.x + 0.01 || a.y + a.h <= b.y + 0.01 || b.y + b.h <= a.y + 0.01,
      `${label}: boxes ${Object.keys(boxes)[i]} and ${Object.keys(boxes)[j]} overlap`)
  }
  checkedEdges += paths.length
  return { bands, boxes }
}

// -- wide-shallow REGRESSION: one wide band of depth columns wraps into bands;
//    narrow canvas forces many bands, wide canvas fits one.
const wide = []
for (let i = 0; i < 12; i++) wide.push(i === 0 ? { id: `n${i}` } : { id: `n${i}`, after: [`n${i - 1}`] })
const oneBand = checkWrap(wide, 4000, false, 'wide canvas')
assert.equal(oneBand.bands.length, 1, 'a canvas wide enough keeps a single band')
const many = checkWrap(wide, 600, false, 'narrow canvas')
assert.ok(many.bands.length > 1, `narrow canvas wraps (${many.bands.length} bands)`)
for (const r of Object.values(many.boxes)) assert.ok(r.x + r.w <= 600, 'no card beyond the narrow canvas')

// -- deep-narrow graph (tall columns) also wraps by width, not depth.
const fan = [{ id: 'root' }, ...Array.from({ length: 6 }, (_, i) => ({ id: `w${i}`, after: ['root'] })),
  { id: 'join', after: Array.from({ length: 6 }, (_, i) => `w${i}`) }]
checkWrap(fan, 640, false, 'fan-in at narrow width')
checkWrap(fan, 2000, false, 'fan-in at wide width')

// -- mini pills: same law at pill scale.
const mini = checkWrap(wide, 300, true, 'mini narrow')
assert.ok(mini.bands.length > 1, 'mini wraps too')
for (const r of Object.values(mini.boxes)) assert.ok(r.x + r.w <= 300, 'no pill beyond the mini canvas')

// -- bandRows pure contract: band right edge never exceeds avail; every depth
//    appears exactly once, in order.
const cols = columnGroups(wide, depthMap(wide))
for (const avail of [1, 100, 250, 375, 600, 10000]) {
  const bands = bandRows(cols, avail, () => PAGE.w, PAGE.colGap)
  const seen = bands.flat().map(([d]) => d)
  assert.deepEqual(seen, [...seen].sort((a, b) => a - b), 'depths stay in order across bands')
  assert.equal(new Set(seen).size, seen.length, 'one band per depth')
  for (const row of bands) {
    const last = row.at(-1)
    assert.ok(last[2] + PAGE.w <= Math.max(1, avail) + 0.01 || row.length === 1,
      `band fits avail=${avail}: right=${last[2] + PAGE.w}`)
  }
}
// resize recomputes: narrower width must never yield FEWER bands.
const w600 = bandRows(cols, 600 - PAGE.pad * 2, () => PAGE.w, PAGE.colGap).length
const w900 = bandRows(cols, 900 - PAGE.pad * 2, () => PAGE.w, PAGE.colGap).length
const w3000 = bandRows(cols, 3000 - PAGE.pad * 2, () => PAGE.w, PAGE.colGap).length
assert.ok(w600 >= w900 && w900 >= w3000, 'narrower canvas packs into at least as many bands')

// -- scrollbar law is gone from both canvases (static regression).
assert.doesNotMatch(src, /overflow-x-auto/, 'page canvas lost the horizontal scrollbar')
const miniBody = src.slice(src.indexOf('function MiniGraph('))
assert.doesNotMatch(miniBody.slice(0, miniBody.indexOf('function GraphView')), /overflowX/, 'mini canvas lost overflowX')

console.log(`canvas wrap PASS: wide-shallow ${many.bands.length}-band regression, page+mini, ${checkedEdges} wrapped edges routed, overlap/clip/scrollbar laws hold`)
