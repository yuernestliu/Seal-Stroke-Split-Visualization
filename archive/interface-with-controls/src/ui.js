(() => {
  const SVG_NS = "http://www.w3.org/2000/svg";
  function svgElement(tag, attributes = {}) {
    const element = document.createElementNS(SVG_NS, tag);
    Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
    return element;
  }

  function strokePath(points) {
    return (points || [])
      .filter((point) => Array.isArray(point) && point.length >= 2)
      .map(([y, x], index) => `${index ? "L" : "M"} ${Number(x)} ${Number(y)}`)
      .join(" ");
  }

  function revealWidth(segment) {
    const points = Math.max(1, segment.pointCount || segment.points?.length || 1);
    const pixels = Math.max(1, segment.pixelCount || points);
    return Math.max(1.4, Math.min(5, (pixels / points) * 1.05));
  }

  function animateMaskPath(path) {
    requestAnimationFrame(() => {
      const length = path.getTotalLength();
      if (!Number.isFinite(length) || length <= 0) return;
      path.style.strokeDasharray = `${length} ${length}`;
      path.style.strokeDashoffset = `${length}`;
      path.style.transition = "stroke-dashoffset 360ms linear";
      requestAnimationFrame(() => { path.style.strokeDashoffset = "0"; });
    });
  }

  const escapeHtml = (value) => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function setText(id, value) {
    document.querySelector(id).textContent = value;
  }

  function vectorShape(vector, fill = 'currentColor', extra = {}) {
    return svgElement('path', {d:vector.path, fill, 'fill-rule':'evenodd', ...extra});
  }
  function vectorMarkup(glyph, vector = window.GLYPH_VECTORS?.[glyph.id]) {
    if (!vector) return `<img src="${escapeHtml(encodeURI(glyph.assets.original))}" alt="${escapeHtml(glyph.mark)} 小篆" loading="lazy" />`;
    return `<svg viewBox="-2 -2 ${vector.width + 4} ${vector.height + 4}" role="img" aria-label="${escapeHtml(glyph.mark)} 小篆" class="glyph-vector"><path d="${escapeHtml(vector.path)}" fill="currentColor" fill-rule="evenodd" /></svg>`;
  }
  function renderImage(glyph, state) {
    const image = document.querySelector('#glyphImage');
    const canvas = document.querySelector('#replayCanvas');
    const caption = document.querySelector('#imageCaption');
    const vector = window.GLYPH_VECTORS?.[glyph.id];
    const {selectedSegment, selectedView, replayStep, replayFinished, isPlaying} = state;
    const tracing = selectedView === 'trace';
    const fontLayer = document.querySelector('#fontGlyph');
    fontLayer.hidden = true;
    const inReplay = isPlaying || replayStep > 0 || replayFinished;
    document.querySelector('#traceCanvas').hidden = !tracing;
    document.querySelector('#glyphStage').classList.toggle('is-tracing',tracing);
    canvas.classList.toggle('trace-reference',tracing);
    canvas.replaceChildren();
    const useFont = window.SEAL_FONT?.ready && window.SEAL_FONT.glyphIds.includes(glyph.id)
      && selectedView === 'original' && !selectedSegment && !inReplay;
    document.querySelector('#displaySource').textContent = useFont ? '崇羲篆體' : '样本字形';
    if (useFont) {
      image.hidden = true; canvas.hidden = true; fontLayer.hidden = false;
      fontLayer.replaceChildren();
      const letter = document.createElement('span');
      letter.className = 'seal-font-letter'; letter.textContent = glyph.mark;
      letter.setAttribute('role','img'); letter.setAttribute('aria-label',`${glyph.mark} 的崇羲篆體字形`);
      fontLayer.append(letter); caption.textContent = '崇羲篆體';
      return;
    }
    // A newly imported glyph without generated vectors can still use its source.
    image.hidden = !!vector;
    canvas.hidden = !vector;
    if (!vector) {
      image.src = selectedView === 'composite' ? glyph.assets.composite : glyph.assets.original;
      image.alt = `${glyph.title} 的原始字形`;
      caption.textContent = '原始字形';
      return;
    }
    const {width,height} = vector;
    const svg = svgElement('svg',{viewBox:`-2 -2 ${width + 4} ${height + 4}`,role:'img','aria-label':`${glyph.title} 的小篆字形`});
    const palette = ['#eeb377','#a5c4b1','#d89181','#bfafd0','#e6d38a','#8eb8c4'];
    function maskSegments(segments, color, key, animate = false) {
      const defs = svgElement('defs');
      const maskId = `stroke-${glyph.sourceId}-${key}`;
      const mask = svgElement('mask',{id:maskId,x:-2,y:-2,width:width+4,height:height+4,maskUnits:'userSpaceOnUse',maskContentUnits:'userSpaceOnUse'});
      mask.append(svgElement('rect',{x:-2,y:-2,width:width+4,height:height+4,fill:'black'}));
      segments.forEach((segment,i) => {
        const d = strokePath(segment.points); if (!d) return;
        const line = svgElement('path',{d,fill:'none',stroke:'white','stroke-width':revealWidth(segment),'stroke-linecap':'round','stroke-linejoin':'round'});
        mask.append(line);
        if (animate && i === segments.length - 1) animateMaskPath(line);
      });
      defs.append(mask); svg.append(defs,vectorShape(vector,color,{mask:`url(#${maskId})`}));
    }
    if (tracing) {
      svg.append(vectorShape(vector)); caption.textContent = '按住拖动，描一描。';
    } else if (selectedSegment) {
      svg.append(vectorShape(vector,'currentColor',{opacity:.14}));
      maskSegments([selectedSegment],selectedView === 'composite' ? palette[glyph.segments.indexOf(selectedSegment) % palette.length] : 'currentColor','selected',true);
      caption.textContent = `第 ${selectedSegment.id} 笔`;
    } else if (selectedView === 'composite') {
      svg.append(vectorShape(vector,'currentColor',{opacity:.12}));
      const visible = inReplay && !replayFinished ? glyph.segments.slice(0,replayStep) : glyph.segments;
      visible.forEach((segment,i) => maskSegments([segment],palette[i % palette.length],`color-${i}`,isPlaying && i === visible.length-1));
      caption.textContent = '按笔段着色';
    } else if (inReplay && !replayFinished) {
      svg.append(vectorShape(vector,'currentColor',{opacity:.12}));
      maskSegments(glyph.segments.slice(0,replayStep),'currentColor','replay',true);
      caption.textContent = `正在展示第 ${replayStep} 笔`;
    } else {
      svg.append(vectorShape(vector)); caption.textContent = replayFinished ? '书写演示完成' : '小篆字形';
    }
    canvas.append(svg);
  }
  const $ = (id) => document.querySelector(id);
  const xz = (text) => window.renderXiaozhuan(text || '');
  function markImage(glyph) {
    if (window.SEAL_FONT?.ready && window.SEAL_FONT.glyphIds.includes(glyph.id)) {
      return `<span class="seal-font-letter seal-font-thumb" role="img" aria-label="${escapeHtml(glyph.mark)} 崇羲篆體">${escapeHtml(glyph.mark)}</span>`;
    }
    return vectorMarkup(glyph);
  }
  function renderCatalog(glyphs, state, onSelect) {
    const query = state.query.trim().toLowerCase();
    const filtered = glyphs.filter(g => {
      const search = [g.mark, g.title, g.sourceId, g.source.section, ...(g.parts || [])].join(' ').toLowerCase();
      return (!query || search.includes(query)) && (state.catalogFilter === 'all'
        || (state.catalogFilter === 'story' && !!g.original_meaning)
        || (state.catalogFilter === 'saved' && state.saved.has(g.id))
        || (state.catalogFilter === 'two-to-four' && g.segments.length <= 4)
        || (state.catalogFilter === 'five-plus' && g.segments.length >= 5));
    });
    $('#catalogResult').textContent = `${filtered.length} 个字形${state.catalogFilter === 'saved' ? ' · 保存在当前浏览器的字袋里' : ' · 点一个，开始探索'}`;
    const list = $('#glyphList'); list.replaceChildren();
    for (const glyph of filtered) {
      const button = document.createElement('button');
      button.type = 'button'; button.className = `glyph-item${glyph.id === state.selectedId ? ' is-active' : ''}`;
      button.dataset.glyphId = glyph.id;
      button.setAttribute('aria-label', `探索 ${glyph.title}，${glyph.segments.length} 个笔段`);
      button.setAttribute('aria-pressed', String(glyph.id === state.selectedId));
      button.innerHTML = `<span class="glyph-item-mark">${markImage(glyph)}</span><strong>${escapeHtml(glyph.title)}</strong><small>${glyph.segments.length} 笔${state.saved.has(glyph.id) ? ' · ♥' : ''}</small>`;
      button.addEventListener('click', () => onSelect(glyph.id)); list.append(button);
    }
    if (!filtered.length) list.innerHTML = `<p class="empty-state">${state.catalogFilter === 'saved' ? '字袋还是空的。遇见喜欢的字，点一下「收进字袋」。' : '还没找到这个字，换个字或部首试试。'}</p>`;
  }
  function renderPlaybackControls(glyph, state) {
    const trace = state.selectedView === 'trace';
    $('#playbackControls').hidden = trace; $('#traceControls').hidden = !trace;
    $('#replayProgress').textContent = `${state.replayStep} / ${glyph.segments.length}`;
    $('#replayPlay').textContent = state.isPlaying ? 'Ⅱ 暂停一下' : state.replayFinished ? '▶ 再看一遍' : '▶ 写给我看';
    $('#replayPlay').disabled = glyph.segments.length === 0;
    $('#replayPrevious').disabled = state.replayStep === 0;
    $('#replayNext').disabled = state.replayStep >= glyph.segments.length;
    $('#replayScrub').max = String(glyph.segments.length); $('#replayScrub').value = String(state.replayStep);
    $('#replaySpeed').value = String(state.replayDelay);
    for (const tab of document.querySelectorAll('.view-tab')) {
      tab.classList.toggle('is-active', tab.dataset.view === state.selectedView);
      tab.setAttribute('aria-pressed', String(tab.dataset.view === state.selectedView));
    }
    for (const button of document.querySelectorAll('.segment-button')) {
      const active = String(state.selectedSegment?.id) === button.dataset.segmentId;
      button.classList.toggle('is-active', active); button.setAttribute('aria-pressed', String(active));
    }
  }
  function renderSegments(glyph, onSelect) {
    $('#strokeCount').textContent = `${glyph.segments.length} 个笔段`;
    const list = $('#segmentsList'); list.replaceChildren();
    for (const [i, segment] of glyph.segments.entries()) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'segment-button';
      button.dataset.segmentId = segment.id; button.setAttribute('aria-label', `单独看第 ${i + 1} 笔`); button.setAttribute('aria-pressed', 'false');
      const vector = window.GLYPH_VECTORS?.[glyph.id]?.segments[i];
      button.innerHTML = `<span class="segment-thumb">${vector ? vectorMarkup(glyph,vector) : `<img src="${escapeHtml(encodeURI(segment.image))}" alt="" loading="lazy" />`}</span><span class="segment-number">${String(i + 1).padStart(2, '0')}</span>`;
      button.addEventListener('click', () => onSelect(segment)); list.append(button);
    }
  }
  function renderRecord(glyph, glyphs, onSelect) {
    const story = window.GLYPH_STORIES?.[glyph.id] || window.GLYPH_STORIES?.[glyph.mark] || {};
    setText('#glyphTitle', glyph.title); setText('#stageMark', glyph.mark);
    setText('#glyphSection', glyph.source.section.replace(/^說文‧/, ''));
    setText('#glyphSource', `${glyph.source.collection} · ${glyph.source.section.replace(/^說文‧/, '')}`);
    setText('#glyphNumber', `NO. ${glyph.sourceId}`);
    const description = glyph.structure_desc || '';
    const formation = description.match(/形声字|会意字|象形字|指事字|独体字/)?.[0] || '字形观察';
    setText('#formationType', formation);
    setText('#storyHeadline', story.headline || (glyph.original_meaning ? `「${glyph.mark}」的来处。` : '故事待补。'));
    $('#glyphOriginalMeaning').innerHTML = glyph.original_meaning ? `${xz(glyph.original_meaning)}` : '释读资料正在整理。';
    $('#glyphMeaningExtendBlock').hidden = !glyph.meaning_extend;
    $('#glyphMeaningExtend').innerHTML = xz(glyph.meaning_extend);
    $('#structureDesc').innerHTML = description ? xz(description) : '构形资料待补。';
    const components = $('#componentList'); components.replaceChildren();
    const parts = glyph.parts?.length ? glyph.parts.map((name, i) => ({name, kind: glyph.part_type?.[i], comment: glyph.part_comment?.[i]})) : (glyph.components || []).map(c => ({...c, comment: c.status}));
    for (const part of parts) {
      const target = glyphs.find(g => g.mark === part.name);
      const card = document.createElement(target ? 'button' : 'div');
      card.className = `component-card${target ? '' : ' component-static'}`;
      if (target) { card.type = 'button'; card.setAttribute('aria-label', `探索部件 ${part.name}`); card.addEventListener('click', () => onSelect(target.id)); }
      card.innerHTML = `<span class="component-name">${window.renderXiaozhuanChar(part.name)}</span><span class="component-copy"><strong>${escapeHtml(part.name)} · ${escapeHtml(part.kind || '构件')}</strong>${part.comment ? `<p>${xz(part.comment)}</p>` : ''}</span>`;
      components.append(card);
    }
    const milestones = story.timeline?.length ? story.timeline : [
      {label:'小篆', image:glyph.assets.original, caption:''}, {label:'今字', text:glyph.mark, caption:''}
    ];
    const timeline = $('#evolutionList'); timeline.replaceChildren();
    for (const [i, step] of milestones.entries()) {
      if (i) { const arrow = document.createElement('span'); arrow.className = 'evolution-arrow'; arrow.textContent = '→'; arrow.setAttribute('aria-hidden', 'true'); timeline.append(arrow); }
      const item = document.createElement('div'); item.className = 'evolution-item';
      const art = document.createElement('div'); art.className = 'evolution-image';
      if (step.image === glyph.assets.original && window.GLYPH_VECTORS?.[glyph.id]) { art.innerHTML = vectorMarkup(glyph); } else if (step.image) { const img = document.createElement('img'); img.src = step.image; img.alt = `${glyph.mark} · ${step.label}`; art.append(img); } else art.textContent = step.text || '';
      const label = document.createElement('span'); label.textContent = step.label; item.append(art, label);
      if (step.caption) { const caption = document.createElement('p'); caption.textContent = step.caption; item.append(caption); }
      if (step.source) { const source = document.createElement('p'); source.textContent = `来源：${step.source}`; item.append(source); }
      timeline.append(item);
    }
    setText('#evolutionLabel', story.timeline?.length ? '字形路径' : '古今对照');
    setText('#evolutionNote', story.timeline?.length ? '字形与说明依据已登记材料呈现。' : '先看小篆与今字的形态差异。更多时代的字形，随资料补充。');
    $('#sourceDetails').innerHTML = [['材料',glyph.source.collection],['分部',glyph.source.section],['编号',glyph.sourceId],['校核',glyph.reviewStatus]].map(([k,v]) => `<div><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`).join('');
    setText('#storySource', story.source || '');
    $('#sourceOriginal').src = glyph.assets.original; $('#sourceOriginal').alt = `${glyph.mark} 的原始样本`;
    document.querySelector('.source-note').open = false;
  }
  function renderSimilar(relations, onSelect) {
    const list = $('#similarList'); list.replaceChildren();
    for (const relation of relations) {
      const button = document.createElement('button'); button.type = 'button'; button.className = `similar-item relation-${relation.type}`;
      button.dataset.glyphId = relation.glyph.id; button.setAttribute('aria-label', `探索 ${relation.glyph.title}，${relation.label}`);
      button.innerHTML = `<span class="similar-arrow" aria-hidden="true">↗</span><span class="similar-mark">${markImage(relation.glyph)}</span><span class="similar-title">${escapeHtml(relation.glyph.title)}</span><span class="similar-label">${escapeHtml(relation.label)}</span>`;
      button.addEventListener('click', () => onSelect(relation.glyph.id)); list.append(button);
    }
    if (!relations.length) list.innerHTML = '<p class="empty-state">这一组联系还在整理。换一种筛选，或去字库遇见下一个字。</p>';
    setText('#graphSummary', relations.length ? '共用一个部件，会带来怎样的联系？点一张字形贴片，继续探索。' : '还有更多字间关系，等待被发现。');
  }
  window.GlyphUI = {renderCatalog, renderImage, renderPlaybackControls, renderSegments, renderRecord, renderSimilar};
})();
