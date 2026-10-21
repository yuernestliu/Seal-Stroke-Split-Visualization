(() => {
  const {glyphs,byId} = window.GlyphLibrary;
  window.ComponentDeriver.annotate(glyphs);
  const $ = selector => document.querySelector(selector);
  const initial = new URLSearchParams(location.hash.slice(1)).get('glyph');
  const state = {selectedId:byId.has(initial) ? initial : glyphs.find(g => g.mark === '安')?.id || glyphs[0].id,split:false,query:'',scope:'500',catalogLimit:96};
  const current = () => byId.get(state.selectedId);
  function paintStage() {
    window.GlyphUI.renderImage(current(),state);
    $('#splitGlyph').setAttribute('aria-expanded',String(state.split));
    const kind = window.GlyphLibrary.splitKind(current());
    $('#splitStrokes').setAttribute('aria-label',kind === 'parts' ? '拆开的候选部件' : '拆开的独立笔段');
    $('#splitGlyph').disabled = !kind;
    $('#splitGlyph').innerHTML = state.split ? '合字 <span aria-hidden="true">↑</span>' : kind === 'parts' ? '拆部件 <span aria-hidden="true">↓</span>' : kind ? '拆笔 <span aria-hidden="true">↓</span>' : '拆分待完成';
    $('#splitStrokes').hidden = !state.split;
  }
  function paintCatalog() { window.GlyphUI.renderCatalog(window.GlyphLibrary.forScope(state.scope),state,selectGlyph); }
  function paintRelations() {
    window.RelationsPanel.render({container:$('#relationsPanel'),glyph:current(),glyphs:window.GlyphLibrary.forScope(state.scope),onSelect:selectGlyph});
  }
  function paintGlyph() {
    window.StoryPanel.renderRecord(current(),glyphs,selectGlyph);
    window.GlyphUI.renderSegments(current());
    paintStage(); paintRelations();
  }
  function selectGlyph(id,updateUrl = true) {
    if (!byId.has(id)) return;
    state.selectedId = id; state.split = false;
    if ($('#catalogDialog').open) $('#catalogDialog').close();
    if (updateUrl) { try {history.replaceState(null,'',`#glyph=${encodeURIComponent(id)}`);} catch { /* file:// 也可浏览。 */ } }
    paintGlyph();
    if (window.scrollY > $('#workspace').offsetTop + 100) $('#workspace').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',block:'start'});
  }
  $('#splitGlyph').addEventListener('click',() => {state.split = !state.split; paintStage();});
  $('#randomGlyph').addEventListener('click',() => {
    const poolGlyphs = window.GlyphLibrary.forScope(state.scope);
    const withStories = poolGlyphs.filter(g => g.id !== state.selectedId && g.original_meaning);
    const pool = withStories.length ? withStories : poolGlyphs.filter(g => g.id !== state.selectedId);
    if (pool.length) selectGlyph(pool[Math.floor(Math.random()*pool.length)].id);
  });
  $('#openCatalog').addEventListener('click',() => {paintCatalog(); $('#catalogDialog').showModal(); $('#glyphSearch').focus();});
  $('#closeCatalog').addEventListener('click',() => $('#catalogDialog').close());
  $('#catalogDialog').addEventListener('click',event => {
    if (event.target !== $('#catalogDialog')) return;
    const rect = event.target.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.target.close();
  });
  $('#glyphSearch').addEventListener('input',event => {state.query = event.target.value; state.catalogLimit = 96; paintCatalog();});
  document.querySelectorAll('[data-library-scope]').forEach(button => button.addEventListener('click',() => {
    state.scope = button.dataset.libraryScope; state.catalogLimit = 96;
    document.querySelectorAll('[data-library-scope]').forEach(b => b.setAttribute('aria-pressed',String(b === button)));
    paintCatalog(); paintRelations();
  }));
  $('#catalogMore').addEventListener('click',() => {state.catalogLimit += 96; paintCatalog();});
  window.addEventListener('hashchange',() => {
    const id = new URLSearchParams(location.hash.slice(1)).get('glyph');
    if (byId.has(id) && id !== state.selectedId) selectGlyph(id,false);
  });
  $('#glyphCount').textContent = String(glyphs.length);
  paintGlyph();
  if (document.fonts && window.SEAL_FONT) {
    document.fonts.load('200px "Chongxi Seal"','宇').then(faces => {
      if (!faces.length) return;
      window.SEAL_FONT.ready = true;
      paintStage();
      if ($('#catalogDialog').open) paintCatalog();
    }).catch(() => { /* 字体未加载时显示样本 SVG。 */ });
  }
})();
