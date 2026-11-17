// Session tiles (a chat opened in another tab) and empty chats, with CSS alone.
// Duckwork puts data-tour only on the primary pill, so the tile's pill is matched
// as the button right before the reasoning pill, or as the first menu button of
// the controls when the model has no reasoning levels. An empty chat gets the T3
// headline with the composer in the middle, unless a bot owns the empty state.
const {chromium}=require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../desktop/plugin.js'),'utf8');
const css=source.match(/const css = `([\s\S]*?)\n`/)[1]+source.match(/const composerCss = `([\s\S]*?)\n`/)[1].replace(/\$\{[^}]+\}/g,'none');
const composer=(tour,reasoning=true)=>`<div data-slot="composer-fade"><div class="grid">
  <div class="[grid-area:menu]"><button><i class="codicon codicon-add"></i></button></div>
  <div class="[grid-area:input]"><div data-slot="composer-rich-input"></div></div>
  <div class="[grid-area:controls]"><div class="flex"><button ${tour} aria-label="Model" aria-haspopup="menu"><span>GPT-6-Sol</span></button>${reasoning?'<button data-testid="reasoning-pill" aria-haspopup="menu"><span>Low</span></button>':''}</div>
  <div class="flex items-center"><button aria-label="Voice dictation">m</button></div></div></div></div>`;
const hero='<h1 data-t3-empty-hero>What should we build?</h1>';
const surface=(id,target,inner)=>`<main data-chat-surface id="${id}" data-composer-target="${target}" style="position:relative;height:600px">${inner}
  <div data-slot="composer-dock" style="position:absolute;bottom:0;height:100px">${composer(target==='main'?'data-tour="model-pill"':'',id!=='chat')}</div></main>`;
(async()=>{const browser=await chromium.launch();try{
const page=await browser.newPage();
await page.setContent(`<html data-duckwork-theme="t3-code-theme"><head><style>${css}</style></head><body>
${surface('main','main',`<div>${hero}</div>`)}${surface('tile','tile:1',`<div>${hero}</div>`)}
${surface('bot','tile:2',`<div>${hero}<div data-slot="bot_chat_empty">Bot</div></div>`)}${surface('chat','tile:3','<div><p>A message</p></div>')}</body></html>`);
const r=await page.evaluate(()=>{const q=(id,s)=>document.querySelector(`#${id} ${s}`),cs=(id,s)=>getComputedStyle(q(id,s));
  const pill=id=>q(id,'[aria-label="Model"]');
  return {order:{primary:cs('main','[aria-label="Model"]').order,tile:cs('tile','[aria-label="Model"]').order,noReasoning:cs('chat','[aria-label="Model"]').order,reasoning:cs('tile','[data-testid="reasoning-pill"]').order,voice:cs('tile','[aria-label="Voice dictation"]').order},
    size:[getComputedStyle(pill('main')).fontSize,getComputedStyle(pill('tile')).fontSize,getComputedStyle(pill('tile')).height],
    hero:{main:cs('main','h1').display,tile:cs('tile','h1').display,bot:cs('bot','h1').display,size:cs('tile','h1').fontSize},
    dockTop:{main:cs('main','[data-slot="composer-dock"]').top,tile:cs('tile','[data-slot="composer-dock"]').top,bot:cs('bot','[data-slot="composer-dock"]').top,chat:cs('chat','[data-slot="composer-dock"]').top}};
});
assert.deepEqual(r.order,{primary:'1',tile:'1',noReasoning:'1',reasoning:'2',voice:'4'},'Model pill first, then effort, in the primary chat and in a tile; other controls keep their place');
assert.deepEqual(r.size,['14px','14px','28px'],'The tile pill gets the same T3 control size as the primary one');
assert.deepEqual(r.hero,{main:'block',tile:'block',bot:'none',size:'30px'},'Empty chats show the headline; a bot that owns the empty state keeps it alone');
assert.deepEqual(r.dockTop,{main:'300px',tile:'300px',bot:'500px',chat:'500px'},'Only a truly empty chat centers its composer');
console.log('PASS tiles and empty chats: pill found without data-tour, headline and centered composer, bot stands alone');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
