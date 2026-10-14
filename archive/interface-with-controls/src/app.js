(() => {
  const {glyphs} = window.GLYPH_DATA;
  window.ComponentDeriver.annotate(glyphs);
  const byId = new Map(glyphs.map(g => [g.id, g]));
  const $ = id => document.querySelector(id);
  const savedKey = 'seal-play:saved';
  let saved = [];
  try { const value = JSON.parse(localStorage.getItem(savedKey) || '[]'); if (Array.isArray(value)) saved = value.filter(id => byId.has(id)); } catch { /* 浏览器禁用存储时仍可使用本次字袋。 */ }
  const initial = new URLSearchParams(location.hash.slice(1)).get('glyph');
  const state = {selectedId:byId.has(initial) ? initial : glyphs.find(g => g.mark === '宇')?.id || glyphs[0].id,
    selectedSegment:null, selectedView:'original', query:'', catalogFilter:'all', relationFilter:'all', replayStep:0,
    replayDelay:800, isPlaying:false, replayTimer:null, replayFinished:false, saved:new Set(saved), guessing:false, graphOpen:false};
  let toastTimer;
  const current = () => byId.get(state.selectedId);
  function toast(message) { clearTimeout(toastTimer); $('#toast').textContent = message; $('#toast').hidden = false; toastTimer = setTimeout(() => {$('#toast').hidden = true;}, 2500); }
  function stopReplay() { state.isPlaying = false; clearTimeout(state.replayTimer); state.replayTimer = null; }
  function resetReplay() { stopReplay(); state.replayStep = 0; state.replayFinished = false; state.selectedSegment = null; paintStage(); }
  function paintStage() {
    const glyph = current(); window.GlyphUI.renderImage(glyph,state); window.GlyphUI.renderPlaybackControls(glyph,state);
    window.GlyphTracing.setMode(glyph.id,state.selectedView === 'trace');
    if (state.guessing) {
      $('#glyphImage').alt = '待猜的小篆字形'; $('#replayCanvas svg')?.setAttribute('aria-label','待猜字形的笔段演示');
      $('#fontGlyph [role=img]')?.setAttribute('aria-label','待猜的小篆字形');
    }
  }
  function paintGuess() {
    document.body.classList.toggle('is-guessing',state.guessing);
    $('#story').inert = state.guessing; $('#story').setAttribute('aria-hidden',String(state.guessing));
    $('#relations').inert = state.guessing; $('#relations').setAttribute('aria-hidden',String(state.guessing));
    $('#guessToggle').textContent = state.guessing ? '揭晓 ↗' : '猜一猜 ↗';
    $('#guessToggle').setAttribute('aria-pressed',String(state.guessing));
  }
  function paintSaved() {
    const stored = state.saved.has(state.selectedId);
    $('#bookmarkGlyph').textContent = stored ? '♥ 已在字袋里' : '♡ 收进字袋'; $('#bookmarkGlyph').setAttribute('aria-pressed',String(stored));
  }
  function paintRelations() {
    const glyph = current();
    const relations = window.RelationEngine.filterRelations(window.RelationEngine.relatedGlyphs(glyphs,glyph,glyphs.length),state.relationFilter).slice(0,6);
    window.GlyphUI.renderSimilar(relations,selectGlyph);
    if (state.graphOpen) window.GraphRenderer.render($('#relationGraph'),glyph,relations,selectGlyph);
  }
  function paintCatalog() { window.GlyphUI.renderCatalog(glyphs,state,selectGlyph); }
  function paintGlyph() {
    window.GlyphUI.renderRecord(current(),glyphs,selectGlyph);
    window.GlyphUI.renderSegments(current(),selectSegment); paintStage(); paintSaved(); paintGuess(); paintRelations();
    if ($('#catalogDialog').open) paintCatalog();
  }
  function selectGlyph(id, updateUrl = true) {
    if (!byId.has(id)) return;
    stopReplay(); state.selectedId = id; state.selectedSegment = null; state.selectedView = 'original'; state.replayStep = 0; state.replayFinished = false; state.guessing = false;
    if ($('#catalogDialog').open) $('#catalogDialog').close();
    if (updateUrl) { try { history.replaceState(null,'',`#glyph=${encodeURIComponent(id)}`); } catch { /* file:// 下仍可正常浏览。 */ } }
    paintGlyph();
    if (window.scrollY > $('#workspace').offsetTop + 100) $('#workspace').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',block:'start'});
  }
  function selectSegment(segment) {
    stopReplay(); state.selectedSegment = state.selectedSegment?.id === segment.id ? null : segment;
    if (state.selectedView === 'trace') state.selectedView = 'original';
    state.replayStep = 0; state.replayFinished = false; paintStage();
  }
  function scheduleReplay() {
    state.replayTimer = setTimeout(() => {
      if (!state.isPlaying) return;
      state.replayStep += 1; state.replayFinished = state.replayStep >= current().segments.length;
      if (state.replayFinished) stopReplay(); paintStage(); if (state.isPlaying) scheduleReplay();
    },state.replayDelay);
  }
  function toggleReplay() {
    if (state.isPlaying) {stopReplay(); paintStage(); return;}
    if (!current().segments.length) return;
    state.selectedSegment = null; if (state.replayFinished) state.replayStep = 0;
    state.replayFinished = false; state.isPlaying = true; paintStage(); scheduleReplay();
  }
  function moveReplay(step) {
    stopReplay(); state.selectedSegment = null; state.replayStep = Math.max(0,Math.min(step,current().segments.length));
    state.replayFinished = state.replayStep >= current().segments.length; paintStage();
  }
  $('#viewTabs').addEventListener('click',event => {
    const tab = event.target.closest('[data-view]'); if (!tab) return;
    stopReplay(); state.selectedView = tab.dataset.view; state.selectedSegment = null; state.replayStep = 0; state.replayFinished = false; paintStage();
  });
  $('#replayPlay').addEventListener('click',toggleReplay); $('#replayReset').addEventListener('click',resetReplay);
  $('#replayPrevious').addEventListener('click',() => moveReplay(state.replayStep - 1)); $('#replayNext').addEventListener('click',() => moveReplay(state.replayStep + 1));
  $('#replayScrub').addEventListener('input',event => moveReplay(Number(event.target.value)));
  $('#replaySpeed').addEventListener('change',event => {state.replayDelay = Number(event.target.value); if (state.isPlaying) {clearTimeout(state.replayTimer); scheduleReplay();}});
  $('#clearTrace').addEventListener('click',() => {window.GlyphTracing.clear(); toast('画布清空了，再写一次吧。');});
  $('#randomGlyph').addEventListener('click',() => {
    const pool = glyphs.filter(g => g.id !== state.selectedId && g.original_meaning); const candidates = pool.length ? pool : glyphs.filter(g => g.id !== state.selectedId);
    if (candidates.length) {selectGlyph(candidates[Math.floor(Math.random()*candidates.length)].id); toast('偶遇一个有故事的字。');}
  });
  $('#guessToggle').addEventListener('click',() => {state.guessing = !state.guessing; paintGuess(); paintStage();});
  $('#bookmarkGlyph').addEventListener('click',() => {
    const id = state.selectedId; if (state.saved.has(id)) state.saved.delete(id); else state.saved.add(id);
    let persisted = true; try {localStorage.setItem(savedKey,JSON.stringify([...state.saved]));} catch {persisted = false;}
    paintSaved(); if ($('#catalogDialog').open) paintCatalog();
    toast(state.saved.has(id) ? persisted ? '收进字袋了，下次还能找到。' : '已放进本次字袋，浏览器未允许长期保存。' : '已经从字袋取出。');
  });
  $('#openCatalog').addEventListener('click',() => {paintCatalog(); $('#catalogDialog').showModal(); $('#glyphSearch').focus();});
  $('#closeCatalog').addEventListener('click',() => $('#catalogDialog').close());
  $('#catalogDialog').addEventListener('click',event => {if (event.target === $('#catalogDialog')) {const r = event.target.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) event.target.close();}});
  $('#glyphSearch').addEventListener('input',event => {state.query = event.target.value; paintCatalog();});
  $('#catalogFilter').addEventListener('change',event => {state.catalogFilter = event.target.value; paintCatalog();});
  $('#relationFilter').addEventListener('change',event => {state.relationFilter = event.target.value; paintRelations();});
  $('#toggleGraph').addEventListener('click',() => {state.graphOpen = !state.graphOpen; $('#relationGraphPanel').hidden = !state.graphOpen; $('#toggleGraph').setAttribute('aria-expanded',String(state.graphOpen)); $('#toggleGraph').textContent = state.graphOpen ? '收起关系图 ↙' : '展开关系图 ↗'; paintRelations();});
  window.addEventListener('hashchange',() => {const id = new URLSearchParams(location.hash.slice(1)).get('glyph'); if (byId.has(id) && id !== state.selectedId) selectGlyph(id,false);});
  document.addEventListener('visibilitychange',() => {if (document.hidden && state.isPlaying) {stopReplay(); paintStage();}});
  $('#datasetStatus').textContent = String(glyphs.length); $('#glyphCount').textContent = String(glyphs.length);
  paintGlyph();
  // Keep SVG visible until the actual font has loaded, and on any font failure.
  if (document.fonts && window.SEAL_FONT) {
    document.fonts.load('200px "Chongxi Seal"', '宇').then(faces => {
      if (!faces.length) return;
      window.SEAL_FONT.ready = true;
      paintStage(); paintRelations();
      if ($('#catalogDialog').open) paintCatalog();
    }).catch(() => { /* The sample SVG remains available, including offline. */ });
  }
})();
