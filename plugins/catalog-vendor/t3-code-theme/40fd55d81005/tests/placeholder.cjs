// Composer placeholder: Duckwork rolls a random starter or follow-up line, so
// T3's text must replace all of them, not one hardcoded string. Connection
// states and the message-edit composer must keep Duckwork' own text.
const {chromium}=require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../desktop/plugin.js'),'utf8');
const css=source.match(/const composerCss = `([\s\S]*?)\n`/)[1];
const T3='"Ask anything, @tag files/folders, or / for commands"';
(async()=>{const browser=await chromium.launch();try{
const page=await browser.newPage();
const shown=async(placeholder,{edit=false,theme='t3-code-theme'}={})=>page.evaluate(({placeholder,edit,theme,css})=>{
  document.documentElement.dataset.duckworkTheme=theme;
  document.head.innerHTML='<style>'+css.replace(/\$\{[^}]+\}/g,'none')+'</style>';
  document.body.innerHTML=edit
    ?'<div data-slot="aui_edit-composer-root"><div data-slot="composer-rich-input" data-placeholder=""></div></div>'
    :'<div data-slot="composer-fade"><div data-slot="composer-rich-input" data-placeholder=""></div></div>';
  const input=document.querySelector('[data-slot="composer-rich-input"]');input.dataset.placeholder=placeholder;
  return getComputedStyle(input,'::before').content;
},{placeholder,edit,theme,css});
for(const line of ['What are we building?','What should we tackle?','Ask anything','Add more context',"What's next?"])
  assert.equal(await shown(line),T3,`Random Duckwork line "${line}" must read as T3`);
assert.equal(await shown('Starting Duckwork...'),'none','Cold start state must stay visible');
assert.equal(await shown('Reconnecting to Duckwork…'),'none','Reconnect state must stay visible');
assert.equal(await shown('Edit message',{edit:true}),'none','Message-edit composer keeps its own placeholder');
assert.equal(await shown('Ask anything',{theme:'fordex'}),'none','Other themes are untouched');
console.log('PASS T3 placeholder over every random Duckwork line, states and edit composer kept');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
