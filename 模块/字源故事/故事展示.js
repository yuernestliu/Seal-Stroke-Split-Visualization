/* Story presentation has its own boundary; shape rendering is provided by GlyphUI. */
(() => {
  const $ = selector => document.querySelector(selector);
  const xz = text => window.renderXiaozhuan(text || '');
  const escapeHtml = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const setText = (id,value) => { $(id).textContent = value; };
  const vectorMarkup = (...args) => window.GlyphUI.vectorMarkup(...args);
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

  window.StoryPanel = {renderRecord};
})();
