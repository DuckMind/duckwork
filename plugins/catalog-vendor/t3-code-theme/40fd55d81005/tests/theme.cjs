const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const pluginPath = require('node:path').join(__dirname,'..','desktop','plugin.js');
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:900}});
    await page.route('http://t3.test/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/plugin.js') return route.fulfill({contentType:'text/javascript',body:fs.existsSync(pluginPath) ? fs.readFileSync(pluginPath,'utf8') : 'export default {register(){}}'});
      if (url.pathname === '/react.js') return route.fulfill({contentType:'text/javascript',body:'export const useEffect=fn=>{fn()};'});
      if (url.pathname === '/jsx.js') return route.fulfill({contentType:'text/javascript',body:'export const jsx=()=>null;'});
      if (url.pathname === '/sdk.js') return route.fulfill({contentType:'text/javascript',body:`export const THEMES_AREA='themes'; export const CHAT_EMPTY_AREA='chat.empty'; export function requestTheme(name){document.documentElement.dataset.duckworkTheme=name;return true} export const PALETTE_AREA='palette';`});
      return route.fulfill({contentType:'text/html',body:`<!doctype html><html data-duckwork-theme="fordex"><head><script type="importmap">{"imports":{"@duckwork/plugin-sdk":"/sdk.js","react":"/react.js","react/jsx-runtime":"/jsx.js"}}</script><style>
      *{box-sizing:border-box}body{margin:0}:root{--composer-width:100%} [data-chat-surface]{position:relative;width:100%;height:900px} [data-slot="aui_thread-content"]{width:100%;max-width:var(--composer-width);margin:auto;padding:0 24px} [data-slot="composer-dock"]{position:absolute;left:50%;transform:translateX(-50%);width:calc(min(var(--composer-width),calc(100% - 2rem)) + 10px);padding:0 5px;bottom:20px} [data-slot="composer-surface"]{width:100%;height:120px} [data-slot="aui_user-bubble-actions"]{position:relative;width:100%;max-width:100%}.composer-human-message{width:100%;height:70px} [data-slot="aui_user-message-root"]{display:flex;flex-direction:column;align-items:stretch} </style></head><body><main data-chat-surface><section data-slot="aui_thread-content"><div data-slot="aui_user-message-root"><div data-slot="aui_user-bubble-actions"><button class="composer-human-message">Test prompt</button></div></div><article data-slot="aui_assistant-message-content">Test response</article></section><div data-slot="composer-dock"><div data-slot="composer-root"><div data-slot="composer-surface"></div></div></div></main><script type="module">import plugin from '/plugin.js';const data=new Map();let theme;const before=document.querySelectorAll('style').length;plugin.register({register(c){if(c.area==='themes')theme=c.data;return()=>{}},onDispose(){},storage:{get:(k,d)=>data.has(k)?data.get(k):d,set:(k,v)=>data.set(k,v)}});window.pluginStyles=document.querySelectorAll('style').length-before;/* Duckwork injects the active theme's customCSS itself. */const style=document.createElement('style');style.id='duckwork-desktop-custom-css';style.textContent=theme.customCSS;document.head.append(style);window.ready=true;</script></body></html>`});
    });
    await page.goto('http://t3.test/'); await page.waitForFunction(()=>window.ready);
    const measure = () => page.evaluate(() => { const box=s=>{const r=document.querySelector(s).getBoundingClientRect();return {x:r.x,width:r.width}};return {thread:box('[data-slot="aui_thread-content"]'),composer:box('[data-slot="composer-surface"]'),bubble:box('[data-slot="aui_user-bubble-actions"]'),viewport:innerWidth}; });
    let m=await measure(); assert(m.thread.width<=860 && m.thread.width>=740,'Wide chat must be constrained to a reading column, not full-width');
    assert(Math.abs(m.thread.x-(m.viewport-m.thread.width)/2)<1,'Chat must be centered');
    assert(Math.abs(m.composer.x-(m.viewport-m.composer.width)/2)<1,'Composer must be centered');
    assert.equal(m.composer.width,768,'T3 48rem column');
    const tokens = await page.evaluate(()=>({bubble:getComputedStyle(document.querySelector('[data-slot="aui_user-bubble-actions"]')).maxWidth,radius:getComputedStyle(document.querySelector('[data-slot="composer-surface"]')).borderRadius}));
    assert.equal(tokens.bubble,'80%');assert.equal(tokens.radius,'22px');
    assert(m.bubble.width < m.thread.width-48,'User bubble must be narrower than the chat');
    console.log('PASS wide centered chat/composer and narrower bubble',m);
    for(const width of [900,390]){await page.setViewportSize({width,height:900});m=await measure();assert(m.thread.width<=width && m.composer.width<=width,'Must fit smaller windows');assert(m.composer.x>=0,'Composer must stay onscreen');console.log('PASS responsive',width,m);}
    await page.setViewportSize({width:1440,height:900});
    await page.evaluate(()=>document.documentElement.dataset.duckworkTheme='fordex');
    m=await measure();assert.equal(m.thread.width,1440,'Selecting another theme restores default layout');console.log('PASS theme isolation');
    assert.equal(await page.evaluate(()=>window.pluginStyles),0,'The plugin adds no stylesheet of its own: Duckwork owns the theme CSS');console.log('PASS no stylesheet injected by the plugin');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
