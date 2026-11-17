// Fixtures using the real slots from components/ui/dropdown-menu.tsx.
const {chromium}=require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch();try{const page=await browser.newPage();
await page.setContent(`<html data-duckwork-theme="t3-code-theme"><body><div data-slot="dropdown-menu-content" style="width:256px"><div data-slot="dropdown-menu-search"><input></div><div data-slot="dropdown-menu-item">Native test model</div></div><div data-slot="dropdown-menu-sub-content"><div data-slot="dropdown-menu-radio-item" data-state="checked">Native test option</div></div><div data-slot="composer-root"><div data-slot="composer-surface"><div aria-hidden="true" class="backdrop-blur-md"></div></div></div><button class="composer-human-message">Test</button></body></html>`);
await page.addStyleTag({content:fs.readFileSync(require('node:path').join(__dirname,'../desktop/plugin.js'),'utf8').match(/const css = `([\s\S]*?)`/)[1]});
const m=await page.evaluate(()=>{const s=q=>{const c=getComputedStyle(document.querySelector(q));return{radius:c.borderRadius,padding:c.padding,font:c.fontSize,line:c.lineHeight,shadow:c.boxShadow,blur:c.backdropFilter,background:c.backgroundColor,maxWidth:c.maxWidth}};return{menu:s('[data-slot=dropdown-menu-content]'),item:s('[data-slot=dropdown-menu-item]'),radio:s('[data-slot=dropdown-menu-radio-item]'),backing:s('[aria-hidden]'),bubble:s('.composer-human-message')}});
assert.equal(m.menu.radius,'10px');assert.equal(m.menu.blur,'blur(16px) saturate(1.08)');assert(m.menu.shadow.includes('18px 44px -18px'));
assert.equal(m.item.radius,'8px');assert.equal(m.item.font,'12px');assert.equal(m.item.line,'16.5px');assert.equal(m.radio.radius,'6px');assert.equal(m.radio.font,'14px');
assert.equal(m.backing.blur,'blur(16px) saturate(1.08)');
assert.equal(m.bubble.padding,'12px','No inner reserve: restore/stop live in the row under the bubble');
await page.evaluate(()=>document.documentElement.dataset.duckworkTheme='fordex');assert.equal(await page.$eval('[data-slot=dropdown-menu-content]',e=>getComputedStyle(e).borderRadius),'0px');
await page.evaluate(()=>document.documentElement.dataset.duckworkTheme='t3-code-theme');
await page.addStyleTag({content:'[data-slot="composer-surface"]{border-color:var(--ui-stroke-secondary)!important}'});
assert.equal(await page.$eval('[data-slot=composer-surface]',e=>getComputedStyle(e).borderTopColor),'rgba(255, 255, 255, 0.05)','T3 outline wins over the native !important');
console.log('PASS portaled menus, glass, native options and action reserve',m);
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
