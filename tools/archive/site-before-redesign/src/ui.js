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

  function renderCatalog(glyphs, selectedId, query, filter, onSelect) {
    const normalizedQuery = query.trim().toLowerCase();
    const filtered = glyphs.filter((glyph) => {
      const searchable = [glyph.mark, glyph.title, glyph.sourceId, glyph.source.section, glyph.reviewStatus].join(" ").toLowerCase();
      const matchQuery = !normalizedQuery || searchable.includes(normalizedQuery);
      const segments = glyph.metrics.segmentCount;
      const matchFilter = filter === "all"
        || (filter === "review" && glyph.reviewStatus.includes("待"))
        || (filter === "two-to-four" && segments >= 2 && segments <= 4)
        || (filter === "five-plus" && segments >= 5);
      return matchQuery && matchFilter;
    });
    const container = document.querySelector("#glyphList");
    container.replaceChildren();
    filtered.forEach((glyph) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `glyph-item${glyph.id === selectedId ? " is-active" : ""}`;
      button.innerHTML = `
        <span class="glyph-item-mark">${window.renderXiaozhuanChar(glyph.mark, { className: 'xiaozhuan-mark', boxStyle: 'max-width:32px; max-height:32px; object-fit:contain; display:block;' })}</span>
        <span class="glyph-item-copy"><strong>${escapeHtml(glyph.title)}</strong><small>${glyph.metrics.segmentCount} 笔</small></span>
        <span class="glyph-item-id">${escapeHtml(glyph.sourceId)}</span>`;
      button.addEventListener("click", () => onSelect(glyph.id));
      container.append(button);
    });
    if (!filtered.length) {
      container.innerHTML = '<p class="empty-state">没有匹配的字形。</p>';
    }
  }

  /**
   * 观察方式切换标签（原字 / 笔画拆解）
   */
  function renderTabs(selectedView, onViewChange) {
    const tabs = document.querySelector("#viewTabs");
    const tabsData = [
      { view: "original", label: "原字" },
      { view: "composite", label: "笔画拆解" },
    ];
    tabs.replaceChildren();
    tabsData.forEach((tabData) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `view-tab${selectedView === tabData.view ? " is-active" : ""}`;
      button.dataset.view = tabData.view;
      button.textContent = tabData.label;
      button.addEventListener("click", () => onViewChange(tabData.view));
      tabs.append(button);
    });
  }

  /**
   * 单一字形舞台渲染
   *   - 原字视图：默认显示原字；逐笔书写时 canvas 浮在原字之上播放
   *   - 笔画拆解视图：显示按笔着色的原字彩图
   *   - 选中笔画：显示该单笔（两种视图都生效）
   */
  function renderImage(glyph, state) {
    const image = document.querySelector("#glyphImage");
    const replayCanvas = document.querySelector("#replayCanvas");
    const caption = document.querySelector("#imageCaption");
    const { selectedSegment, selectedView, replayStep, replayFinished, isPlaying } = state;
    const inReplay = isPlaying || replayStep > 0 || replayFinished;

    // 单笔查看：整字 ghost 背景 + 选中这一笔单独亮起（和播放笔画同一套 SVG mask 逻辑）
    if (selectedSegment) {
      image.hidden = true;
      replayCanvas.hidden = false;
      replayCanvas.replaceChildren();
      const width = glyph.canvas?.width || 80;
      const height = glyph.canvas?.height || 80;
      const svg = svgElement("svg", {
        viewBox: `0 0 ${width} ${height}`,
        preserveAspectRatio: "xMidYMid meet",
        role: "img",
        "aria-label": `${glyph.title} 第 ${selectedSegment.id} 笔`,
      });
      // 底图：原字视图用原字，笔画拆解视图用按笔着色的彩图
      const baseAsset = selectedView === "composite" ? glyph.assets.composite : glyph.assets.original;
      const base = encodeURI(baseAsset);
      // 整字 ghost 背景
      svg.append(svgElement("image", { href: base, x: 0, y: 0, width, height, opacity: "0.1" }));
      // mask：只有选中那一笔是白色区域
      const maskId = `segment-mask-${glyph.sourceId}-${selectedSegment.id}`;
      const defs = svgElement("defs");
      const mask = svgElement("mask", {
        id: maskId,
        x: 0, y: 0, width, height,
        maskUnits: "userSpaceOnUse",
        maskContentUnits: "userSpaceOnUse",
      });
      mask.append(svgElement("rect", { x: 0, y: 0, width, height, fill: "black" }));
      const pathData = strokePath(selectedSegment.points);
      if (pathData) {
        const path = svgElement("path", {
          d: pathData,
          fill: "none",
          stroke: "white",
          "stroke-width": revealWidth(selectedSegment),
          "stroke-linecap": "round",
          "stroke-linejoin": "round",
        });
        mask.append(path);
        // 与播放笔画保持一致的"亮起"动画
        animateMaskPath(path);
      }
      defs.append(mask);
      svg.append(defs, svgElement("image", {
        href: base,
        x: 0, y: 0, width, height,
        mask: `url(#${maskId})`,
      }));
      replayCanvas.append(svg);
      caption.textContent = `第 ${selectedSegment.id} 笔`;
      return;
    }

    // 笔画拆解视图：image 切到 composite
    if (selectedView === "composite") {
      image.hidden = false;
      image.src = glyph.assets.composite;
      image.alt = `${glyph.title}：按笔着色的原字`;
      replayCanvas.hidden = true;
      replayCanvas.replaceChildren();
      caption.textContent = "按笔着色的原字彩图";
      return;
    }

    // 原字视图：逐笔书写时 canvas 浮在原字之上
    if (inReplay) {
      image.hidden = true;
      replayCanvas.hidden = false;
      replayCanvas.replaceChildren();
      const width = glyph.canvas?.width || 80;
      const height = glyph.canvas?.height || 80;
      const svg = svgElement("svg", {
        viewBox: `0 0 ${width} ${height}`,
        preserveAspectRatio: "xMidYMid meet",
        role: "img",
        "aria-label": `${glyph.title} 的逐笔书写过程`,
      });
      const original = encodeURI(glyph.assets.original);
      const ghost = svgElement("image", { href: original, x: 0, y: 0, width, height, opacity: "0.1" });
      svg.append(ghost);

      if (replayFinished) {
        svg.append(svgElement("image", { href: original, x: 0, y: 0, width, height }));
        caption.textContent = "书写完成，回到原字";
      } else {
        const maskId = `replay-mask-${glyph.sourceId}`;
        const defs = svgElement("defs");
        const mask = svgElement("mask", {
          id: maskId,
          x: 0, y: 0, width, height,
          maskUnits: "userSpaceOnUse",
          maskContentUnits: "userSpaceOnUse",
        });
        mask.append(svgElement("rect", { x: 0, y: 0, width, height, fill: "black" }));
        glyph.segments.slice(0, replayStep).forEach((segment, index) => {
          const pathData = strokePath(segment.points);
          if (!pathData) return;
          const path = svgElement("path", {
            d: pathData,
            fill: "none",
            stroke: "white",
            "stroke-width": revealWidth(segment),
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
          });
          mask.append(path);
          if (index === replayStep - 1) animateMaskPath(path);
        });
        defs.append(mask);
        svg.append(defs, svgElement("image", {
          href: original,
          x: 0, y: 0, width, height,
          mask: `url(#${maskId})`,
        }));
        caption.textContent = replayStep
          ? `正在书写第 ${replayStep} 笔`
          : "准备播放：点击「播放」开始逐笔书写";
      }
      replayCanvas.append(svg);
      return;
    }

    // 默认：原字
    image.hidden = false;
    image.src = glyph.assets.original;
    image.alt = `${glyph.title} 的原字`;
    replayCanvas.hidden = true;
    replayCanvas.replaceChildren();
    caption.textContent = "原字";
  }

  // 每一笔分配一种可区分的颜色；笔画多于预设色数时用黄金角继续生成
  function strokePalette(count) {
    const base = [
      [217, 68, 68],   // 红
      [232, 158, 49],  // 橙
      [225, 199, 56],  // 黄
      [78, 178, 110],  // 绿
      [64, 165, 205],  // 青
      [158, 110, 200], // 紫
      [214, 105, 160], // 粉
      [80, 190, 175],  // 蓝绿
    ];
    if (count <= base.length) return base.slice(0, count);
    const out = base.slice();
    for (let i = base.length; i < count; i += 1) {
      const h = (i * 137.5) % 360;
      out.push(hslToRgb(h, 0.65, 0.55));
    }
    return out;
  }

  function hslToRgb(h, s, l) {
    h = h / 360;
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs((h * 6) % 2 - 1));
    const m = l - c / 2;
    let r = 0;
    let g = 0;
    let b = 0;
    if (h < 1 / 6) { r = c; g = x; b = 0; }
    else if (h < 2 / 6) { r = x; g = c; b = 0; }
    else if (h < 3 / 6) { r = 0; g = c; b = x; }
    else if (h < 4 / 6) { r = 0; g = x; b = c; }
    else if (h < 5 / 6) { r = x; g = 0; b = c; }
    else { r = c; g = 0; b = x; }
    return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
  }

  function renderPlaybackControls(glyph, state) {
    const controls = document.querySelector("#playbackControls");
    // 仅在原字视图显示逐笔书写控制条
    controls.hidden = state.selectedView !== "original";
    if (controls.hidden) return;
    const { replayStep, isPlaying, replayDelay, selectedSegment } = state;
    document.querySelector("#replayProgress").textContent = `${replayStep} / ${glyph.segments.length} 笔`;
    document.querySelector("#replayPlay").textContent = isPlaying ? "❚❚ 暂停" : "▶ 播放";
    document.querySelector("#replayPrevious").disabled = !!selectedSegment || replayStep === 0;
    document.querySelector("#replayNext").disabled = !!selectedSegment || replayStep >= glyph.segments.length;
    document.querySelector("#replaySpeed").value = String(replayDelay);
  }

  function renderMetrics(glyph) {
    const metrics = [
      ["笔画数量", `${glyph.metrics.segmentCount} 笔`],
      ["观察方式", "可逐笔观看"],
    ];
    document.querySelector("#metricStrip").innerHTML = metrics
      .map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`)
      .join("");
  }

  function renderSegments(glyph, selectedSegment, onSelect) {
    const container = document.querySelector("#segmentsList");
    container.replaceChildren();
    glyph.segments.forEach((segment) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `segment-button${selectedSegment && selectedSegment.id === segment.id ? " is-active" : ""}`;
      button.innerHTML = `
        <span class="segment-thumb"><img src="${encodeURI(segment.image)}" alt="" /></span>
        <span class="segment-copy"><strong>第 ${segment.id} 笔</strong><small>点击查看这一笔</small></span>`;
      button.addEventListener("click", () => onSelect(segment));
      container.append(button);
    });
  }

  function renderRecord(glyph) {
    setText("#glyphSource", `${glyph.source.collection} · ${glyph.source.section}`);
    // 标题也用小篆图渲染（如：尚 → 小篆"尚"）
    const titleEl = document.querySelector("#glyphTitle");
    if (titleEl) {
      titleEl.innerHTML = window.renderXiaozhuanChar(glyph.title, { className: 'xiaozhuan-title', boxStyle: 'max-height:54px; max-width:54px; object-fit:contain; display:inline-block; vertical-align:middle;' });
    }

    const xz = window.renderXiaozhuan;

    // 1. 标题行 mark_text(支持小篆标记)
    const markEl = document.querySelector("#glyphMarkText");
    if (markEl) {
      if (glyph.mark_text && xz) markEl.innerHTML = xz(glyph.mark_text);
      else if (markEl) markEl.textContent = "";
    }

    // 2. 本义（支持小篆标记）
    const originalMeaning = glyph.original_meaning || "";
    const origEl = document.querySelector("#glyphOriginalMeaning");
    if (origEl) {
      if (originalMeaning) {
        origEl.innerHTML = xz ? xz(originalMeaning) : escapeHtml(originalMeaning);
      } else {
        origEl.textContent = "（本义待补）";
      }
    }
    const originalBlock = document.querySelector("#glyphOriginalMeaningBlock");
    if (originalBlock) originalBlock.hidden = !originalMeaning;

    // 3. 字义拓展（空字符串时整个块整体隐藏；支持小篆标记）
    const extendBlock = document.querySelector("#glyphMeaningExtendBlock");
    const extendEl = document.querySelector("#glyphMeaningExtend");
    const extend = glyph.meaning_extend || "";
    if (extendBlock) {
      if (extend.trim()) {
        extendBlock.hidden = false;
        if (extendEl) extendEl.innerHTML = xz ? xz(extend) : escapeHtml(extend);
      } else {
        extendBlock.hidden = true;
      }
    }

    // 4. 来源明细
    document.querySelector("#sourceDetails").innerHTML = [
      ["材料", glyph.source.collection],
      ["分部", glyph.source.section],
    ].map(([term, definition]) => `<div><dt>${escapeHtml(term)}</dt><dd>${escapeHtml(definition)}</dd></div>`).join("");

    // 5. 构形解析总起 structure_desc(支持小篆标记)
    const descEl = document.querySelector("#structureDesc");
    if (descEl) {
      if (glyph.structure_desc && xz) descEl.innerHTML = xz(glyph.structure_desc);
      else descEl.textContent = glyph.structure_desc || "";
    }

    // 6. 构件卡片：parts[] / part_type[] / part_comment[]（comment 支持小篆标记）
    const components = document.querySelector("#componentList");
    if (Array.isArray(glyph.parts) && glyph.parts.length) {
      components.innerHTML = glyph.parts.map((name, i) => {
        const type = (glyph.part_type && glyph.part_type[i]) || "";
        const comment = (glyph.part_comment && glyph.part_comment[i]) || "";
        const cls = type ? ` part-${escapeHtml(type)}` : "";
        const commentHtml = comment
          ? `<p class="component-comment">${xz ? xz(comment) : escapeHtml(comment)}</p>`
          : "";
        return `
          <div class="component-card${cls}">
            <div class="component-head">
              <strong class="component-name">${window.renderXiaozhuanChar(name)}</strong>
              ${type ? `<span class="component-type">${escapeHtml(type)}</span>` : ""}
            </div>
            ${commentHtml}
          </div>`;
      }).join("");
    } else if (Array.isArray(glyph.components) && glyph.components.length) {
      // 兼容旧 components 数据
      components.innerHTML = glyph.components.map((component) => `
        <div class="component-card">
          <div class="component-head">
            <strong class="component-name">${window.renderXiaozhuanChar(component.name)}</strong>
            <span class="component-type">${escapeHtml(component.kind)}</span>
          </div>
          <p class="component-comment">${xz ? xz(component.status) : escapeHtml(component.status)}</p>
        </div>`).join("");
    } else {
      components.innerHTML = '<p class="empty-state compact">这一字形的部件说明仍在整理中。</p>';
    }
  }

  function renderSimilar(relations, onSelect) {
    const container = document.querySelector("#similarList");
    container.replaceChildren();
    if (!relations.length) {
      container.innerHTML = '<p class="empty-state compact">当前筛选下没有满足同声旁 / 同形旁 / 同部首任一条件的候选字形。</p>';
      return;
    }
    relations.forEach((relation) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `similar-item relation-${relation.type}`;
      button.dataset.type = relation.type;
      button.innerHTML = `<span class="similar-mark">${window.renderXiaozhuanChar(relation.glyph.mark, { className: 'xiaozhuan-mark', boxStyle: 'max-width:27px; max-height:27px; object-fit:contain; display:block;' })}</span><span><strong>${escapeHtml(relation.glyph.title)}</strong><small>${escapeHtml(relation.label)}</small></span><span class="similar-count">${relation.glyph.metrics.segmentCount} 段</span>`;
      button.addEventListener("click", () => onSelect(relation.glyph.id));
      container.append(button);
    });
  }

  function renderDatasetStatus(dataset) {
    setText("#datasetStatus", `${dataset.count} 个字形`);
    setText("#glyphCount", `${dataset.count} 个`);
  }

  window.GlyphUI = {
    renderCatalog,
    renderTabs,
    renderImage,
    renderPlaybackControls,
    renderMetrics,
    renderSegments,
    renderRecord,
    renderSimilar,
    renderDatasetStatus,
  };
})();
