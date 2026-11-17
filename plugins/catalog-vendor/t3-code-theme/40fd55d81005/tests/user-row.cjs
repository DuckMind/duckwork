// Restore/stop move from inside the user bubble to a T3-style row under it.
// Fixture mirrors Duckwork' user-message.tsx: the action box is an absolute sibling of the bubble.
const {chromium}=require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch();try{const page=await browser.newPage();
await page.setContent(`<html data-duckwork-theme="t3-code-theme"><body><style>.rel{position:relative}.abs{position:absolute;right:8px;bottom:8px;display:flex;align-items:center}.b{display:flex;padding:8px 36px 8px 12px;border:1px solid}.s6{width:24px;height:24px;display:grid}</style>
<div data-slot="aui_user-message-root"><div data-slot="aui_user-bubble-actions" class="rel"><div><div class="rel" data-context-menu-skip="">
<button class="composer-human-message b">a short prompt</button><div class="abs"><button aria-label="Restore checkpoint" class="s6"><i class="codicon" style="font-size:0.875rem">x</i></button></div>
</div></div></div></div><article data-slot="aui_response-group">reply</article></body></html>`);
await page.addStyleTag({content:fs.readFileSync(path.join(__dirname,'../desktop/plugin.js'),'utf8').match(/const css = `([\s\S]*?)`/)[1]});
const m=await page.evaluate(()=>{const r=q=>document.querySelector(q).getBoundingClientRect();const b=r('.composer-human-message'),a=r('[aria-label="Restore checkpoint"]'),n=r('[data-slot=aui_response-group]');
 return{pad:getComputedStyle(document.querySelector('.composer-human-message')).padding,gap:a.top-b.bottom,right:b.right-a.right,height:a.height,next:n.top-a.bottom,icon:getComputedStyle(document.querySelector('.codicon')).fontSize}});
assert.equal(m.pad,'12px','Bubble keeps even padding, no reserve for the button');
assert.equal(m.gap,4,'Button sits 4px under the bubble, as in T3');
assert.equal(m.right,4,'Right-aligned with T3 pe-1');
assert.equal(m.height,24);assert.ok(m.next>=0,'Row takes layout space, so it never covers the reply');
assert.equal(m.icon,'12px');
console.log('PASS user row: restore/stop under the bubble',m);
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
