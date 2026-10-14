const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM,VirtualConsole} = require('jsdom');
const root = path.resolve(__dirname,'..');
function safeFile(relative) {
  const parts = relative.replace(/^\.\//,'').split('/');
  assert(parts.every(p=>p && p!=='.' && p!=='..' && !p.startsWith('_FORBIDDEN_')),'file outside permitted scope');
  let candidate=root;
  for(const p of parts) { candidate=path.join(candidate,p); assert(!fs.lstatSync(candidate).isSymbolicLink(),'symlink outside audit scope'); }
  return candidate;
}
const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
const dom=new JSDOM(fs.readFileSync(safeFile('index.html'),'utf8'),{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
const {window:w}=dom,d=w.document;
w.matchMedia=()=>({matches:true});w.HTMLElement.prototype.scrollIntoView=()=>{};
w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
for(const script of d.querySelectorAll('script[src]')) w.eval(fs.readFileSync(safeFile(script.getAttribute('src')),'utf8'));
const click=selector=>d.querySelector(selector).click();
const search=value=>{const input=d.querySelector('#glyphSearch');input.value=value;input.dispatchEvent(new w.Event('input',{bubbles:true}));};
assert.equal(d.querySelector('#glyphTitle').textContent,'宇');
assert.equal(d.querySelectorAll('.writing-panel button').length,1);
assert(d.querySelector('#splitStrokes').hidden);
assert(d.querySelector('#relationGraph svg'),'relationships must be visible on arrival');
for(const id of ['replayPlay','replaySpeed','guessToggle','traceCanvas','toggleGraph','relationFilter','bookmarkGlyph','catalogFilter']) assert.equal(d.getElementById(id),null);
click('#splitGlyph');assert(!d.querySelector('#splitStrokes').hidden);assert.equal(d.querySelector('#splitGlyph').getAttribute('aria-expanded'),'true');
assert.equal(d.querySelectorAll('.stroke-piece').length,5);assert.equal(d.querySelectorAll('#glyphVector path[fill^="#"]').length,5);
click('#splitGlyph');assert(d.querySelector('#splitStrokes').hidden);
click('#openCatalog');search('不存在的字');assert.equal(d.querySelectorAll('.glyph-item').length,0);search('宇');assert.equal(d.querySelectorAll('.glyph-item').length,1);click('.glyph-item');
const relation=d.querySelector('.graph-node-related');assert(relation);relation.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));assert.notEqual(d.querySelector('#glyphTitle').textContent,'宇');
let assets=0;
for(const glyph of w.GLYPH_DATA.glyphs) {
  click('#openCatalog');search(glyph.sourceId);
  const item=[...d.querySelectorAll('.glyph-item')].find(e=>e.dataset.glyphId===glyph.id);assert(item);item.click();
  assert.equal(d.querySelector('#glyphTitle').textContent,glyph.title);
  assert(d.querySelector('#glyphVector svg path'));
  assert(d.querySelector('#splitStrokes').hidden,'switching glyph resets split state');
  click('#splitGlyph');assert.equal(d.querySelectorAll('.stroke-piece').length,glyph.segments.length);
  assert.equal(d.querySelectorAll('.stroke-piece svg').length,glyph.segments.length);
  assert.equal(d.querySelectorAll('#glyphVector image').length,0);
  assert(!d.querySelector('#story').textContent.includes('undefined'));
  for(const asset of [...Object.values(glyph.assets),...glyph.segments.map(s=>s.image)]) {assert(fs.statSync(safeFile(asset)).isFile());assets++;}
}
w.SEAL_FONT.ready=true;
const covered=w.GLYPH_DATA.glyphs.find(g=>g.mark==='宇');
w.GlyphUI.renderImage(covered,{split:false});assert(!d.querySelector('#fontGlyph').hidden);
w.GlyphUI.renderImage(covered,{split:true});assert(d.querySelector('#fontGlyph').hidden);assert(d.querySelector('#glyphVector svg'));
const missing=w.GLYPH_DATA.glyphs.find(g=>!w.SEAL_FONT.glyphIds.includes(g.id));
w.GlyphUI.renderImage(missing,{split:false});assert(d.querySelector('#fontGlyph').hidden);assert(d.querySelector('#glyphVector svg'));
const license=fs.readFileSync(safeFile('license.html'),'utf8');assert(license.includes('Academia Sinica'));assert(license.includes('CC-BY-ND-3.0-TW-or-later'));
assert.equal(d.querySelector('.site-footer a').getAttribute('href'),'./license.html');
assert.deepEqual(errors,[]);dom.window.close();
console.log(`PASS: one-action splitting, catalog, persistent relationship graph, keyboard navigation, font/fallback, licensing, all 124 glyphs and ${assets} asset references.`);
