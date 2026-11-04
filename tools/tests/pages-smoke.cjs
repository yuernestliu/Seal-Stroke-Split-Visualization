const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const project=path.resolve(__dirname,'..');
const root=path.resolve(project,process.argv[2]||'_site-display');
assert(root.startsWith(project+path.sep),'artifact must be inside this project');
function file(relative){
  const parts=relative.replace(/^\.\//,'').split('/');
  assert(parts.every(p=>p&&p!=='.'&&p!=='..'&&!p.startsWith('_FORBIDDEN_')));
  let p=root;for(const part of parts){p=path.join(p,part);assert(!fs.lstatSync(p).isSymbolicLink());}return p;
}
const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
const dom=new JSDOM(fs.readFileSync(file('index.html'),'utf8'),{url:'https://example.org/Seal-Stroke-Split-Visualization/',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
const w=dom.window,d=w.document;w.matchMedia=()=>({matches:true});w.HTMLElement.prototype.scrollIntoView=()=>{};
w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
for(const s of d.querySelectorAll('script[src]'))w.eval(fs.readFileSync(file(s.getAttribute('src')),'utf8'));
assert.equal(d.querySelector('#glyphTitle').textContent,'安');assert(d.querySelector('#relationGraph svg'));
d.querySelector('#splitGlyph').click();assert.equal(d.querySelectorAll('.stroke-piece').length,5);
assert.equal(w.GlyphLibrary.forScope('500').length,500);assert.equal(w.GlyphLibrary.forScope('2000').length,2000);
assert.equal(w.GlyphLibrary.glyphs.length,14120);
for(const [id] of w.SEAL_LIBRARY.entries)assert(fs.statSync(file(w.SEAL_LIBRARY.imageBase+id+'.png')).isFile());
for(const glyph of w.GlyphLibrary.glyphs.filter(g=>g.source.experiment!=='raw')){
  w.StoryPanel.renderRecord(glyph,w.GlyphLibrary.glyphs,()=>{});
  w.GlyphUI.renderImage(glyph,{split:false});w.GlyphUI.renderSegments(glyph);
  if(w.GlyphLibrary.splitKind(glyph))w.GlyphUI.renderImage(glyph,{split:true});
  for(const asset of [...Object.values(glyph.assets),...glyph.segments.map(s=>s.image),...(glyph.templateParts||[]).map(p=>p.mask)])assert(fs.statSync(file(asset)).isFile());
  assert(!d.querySelector('#story').textContent.includes('undefined'));
}
assert.equal(w.GLYPH_DATA.glyphs[0].analysis,undefined);assert.equal(w.GLYPH_DATA.glyphs[0].canvas,undefined);
for(const name of ['资料','research','archive','node_modules','字库/来源','字库/字表','data/glyph-notes.json','data/cleaned-glyphs'])assert(!fs.existsSync(path.join(root,name)),name+' must remain in the repository');
function audit(folder){for(const entry of fs.readdirSync(folder,{withFileTypes:true})){
  if(entry.name.startsWith('_FORBIDDEN_'))continue;
  assert(!entry.isSymbolicLink());const p=path.join(folder,entry.name);
  if(entry.isDirectory())audit(p);else assert(!/\.(csv|json|txt)$/i.test(entry.name),'raw research data in artifact: '+entry.name);
}}
audit(root);assert.deepEqual(errors,[]);dom.window.close();
console.log('PASS: display-only export, default 安, 500/2000/all, original and template rendering, image dependencies, and no research/database files.');
