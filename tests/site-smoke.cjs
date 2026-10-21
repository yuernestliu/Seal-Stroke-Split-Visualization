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
assert.equal(d.querySelector('#glyphTitle').textContent,'安');
assert.equal(d.querySelectorAll('.writing-panel button').length,1);
assert(d.querySelector('#splitStrokes').hidden);
assert(d.querySelector('#relationGraph svg'),'relationships must be visible on arrival');
for(const id of ['replayPlay','replaySpeed','guessToggle','traceCanvas','toggleGraph','relationFilter','bookmarkGlyph','catalogFilter']) assert.equal(d.getElementById(id),null);
click('#splitGlyph');assert(!d.querySelector('#splitStrokes').hidden);assert.equal(d.querySelector('#splitGlyph').getAttribute('aria-expanded'),'true');
assert.equal(d.querySelectorAll('.stroke-piece').length,5);assert.equal(d.querySelectorAll('#glyphVector path[stroke^="#"]').length,5);
click('#splitGlyph');assert(d.querySelector('#splitStrokes').hidden);
click('#openCatalog');assert.equal(d.querySelector('[data-library-scope="500"]').getAttribute('aria-pressed'),'true');assert.equal(d.querySelectorAll('.glyph-item').length,96);
click('#catalogMore');assert.equal(d.querySelectorAll('.glyph-item').length,192);
click('[data-library-scope="all"]');search('不存在的字');assert.equal(d.querySelectorAll('.glyph-item').length,0);search('宇');assert.equal(d.querySelectorAll('.glyph-item').length,1);click('.glyph-item');
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
const covered=w.GLYPH_DATA.glyphs.find(g=>w.SEAL_FONT.glyphIds.includes(g.id) && !w.CLEANED_GLYPHS[g.id]);
w.GlyphUI.renderImage(covered,{split:false});assert(!d.querySelector('#fontGlyph').hidden);
w.GlyphUI.renderImage(covered,{split:true});assert(d.querySelector('#fontGlyph').hidden);assert(d.querySelector('#glyphVector svg'));
const missing=w.GLYPH_DATA.glyphs.find(g=>!w.SEAL_FONT.glyphIds.includes(g.id));
w.GlyphUI.renderImage(missing,{split:false});assert(d.querySelector('#fontGlyph').hidden);assert(d.querySelector('#glyphVector svg'));
// Cleaned examples take priority even after the official font finishes loading.
assert.equal(Object.keys(w.CLEANED_GLYPHS).length,4);
const geometry=svg=>[...svg.querySelectorAll('path')].map(p=>['data-stroke-id','d','stroke-width','stroke-linecap','stroke-linejoin'].map(a=>p.getAttribute(a)));
for(const mark of ['安','宇','包','光']) {
  const glyph=w.GLYPH_DATA.glyphs.find(g=>g.mark===mark),record=w.CLEANED_GLYPHS[glyph.id];
  assert(record);assert.equal(record.strokes.length,glyph.segments.length);
  w.GlyphUI.renderImage(glyph,{split:false});assert(d.querySelector('#fontGlyph').hidden);
  const combined=geometry(d.querySelector('#glyphVector svg'));
  w.GlyphUI.renderImage(glyph,{split:true});assert.deepEqual(geometry(d.querySelector('#glyphVector svg')),combined);
  w.GlyphUI.renderSegments(glyph);
  [...d.querySelectorAll('.stroke-piece svg')].forEach((svg,i)=>assert.deepEqual(geometry(svg),[combined[i]]));
  w.GlyphUI.renderCatalog(w.GLYPH_DATA.glyphs,{query:mark,selectedId:glyph.id},()=>{});
  assert(d.querySelector(`.glyph-item[data-glyph-id="${glyph.id}"] .cleaned-glyph`));
}
const license=fs.readFileSync(safeFile('license.html'),'utf8');assert(license.includes('Academia Sinica'));assert(license.includes('CC-BY-ND-3.0-TW-or-later'));
assert(d.querySelector('.site-footer a[href="./license.html"]'));
assert(d.querySelector('.site-footer a[href="./plan.html"]'));
const all=JSON.parse(fs.readFileSync(safeFile('字库/字表/全部字形.json'),'utf8'));
assert.equal(w.GlyphLibrary.glyphs.length,all.glyphs.length);assert.equal(w.GLYPH_DATA.glyphs.length,124);
for(const glyph of all.glyphs) assert(fs.statSync(safeFile(glyph.image)).isFile());
const sets=[500,2000].map(size=>JSON.parse(fs.readFileSync(safeFile(`字库/字表/常用${size}字.json`),'utf8')));
assert.equal(sets[0].targets.length,500);assert.equal(sets[1].targets.length,2000);
assert.deepEqual(sets[0].targets,sets[1].targets.slice(0,500));
for(const set of sets) assert.equal(set.stats.matchedTargets+set.stats.missingTargets,set.stats.targetCharacters);
assert.equal(sets[0].stats.availableGlyphs,500);assert.equal(sets[1].stats.availableGlyphs,2000);
assert(JSON.parse(fs.readFileSync(safeFile('字库/字表/待补字形.json'),'utf8')).length>0,'missing source glyphs must remain explicit');
for(const prior of Object.values(w.COMPONENT_PRIORS)) {assert.equal(prior.confirmed,false);assert.equal(prior.geometryStatus,'not_pixel_alignment');}
const template=w.GlyphLibrary.glyphs.find(g=>g.templateParts?.length>1);
click('#openCatalog');search(template.sourceId);[...d.querySelectorAll('.glyph-item')].find(e=>e.dataset.glyphId===template.id).click();
assert(d.querySelector('#splitGlyph').textContent.includes('拆部件'));
const focus=d.querySelector('#glyphVector .template-character');focus.dispatchEvent(new w.Event('pointerenter'));assert(d.body.classList.contains('template-focus-active'));focus.dispatchEvent(new w.Event('pointerleave'));assert(!d.body.classList.contains('template-focus-active'));
click('#splitGlyph');assert(d.querySelector('#glyphVector .is-exploded'));assert.equal(d.querySelectorAll('.stroke-piece').length,template.templateParts.length);
for(const glyph of w.GlyphLibrary.glyphs.filter(g=>g.templateParts)) for(const part of glyph.templateParts) assert(fs.statSync(safeFile(part.mask)).isFile());
const raw=w.GlyphLibrary.glyphs.find(g=>g.source.experiment==='raw' && !g.templateParts);
click('#openCatalog');search(raw.sourceId);[...d.querySelectorAll('.glyph-item')].find(e=>e.dataset.glyphId===raw.id).click();
assert(d.querySelector('#splitGlyph').disabled);assert(!d.querySelector('#glyphImage').hidden);
assert(!d.querySelector('#story').textContent.includes('undefined'));
const plan=new JSDOM(fs.readFileSync(safeFile('plan.html'),'utf8'),{runScripts:'outside-only',virtualConsole:vc});
for(const script of plan.window.document.querySelectorAll('script')) plan.window.eval(script.src ? fs.readFileSync(safeFile(script.getAttribute('src')),'utf8') : script.textContent);
const planStats=w.GlyphLibrary.stats.inventories['500'];
assert.equal(plan.window.document.querySelector('#pilotCount').textContent,'500');
assert.equal(plan.window.document.querySelector('#outlineCount').textContent,String(planStats.outlineGlyphs));
assert.equal(plan.window.document.querySelector('#cleanCount').textContent,String(planStats.cleanedGlyphs),'student progress must use the pilot inventory, not global cleaned examples');
plan.window.close();
assert.deepEqual(errors,[]);dom.window.close();
console.log(`PASS: default 安, four shared-geometry glyphs, 500/2000/all inventories, paginated catalog, raw/template/stroke modes, candidate priors, graph/keyboard/font/license, ${all.glyphs.length} raw paths and ${assets} original asset references.`);
