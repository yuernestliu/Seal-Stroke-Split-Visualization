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

  let templateMaskSequence = 0;
  function templatePartInfo(glyph, index) {
    const explicitName = glyph.parts?.[index] || '';
    const section = glyph.source?.section?.replace(/^說文‧/, '').replace(/部$/, '') || '';
    const name = explicitName || `候选部件 ${index + 1}`;
    const known = window.COMPONENT_MEANINGS?.[name];
    const comment = explicitName ? glyph.part_comment?.[index] : '';
    return {
      name,
      meaning: comment || known?.meaning || '模板图中的颜色分区，构件名称与释义待校核。',
      source: known?.source || '按模板识别图的颜色分区'
    };
  }

  function annotationText(value) {
    const text = String(value || '').replace(/[“”"']/g, '');
    return text.length > 26 ? `${text.slice(0, 25)}…` : text;
  }

  function templateSvg(glyph, {interactive = false, expanded = false} = {}) {
    const template = glyph.templateParts;
    if (!template?.length) return null;
    const {width, height} = glyph.templateSize || {};
    const record = glyph.templateRecord;
    const viewWidth = width || record?.width || glyph.templateWidth || 56;
    const viewHeight = height || record?.height || glyph.templateHeight || 80;
    const root = svgElement('svg', {
      viewBox:`0 0 ${viewWidth} ${viewHeight}`,
      role:'img',
      'aria-label':`${glyph.title} 的小篆字形${interactive && template.length > 1 ? '，悬停可查看部件' : ''}`,
      class:'glyph-vector template-character'
    });
    const defs = svgElement('defs');
    const groups = [];
    const centerX = viewWidth / 2, centerY = viewHeight / 2;
    const suffix = `${++templateMaskSequence}`;
    template.forEach((part, index) => {
      const maskId = `template-mask-${suffix}-${index}`;
      const mask = svgElement('mask', {id:maskId, x:0, y:0, width:viewWidth, height:viewHeight, maskUnits:'userSpaceOnUse', style:'mask-type:alpha'});
      mask.append(svgElement('image', {href:part.mask, x:0, y:0, width:viewWidth, height:viewHeight, preserveAspectRatio:'none'}));
      defs.append(mask);
      const group = svgElement('g', {class:'template-part', style:`--part-color:${part.palette || palette[index % palette.length]}`, 'data-part-index':index});
      group.append(svgElement('rect', {x:0, y:0, width:viewWidth, height:viewHeight, fill:'currentColor', mask:`url(#${maskId})`}));
      if ((interactive || expanded) && template.length > 1) {
        const dx = Number(part.cx) - centerX, dy = Number(part.cy) - centerY;
        let length = Math.hypot(dx, dy), ux, uy;
        if (length < 1) { const angle = (index / template.length) * Math.PI * 2; ux = Math.cos(angle); uy = Math.sin(angle); }
        else { ux = dx / length; uy = dy / length; }
        group.dataset.spreadX = String(Math.round(ux * 8));
        group.dataset.spreadY = String(Math.round(uy * 8));
        const info = templatePartInfo(glyph, index);
        const lineLength = 14;
        const endX = Number(part.cx) + ux * lineLength;
        const endY = Number(part.cy) + uy * lineLength;
        const textX = endX + (ux < -0.15 ? -1.5 : 1.5);
        const textAnchor = ux < -0.15 ? 'end' : 'start';
        const annotation = svgElement('g', {class:'template-annotation', 'data-part-index':index, 'aria-label':`${info.name}：${info.meaning}`});
        const label = svgElement('text', {x:textX, y:endY - 0.2, 'text-anchor':textAnchor});
        label.append(document.createTextNode(info.name));
        annotation.append(
          svgElement('line', {x1:Number(part.cx), y1:Number(part.cy), x2:endX, y2:endY}),
          svgElement('rect', {x:textAnchor === 'end' ? textX - 22 : textX, y:endY - 3.2, width:22, height:5.5, fill:'transparent'}),
          label
        );
        group.append(annotation);
      }
      groups.push(group);
    });
    root.append(defs, ...groups);
    if (expanded && template.length > 1) {
      root.classList.add('is-exploded');
      groups.forEach(group => group.setAttribute('transform', `translate(${group.dataset.spreadX} ${group.dataset.spreadY})`));
    }
    if (interactive && template.length > 1) {
      let explodeTimer = null;
      const setExploded = expanded => {
        if (explodeTimer) { clearTimeout(explodeTimer); explodeTimer = null; }
        if (expanded) {
          root.classList.remove('is-exploded');
          document.body.classList.add('template-focus-active');
          const delay = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ? 0 : 230;
          explodeTimer = setTimeout(() => {
            root.classList.add('is-exploded');
            groups.forEach(group => group.setAttribute('transform', `translate(${group.dataset.spreadX} ${group.dataset.spreadY})`));
            explodeTimer = null;
          }, delay);
        } else {
          root.classList.remove('is-exploded');
          document.body.classList.remove('template-focus-active');
          groups.forEach(group => group.setAttribute('transform', 'translate(0 0)'));
        }
      };
      root.addEventListener('pointerenter', () => setExploded(true));
      root.addEventListener('pointerleave', () => setExploded(false));
      root.addEventListener('focus', () => setExploded(true));
      root.addEventListener('blur', () => setExploded(false));
      root.setAttribute('tabindex','0');
    }
    return root;
  }

  const $ = selector => document.querySelector(selector);
  const xz = text => window.renderXiaozhuan(text || '');

  const palette = ['#eeb377','#a5c4b1','#d89181','#bfafd0','#e6d38a','#8eb8c4'];
  function renderImage(glyph,{split}) {
    const image = $('#glyphImage'), canvas = $('#glyphVector'), fontLayer = $('#fontGlyph');
    document.body.classList.remove('template-focus-active');
    image.hidden = true; canvas.hidden = true; fontLayer.hidden = true;
    canvas.replaceChildren(); fontLayer.replaceChildren();
    const clean = window.CleanGlyphShapes?.svg(glyph,{colored:split});
    const template = clean ? null : templateSvg(glyph,{interactive:!split,expanded:split});
    if (template) {
      canvas.append(template); canvas.hidden = false;
    } else if (clean) {
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
    if (!template && !split) {
      const focusTarget = canvas.hidden ? (fontLayer.hidden ? image : fontLayer.firstElementChild) : canvas.firstElementChild;
      if (focusTarget) {
        focusTarget.classList.add('glyph-focus-target');
        focusTarget.addEventListener('pointerenter', () => document.body.classList.add('template-focus-active'));
        focusTarget.addEventListener('pointerleave', () => document.body.classList.remove('template-focus-active'));
      }
    }
    $('#imageCaption').textContent = template && glyph.templateParts.length > 1 ? split ? `已展开 ${glyph.templateParts.length} 个独立部件` : '移到字形上方，查看部件拆解' : split ? `已展开 ${glyph.segments.length} 个独立笔段` : `${glyph.mark} 的小篆字形`;
  }
  function renderSegments(glyph) {
    const list = $('#splitStrokes'); list.replaceChildren();
    if (glyph.templateParts?.length) {
      glyph.templateParts.forEach((part,index) => {
        const piece = document.createElement('div'); piece.className = 'stroke-piece'; piece.style.color = part.palette || palette[index % palette.length];
        piece.append(templateSvg({...glyph,templateParts:[part]}));
        list.append(piece);
      });
      return;
    }
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
    const template = templateSvg(glyph);
    if (template) return template.outerHTML;
    if (window.SEAL_FONT?.ready && window.SEAL_FONT.glyphIds.includes(glyph.id)) return `<span class="seal-font-letter seal-font-thumb" role="img" aria-label="${escapeHtml(glyph.mark)} 小篆">${escapeHtml(glyph.mark)}</span>`;
    return vectorMarkup(glyph);
  }
  function renderCatalog(glyphs,state,onSelect) {
    const query = state.query.trim().toLowerCase();
    const filtered = glyphs.filter(glyph => !query || [glyph.mark,glyph.title,glyph.sourceId,glyph.source.section,...(glyph.parts || []),...(glyph.aliases || [])].join(' ').toLowerCase().includes(query));
    $('#catalogResult').textContent = `${filtered.length} 个字形${filtered.length > (state.catalogLimit || 96) ? ' · 分批加载' : ''}`;
    $('#catalogMore').hidden = filtered.length <= (state.catalogLimit || 96);
    const list = $('#glyphList'); list.replaceChildren();
    filtered.slice(0,state.catalogLimit || 96).forEach(glyph => {
      const button = document.createElement('button'); button.type = 'button';
      button.className = `glyph-item${glyph.id === state.selectedId ? ' is-active' : ''}`;
      button.dataset.glyphId = glyph.id; button.setAttribute('aria-label',`查看 ${glyph.title}`);
      button.setAttribute('aria-pressed',String(glyph.id === state.selectedId));
      button.innerHTML = `<span class="glyph-item-mark">${catalogMark(glyph)}</span><strong>${escapeHtml(glyph.title)}</strong>`;
      button.addEventListener('click',() => onSelect(glyph.id)); list.append(button);
    });
    if (!filtered.length) list.innerHTML = '<p class="empty-state">没有匹配的字形。</p>';
  }
  window.GlyphUI = {renderCatalog,renderImage,renderSegments,vectorMarkup};
})();
