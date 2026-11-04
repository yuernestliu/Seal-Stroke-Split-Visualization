(() => {
  const { dataset, glyphs } = window.GLYPH_DATA;
  // 给每个字派生 _radical / _phonetic / _semantic，供相似字筛选使用
  window.ComponentDeriver?.annotate(glyphs);
  const glyphById = new Map(glyphs.map((glyph) => [glyph.id, glyph]));
  const state = {
    selectedId: glyphs.find((glyph) => glyph.mark === "尚")?.id || glyphs[0].id,
    selectedSegment: null,
    selectedView: "original",
    query: "",
    catalogFilter: "all",
    relationFilter: "all",
    replayStep: 0,
    replayDelay: 800,
    isPlaying: false,
    replayTimer: null,
    replayFinished: false,
  };

  function selectedGlyph() {
    return glyphById.get(state.selectedId);
  }

  function stopReplay() {
    state.isPlaying = false;
    if (state.replayTimer) window.clearTimeout(state.replayTimer);
    state.replayTimer = null;
  }

  function resetToOriginal() {
    stopReplay();
    state.replayStep = 0;
    state.replayFinished = false;
  }

  function selectGlyph(id) {
    if (!glyphById.has(id)) return;
    resetToOriginal();
    state.selectedId = id;
    state.selectedSegment = null;
    state.selectedView = "original";
    render();
  }

  function selectSegment(segment) {
    stopReplay();
    state.selectedSegment = segment;
    state.replayStep = 0;
    state.replayFinished = false;
    render();
  }

  function clearSegment() {
    if (!state.selectedSegment) return;
    state.selectedSegment = null;
    render();
  }

  function toggleReplay() {
    if (state.selectedSegment) clearSegment();
    if (state.isPlaying) {
      stopReplay();
      render();
      return;
    }
    const glyph = selectedGlyph();
    if (state.replayStep >= glyph.segments.length) state.replayStep = 0;
    state.replayFinished = false;
    state.isPlaying = true;
    render();
    scheduleReplay();
  }

  function scheduleReplay() {
    if (!state.isPlaying) return;
    state.replayTimer = window.setTimeout(() => {
      const glyph = selectedGlyph();
      if (state.replayStep < glyph.segments.length) {
        state.replayStep += 1;
      } else {
        state.isPlaying = false;
        state.replayFinished = true;
      }
      render();
      scheduleReplay();
    }, state.replayDelay);
  }

  function moveReplay(step) {
    if (state.selectedSegment) clearSegment();
    stopReplay();
    const glyph = selectedGlyph();
    state.replayStep = Math.max(0, Math.min(step, glyph.segments.length));
    state.replayFinished = state.replayStep >= glyph.segments.length;
    render();
  }

  function resetReplay() {
    if (state.selectedSegment) clearSegment();
    resetToOriginal();
    render();
  }

  function setView(view) {
    if (state.selectedView === view) return;
    if (state.selectedSegment) clearSegment();
    stopReplay();
    state.replayStep = 0;
    state.replayFinished = false;
    state.selectedView = view;
    render();
  }

  function render() {
    const glyph = selectedGlyph();
    const allRelations = window.RelationEngine.relatedGlyphs(glyphs, glyph);
    const relations = window.RelationEngine.filterRelations(allRelations, state.relationFilter);
    window.GlyphUI.renderCatalog(glyphs, state.selectedId, state.query, state.catalogFilter, selectGlyph);
    window.GlyphUI.renderTabs(state.selectedView, setView);
    window.GlyphUI.renderImage(glyph, state);
    window.GlyphUI.renderPlaybackControls(glyph, state);
    window.GlyphUI.renderMetrics(glyph);
    window.GlyphUI.renderSegments(glyph, state.selectedSegment, selectSegment);
    window.GlyphUI.renderRecord(glyph);
    window.GlyphUI.renderSimilar(relations, selectGlyph);
    window.GraphRenderer.render(document.querySelector("#relationGraph"), glyph, relations, selectGlyph);
    document.querySelector("#graphSummary").textContent = relations.length
      ? `当前展示 ${relations.length} 个可能相近的字形，供观察和讨论。`
      : "当前筛选下暂未找到相近字形。可切换筛选方式再看看。";
  }

  document.querySelector("#glyphSearch").addEventListener("input", (event) => {
    state.query = event.target.value;
    window.GlyphUI.renderCatalog(glyphs, state.selectedId, state.query, state.catalogFilter, selectGlyph);
  });
  document.querySelector("#catalogFilter").addEventListener("change", (event) => {
    state.catalogFilter = event.target.value;
    window.GlyphUI.renderCatalog(glyphs, state.selectedId, state.query, state.catalogFilter, selectGlyph);
  });
  document.querySelector("#relationFilter").addEventListener("change", (event) => {
    state.relationFilter = event.target.value;
    render();
  });
  document.querySelector("#replayPlay").addEventListener("click", toggleReplay);
  document.querySelector("#replayReset").addEventListener("click", resetReplay);
  document.querySelector("#replayPrevious").addEventListener("click", () => moveReplay(state.replayStep - 1));
  document.querySelector("#replayNext").addEventListener("click", () => moveReplay(state.replayStep + 1));
  document.querySelector("#replaySpeed").addEventListener("change", (event) => {
    state.replayDelay = Number(event.target.value);
    if (state.isPlaying) {
      stopReplay();
      state.isPlaying = true;
      scheduleReplay();
    }
    render();
  });
  document.querySelector("#viewTabs").addEventListener("click", (event) => {
    const button = event.target.closest(".view-tab");
    if (button && button.dataset.view) setView(button.dataset.view);
  });

  // 监听图片舞台的点击：点击原字图像区域 = 复位回原字
  document.querySelector("#replayCanvas").addEventListener("click", (event) => {
    // 仅在画布处于静态/完成态时，单击 = 回原字
    if (!state.isPlaying) resetToOriginal(), render();
  });

  window.GlyphUI.renderDatasetStatus(dataset);
  render();

  // 若 file:// 模式下索引还在异步加载，加载完后再渲染一次，确保小篆图能显示
  if (window.whenXiaozhuanReady) {
    window.whenXiaozhuanReady(() => {
      render();
    });
  }
})();
