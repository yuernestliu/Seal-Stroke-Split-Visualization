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
    const clean = window.CleanGlyphShapes?.svg(glyph);
    if (clean) return clean.outerHTML;
    if (!vector) return `<img src="${escapeHtml(encodeURI(glyph.assets.original))}" alt="${escapeHtml(glyph.mark)} 小篆" loading="lazy" />`;
    return `<svg viewBox="-2 -2 ${vector.width + 4} ${vector.height + 4}" role="img" aria-label="${escapeHtml(glyph.mark)} 小篆" class="glyph-vector"><path d="${escapeHtml(vector.path)}" fill="currentColor" fill-rule="evenodd" /></svg>`;
  }

  const $ = selector => document.querySelector(selector);
  const xz = text => window.renderXiaozhuan(text || '');
  function renderRecord(glyph, glyphs, onSelect) {
    const story = window.GLYPH_STORIES?.[glyph.id] || window.GLYPH_STORIES?.[glyph.mark] || {};
    setText('#glyphTitle', glyph.title);
    setText('#glyphSource', `${glyph.source.collection} · ${glyph.source.section.replace(/^說文‧/, '')}`);
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
    setText('#evolutionNote', story.timeline?.length ? '字形与说明依据已登记材料呈现。' : '先看小篆与今字的形态差异。更多时代的字形，随资料补充。');
    $('#sourceDetails').innerHTML = [['材料',glyph.source.collection],['分部',glyph.source.section],['编号',glyph.sourceId],['校核',glyph.reviewStatus]].map(([k,v]) => `<div><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`).join('');
    setText('#storySource', story.source || '');
    $('#sourceOriginal').src = glyph.assets.original; $('#sourceOriginal').alt = `${glyph.mark} 的原始样本`;
    document.querySelector('.source-note').open = false;
  }

  const palette = ['#eeb377','#a5c4b1','#d89181','#bfafd0','#e6d38a','#8eb8c4'];
  function renderImage(glyph,{split}) {
    const image = $('#glyphImage'), canvas = $('#glyphVector'), fontLayer = $('#fontGlyph');
    image.hidden = true; canvas.hidden = true; fontLayer.hidden = true;
    canvas.replaceChildren(); fontLayer.replaceChildren();
    const clean = window.CleanGlyphShapes?.svg(glyph,{colored:split});
    if (clean) {
      canvas.append(clean); canvas.hidden = false;
    } else if (!split && window.SEAL_FONT?.ready && window.SEAL_FONT.glyphIds.includes(glyph.id)) {
      const letter = document.createElement('span');
      letter.className = 'seal-font-letter'; letter.textContent = glyph.mark;
      letter.setAttribute('role','img'); letter.setAttribute('aria-label',`${glyph.mark} 的小篆字形`);
      fontLayer.append(letter); fontLayer.hidden = false;
    } else {
      const vector = window.GLYPH_VECTORS?.[glyph.id];
      if (!vector) {
        image.hidden = false; image.src = split ? glyph.assets.composite : glyph.assets.original;
        image.alt = `${glyph.title} 的字形`;
      } else {
        const {width,height} = vector;
        const svg = svgElement('svg',{viewBox:`-2 -2 ${width+4} ${height+4}`,role:'img','aria-label':`${glyph.title} ${split ? '拆笔' : '小篆'}字形`});
        svg.append(vectorShape(vector,'currentColor',split ? {opacity:.12} : {}));
        if (split) glyph.segments.forEach((segment,i) => {
          const id = `stroke-${glyph.sourceId}-${i}`;
          const defs = svgElement('defs');
          const mask = svgElement('mask',{id,x:-2,y:-2,width:width+4,height:height+4,maskUnits:'userSpaceOnUse',maskContentUnits:'userSpaceOnUse'});
          mask.append(svgElement('rect',{x:-2,y:-2,width:width+4,height:height+4,fill:'black'}));
          mask.append(svgElement('path',{d:strokePath(segment.points),fill:'none',stroke:'white','stroke-width':revealWidth(segment),'stroke-linecap':'round','stroke-linejoin':'round'}));
          defs.append(mask); svg.append(defs,vectorShape(vector,palette[i%palette.length],{mask:`url(#${id})`}));
        });
        canvas.append(svg); canvas.hidden = false;
      }
    }
    $('#imageCaption').textContent = split ? `已展开 ${glyph.segments.length} 个独立笔段` : `${glyph.mark} 的小篆字形`;
  }
  function renderSegments(glyph) {
    const list = $('#splitStrokes'); list.replaceChildren();
    glyph.segments.forEach((segment,i) => {
      const piece = document.createElement('div'); piece.className = 'stroke-piece'; piece.style.color = palette[i%palette.length];
      const vector = window.GLYPH_VECTORS?.[glyph.id]?.segments[i];
      const clean = window.CleanGlyphShapes?.svg(glyph,{colored:true,strokeIndex:i,label:`第 ${i+1} 个笔段`});
      if (clean) { piece.append(clean); } else if (vector) {
        piece.innerHTML = vectorMarkup(glyph,vector);
        piece.querySelector('svg').setAttribute('aria-label',`第 ${i+1} 个笔段`);
      } else {
        const image = document.createElement('img'); image.src = segment.image; image.alt = `第 ${i+1} 个笔段`; piece.append(image);
      }
      list.append(piece);
    });
  }
  function catalogMark(glyph) {
    const clean = window.CleanGlyphShapes?.svg(glyph);
    if (clean) return clean.outerHTML;
    if (window.SEAL_FONT?.ready && window.SEAL_FONT.glyphIds.includes(glyph.id)) return `<span class="seal-font-letter seal-font-thumb" role="img" aria-label="${escapeHtml(glyph.mark)} 小篆">${escapeHtml(glyph.mark)}</span>`;
    return vectorMarkup(glyph);
  }
  function renderCatalog(glyphs,state,onSelect) {
    const query = state.query.trim().toLowerCase();
    const filtered = glyphs.filter(glyph => !query || [glyph.mark,glyph.title,glyph.sourceId,glyph.source.section,...(glyph.parts || [])].join(' ').toLowerCase().includes(query));
    $('#catalogResult').textContent = `${filtered.length} 个字形`;
    const list = $('#glyphList'); list.replaceChildren();
    filtered.forEach(glyph => {
      const button = document.createElement('button'); button.type = 'button';
      button.className = `glyph-item${glyph.id === state.selectedId ? ' is-active' : ''}`;
      button.dataset.glyphId = glyph.id; button.setAttribute('aria-label',`查看 ${glyph.title}`);
      button.setAttribute('aria-pressed',String(glyph.id === state.selectedId));
      button.innerHTML = `<span class="glyph-item-mark">${catalogMark(glyph)}</span><strong>${escapeHtml(glyph.title)}</strong>`;
      button.addEventListener('click',() => onSelect(glyph.id)); list.append(button);
    });
    if (!filtered.length) list.innerHTML = '<p class="empty-state">没有匹配的字形。</p>';
  }
  window.GlyphUI = {renderCatalog,renderImage,renderSegments,renderRecord};
})();
