// Fixture with Duckwork' real user-message structure (user-message.tsx @28aceb3451):
// the attachments div is a flow SIBLING of the sticky root. Checks the v2 polish
// aligns it under the right-aligned bubble, and that other themes stay native.
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const src = fs.readFileSync(require('node:path').join(__dirname,'..','desktop','plugin.js'), 'utf8');
const start = src.indexOf('const css = `') + 13;
const css = src.slice(start, src.indexOf('`', start));
const img = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"/>');
const html = `<html data-duckwork-theme="t3-code-theme"><head><style>*{box-sizing:border-box}body{margin:0}
.flex{display:flex}.flex-col{flex-direction:column}.flex-wrap{flex-wrap:wrap}.gap-1{gap:4px}.-mt-3{margin-top:-12px}.mb-2{margin-bottom:8px}
[data-slot=aui_thread-content]{max-width:var(--composer-width);margin:auto;padding:0 24px}
.bubble{padding:12px}img{max-height:192px;display:block}</style><style>${css}</style></head><body>
<div data-slot="aui_thread-content" class="flex flex-col">
 <div data-slot="aui_user-message-root" class="flex flex-col"><div data-slot="aui_user-bubble-actions"><button class="composer-human-message bubble">hello with image</button></div></div>
 <div class="flex flex-wrap gap-1 -mt-3 mb-2"><span data-slot="aui_directive-text"><span data-slot="aui_embedded-images" class="flex flex-wrap"><span data-slot="aui_directive-image"><img src="${img}"></span><span data-slot="aui_directive-image"><img src="${img}"></span></span></span></div>
 <div data-slot="aui_assistant-message-content">respuesta</div>
</div></body></html>`;
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
    await page.setContent(html);
    const box = s => page.locator(s).first().evaluate(e => { const r = e.getBoundingClientRect(); return { x: r.x, right: r.right, y: r.y, bottom: r.bottom } });
    const bubble = await box('.composer-human-message'), row = await box('[data-slot=aui_user-message-root] + div'), thread = await box('[data-slot=aui_thread-content]');
    const images = await page.locator('img').evaluateAll(es => es.map(e => e.getBoundingClientRect().toJSON()));
    assert(Math.abs(bubble.right - thread.right) < 1, 'bubble flush with column edge');
    assert(Math.abs(images.at(-1).right - bubble.right) < 1, 'last image flush right with bubble');
    assert(row.y >= bubble.bottom, 'attachments start below bubble, never under it');
    assert(images[0].x >= thread.x + (thread.right - thread.x) * 0.2 - 1, 'attachments within 80% lane');
    assert.equal(await page.locator('img').first().evaluate(e => getComputedStyle(e).borderRadius), '12px');
    console.log('PASS attachments aligned under bubble');
    await page.evaluate(() => document.documentElement.dataset.duckworkTheme = 'fordex');
    assert((await box('[data-slot=aui_user-message-root] + div')).x < 400, 'other themes keep native left-aligned attachments');
    console.log('PASS theme isolation');
  } finally { await browser.close() }
})().catch(e => { console.error(e); process.exit(1) });
