// Reproduce the step-2 recon lap: skip-column dependencies cross coverage/critic.
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
const src = readFileSync(new URL('../desktop/plugin.js', import.meta.url), 'utf8')
const grab = name => {
  const i = src.indexOf(`function ${name}(`)
  if (i < 0) return ''
  let depth = 0, j = src.indexOf(') {', i) + 2
  for (; j < src.length; j++) if (src[j] === '{') depth++; else if (src[j] === '}' && --depth === 0) break
  return src.slice(i, j + 1)
}
let instance = 0
const jsx = (type, props, key) => ({ type, props, key })
const { Edges, depthMap } = new Function('jsx', 'jsxs', 'useId',
  `const EDGE_TONE = { done:'teal', pending:'gray', failed:'red', running:'blue', held:'orange', skipped:'gray' };\nconst NODE_TONE = Object.fromEntries(Object.entries(EDGE_TONE).map(([k,v]) => [k, { color:v, borderColor:v, shadow:null, shadowHover:null, pulseMs:null, calm:true, ui:'muted', gate:null, breathe:null }]));\nNODE_TONE.waiting = NODE_TONE.pending;\n${['edgeFlowPolicy','depthMap','graphLinks','edgePath','routeEdge','edgeTone','nodeState','Edges'].map(grab).join('\n')}\nreturn { Edges, depthMap }`)(jsx, jsx, () => `test-${++instance}`)
const nodes = [
  {id:'hub-a'}, {id:'hub-b'}, {id:'mac'},
  {id:'coverage', after:['hub-a']},
  {id:'verify', after:['hub-a','hub-b','mac','coverage']},
  {id:'critic', after:['verify']},
  {id:'consolidate', after:['verify','critic']}
]
function rectsFor(defs, mini = false) {
  const depths = depthMap(defs), rects = {}, cols = []
  for (const n of defs) (cols[depths.get(n.id)] ||= []).push(n)
  let x = 20
  cols.forEach(col => {
    let y = 80
    for (const n of col) {
      rects[n.id] = {x,y,w:mini ? 50+n.id.length*4 : 168,h:mini ? 20 : 74}
      y += rects[n.id].h + (mini ? 6 : 28)
    }
    x += Math.max(...col.map(n=>rects[n.id].w)) + (mini ? 34 : 112)
  })
  return rects
}
function points(d) {
  const t = d.match(/[A-Za-z]|-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/g), out = []
  let i=0, x=0, y=0
  while (i<t.length) {
    const op=t[i++], ax=x, ay=y
    if(op==='M') {x=+t[i++];y=+t[i++];out.push([x,y]);continue}
    if(op==='C') {
      const bx=+t[i++],by=+t[i++],cx=+t[i++],cy=+t[i++];x=+t[i++];y=+t[i++]
      for(let j=1;j<=200;j++) {const s=j/200,u=1-s;out.push([u*u*u*ax+3*u*u*s*bx+3*u*s*s*cx+s*s*s*x,u*u*u*ay+3*u*u*s*by+3*u*s*s*cy+s*s*s*y])}
    } else {
      if(op==='H') x=+t[i++]; else if(op==='V') y=+t[i++]; else if(op==='L') {x=+t[i++];y=+t[i++]} else throw new Error('unknown path '+op)
      for(let j=1;j<=200;j++) out.push([ax+(x-ax)*j/200,ay+(y-ay)*j/200])
    }
  }
  return out
}
function check(defs, rects, label) {
  const states=Object.fromEntries(defs.map(n=>[n.id,{status:'done'}]))
  const svg=Edges({nodes:defs,rects,states}), paths=svg.props.children.filter(x=>x.type==='path')
  assert.equal(paths.length,defs.reduce((n,d)=>n+(d.after?.length||0),0),'retain every explicit dependency')
  const ports={}
  for(const path of paths) {
    const [a,b]=path.key.split('->'), p=points(path.props.d), from=rects[a], to=rects[b]
    // Ports sit ON the card edge but may spread along it so arrowheads never pile.
    assert.equal(p[0][0],from.x+from.w);assert.equal(p.at(-1)[0],to.x)
    assert.ok(p[0][1]>=from.y+1 && p[0][1]<=from.y+from.h-1,`${label}: exit port on ${a} edge`)
    assert.ok(p.at(-1)[1]>=to.y+1 && p.at(-1)[1]<=to.y+to.h-1,`${label}: entry port on ${b} edge`)
    assert.ok(p.every(([x,y])=>Number.isFinite(x)&&Number.isFinite(y)&&x>=0&&y>=0), 'path stays in reserved canvas')
    for(const [id,r] of Object.entries(rects)) {
      if(id===a||id===b) continue
      assert.ok(!p.some(([x,y])=>x>r.x && x<r.x+r.w && y>r.y && y<r.y+r.h),`${label}: ${path.key} passes through unrelated ${id}`)
    }
    ;(ports[b] ||= []).push(p.at(-1)[1])
  }
  for(const ys of Object.values(ports)) assert.equal(new Set(ys).size,ys.length,'incoming arrowheads must not pile onto one point')
  return {svg,rects}
}
const page=check(nodes,rectsFor(nodes),'page')
check(nodes,rectsFor(nodes,true),'mini: variable-width pills')
const chain=[{id:'a'},{id:'b',after:['a']},{id:'c',after:['b']}]
check(chain,rectsFor(chain),'ordinary chain')
// Resized content and scrolled coordinate offsets use the same measured-rect contract.
const shifted=Object.fromEntries(Object.entries(rectsFor(nodes)).map(([id,r])=>[id,{...r,x:r.x+73,y:r.y+20}]))
check(nodes,shifted,'scrolled canvas')
const tall=rectsFor(nodes);tall.coverage.h=130;check(nodes,tall,'expanded middle card')
const omitted={...rectsFor(nodes)};delete omitted.coverage
assert.doesNotThrow(()=>Edges({nodes,rects:omitted,states:{}}),'unmeasured cards during mount are safe')
const failed=Edges({nodes:chain,rects:rectsFor(chain),states:{a:{status:'failed'}}})
const dead=failed.props.children.find(x=>x.key==='a->b')
assert.equal(dead.props.strokeDasharray,'3 3');assert.match(dead.props.markerEnd,/-dead\)/)
assert.notEqual(failed.props.children[0].props.children[0].props.id,page.svg.props.children[0].props.children[0].props.id,'markers remain per-instance')
if(process.argv.includes('--fixture')) writeFileSync(fileURLToPath(new URL('../edge-fixture.json',import.meta.url)),JSON.stringify(page,null,2))
console.log('edge routing PASS: real skip-column graph, page/mini, resize, scroll, chain, missing measurements, failed tone and markers')
