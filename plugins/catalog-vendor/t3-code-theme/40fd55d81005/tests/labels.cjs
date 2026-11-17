// T3 display labels: the composer pill must read like T3 Code.
const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../desktop/plugin.js'),'utf8');
const sandbox={};vm.createContext(sandbox);
vm.runInContext(source.replace(/^import .*\n/gm,'').replace('export default','globalThis.plugin =')+'\nglobalThis.api={t3ModelLabel,nativeModelParts,providerSvg}',sandbox);
const {t3ModelLabel,nativeModelParts,providerSvg}=sandbox.api;
assert.equal(t3ModelLabel('claude-opus-5-5[1m]'),'Claude Opus 5.5');
assert.equal(t3ModelLabel('claude-haiku-4-5-20251001'),'Claude Haiku 4.5');
assert.equal(t3ModelLabel('gpt-6-astra'),'GPT-6-Astra');
assert.equal(t3ModelLabel('gpt-6-astra-fast'),'GPT-6-Astra Fast','Fast variant stays visible on the pill');
assert.equal(t3ModelLabel('gemini-3.1-pro-preview'),'Gemini 3.1 Pro');
// Row names must equal Duckwork' modelDisplayParts, or rows stay unidentified.
const parts=m=>{const p=nativeModelParts(m);return p.name+(p.tag?' | '+p.tag:'')};
assert.equal(parts('claude-sonnet-5[1m]'),'Sonnet 5 | 1M');
assert.equal(parts('gemini-3.1-pro-preview'),'Gemini 3.1 Pro | Preview','Gemini names are title-cased now');
assert.equal(parts('deepseek-v4.1-flash'),'DeepSeek V4.1 | Flash','Flash is a variant tag with vendor casing');
assert.equal(parts('glm-5.2'),'GLM 5.2');assert.equal(parts('qwen/qwen3.8-27b'),'Qwen3.8 27B','Parameter counts read 27B');
assert.equal(parts('model-flash-Q4_K_XL'),parts('model-Q4_K_XL-flash'),'Quant and variant split in either order');
assert.equal(t3ModelLabel('deepseek-v4.1-flash'),'DeepSeek V4.1 Flash','Flash stays in the T3 label');
// Provider marks: Grok and Copilot from T3 Code, Groq and Fordex from LobeHub; unknown slugs keep a monogram.
const mark=slug=>providerSvg(slug,'#fff').svg;
assert(mark('xai-oauth').includes('M9.26905 15.284'),'Grok mark for xAI');assert(mark('copilot').includes('viewBox="0 0 256 208"'),'Copilot mark');
assert(mark('groq').includes('M12.036 2c'),'Groq mark');assert(mark('fordex').includes('M5.938 12.835'),'Fordex mark');
assert(mark('groq').includes('fill="#fff"'),'Single-color marks take the requested fill');
assert.equal(providerSvg('deepseek').colored,true,'Brand-colored marks paint as images');
assert(mark('groqish').includes('<text'),'Patterns match whole slugs only');
console.log('PASS T3 model labels and provider marks');
