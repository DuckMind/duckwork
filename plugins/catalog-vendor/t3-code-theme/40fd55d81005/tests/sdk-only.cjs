// Catalog rule: the plugin extends Duckwork only through the plugin SDK. It must
// never query, observe, listen to or change the app's document, and its
// stylesheet reaches Duckwork as the theme's customCSS, not as a <style> of its own.
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs = require('node:fs'), assert = require('node:assert/strict');
const pluginPath = require('node:path').join(__dirname, '..', 'desktop', 'plugin.js');
const source = fs.readFileSync(pluginPath, 'utf8');

// Static: none of these may appear in code (comments and CSS are stripped).
const code = source.replace(/`[\s\S]*?`/g, '``').replace(/^\s*\/\/.*$/gm, '');
for (const banned of ['document', 'window', 'querySelector', 'MutationObserver', 'addEventListener', '.click(', 'getQueryCache', 'innerHTML', 'localStorage']) {
  assert(!code.includes(banned), `plugin code must not use "${banned}"`);
}
console.log('PASS source uses no document, window, observer, listener or cache access');

const sdk = `
export const THEMES_AREA='themes', CHAT_EMPTY_AREA='chat.empty';
export const COMPOSER_AREAS={top:'composer.top',modelPill:'composer.modelPill'}, SESSION_ROW_AREAS={leading:'sessionRow.leading',trailing:'sessionRow.trailing'};
export function requestTheme(name){ window.requested=name; return true }
export const useTheme=()=>({theme:{name:window.painted}});
export const atom=v=>({get:()=>v,set(n){v=n},listen(){return()=>{}}});
export const useValue=a=>a.get();
const state=v=>({get:()=>v,listen(){return()=>{}}});
export const host={state:{connectionId:state('local'),focusedStoredSessionId:state('s1')},connections:async()=>[],
  listPersistedSessions:async()=>(window.reads=(window.reads||0)+1,{sessions:[{id:'s1',git_repo_root:'/Users/me/acme',git_branch:'main',billing_provider:'anthropic'}]})};`;
const page = `<!doctype html><html data-duckwork-theme="t3-code-theme"><head>
<script type="importmap">{"imports":{"@duckwork/plugin-sdk":"/sdk.js","react":"/react.js","react/jsx-runtime":"/jsx.js"}}</script></head><body><main></main>
<script type="module">
// Record every document touch made from plugin code, before it loads.
const own=()=>new Error().stack.includes('/plugin.js');
window.touches=[];
const spy=(target,name)=>{const native=target[name];target[name]=function(...args){if(own())window.touches.push(name);return native.apply(this,args)}};
for(const name of ['querySelector','querySelectorAll','getElementById','getElementsByClassName','createElement','addEventListener'])spy(Document.prototype,name);
for(const name of ['querySelector','querySelectorAll','closest','setAttribute','removeAttribute','toggleAttribute','append','appendChild','prepend','remove','click','addEventListener'])spy(Element.prototype,name);
spy(EventTarget.prototype,'addEventListener');
const Native=MutationObserver;window.MutationObserver=class extends Native{constructor(fn){super(fn);if(own())window.touches.push('MutationObserver')}};
const before=document.documentElement.outerHTML.length;
const {default:plugin}=await import('/plugin.js');
const data=new Map(), disposers=[], regs=[];
plugin.register({register(c){regs.push(c);const off=()=>{const i=regs.indexOf(c);if(i>=0)regs.splice(i,1)};disposers.push(off);return off},onDispose:fn=>disposers.push(fn),
  storage:{get:(k,d)=>data.has(k)?data.get(k):d,set:(k,v)=>data.set(k,v)}});
window.app={regs,data,find:id=>regs.find(c=>c.id===id),dispose:()=>disposers.splice(0).forEach(fn=>fn()),unchanged:()=>document.documentElement.outerHTML.length===before};
window.ready=true;
</script></body></html>`;
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const p = await browser.newPage();
    await p.route('http://t3.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/plugin.js') return route.fulfill({ contentType: 'text/javascript', body: source });
      if (path === '/react.js') return route.fulfill({ contentType: 'text/javascript', body: `export const useEffect=fn=>{fn()};` });
      if (path === '/jsx.js') return route.fulfill({ contentType: 'text/javascript', body: `export const jsx=(type,props)=>typeof type==='function'?type(props):{type,props};` });
      if (path === '/sdk.js') return route.fulfill({ contentType: 'text/javascript', body: sdk });
      return route.fulfill({ contentType: 'text/html', body: page });
    });
    await p.goto('http://t3.test/'); await p.waitForFunction(() => window.ready);
    const out = await p.evaluate(async () => {
      const { app } = window, tick = () => new Promise(r => setTimeout(r, 20));
      const theme = app.find('theme').data, watch = app.find('theme-watch'), label = () => app.find('model-pill-label');
      const hero = () => app.find('empty-hero').data.render(), foot = () => app.find('row-foot').data.render({ sessionId: 's1' }), badge = () => app.find('row-badge').data.render({ sessionId: 's1' });
      const r = { areas: app.regs.map(c => c.area), css: theme.customCSS, requested: window.requested, installed: app.data.get('installed'), labelBefore: !!label() };
      await tick(); r.readsAtRegister = window.reads || 0;
      // Exercise every contribution under this theme, then under another one.
      window.painted = 't3-code-theme-dark'; watch.render(); badge(); await tick();
      r.t3 = { label: label()?.data.label({ model: 'claude-opus-5-5' }), hero: hero()?.props.children, badge: badge()?.props.children, branch: foot()?.props.children[0].props.children };
      const reads = window.reads;
      window.painted = 'fordex-dark'; watch.render(); await tick();
      r.other = { label: !!label(), hero: hero(), badge: badge(), foot: foot() }; await tick();
      r.readsOtherTheme = window.reads - reads;
      app.dispose(); watch.render();
      r.afterDispose = { regs: app.regs.length, unchanged: app.unchanged() };
      r.touches = window.touches;
      return r;
    });
    assert.deepEqual(out.touches, [], 'The plugin never touches the document, at register, render, theme change or dispose');
    assert.deepEqual(out.afterDispose, { regs: 0, unchanged: true }, 'Nothing is left behind and the document is unchanged');
    console.log('PASS no document access at runtime');

    assert.deepEqual(out.areas.sort(), ['chat.empty', 'composer.top', 'sessionRow.leading', 'sessionRow.trailing', 'themes'], 'Only SDK areas, and the pill label waits for the theme');
    assert.equal(out.labelBefore, false);
    assert(out.css.includes(':root[data-duckwork-theme="t3-code-theme"]') && out.css.includes('[data-slot="composer-fade"]') && out.css.includes('[data-t3-row-foot]'), 'The stylesheet travels as the theme\'s customCSS');
    // Selector lists split on top-level commas only (not the ones inside :is()).
    const parts = sel => { const out = ['']; let depth = 0; for (const ch of sel) { if (ch === '(') depth++; else if (ch === ')') depth--; if (ch === ',' && !depth) out.push(''); else out[out.length - 1] += ch } return out };
    const unscoped = out.css.split('}').map(rule => rule.split('{')[0].replace(/\/\*[\s\S]*?\*\//g, '').trim()).filter(sel => sel && !sel.startsWith('@') && !/^(50%|from|to)$/.test(sel) && !parts(sel).every(part => part.includes('[data-duckwork-theme="t3-code-theme"]')));
    assert.deepEqual(unscoped, [], 'Every rule is scoped to this theme');
    assert.deepEqual([out.requested, out.installed], ['t3-code-theme', true], 'One-time activation is recorded');
    console.log('PASS SDK contributions only, CSS as scoped customCSS');

    assert.deepEqual(out.t3, { label: 'Claude Opus 5.5', hero: 'What should we build?', badge: 'AC', branch: 'main' });
    assert.deepEqual(out.other, { label: false, hero: null, badge: null, foot: null }, 'Under another theme every contribution stands down');
    assert.deepEqual([out.readsAtRegister, out.readsOtherTheme], [0, 0], 'The session list is only read while this theme is painted');
    console.log('PASS contributions follow the painted theme');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1) });
