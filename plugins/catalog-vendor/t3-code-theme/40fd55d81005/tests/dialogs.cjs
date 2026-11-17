// Confirm dialogs follow T3's AlertDialog. Fixture mirrors Duckwork' ConfirmDialog
// (components/ui/confirm-dialog.tsx + dialog.tsx): overlay and content are portal
// siblings, and header + footer sit in the content's body box.
const {chromium}=require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
const dialog=(footer)=>`<div data-slot="dialog-overlay"></div><style>.shell{position:fixed;left:40px;top:40px;width:448px;display:flex;flex-direction:column}.body{display:grid;gap:12px;padding:16px;overflow-y:auto;border-radius:inherit}.col{display:flex;flex-direction:column;gap:4px}.row{display:flex;justify-content:flex-end}</style><div role="dialog" data-slot="dialog-content" class="shell max-w-md">
 <div class="body"><div data-slot="dialog-header" class="col"><h2 data-slot="dialog-title">Delete this chat?</h2><p data-slot="dialog-description">This cannot be undone.</p></div>
 ${footer}</div><button data-slot="dialog-close-button">x</button></div>`;
(async()=>{const browser=await chromium.launch();try{const page=await browser.newPage();
await page.setContent(`<html data-duckwork-theme="t3-code-theme"><body>${dialog('<div data-slot="dialog-footer" class="row"><button data-variant="ghost">Cancel</button><button data-variant="destructive">Delete</button></div>')}</body></html>`);
await page.addStyleTag({content:fs.readFileSync(require('node:path').join(__dirname,'../desktop/plugin.js'),'utf8').match(/const css = `([\s\S]*?)`/)[1]});
const m=await page.evaluate(()=>{const c=q=>getComputedStyle(document.querySelector(q));return{
 popup:{radius:c('[data-slot=dialog-content]').borderRadius,blur:c('[data-slot=dialog-content]').backdropFilter,border:c('[data-slot=dialog-content]').borderTopColor},
 overlay:c('[data-slot=dialog-overlay]').backdropFilter,close:c('[data-slot=dialog-close-button]').display,
 body:c('[data-slot=dialog-content] > div').padding,title:[c('[data-slot=dialog-title]').fontSize,c('[data-slot=dialog-title]').fontWeight],
 description:c('[data-slot=dialog-description]').fontSize,
 footer:{padding:c('[data-slot=dialog-footer]').padding,border:c('[data-slot=dialog-footer]').borderTopWidth,background:c('[data-slot=dialog-footer]').backgroundColor,
  edges:(()=>{const f=document.querySelector('[data-slot=dialog-footer]').getBoundingClientRect(),d=document.querySelector('[data-slot=dialog-content]').getBoundingClientRect();return[f.left-d.left,d.right-f.right,d.bottom-f.bottom]})()},
 cancel:[c('[data-variant=ghost]').height,c('[data-variant=ghost]').borderRadius,c('[data-variant=ghost]').fontSize,c('[data-variant=ghost]').borderTopColor],
 confirm:[c('[data-variant=destructive]').backgroundColor,c('[data-variant=destructive]').color]}});
assert.equal(m.popup.radius,'18px');assert.equal(m.popup.blur,'blur(16px) saturate(1.08)');assert.equal(m.popup.border,'rgba(255, 255, 255, 0.08)');
assert.equal(m.overlay,'blur(4px)');assert.equal(m.close,'none','T3 confirm has no close X; Escape still dismisses');
assert.equal(m.body,'24px 24px 0px');assert.deepEqual(m.title,['20px','600']);assert.equal(m.description,'14px');
assert.equal(m.footer.padding,'16px 24px');assert.equal(m.footer.border,'1px');assert.equal(m.footer.background,'rgba(17, 17, 17, 0.72)');
assert.deepEqual(m.footer.edges.map(Math.round),[1,1,1],'Footer bar spans the popup edge to edge inside its 1px border');
assert.deepEqual(m.cancel,['32px','8px','14px','rgb(30, 30, 30)'],'Cancel is T3 outline');
assert.deepEqual(m.confirm,['rgb(251, 65, 74)','rgb(255, 255, 255)']);
// A dialog without a footer (settings, media) keeps Duckwork' own layout.
await page.evaluate(()=>{document.querySelector('[data-slot=dialog-footer]').remove()});
assert.equal(await page.$eval('[data-slot=dialog-content]',e=>getComputedStyle(e).borderRadius),'0px');
assert.notEqual(await page.$eval('[data-slot=dialog-close-button]',e=>getComputedStyle(e).display),'none');
await page.setContent(`<html data-duckwork-theme="fordex"><body>${dialog('<div data-slot="dialog-footer"><button data-variant="default">Confirm</button></div>')}</body></html>`);
await page.addStyleTag({content:fs.readFileSync(require('node:path').join(__dirname,'../desktop/plugin.js'),'utf8').match(/const css = `([\s\S]*?)`/)[1]});
assert.equal(await page.$eval('[data-slot=dialog-content]',e=>getComputedStyle(e).borderRadius),'0px','Other themes are untouched');
console.log('PASS T3 confirm dialog: glass popup, 20px title, muted footer bar, outline/primary buttons',m);
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
