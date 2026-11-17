// Sidebar chat rows, T3's thread list: the title must read above its metadata
// (Duckwork' sidebar tokens paint both the same gray), and only chats running on
// another machine get a glyph, the rule T3 uses so local rows stay quiet. In
// Duckwork' card style the row becomes T3's card: project badge, title, then
// branch and provider in a footer that replaces Duckwork' model/size line.
const {chromium}=require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../desktop/plugin.js'),'utf8');
const layoutCss=source.match(/const css = `([\s\S]*?)\n`/)[1];
const row=(selected)=>`<div class="group row-hover relative rounded-md${selected?' bg-(--ui-row-active-background)':''}" data-slot="context-menu-trigger">
  <button data-slot="row-button"><span class="min-w-0 flex-1 self-center">
    <span class="hover-marquee block text-[0.8125rem]"><span class="hover-marquee-inner">Title</span></span>
    <span class="mt-0.5 block truncate text-[0.625rem]">gpt-6-sol · 10 messages</span>
  </span></button></div>`;
(async()=>{const browser=await chromium.launch();try{
const page=await browser.newPage();
await page.setContent(`<html data-duckwork-theme="t3-code-theme"><head><style>/* Duckwork' own row classes */ .hover-marquee{color:#a3a3a3;font-size:13px}.truncate{color:#a3a3a3;font-size:10px}.rounded-md{border-radius:2px}</style><style>${layoutCss}</style></head><body>
<nav data-tour="sessions-sidebar"><div id="idle">${row(false)}</div><div id="selected">${row(true)}</div></nav></body></html>`);
const css=await page.evaluate(()=>{
  const read=(id)=>{const r=document.querySelector(`#${id} .row-hover`);const t=r.querySelector('.hover-marquee'),m=t.nextElementSibling;
    return {title:getComputedStyle(t).color,weight:getComputedStyle(t).fontWeight,meta:getComputedStyle(m).color,metaSize:getComputedStyle(m).fontSize,radius:getComputedStyle(r).borderRadius}};
  return {idle:read('idle'),selected:read('selected')};
});
assert.notEqual(css.idle.title,css.idle.meta,'Title and metadata must not share one color');
assert.equal(css.idle.weight,'500','T3 titles are medium weight');
assert.equal(css.selected.title,'rgb(245, 245, 245)','The selected chat title reads at full strength');
assert.notEqual(css.idle.title,css.selected.title,'Idle titles recede until hover or selection');
assert.equal(css.idle.metaSize,'11px');
assert.equal(css.idle.radius,'8px','Rounded row surface like T3');
console.log('PASS sidebar rows: title above metadata, selected full strength, rounded');

const cardRow=(dot)=>`<div class="group row-hover relative rounded-md" data-slot="context-menu-trigger">
  <button data-slot="row-button" class="flex flex-col"><div class="flex"><span class="grid"><span class="flex">${dot}</span></span>
    <span class="min-w-0 flex-1 truncate">acme</span><div data-row-actions="true"><span class="session-row-tail">1d</span></div></div>
    <div class="flex flex-col"><span class="hover-marquee"><span class="hover-marquee-inner">Title</span></span></div>
    <span class="native-foot">gpt-6-sol 6 messages</span></button></div>`;
await page.setContent(`<html data-duckwork-theme="t3-code-theme"><head><style>.hover-marquee{color:#a3a3a3;font-size:13px}.flex{display:flex}.flex-col{flex-direction:column}</style><style>${layoutCss}</style></head><body>
<nav data-tour="sessions-sidebar"><div id="idle">${cardRow('<span class="size-1 rounded-full" aria-hidden="true"></span>')}</div>
<div id="busy">${cardRow('<span class="size-1.5 rounded-full" role="status"></span>')}</div></nav></body></html>`);
const cardCss=await page.evaluate(()=>{
  const q=(id,s)=>document.querySelector(`#${id} ${s}`),cs=(id,s)=>getComputedStyle(q(id,s));
  return {idleLead:cs('idle','.grid').display,busyLead:cs('busy','.grid').display,foot:cs('idle','.native-foot').display,
    title:cs('idle','.hover-marquee').fontSize,titleColor:cs('idle','.hover-marquee').color,project:cs('idle','.flex-1').fontSize,padBottom:cs('idle','[data-slot="row-button"]').paddingBottom};
});
assert.equal(cardCss.idleLead,'none','An idle card has no dot, like T3; the badge leads');
assert.notEqual(cardCss.busyLead,'none','A working or unread dot stays: it is the only status signal');
assert.equal(cardCss.foot,'none','Duckwork model/size line gives way to the T3 footer');
assert.equal(cardCss.padBottom,'28px','The card keeps room for the drawn footer');
assert.equal(cardCss.title,'14px');
assert.equal(cardCss.titleColor,'rgba(245, 245, 245, 0.9)','Card titles read at T3 foreground/90 at rest');
assert.equal(cardCss.project,'12px');
console.log('PASS sidebar card: no idle dot, native footer replaced, T3 type scale');

// Duckwork' list is an overflowing flex column and its min-h-[3.375rem] replaces
// min-height: auto, so without flex-shrink: 0 the browser squeezes each card
// below its content: the preview is clipped and the drawn footer covers it.
const stackRow=`<div class="row-hover" style="position:relative;display:grid;min-height:54px">
  <button data-slot="row-button" class="flex flex-col" style="height:100%"><div class="flex" style="height:20px"></div>
    <div class="flex flex-col" style="height:40px"></div></button></div>`;
await page.setContent(`<html data-duckwork-theme="t3-code-theme"><head><style>.flex{display:flex}.flex-col{flex-direction:column}</style><style>${layoutCss}</style></head><body>
<nav data-tour="sessions-sidebar"><div id="list" style="display:flex;flex-direction:column;height:200px;overflow-y:auto">${stackRow.repeat(4)}</div></nav></body></html>`);
const squeeze=await page.evaluate(()=>Array.from(document.querySelectorAll('#list .row-hover')).map(r=>r.getBoundingClientRect().height-r.firstElementChild.getBoundingClientRect().height));
assert(squeeze.every(d=>Math.abs(d)<0.5),`Cards in an overflowing list keep their full height, got ${squeeze}`);
console.log('PASS sidebar card: an overflowing list never clips a card');

await page.addScriptTag({content:source.replace(/^import .*\n/gm,'').replace('export default','globalThis.plugin =')});
const glyph=await page.evaluate(async()=>{
  // jsx stand-in: components run inline, elements come back as plain objects.
  globalThis.jsx=(type,props)=>typeof type==='function'?type(props):{type,props};globalThis.useEffect=fn=>{fn()};
  const store=v=>{const fns=[];return {get:()=>v,set(x){v=x;fns.forEach(f=>f(x))},listen(f){fns.push(f);return()=>{}}}};
  const active=store(null),regs=[],disposers=[];
  window.painted='t3-code-theme-dark';
  const sdk={atom:store,useValue:a=>a.get(),useTheme:()=>({theme:{name:window.painted}}),SESSION_ROW_AREAS:{leading:'sessionRow.leading',trailing:'sessionRow.trailing'},
    host:{state:{connectionId:active,focusedStoredSessionId:store('a')},
      connections:async()=>[{id:'local',kind:'local',label:'This device'},{id:'srv',kind:'remote',label:'Home server'}],
      listPersistedSessions:async(route,opts)=>{window.reads=(window.reads||0)+1;if(opts.profile!=='all')throw new Error('needs the unified list');
        return {sessions:[{id:'loc1',git_repo_root:'/Users/me/work/acme/',git_branch:'main',billing_provider:'openai-codex'},
          {id:'rem1',connection_id:'srv',cwd:'/home/me'},{id:'tip2',_lineage_root_id:'rem2',connection_id:'srv'}]}}}};
  installRowCard({register:r=>regs.push(r),onDispose:fn=>disposers.push(fn)},sdk);
  await new Promise(r=>setTimeout(r,20));
  const reg=area=>regs.find(r=>r.area===area);
  // Nothing is read until a row is on screen under this theme; the first row asks for the list.
  const readsAtInstall=window.reads||0;reg('sessionRow.leading').data.render({sessionId:'loc1'});await new Promise(r=>setTimeout(r,20));
  const foot=id=>reg('sessionRow.trailing').data.render({sessionId:id}).props.children;
  const badge=id=>reg('sessionRow.leading').data.render({sessionId:id});
  const machine=id=>foot(id)[1]?.props?.title??null;
  const out={local:machine('loc1'),remote:machine('rem1'),lineage:machine('rem2'),unknownLocal:machine('new'),
    branch:foot('loc1')[0].props.children,provider:foot('loc1')[2]?.props?.['data-t3-row-provider'],noProvider:foot('rem1')[2],
    badge:badge('loc1').props.children,homeBadge:badge('rem1').props['data-t3-row-badge'],unknownBadge:badge('new')};
  active.set('srv');out.unknownOnServer=machine('new');
  // A row the list never returns is asked for once more, not on every render.
  out.readsAtInstall=readsAtInstall;for(let i=0;i<5;i++)badge('new');await new Promise(r=>setTimeout(r,20));out.reads=window.reads;
  window.painted='fordex-dark';active.set('other');out.otherTheme=[reg('sessionRow.trailing').data.render({sessionId:'loc1'}),badge('loc1')];
  await new Promise(r=>setTimeout(r,20));out.readsOtherTheme=window.reads-out.reads;
  disposers.forEach(fn=>fn());
  return out;
});
assert.equal(glyph.local,null,'A local chat carries no machine marker');
assert.equal(glyph.remote,'Running on Home server','A chat on another gateway shows where it runs');
assert.equal(glyph.lineage,'Running on Home server','Rows are matched by their durable lineage id too');
assert.equal(glyph.unknownLocal,null,'An unlisted chat on the local gateway stays unmarked');
assert.equal(glyph.unknownOnServer,'Running on Home server','An unlisted chat follows the active remote gateway');
assert.equal(glyph.branch,'main','The footer leads with the branch, T3\'s most stable row identifier');
assert.equal(glyph.provider,'openai-codex','The footer ends with the provider that ran the chat');
assert.equal(glyph.noProvider,null);
assert.equal(glyph.badge,'AC','The badge is the repo root\'s initials, the key Duckwork groups projects by');
assert.equal(glyph.homeBadge,'home','A chat outside any repo gets the Home badge Duckwork labels it with');
assert.equal(glyph.unknownBadge,null,'No badge until the row is known, never a guessed project');
assert.deepEqual(glyph.otherTheme,[null,null],'Under another theme the rows render nothing');
assert.equal(glyph.readsAtInstall,0,'The session list is not read until a row renders under this theme');
assert(glyph.reads<=3,`An unlisted row must not re-read the list on every render, got ${glyph.reads} reads`);
assert.equal(glyph.readsOtherTheme,0,'Under another theme the list is never read, even when the connection changes');
console.log('PASS sidebar card data: badge, branch, provider, remote-only machine glyph, lineage ids, theme scope');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
