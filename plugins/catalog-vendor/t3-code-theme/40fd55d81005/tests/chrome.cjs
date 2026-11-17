// Chat-area titlebar: Duckwork paints every tab strip with the sidebar black,
// which would leave a black band inside the chat pane's canvas titlebar.
const {chromium}=require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../desktop/plugin.js'),'utf8');
const layoutCss=source.match(/const css = `([\s\S]*?)\n`/)[1];
(async()=>{const browser=await chromium.launch();try{
const page=await browser.newPage();
await page.setContent(`<html data-duckwork-theme="t3-code-theme"><head><style>[data-zone-tabstrip]{background:var(--ui-sidebar-surface-background)}${layoutCss}</style></head><body>
<div data-tree-group="grp-main" data-window-top="true"><div data-panel-header><div data-zone-tabstrip="grp-main"><div role="tablist"></div></div></div><div data-chat-surface></div></div>
<div data-tree-group="grp-side"><div data-tour="sessions-sidebar"></div><div data-panel-header><div data-zone-tabstrip="grp-side"><div role="tablist"></div></div></div></div></body></html>`);
const strips=await page.evaluate(()=>['grp-main','grp-side'].map(g=>getComputedStyle(document.querySelector(`[data-zone-tabstrip="${g}"]`)).backgroundColor));
assert.deepEqual(strips,['rgb(10, 10, 10)','rgb(0, 0, 0)'],'Chat tab strip matches the canvas titlebar; the sidebar strip stays black');
console.log('PASS chat tab strip matches the canvas titlebar');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
